import time
from collections.abc import Awaitable, Callable
from typing import Any

from bot.byte_semantics import format_chat_reply
from bot.control_plane import (
    RISK_AUTO_CHAT,
    RISK_CLIP_CANDIDATE,
    RISK_MODERATION_ACTION,
    RISK_SUGGEST_STREAMER,
    control_plane,
)
from bot.control_plane_constants import utc_iso
from bot.hud_runtime import hud_runtime
from bot.logic import MAX_REPLY_LENGTH, MAX_REPLY_LINES, agent_inference, context_manager
from bot.observability import observability
from bot.runtime_config import CHANNEL_ID, ENABLE_LIVE_CONTEXT_LEARNING, client

AutoChatDispatcher = Callable[[str], Awaitable[None]]


def _clip_line(text: str, max_chars: int = 80) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


async def generate_goal_text(prompt: str, risk: str, channel_id: str | None = None) -> str:
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

    ctx = context_manager.get(channel_id)
    answer = await agent_inference(
        autonomy_prompt,
        "autonomy",
        client,
        ctx,
        enable_live_context=ENABLE_LIVE_CONTEXT_LEARNING,
        max_lines=MAX_REPLY_LINES,
        max_length=MAX_REPLY_LENGTH,
    )
    safe_text = format_chat_reply(str(answer or ""))
    return safe_text.replace("[BYTE_SPLIT]", "").strip()


async def process_autonomy_goal(
    goal: dict[str, Any],
    dispatcher: AutoChatDispatcher | None,
    channel_id: str | None = None,
) -> dict[str, Any]:
    goal_id = str(goal.get("id", "goal") or "goal")
    goal_name = _clip_line(str(goal.get("name", goal_id) or goal_id), max_chars=60)
    risk = str(goal.get("risk", RISK_SUGGEST_STREAMER) or RISK_SUGGEST_STREAMER)
    prompt = str(goal.get("prompt", "") or "").strip()
    safe_prompt = prompt or f"Objetivo autonomo {goal_name}."

    try:
        ctx = context_manager.ensure_channel_config_loaded(channel_id)
    except Exception as error:
        observability.record_error(
            category="autonomy_channel_config",
            details=str(error),
            channel_id=channel_id,
        )
        ctx = context_manager.get(channel_id)

    if bool(getattr(ctx, "channel_paused", False)):
        observability.record_autonomy_goal(
            risk=risk,
            outcome="channel_paused",
            details=goal_id,
            channel_id=channel_id,
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "channel_paused",
        }

    control_plane.register_goal_run(goal_id=goal_id, risk=risk)

    generated_text = await generate_goal_text(prompt=safe_prompt, risk=risk, channel_id=channel_id)
    if not generated_text:
        control_plane.register_dispatch_failure("goal_generation_empty")
        observability.record_error(
            category="autonomy_goal",
            details=f"{goal_id}: resposta vazia",
            channel_id=channel_id,
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "generation_empty",
        }

    if risk == RISK_AUTO_CHAT:
        return await _handle_auto_chat(
            goal_id, risk, goal_name, generated_text, dispatcher, channel_id=channel_id
        )

    if risk == RISK_CLIP_CANDIDATE:
        return _handle_clip_candidate(
            goal_id,
            risk,
            goal_name,
            generated_text,
            channel_id=channel_id,
        )

    return _handle_generic_suggestion(
        goal_id,
        risk,
        goal_name,
        safe_prompt,
        generated_text,
        channel_id=channel_id,
    )


