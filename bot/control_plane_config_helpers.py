from collections import deque
from typing import Any

from bot.control_plane_constants import (
    RISK_SUGGEST_STREAMER,
    SUPPORTED_GOAL_KPI_COMPARISONS,
    SUPPORTED_GOAL_KPI_NAMES,
    SUPPORTED_RISK_LEVELS,
    clip_text,
    default_goal_kpi_name,
    default_goals_copy,
    to_float,
    to_int,
    utc_iso,
)

GOAL_KPI_SUCCESS_OUTCOMES: dict[str, set[str]] = {
    "auto_chat_sent": {"auto_chat_sent"},
    "action_queued": {"queued"},
    "clip_candidate_queued": {"queued"},
}


def sanitize_goal_comparison(raw_value: Any) -> str:
    comparison = str(raw_value or "").strip().lower()
    if comparison not in SUPPORTED_GOAL_KPI_COMPARISONS:
        return "gte"
    return comparison


def infer_goal_observed_value(goal: dict[str, Any], outcome: str) -> float:
    kpi_name = str(goal.get("kpi_name", "") or "").strip().lower()
    safe_outcome = str(outcome or "").strip().lower()
    success_outcomes = GOAL_KPI_SUCCESS_OUTCOMES.get(kpi_name, {"queued"})
    return 1.0 if safe_outcome in success_outcomes else 0.0


def goal_target_met(observed_value: float, target_value: float, comparison: str) -> bool:
    safe_comparison = sanitize_goal_comparison(comparison)
    if safe_comparison == "lte":
        return observed_value <= target_value
    if safe_comparison == "eq":
        return abs(observed_value - target_value) <= 1e-6
    return observed_value >= target_value


def _normalize_goal_session_result(
    raw_result: Any,
    *,
    kpi_name: str,
    target_value: float,
    comparison: str,
) -> dict[str, Any]:
    result = raw_result if isinstance(raw_result, dict) else {}
    evaluated_at = str(result.get("evaluated_at", "") or "").strip()
    if not evaluated_at:
        return {}

    return {
        "kpi_name": kpi_name,
        "target_value": float(target_value),
        "comparison": comparison,
        "observed_value": to_float(
            result.get("observed_value", 0.0),
            minimum=0.0,
            maximum=10_000.0,
            fallback=0.0,
        ),
        "met": bool(result.get("met", False)),
        "outcome": clip_text(str(result.get("outcome", "") or "").strip(), max_chars=80),
        "details": clip_text(str(result.get("details", "") or "").strip(), max_chars=180),
        "evaluated_at": evaluated_at,
    }


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
    default_kpi_name = default_goal_kpi_name(risk)
    kpi_name = str(goal.get("kpi_name", "") or default_kpi_name).strip().lower()
    if kpi_name not in SUPPORTED_GOAL_KPI_NAMES:
        kpi_name = default_kpi_name
    target_value = to_float(
        goal.get("target_value", 1.0),
        minimum=0.0,
        maximum=10_000.0,
        fallback=1.0,
    )
    window_minutes = to_int(
        goal.get("window_minutes", 60),
        minimum=1,
        maximum=1_440,
        fallback=60,
    )
    comparison = sanitize_goal_comparison(goal.get("comparison"))
    session_result = _normalize_goal_session_result(
        goal.get("session_result"),
        kpi_name=kpi_name,
        target_value=target_value,
        comparison=comparison,
    )
    return {
        "id": goal_id,
        "name": name,
        "prompt": prompt,
        "risk": risk,
        "interval_seconds": interval_seconds,
        "enabled": enabled,
        "kpi_name": kpi_name,
        "target_value": target_value,
        "window_minutes": window_minutes,
        "comparison": comparison,
        "session_result": session_result,
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
        "autonomy_goal_kpi_met_total": int(runtime.get("autonomy_goal_kpi_met_total", 0)),
        "autonomy_goal_kpi_missed_total": int(runtime.get("autonomy_goal_kpi_missed_total", 0)),
        "autonomy_last_goal_kpi_status": str(runtime.get("autonomy_last_goal_kpi_status", "")),
        "autonomy_last_goal_kpi_goal_id": str(runtime.get("autonomy_last_goal_kpi_goal_id", "")),
        "autonomy_last_goal_kpi_name": str(runtime.get("autonomy_last_goal_kpi_name", "")),
        "autonomy_last_goal_kpi_observed_value": float(
            runtime.get("autonomy_last_goal_kpi_observed_value", 0.0)
        ),
        "autonomy_last_goal_kpi_target_value": float(
            runtime.get("autonomy_last_goal_kpi_target_value", 0.0)
        ),
        "autonomy_last_goal_kpi_comparison": str(
            runtime.get("autonomy_last_goal_kpi_comparison", "")
        ),
        "autonomy_last_block_reason": str(runtime.get("autonomy_last_block_reason", "")),
        "budget_usage": {
            **usage,
            "limit_10m": int(config.get("budget_messages_10m", 0)),
            "limit_60m": int(config.get("budget_messages_60m", 0)),
            "limit_daily": int(config.get("budget_messages_daily", 0)),
            "cooldown_seconds": int(config.get("min_cooldown_seconds", 0)),
        },
    }
