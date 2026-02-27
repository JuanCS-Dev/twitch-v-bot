from typing import Any

from bot.stream_health_score import STREAM_HEALTH_VERSION


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_band(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"excellent", "stable", "watch", "critical"}:
        return normalized
    return "critical"


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
    safe_sentiment = dict(safe_point.get("sentiment") or {})
    safe_stream_health = dict(safe_point.get("stream_health") or {})
    safe_captured_at = str(captured_at or "") or str(safe_point.get("captured_at") or "")
    if not safe_captured_at and use_timestamp_fallback:
        safe_captured_at = str(safe_point.get("timestamp") or "")
    if not safe_captured_at:
        safe_captured_at = str(fallback_captured_at or "")
    safe_channel_id = str(channel_id or "") or str(
        safe_point.get("channel_id") or default_channel_id
    )
    stream_health_score = max(0, min(100, _coerce_int(safe_stream_health.get("score", 0), 0)))
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
        "sentiment": {
            "vibe": str(safe_sentiment.get("vibe") or "Chill"),
            "avg": _coerce_float(safe_sentiment.get("avg", 0.0), 0.0),
            "count": _coerce_int(safe_sentiment.get("count", 0), 0),
            "positive": _coerce_int(safe_sentiment.get("positive", 0), 0),
            "negative": _coerce_int(safe_sentiment.get("negative", 0), 0),
        },
        "stream_health": {
            "version": str(safe_stream_health.get("version") or STREAM_HEALTH_VERSION),
            "score": stream_health_score,
            "band": _normalize_band(safe_stream_health.get("band")),
        },
        "context": {
            "last_prompt": str(safe_context.get("last_prompt") or ""),
            "last_reply": str(safe_context.get("last_reply") or ""),
        },
    }