async def _handle_auto_chat(
    goal_id: str,
    risk: str,
    goal_name: str,
    text: str,
    dispatcher: AutoChatDispatcher | None,
    channel_id: str | None = None,
) -> dict[str, Any]:
    allowed, block_reason, usage = control_plane.can_send_auto_chat()
    if not allowed:
        control_plane.register_budget_block(block_reason)
        observability.record_autonomy_goal(
            risk=risk,
            outcome="budget_blocked",
            details=block_reason,
            channel_id=channel_id,
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "budget_blocked",
            "block_reason": block_reason,
            "budget_usage": usage,
        }

    if dispatcher is None:
        queued = control_plane.enqueue_action(
            kind="autonomy_fallback",
            risk=RISK_SUGGEST_STREAMER,
            title=f"Auto chat sem dispatcher ({goal_name})",
            body=text,
            payload={"goal_id": goal_id, "source_risk": risk},
            created_by="autonomy",
        )
        observability.record_autonomy_goal(
            risk=risk,
            outcome="queued_no_dispatcher",
            details=goal_id,
            channel_id=channel_id,
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "queued_no_dispatcher",
            "action_id": queued.get("id", ""),
        }

    try:
        await dispatcher(text)
    except Exception as error:
        control_plane.register_dispatch_failure(f"auto_chat_send_error:{error}")
        observability.record_error(
            category="autonomy_dispatch",
            details=str(error),
            channel_id=channel_id,
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "dispatch_error",
            "error": str(error),
        }

    control_plane.register_auto_chat_sent()
    ctx = context_manager.get(channel_id)
    ctx.remember_bot_reply(text)
    observability.record_reply(text=text, channel_id=channel_id)
    observability.record_autonomy_goal(
        risk=risk,
        outcome="auto_chat_sent",
        details=goal_id,
        channel_id=channel_id,
    )
    return {
        "goal_id": goal_id,
        "risk": risk,
        "outcome": "auto_chat_sent",
    }


def _handle_clip_candidate(
    goal_id: str,
    risk: str,
    goal_name: str,
    text: str,
    channel_id: str | None = None,
) -> dict[str, Any]:
    cfg = control_plane.get_config()
    if not cfg.get("clip_pipeline_enabled"):
        observability.record_autonomy_goal(
            risk=risk,
            outcome="disabled",
            details="clip_pipeline_disabled",
            channel_id=channel_id,
        )
        return {
            "goal_id": goal_id,
            "risk": risk,
            "outcome": "disabled",
        }

    if len(text) < 5 or "nada" in text.lower():
        control_plane.register_dispatch_failure("clip_candidate_none")
        observability.record_autonomy_goal(
            risk=risk,
            outcome="no_candidate",
            details="LLM retornou NADA",
            channel_id=channel_id,
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
        "suggested_title": text[:100],
        "source": "autonomy_goal",
        "source_ts": now_ts,
        "context_excerpt": text,
        "dedupe_key": f"clip_{int(time.time() / 60)}",
    }

    queued_item = control_plane.enqueue_action(
        kind="clip_candidate",
        risk=RISK_CLIP_CANDIDATE,
        title=f"Sugestao de Clip ({goal_name})",
        body=text,
        payload=candidate_payload,
        created_by="autonomy",
    )
    observability.record_autonomy_goal(
        risk=risk,
        outcome="queued",
        details=queued_item.get("id", ""),
        channel_id=channel_id,
    )
    return {
        "goal_id": goal_id,
        "risk": risk,
        "outcome": "queued",
        "action_id": queued_item.get("id", ""),
    }


def _handle_generic_suggestion(
    goal_id: str,
    risk: str,
    goal_name: str,
    prompt: str,
    text: str,
    channel_id: str | None = None,
) -> dict[str, Any]:
    action_kind = "suggestion" if risk == RISK_SUGGEST_STREAMER else "moderation_review"
    queued_item = control_plane.enqueue_action(
        kind=action_kind,
        risk=risk,
        title=goal_name,
        body=text,
        payload={
            "goal_id": goal_id,
            "goal_prompt": prompt,
            "requires_confirmation": risk == RISK_MODERATION_ACTION,
        },
        created_by="autonomy",
    )
    observability.record_autonomy_goal(
        risk=risk,
        outcome="queued",
        details=queued_item.get("id", ""),
        channel_id=channel_id,
    )
    if risk == RISK_SUGGEST_STREAMER:
        hud_runtime.push_message(text, source="autonomy")
    return {
        "goal_id": goal_id,
        "risk": risk,
        "outcome": "queued",
        "action_id": queued_item.get("id", ""),
    }
