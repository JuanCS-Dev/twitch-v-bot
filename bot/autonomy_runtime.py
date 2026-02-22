import asyncio
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Awaitable, Callable

from bot.byte_semantics import format_chat_reply
from bot.control_plane import (
    RISK_AUTO_CHAT,
    RISK_CLIP_CANDIDATE,
    RISK_MODERATION_ACTION,
    RISK_SUGGEST_STREAMER,
    control_plane,
)
from bot.control_plane_constants import utc_iso
from bot.logic import MAX_REPLY_LENGTH, MAX_REPLY_LINES, agent_inference, context
from bot.observability import observability
from bot.runtime_config import CHANNEL_ID, ENABLE_LIVE_CONTEXT_LEARNING, client, logger

AutoChatDispatcher = Callable[[str], Awaitable[None]]


def _clip_line(text: str, max_chars: int = 80) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


class AutonomyRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_task: asyncio.Task[Any] | None = None
        self._tick_lock: asyncio.Lock | None = None
        self._auto_chat_dispatcher: AutoChatDispatcher | None = None
        self._mode = "eventsub"

    def bind(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        mode: str,
        auto_chat_dispatcher: AutoChatDispatcher | None = None,
    ) -> None:
        with self._lock:
            self._loop = loop
            self._mode = (mode or "eventsub").strip().lower() or "eventsub"
            self._auto_chat_dispatcher = auto_chat_dispatcher
        loop.call_soon_threadsafe(self._ensure_loop_task)

    def unbind(self) -> None:
        with self._lock:
            task = self._loop_task
            self._loop = None
            self._loop_task = None
            self._tick_lock = None
            self._auto_chat_dispatcher = None
            self._mode = "eventsub"
        if task is not None:
            task.cancel()
        control_plane.set_loop_running(False)

    def _ensure_loop_task(self) -> None:
        with self._lock:
            loop = self._loop
            task = self._loop_task
        if loop is None or loop.is_closed():
            return
        if task is not None and not task.done():
            return

        created_task = loop.create_task(self._heartbeat_loop())
        with self._lock:
            if self._loop is loop:
                self._loop_task = created_task
            else:
                created_task.cancel()

    async def _heartbeat_loop(self) -> None:
        control_plane.set_loop_running(True)
        try:
            while True:
                with self._lock:
                    active_loop = self._loop
                if active_loop is None or active_loop is not asyncio.get_running_loop():
                    break

                try:
                    await self._run_tick(force=False, reason="heartbeat")
                except Exception as error:
                    logger.error("Autonomy heartbeat falhou: %s", error)
                    control_plane.register_dispatch_failure(f"heartbeat_error:{error}")
                    observability.record_error(
                        category="autonomy_heartbeat",
                        details=str(error),
                    )

                heartbeat_seconds = int(
                    control_plane.get_config().get("heartbeat_interval_seconds", 60)
                )
                await asyncio.sleep(max(15, heartbeat_seconds))
        except asyncio.CancelledError:
            raise
        finally:
            control_plane.set_loop_running(False)

    async def _run_tick(self, *, force: bool, reason: str) -> dict[str, Any]:
        if self._tick_lock is None:
            self._tick_lock = asyncio.Lock()
        async with self._tick_lock:
            control_plane.touch_heartbeat()
            control_plane.register_tick(reason=reason)

            due_goals = control_plane.consume_due_goals(force=force)
            processed: list[dict[str, Any]] = []
            for goal in due_goals:
                processed.append(await self._process_goal(goal))

            return {
                "ok": True,
                "reason": reason,
                "force": bool(force),
                "due_goals": len(due_goals),
                "processed": processed,
                "runtime": control_plane.runtime_snapshot(),
            }

    async def _process_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        goal_id = str(goal.get("id", "goal") or "goal")
        goal_name = _clip_line(str(goal.get("name", goal_id) or goal_id), max_chars=60)
        risk = str(goal.get("risk", RISK_SUGGEST_STREAMER) or RISK_SUGGEST_STREAMER)
        prompt = str(goal.get("prompt", "") or "").strip()
        safe_prompt = prompt or f"Objetivo autonomo {goal_name}."

        control_plane.register_goal_run(goal_id=goal_id, risk=risk)

        generated_text = await self._generate_goal_text(prompt=safe_prompt, risk=risk)
        if not generated_text:
            control_plane.register_dispatch_failure("goal_generation_empty")
            observability.record_error(
                category="autonomy_goal",
                details=f"{goal_id}: resposta vazia",
            )
            return {
                "goal_id": goal_id,
                "risk": risk,
                "outcome": "generation_empty",
            }

        if risk == RISK_AUTO_CHAT:
            allowed, block_reason, usage = control_plane.can_send_auto_chat()
            if not allowed:
                control_plane.register_budget_block(block_reason)
                observability.record_autonomy_goal(
                    risk=risk,
                    outcome="budget_blocked",
                    details=block_reason,
                )
                return {
                    "goal_id": goal_id,
                    "risk": risk,
                    "outcome": "budget_blocked",
                    "block_reason": block_reason,
                    "budget_usage": usage,
                }

            dispatcher = self._get_auto_chat_dispatcher()
            if dispatcher is None:
                queued = control_plane.enqueue_action(
                    kind="autonomy_fallback",
                    risk=RISK_SUGGEST_STREAMER,
                    title=f"Auto chat sem dispatcher ({goal_name})",
                    body=generated_text,
                    payload={"goal_id": goal_id, "source_risk": risk},
                    created_by="autonomy",
                )
                observability.record_autonomy_goal(
                    risk=risk,
                    outcome="queued_no_dispatcher",
                    details=goal_id,
                )
                return {
                    "goal_id": goal_id,
                    "risk": risk,
                    "outcome": "queued_no_dispatcher",
                    "action_id": queued.get("id", ""),
                }

            try:
                await dispatcher(generated_text)
            except Exception as error:
                control_plane.register_dispatch_failure(f"auto_chat_send_error:{error}")
                observability.record_error(
                    category="autonomy_dispatch",
                    details=str(error),
                )
                return {
                    "goal_id": goal_id,
                    "risk": risk,
                    "outcome": "dispatch_error",
                    "error": str(error),
                }

            control_plane.register_auto_chat_sent()
            context.remember_bot_reply(generated_text)
            observability.record_reply(text=generated_text)
            observability.record_autonomy_goal(
                risk=risk,
                outcome="auto_chat_sent",
                details=goal_id,
            )
            return {
                "goal_id": goal_id,
                "risk": risk,
                "outcome": "auto_chat_sent",
            }

        if risk == RISK_CLIP_CANDIDATE:
            cfg = control_plane.get_config()
            if not cfg.get("clip_pipeline_enabled"):
                observability.record_autonomy_goal(
                    risk=risk,
                    outcome="disabled",
                    details="clip_pipeline_disabled",
                )
                return {
                    "goal_id": goal_id,
                    "risk": risk,
                    "outcome": "disabled",
                }

            if len(generated_text) < 5 or "nada" in generated_text.lower():
                control_plane.register_dispatch_failure("clip_candidate_none")
                observability.record_autonomy_goal(
                    risk=risk,
                    outcome="no_candidate",
                    details="LLM retornou NADA",
                )
                return {
                    "goal_id": goal_id,
                    "risk": risk,
                    "outcome": "no_candidate",
                }

            now_ts = utc_iso(time.time())
            candidate_payload = {
                "candidate_id": f"clip_{int(time.time())}",
                "broadcaster_id": str(CHANNEL_ID),
                "mode": str(cfg.get("clip_mode_default", "live")),
                "suggested_duration": 30.0,
                "suggested_title": generated_text[:100],
                "source": "autonomy_goal",
                "source_ts": now_ts,
                "context_excerpt": generated_text,
                "dedupe_key": f"clip_{int(time.time() / 60)}",
            }

            queued_item = control_plane.enqueue_action(
                kind="clip_candidate",
                risk=RISK_CLIP_CANDIDATE,
                title=f"Sugestao de Clip ({goal_name})",
                body=generated_text,
                payload=candidate_payload,
                created_by="autonomy",
            )
            observability.record_autonomy_goal(
                risk=risk,
                outcome="queued",
                details=queued_item.get("id", ""),
            )
            return {
                "goal_id": goal_id,
                "risk": risk,
                "outcome": "queued",
                "action_id": queued_item.get("id", ""),
            }

        action_kind = "suggestion" if risk == RISK_SUGGEST_STREAMER else "moderation_review"
        queued_item = control_plane.enqueue_action(
            kind=action_kind,
            risk=risk,
            title=goal_name,
            body=generated_text,
            payload={
                "goal_id": goal_id,
                "goal_prompt": safe_prompt,
                "requires_confirmation": risk == RISK_MODERATION_ACTION,
            },
            created_by="autonomy",
        )
        observability.record_autonomy_goal(
            risk=risk,
            outcome="queued",
            details=queued_item.get("id", ""),
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "queued",
            "action_id": queued_item.get("id", ""),
        }

    def _get_auto_chat_dispatcher(self) -> AutoChatDispatcher | None:
        with self._lock:
            return self._auto_chat_dispatcher

    async def _generate_goal_text(self, *, prompt: str, risk: str) -> str:
        risk_hint = {
            RISK_AUTO_CHAT: (
                "Crie uma mensagem para o chat com valor imediato para a live. "
                "Objetivo: estimular conversa util sem parecer spam."
            ),
            RISK_SUGGEST_STREAMER: (
                "Crie uma sugestao objetiva para o streamer melhorar clareza, ritmo "
                "ou engajamento nos proximos minutos."
            ),
            RISK_MODERATION_ACTION: (
                "Identifique risco de moderacao e recomende acao conservadora com justificativa curta."
            ),
            RISK_CLIP_CANDIDATE: (
                "Identifique um momento memoravel recente na live. "
                "Se houver algo digno de clipe, descreva o motivo em 1 frase. "
                "Se nao houver nada relevante, responda apenas 'NADA'."
            ),
        }.get(risk, "Responda com recomendacao objetiva.")
        autonomy_prompt = (
            "Modo autonomia Byte para Twitch.\n"
            f"Risco: {risk}\n"
            f"Tarefa: {prompt}\n"
            f"{risk_hint}\n"
            "Contrato de saida: 1 mensagem, no maximo 4 linhas, alta densidade, sem markdown."
        )
        answer = await agent_inference(
            autonomy_prompt,
            "autonomy",
            client,
            context,
            enable_live_context=ENABLE_LIVE_CONTEXT_LEARNING,
            max_lines=MAX_REPLY_LINES,
            max_length=MAX_REPLY_LENGTH,
        )
        safe_text = format_chat_reply(str(answer or ""))
        return safe_text.replace("[BYTE_SPLIT]", "").strip()

    def run_manual_tick(self, *, force: bool = True, reason: str = "manual") -> dict[str, Any]:
        coroutine = self._run_tick(force=force, reason=reason)
        with self._lock:
            loop = self._loop
        if loop is None or loop.is_closed() or not loop.is_running():
            return asyncio.run(coroutine)

        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=20.0)
        except FutureTimeoutError as error:
            future.cancel()
            raise TimeoutError("Autonomy tick timeout.") from error


autonomy_runtime = AutonomyRuntime()

__all__ = ["AutonomyRuntime", "autonomy_runtime"]
