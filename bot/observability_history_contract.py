from typing import Any


def normalize_observability_history_point(
    point: dict[str, Any] | None,
    *,
    channel_id: str | None = None,
    default_channel_id: str = "default",
    captured_at: str = "",
    fallback_captured_at: str = "",
    use_timestamp_fallback: bool = False,
) -> dict[str, Any]:
    safe_point = dict(point or {})
    safe_metrics = dict(safe_point.get("metrics") or {})
    safe_chatters = dict(safe_point.get("chatters") or {})
    safe_analytics = dict(safe_point.get("chat_analytics") or {})
    safe_outcomes = dict(safe_point.get("agent_outcomes") or {})
    safe_context = dict(safe_point.get("context") or {})
    safe_captured_at = str(captured_at or "") or str(safe_point.get("captured_at") or "")
    if not safe_captured_at and use_timestamp_fallback:
        safe_captured_at = str(safe_point.get("timestamp") or "")
    if not safe_captured_at:
        safe_captured_at = str(fallback_captured_at or "")
    safe_channel_id = str(channel_id or "") or str(
        safe_point.get("channel_id") or default_channel_id
    )
    return {
        "channel_id": safe_channel_id,
        "captured_at": safe_captured_at,
        "metrics": {
            "chat_messages_total": int(safe_metrics.get("chat_messages_total", 0) or 0),
            "byte_triggers_total": int(safe_metrics.get("byte_triggers_total", 0) or 0),
            "replies_total": int(safe_metrics.get("replies_total", 0) or 0),
            "llm_interactions_total": int(safe_metrics.get("llm_interactions_total", 0) or 0),
            "errors_total": int(safe_metrics.get("errors_total", 0) or 0),
        },
        "chatters": {
            "unique_total": int(safe_chatters.get("unique_total", 0) or 0),
            "active_60m": int(safe_chatters.get("active_60m", 0) or 0),
        },
        "chat_analytics": {
            "messages_60m": int(safe_analytics.get("messages_60m", 0) or 0),
            "byte_triggers_60m": int(safe_analytics.get("byte_triggers_60m", 0) or 0),
            "messages_per_minute_60m": float(
                safe_analytics.get("messages_per_minute_60m", 0.0) or 0.0
            ),
        },
        "agent_outcomes": {
            "useful_engagement_rate_60m": float(
                safe_outcomes.get("useful_engagement_rate_60m", 0.0) or 0.0
            ),
            "ignored_rate_60m": float(safe_outcomes.get("ignored_rate_60m", 0.0) or 0.0),
        },
        "context": {
            "last_prompt": str(safe_context.get("last_prompt") or ""),
            "last_reply": str(safe_context.get("last_reply") or ""),
        },
    }
