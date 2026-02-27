from collections import deque
from typing import Any

from bot.control_plane_constants import (
    RISK_SUGGEST_STREAMER,
    SUPPORTED_RISK_LEVELS,
    clip_text,
    default_goals_copy,
    to_int,
    utc_iso,
)


def normalize_goal(raw_goal: Any, index: int) -> dict[str, Any]:
    goal = raw_goal if isinstance(raw_goal, dict) else {}
    fallback_id = f"goal_{index + 1}"
    raw_id = str(goal.get("id", "") or "").strip().lower().replace(" ", "_")
    goal_id = "".join(ch for ch in raw_id if ch.isalnum() or ch == "_") or fallback_id

    name = clip_text(str(goal.get("name", "") or goal_id).strip(), max_chars=60)
    prompt = clip_text(str(goal.get("prompt", "") or "").strip(), max_chars=420)
    risk = str(goal.get("risk", "") or "").strip().lower()
    if risk not in SUPPORTED_RISK_LEVELS:
        risk = RISK_SUGGEST_STREAMER

    interval_seconds = to_int(
        goal.get("interval_seconds", 600),
        minimum=60,
        maximum=86_400,
        fallback=600,
    )
    enabled = bool(goal.get("enabled", True))
    return {
        "id": goal_id,
        "name": name,
        "prompt": prompt,
        "risk": risk,
        "interval_seconds": interval_seconds,
        "enabled": enabled,
    }


def normalize_goals(raw_goals: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_goals, list):
        return default_goals_copy()

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_goals):
        safe_goal = normalize_goal(item, index)
        if safe_goal["id"] in seen_ids:
            safe_goal["id"] = f"{safe_goal['id']}_{index + 1}"
        seen_ids.add(safe_goal["id"])
        normalized.append(safe_goal)

    return normalized or default_goals_copy()


def prune_auto_chat_history(history: deque[float], now: float) -> None:
    daily_cutoff = now - 86_400
    while history and history[0] < daily_cutoff:
        history.popleft()


def budget_usage(history: deque[float], now: float) -> dict[str, int]:
    prune_auto_chat_history(history, now)
    cutoff_10m = now - 600
    cutoff_60m = now - 3600
    usage_10m = 0
    usage_60m = 0
    usage_daily = 0
    for timestamp in history:
        usage_daily += 1
        if timestamp >= cutoff_60m:
            usage_60m += 1
        if timestamp >= cutoff_10m:
            usage_10m += 1
    return {
        "messages_10m": usage_10m,
        "messages_60m": usage_60m,
        "messages_daily": usage_daily,
    }


def runtime_base_snapshot(
    *,
    config: dict[str, Any],
    runtime: dict[str, Any],
    usage: dict[str, int],
) -> dict[str, Any]:
    return {
        "enabled": bool(config.get("autonomy_enabled", False)),
        "suspended": bool(config.get("agent_suspended", False)),
        "suspended_at": (
            utc_iso(float(runtime.get("agent_suspended_at", 0.0)))
            if float(runtime.get("agent_suspended_at", 0.0)) > 0
            else ""
        ),
        "suspended_epoch": float(runtime.get("agent_suspended_at", 0.0)),
        "suspend_reason": str(runtime.get("agent_suspend_reason", "")),
        "last_resumed_at": (
            utc_iso(float(runtime.get("agent_last_resumed_at", 0.0)))
            if float(runtime.get("agent_last_resumed_at", 0.0)) > 0
            else ""
        ),
        "last_resumed_epoch": float(runtime.get("agent_last_resumed_at", 0.0)),
        "last_resume_reason": str(runtime.get("agent_last_resume_reason", "")),
        "loop_running": bool(runtime.get("loop_running", False)),
        "last_heartbeat_at": (
            utc_iso(float(runtime.get("last_heartbeat_at", 0.0)))
            if float(runtime.get("last_heartbeat_at", 0.0)) > 0
            else ""
        ),
        "last_heartbeat_epoch": float(runtime.get("last_heartbeat_at", 0.0)),
        "last_tick_at": (
            utc_iso(float(runtime.get("last_tick_at", 0.0)))
            if float(runtime.get("last_tick_at", 0.0)) > 0
            else ""
        ),
        "last_tick_epoch": float(runtime.get("last_tick_at", 0.0)),
        "last_tick_reason": str(runtime.get("last_tick_reason", "")),
        "last_goal_id": str(runtime.get("last_goal_id", "")),
        "last_goal_risk": str(runtime.get("last_goal_risk", "")),
        "autonomy_ticks_total": int(runtime.get("autonomy_ticks_total", 0)),
        "autonomy_goal_runs_total": int(runtime.get("autonomy_goal_runs_total", 0)),
        "autonomy_budget_blocked_total": int(runtime.get("autonomy_budget_blocked_total", 0)),
        "autonomy_dispatch_failures_total": int(runtime.get("autonomy_dispatch_failures_total", 0)),
        "autonomy_auto_chat_sent_total": int(runtime.get("autonomy_auto_chat_sent_total", 0)),
        "autonomy_last_block_reason": str(runtime.get("autonomy_last_block_reason", "")),
        "budget_usage": {
            **usage,
            "limit_10m": int(config.get("budget_messages_10m", 0)),
            "limit_60m": int(config.get("budget_messages_60m", 0)),
            "limit_daily": int(config.get("budget_messages_daily", 0)),
            "cooldown_seconds": int(config.get("min_cooldown_seconds", 0)),
        },
    }
