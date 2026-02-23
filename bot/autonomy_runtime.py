import asyncio
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Awaitable, Callable

from bot.control_plane import control_plane
from bot.observability import observability
from bot.runtime_config import logger
from bot.autonomy_logic import process_autonomy_goal

AutoChatDispatcher = Callable[[str], Awaitable[None]]


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
            
            dispatcher = self._get_auto_chat_dispatcher()
            for goal in due_goals:
                processed.append(await process_autonomy_goal(goal, dispatcher))

            return {
                "ok": True,
                "reason": reason,
                "force": bool(force),
                "due_goals": len(due_goals),
                "processed": processed,
                "runtime": control_plane.runtime_snapshot(),
            }

    def _get_auto_chat_dispatcher(self) -> AutoChatDispatcher | None:
        with self._lock:
            return self._auto_chat_dispatcher

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
