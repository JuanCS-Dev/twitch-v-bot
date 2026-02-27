import copy
import threading
import time
from collections import deque
from typing import Any

from bot.control_plane_config_helpers import (
    budget_usage,
    goal_target_met,
    infer_goal_observed_value,
    normalize_goals,
)
from bot.control_plane_config_helpers import (
    runtime_base_snapshot as build_runtime_base_snapshot,
)
from bot.control_plane_constants import (
    clip_text,
    default_goals_copy,
    to_float,
    to_int,
    utc_iso,
)


class ControlPlaneConfigRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._config: dict[str, Any] = {
            "version": 1,
            "autonomy_enabled": False,
            "agent_suspended": False,
            "clip_pipeline_enabled": False,
            "clip_api_enabled": False,
            "clip_mode_default": "live",
            "heartbeat_interval_seconds": 60,
            "min_cooldown_seconds": 90,
            "budget_messages_10m": 2,
            "budget_messages_60m": 8,
            "budget_messages_daily": 30,
            "action_ignore_after_seconds": 900,
            "goals": default_goals_copy(),
            "updated_at": utc_iso(time.time()),
        }
        self._runtime: dict[str, Any] = {
            "loop_running": False,
            "agent_suspended_at": 0.0,
            "agent_suspend_reason": "",
            "agent_last_resumed_at": 0.0,
            "agent_last_resume_reason": "",
            "last_heartbeat_at": 0.0,
            "last_tick_at": 0.0,
            "last_tick_reason": "boot",
            "last_goal_id": "",
            "last_goal_risk": "",
            "autonomy_ticks_total": 0,
            "autonomy_goal_runs_total": 0,
            "autonomy_budget_blocked_total": 0,
            "autonomy_dispatch_failures_total": 0,
            "autonomy_auto_chat_sent_total": 0,
            "autonomy_goal_kpi_met_total": 0,
            "autonomy_goal_kpi_missed_total": 0,
            "autonomy_last_goal_kpi_status": "",
            "autonomy_last_goal_kpi_goal_id": "",
            "autonomy_last_goal_kpi_name": "",
            "autonomy_last_goal_kpi_observed_value": 0.0,
            "autonomy_last_goal_kpi_target_value": 0.0,
            "autonomy_last_goal_kpi_comparison": "",
            "autonomy_last_block_reason": "",
        }
        self._auto_chat_sent_timestamps: deque[float] = deque(maxlen=3000)
        self._next_goal_due_at: dict[str, float] = {}

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Payload de configuracao invalido.")

        now = time.time()
        with self._lock:
            config = copy.deepcopy(self._config)

            if "autonomy_enabled" in payload:
                config["autonomy_enabled"] = bool(payload.get("autonomy_enabled"))

            if "agent_suspended" in payload:
                next_suspended = bool(payload.get("agent_suspended"))
                previous_suspended = bool(self._config.get("agent_suspended", False))
                config["agent_suspended"] = next_suspended
                if next_suspended and not previous_suspended:
                    self._runtime["agent_suspended_at"] = now
                    self._runtime["agent_suspend_reason"] = "config_update"
                    self._runtime["last_heartbeat_at"] = now
                if not next_suspended and previous_suspended:
                    self._runtime["agent_suspended_at"] = 0.0
                    self._runtime["agent_suspend_reason"] = ""
                    self._runtime["agent_last_resumed_at"] = now
                    self._runtime["agent_last_resume_reason"] = "config_update"
                    self._runtime["last_heartbeat_at"] = now

            if "clip_pipeline_enabled" in payload:
                config["clip_pipeline_enabled"] = bool(payload.get("clip_pipeline_enabled"))

            if "clip_api_enabled" in payload:
                config["clip_api_enabled"] = bool(payload.get("clip_api_enabled"))

            if "clip_mode_default" in payload:
                val = str(payload.get("clip_mode_default") or "live").strip().lower()
                if val in ("live", "vod"):
                    config["clip_mode_default"] = val

            if "heartbeat_interval_seconds" in payload:
                config["heartbeat_interval_seconds"] = to_int(
                    payload.get("heartbeat_interval_seconds"),
                    minimum=15,
                    maximum=3600,
                    fallback=config["heartbeat_interval_seconds"],
                )

            if "min_cooldown_seconds" in payload:
                config["min_cooldown_seconds"] = to_int(
                    payload.get("min_cooldown_seconds"),
                    minimum=15,
                    maximum=3600,
                    fallback=config["min_cooldown_seconds"],
                )

            if "budget_messages_10m" in payload:
                config["budget_messages_10m"] = to_int(
                    payload.get("budget_messages_10m"),
                    minimum=0,
                    maximum=100,
                    fallback=config["budget_messages_10m"],
                )

            if "budget_messages_60m" in payload:
                config["budget_messages_60m"] = to_int(
                    payload.get("budget_messages_60m"),
                    minimum=0,
                    maximum=600,
                    fallback=config["budget_messages_60m"],
                )

            if "budget_messages_daily" in payload:
                config["budget_messages_daily"] = to_int(
                    payload.get("budget_messages_daily"),
                    minimum=0,
                    maximum=5000,
                    fallback=config["budget_messages_daily"],
                )

            if "action_ignore_after_seconds" in payload:
                config["action_ignore_after_seconds"] = to_int(
                    payload.get("action_ignore_after_seconds"),
                    minimum=60,
                    maximum=86_400,
                    fallback=config["action_ignore_after_seconds"],
                )

            if "goals" in payload:
                previous_results = {
                    str(item.get("id", "") or ""): copy.deepcopy(item.get("session_result") or {})
                    for item in self._config.get("goals", [])
                    if isinstance(item, dict)
                }
                normalized_goals = normalize_goals(payload.get("goals"))
                for goal in normalized_goals:
                    goal_id = str(goal.get("id", "") or "")
                    if not goal.get("session_result") and goal_id in previous_results:
                        goal["session_result"] = previous_results[goal_id]
                config["goals"] = normalized_goals
                active_goal_ids = {goal["id"] for goal in config["goals"]}
                self._next_goal_due_at = {
                    goal_id: due_at
                    for goal_id, due_at in self._next_goal_due_at.items()
                    if goal_id in active_goal_ids
                }

            config["updated_at"] = utc_iso(now)
            self._config = config
            return copy.deepcopy(self._config)

    def suspend_agent(
        self,
        *,
        reason: str = "manual_dashboard",
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_reason = clip_text(reason or "manual_dashboard", max_chars=120)
        with self._lock:
            self._config["agent_suspended"] = True
            self._config["updated_at"] = utc_iso(now)
            self._runtime["agent_suspended_at"] = now
            self._runtime["agent_suspend_reason"] = safe_reason
            self._runtime["last_heartbeat_at"] = now
            return copy.deepcopy(self._config)

    def resume_agent(
        self,
        *,
        reason: str = "manual_dashboard",
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_reason = clip_text(reason or "manual_dashboard", max_chars=120)
        with self._lock:
            self._config["agent_suspended"] = False
            self._config["updated_at"] = utc_iso(now)
            self._runtime["agent_suspended_at"] = 0.0
            self._runtime["agent_suspend_reason"] = ""
            self._runtime["agent_last_resumed_at"] = now
            self._runtime["agent_last_resume_reason"] = safe_reason
            self._runtime["last_heartbeat_at"] = now
            return copy.deepcopy(self._config)

    def set_loop_running(self, running: bool) -> None:
        with self._lock:
            self._runtime["loop_running"] = bool(running)

    def touch_heartbeat(self, timestamp: float | None = None) -> None:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._runtime["last_heartbeat_at"] = now

    def register_tick(self, reason: str, timestamp: float | None = None) -> None:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._runtime["last_tick_at"] = now
            self._runtime["last_tick_reason"] = clip_text(reason or "tick", max_chars=40)
            self._runtime["autonomy_ticks_total"] += 1

    def register_goal_run(
        self,
        goal_id: str,
        risk: str,
        timestamp: float | None = None,
    ) -> None:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._runtime["autonomy_goal_runs_total"] += 1
            self._runtime["last_goal_id"] = clip_text(goal_id, max_chars=60)
            self._runtime["last_goal_risk"] = clip_text(risk, max_chars=32)
            self._runtime["last_heartbeat_at"] = now

    def register_budget_block(self, reason: str, timestamp: float | None = None) -> None:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._runtime["autonomy_budget_blocked_total"] += 1
            self._runtime["autonomy_last_block_reason"] = clip_text(reason, max_chars=80)
            self._runtime["last_heartbeat_at"] = now

    def register_dispatch_failure(self, reason: str, timestamp: float | None = None) -> None:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._runtime["autonomy_dispatch_failures_total"] += 1
            self._runtime["autonomy_last_block_reason"] = clip_text(reason, max_chars=80)
            self._runtime["last_heartbeat_at"] = now

    def register_goal_session_result(
        self,
        *,
        goal_id: str,
        outcome: str,
        observed_value: float | None = None,
        details: str = "",
        timestamp: float | None = None,
    ) -> dict[str, Any] | None:
        now = time.time() if timestamp is None else float(timestamp)
        safe_goal_id = str(goal_id or "").strip()
        safe_outcome = clip_text(str(outcome or "").strip().lower(), max_chars=80)
        if not safe_goal_id:
            return None

        with self._lock:
            matching_goal: dict[str, Any] | None = None
            for goal in self._config.get("goals", []):
                if not isinstance(goal, dict):
                    continue
                if str(goal.get("id", "") or "").strip() == safe_goal_id:
                    matching_goal = goal
                    break
            if matching_goal is None:
                return None

            target_value = to_float(
                matching_goal.get("target_value", 1.0),
                minimum=0.0,
                maximum=10_000.0,
                fallback=1.0,
            )
            comparison = str(matching_goal.get("comparison", "gte") or "gte").strip().lower()
            observed = (
                to_float(
                    observed_value,
                    minimum=0.0,
                    maximum=10_000.0,
                    fallback=0.0,
                )
                if observed_value is not None
                else infer_goal_observed_value(matching_goal, safe_outcome)
            )
            met = goal_target_met(observed, target_value, comparison)
            result = {
                "kpi_name": str(matching_goal.get("kpi_name", "")),
                "target_value": target_value,
                "comparison": comparison,
                "observed_value": observed,
                "met": met,
                "outcome": safe_outcome,
                "details": clip_text(str(details or "").strip(), max_chars=180),
                "evaluated_at": utc_iso(now),
            }
            matching_goal["session_result"] = result
            self._config["updated_at"] = utc_iso(now)
            if met:
                self._runtime["autonomy_goal_kpi_met_total"] += 1
            else:
                self._runtime["autonomy_goal_kpi_missed_total"] += 1
            self._runtime["autonomy_last_goal_kpi_status"] = "met" if met else "missed"
            self._runtime["autonomy_last_goal_kpi_goal_id"] = clip_text(safe_goal_id, max_chars=60)
            self._runtime["autonomy_last_goal_kpi_name"] = clip_text(
                str(matching_goal.get("kpi_name", "")),
                max_chars=60,
            )
            self._runtime["autonomy_last_goal_kpi_observed_value"] = observed
            self._runtime["autonomy_last_goal_kpi_target_value"] = target_value
            self._runtime["autonomy_last_goal_kpi_comparison"] = comparison
            self._runtime["last_heartbeat_at"] = now
            return copy.deepcopy(result)

    def can_send_auto_chat(
        self, timestamp: float | None = None
    ) -> tuple[bool, str, dict[str, int]]:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            usage = budget_usage(self._auto_chat_sent_timestamps, now)
            cfg = self._config

            if bool(cfg.get("agent_suspended", False)):
                return False, "agent_suspended", usage

            if int(cfg["budget_messages_daily"]) <= 0:
                return False, "budget_daily_disabled", usage

            last_sent = (
                self._auto_chat_sent_timestamps[-1] if self._auto_chat_sent_timestamps else 0.0
            )
            min_cooldown = int(cfg["min_cooldown_seconds"])
            if last_sent > 0 and now - last_sent < min_cooldown:
                return False, "cooldown_active", usage

            if int(cfg["budget_messages_10m"]) >= 0 and usage["messages_10m"] >= int(
                cfg["budget_messages_10m"]
            ):
                return False, "budget_10m_exceeded", usage

            if int(cfg["budget_messages_60m"]) >= 0 and usage["messages_60m"] >= int(
                cfg["budget_messages_60m"]
            ):
                return False, "budget_60m_exceeded", usage

            if usage["messages_daily"] >= int(cfg["budget_messages_daily"]):
                return False, "budget_daily_exceeded", usage

            return True, "ok", usage

    def register_auto_chat_sent(self, timestamp: float | None = None) -> None:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._auto_chat_sent_timestamps.append(now)
            self._runtime["autonomy_auto_chat_sent_total"] += 1
            self._runtime["last_heartbeat_at"] = now

    def consume_due_goals(
        self, *, force: bool = False, timestamp: float | None = None
    ) -> list[dict[str, Any]]:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            if bool(self._config.get("agent_suspended", False)) and not force:
                return []

            if not self._config.get("autonomy_enabled", False) and not force:
                return []

            due_goals: list[dict[str, Any]] = []
            active_goal_ids = set()

            for goal in self._config.get("goals", []):
                if not isinstance(goal, dict):
                    continue
                goal_id = str(goal.get("id", "") or "").strip()
                if not goal_id:
                    continue
                active_goal_ids.add(goal_id)

                if not bool(goal.get("enabled", True)):
                    continue

                interval = max(60, int(goal.get("interval_seconds", 600) or 600))
                if force:
                    due_goals.append(copy.deepcopy(goal))
                    self._next_goal_due_at[goal_id] = now + interval
                    continue

                due_at = self._next_goal_due_at.get(goal_id)
                if due_at is None:
                    self._next_goal_due_at[goal_id] = now + interval
                    continue

                if now >= due_at:
                    due_goals.append(copy.deepcopy(goal))
                    self._next_goal_due_at[goal_id] = now + interval

            self._next_goal_due_at = {
                goal_id: due_at
                for goal_id, due_at in self._next_goal_due_at.items()
                if goal_id in active_goal_ids
            }

            return due_goals

    def action_ignore_after_seconds(self) -> int:
        with self._lock:
            return max(60, int(self._config.get("action_ignore_after_seconds", 900)))

    def runtime_base_snapshot(self, *, timestamp: float | None = None) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            usage = budget_usage(self._auto_chat_sent_timestamps, now)
            cfg = dict(self._config)
            rt = dict(self._runtime)

        return build_runtime_base_snapshot(config=cfg, runtime=rt, usage=usage)
