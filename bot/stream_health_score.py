from __future__ import annotations

from typing import Any

STREAM_HEALTH_VERSION = "v1"

_SENTIMENT_WEIGHT = 0.30
_CHAT_VELOCITY_WEIGHT = 0.25
_TRIGGER_HIT_RATE_WEIGHT = 0.25
_ANOMALY_WEIGHT = 0.20


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _compute_sentiment_score(sentiment: dict[str, Any]) -> tuple[float, float]:
    avg = _safe_float(sentiment.get("avg"))
    normalized_avg = _clamp(avg, -2.0, 2.0)
    score = ((normalized_avg + 2.0) / 4.0) * 100.0
    return round(_clamp(score, 0.0, 100.0), 2), normalized_avg


def _compute_chat_velocity_score(chat_analytics: dict[str, Any]) -> tuple[float, float]:
    messages_per_minute_60m = max(0.0, _safe_float(chat_analytics.get("messages_per_minute_60m")))
    # 1.2 msg/min (~72 msg/h) ja cobre o baseline operacional para score maximo.
    ratio = _clamp(messages_per_minute_60m / 1.2, 0.0, 1.0)
    score = 35.0 + (ratio * 65.0) if messages_per_minute_60m > 0 else 0.0
    return round(_clamp(score, 0.0, 100.0), 2), messages_per_minute_60m


def _compute_trigger_hit_rate_score(chat_analytics: dict[str, Any]) -> tuple[float, float]:
    messages_60m = max(0, _safe_int(chat_analytics.get("messages_60m")))
    triggers_60m = max(0, _safe_int(chat_analytics.get("byte_triggers_60m")))
    if messages_60m <= 0:
        return 0.0, 0.0

    ratio = triggers_60m / messages_60m
    target = 0.06
    tolerance = 0.12
    distance = abs(ratio - target)
    score = 100.0 - ((distance / tolerance) * 100.0)
    return round(_clamp(score, 0.0, 100.0), 2), ratio


def _compute_anomaly_score(
    *,
    chat_analytics: dict[str, Any],
    agent_outcomes: dict[str, Any],
    timeline: list[dict[str, Any]],
) -> tuple[float, int, float]:
    messages_60m = max(0, _safe_int(chat_analytics.get("messages_60m")))
    llm_interactions_60m = max(0, _safe_int(agent_outcomes.get("llm_interactions_60m")))
    quality_retry_60m = max(0, _safe_int(agent_outcomes.get("quality_retry_60m")))
    quality_fallback_60m = max(0, _safe_int(agent_outcomes.get("quality_fallback_60m")))
    timeline_errors = sum(max(0, _safe_int(point.get("errors"))) for point in list(timeline or []))
    anomaly_events = quality_retry_60m + quality_fallback_60m + timeline_errors
    observed_volume = max(1, messages_60m + llm_interactions_60m)
    anomaly_ratio = anomaly_events / observed_volume
    score = 100.0 - (anomaly_ratio * 220.0)
    return round(_clamp(score, 0.0, 100.0), 2), anomaly_events, anomaly_ratio


def _resolve_band(score: int) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "stable"
    if score >= 50:
        return "watch"
    return "critical"


def build_stream_health_score(
    *,
    sentiment: dict[str, Any],
    chat_analytics: dict[str, Any],
    agent_outcomes: dict[str, Any],
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    sentiment_score, normalized_avg = _compute_sentiment_score(sentiment)
    chat_velocity_score, messages_per_minute_60m = _compute_chat_velocity_score(chat_analytics)
    trigger_hit_rate_score, trigger_ratio = _compute_trigger_hit_rate_score(chat_analytics)
    anomaly_score, anomaly_events, anomaly_ratio = _compute_anomaly_score(
        chat_analytics=chat_analytics,
        agent_outcomes=agent_outcomes,
        timeline=timeline,
    )

    weighted_score = (
        (sentiment_score * _SENTIMENT_WEIGHT)
        + (chat_velocity_score * _CHAT_VELOCITY_WEIGHT)
        + (trigger_hit_rate_score * _TRIGGER_HIT_RATE_WEIGHT)
        + (anomaly_score * _ANOMALY_WEIGHT)
    )
    score = round(_clamp(weighted_score, 0.0, 100.0))

    return {
        "version": STREAM_HEALTH_VERSION,
        "score": score,
        "band": _resolve_band(score),
        "components": {
            "sentiment": {
                "score": sentiment_score,
                "weight": _SENTIMENT_WEIGHT,
                "avg": round(normalized_avg, 3),
            },
            "chat_velocity": {
                "score": chat_velocity_score,
                "weight": _CHAT_VELOCITY_WEIGHT,
                "messages_per_minute_60m": round(messages_per_minute_60m, 3),
            },
            "trigger_hit_rate": {
                "score": trigger_hit_rate_score,
                "weight": _TRIGGER_HIT_RATE_WEIGHT,
                "ratio": round(trigger_ratio, 4),
            },
            "anomalies": {
                "score": anomaly_score,
                "weight": _ANOMALY_WEIGHT,
                "events": anomaly_events,
                "ratio": round(anomaly_ratio, 4),
            },
        },
    }


__all__ = ["STREAM_HEALTH_VERSION", "build_stream_health_score"]
