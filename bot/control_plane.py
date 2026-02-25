from typing import Any

from bot.control_plane_actions import ControlPlaneActionQueue
from bot.control_plane_config import ControlPlaneConfigRuntime
from bot.control_plane_constants import (
    RISK_AUTO_CHAT,
    RISK_CLIP_CANDIDATE,
    RISK_MODERATION_ACTION,
    RISK_SUGGEST_STREAMER,
    SUPPORTED_DECISIONS,
    SUPPORTED_RISK_LEVELS,
)


class ControlPlaneState:
    MAX_ACTION_ITEMS = 600

    def __init__(self) -> None:
        self._config_runtime = ControlPlaneConfigRuntime()
        self._action_queue = ControlPlaneActionQueue(max_items=self.MAX_ACTION_ITEMS)

    def get_config(self) -> dict[str, Any]:
        return self._config_runtime.get_config()

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._config_runtime.update_config(payload)

    def set_loop_running(self, running: bool) -> None:
        self._config_runtime.set_loop_running(running)

    def touch_heartbeat(self, timestamp: float | None = None) -> None:
        self._config_runtime.touch_heartbeat(timestamp=timestamp)

    def register_tick(self, reason: str, timestamp: float | None = None) -> None:
        self._config_runtime.register_tick(reason=reason, timestamp=timestamp)

    def register_goal_run(
        self,
        goal_id: str,
        risk: str,
        timestamp: float | None = None,
    ) -> None:
        self._config_runtime.register_goal_run(
            goal_id=goal_id,
            risk=risk,
            timestamp=timestamp,
        )

    def register_budget_block(self, reason: str, timestamp: float | None = None) -> None:
        self._config_runtime.register_budget_block(reason=reason, timestamp=timestamp)

    def register_dispatch_failure(self, reason: str, timestamp: float | None = None) -> None:
        self._config_runtime.register_dispatch_failure(reason=reason, timestamp=timestamp)

    def can_send_auto_chat(
        self, timestamp: float | None = None
    ) -> tuple[bool, str, dict[str, int]]:
        return self._config_runtime.can_send_auto_chat(timestamp=timestamp)

    def register_auto_chat_sent(self, timestamp: float | None = None) -> None:
        self._config_runtime.register_auto_chat_sent(timestamp=timestamp)

    def consume_due_goals(
        self, *, force: bool = False, timestamp: float | None = None
    ) -> list[dict[str, Any]]:
        return self._config_runtime.consume_due_goals(force=force, timestamp=timestamp)

    def enqueue_action(
        self,
        *,
        kind: str,
        risk: str,
        title: str,
        body: str,
        payload: dict[str, Any] | None = None,
        created_by: str = "autonomy",
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        return self._action_queue.enqueue_action(
            kind=kind,
            risk=risk,
            title=title,
            body=body,
            payload=payload,
            created_by=created_by,
            timestamp=timestamp,
        )

    def decide_action(
        self,
        *,
        action_id: str,
        decision: str,
        note: str = "",
        decided_by: str = "dashboard",
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        return self._action_queue.decide_action(
            action_id=action_id,
            decision=decision,
            note=note,
            decided_by=decided_by,
            timestamp=timestamp,
        )

    def list_actions(
        self,
        *,
        status: str | None = None,
        limit: int = 80,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        return self._action_queue.list_actions(
            status=status,
            limit=limit,
            ignore_after_seconds=self._config_runtime.action_ignore_after_seconds(),
            timestamp=timestamp,
        )

    def build_capabilities(self, *, bot_mode: str) -> dict[str, Any]:
        safe_mode = (bot_mode or "eventsub").strip().lower() or "eventsub"
        channel_enabled = safe_mode == "irc"
        if channel_enabled:
            channel_reason = "Controle de canais ativo no runtime IRC."
            supported_actions = ["list", "join", "part"]
        else:
            channel_reason = (
                "Channel control de runtime so funciona em TWITCH_CHAT_MODE=irc. "
                "No modo eventsub, join/part ficam bloqueados."
            )
            supported_actions = []

        config = self.get_config()
        return {
            "channel_control": {
                "enabled": channel_enabled,
                "reason": channel_reason,
                "supported_actions": supported_actions,
            },
            "autonomy": {
                "enabled": True,
                "reason": "Autonomia com agenda e budget anti-spam disponivel.",
                "active": bool(config.get("autonomy_enabled", False)),
            },
            "risk_actions": {
                "enabled": True,
                "reason": "Fluxo por risco com fila e decisao approve/reject.",
                "levels": sorted(SUPPORTED_RISK_LEVELS),
            },
            "response_contract": {
                "max_messages": 1,
                "max_lines": 4,
            },
            "clip_pipeline": {
                "enabled": config.get("clip_pipeline_enabled", False),
                "modes": ["live", "vod"],
                "default_mode": config.get("clip_mode_default", "live"),
            },
        }

    def runtime_snapshot(self, *, timestamp: float | None = None) -> dict[str, Any]:
        runtime = self._config_runtime.runtime_base_snapshot(timestamp=timestamp)
        queue_runtime = self._action_queue.runtime_snapshot(
            ignore_after_seconds=self._config_runtime.action_ignore_after_seconds(),
            timestamp=timestamp,
        )
        runtime["queue"] = queue_runtime.get("queue", {})
        runtime["queue_window_60m"] = queue_runtime.get("queue_window_60m", {})
        return runtime


control_plane = ControlPlaneState()

__all__ = [
    "RISK_AUTO_CHAT",
    "RISK_CLIP_CANDIDATE",
    "RISK_MODERATION_ACTION",
    "RISK_SUGGEST_STREAMER",
    "SUPPORTED_DECISIONS",
    "SUPPORTED_RISK_LEVELS",
    "ControlPlaneState",
    "control_plane",
]
