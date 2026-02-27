from __future__ import annotations

from typing import Any

CHURN_RISK_VERSION = "viewer_churn_risk_v1"

_MAX_ALERTS = 4

_SEVERITY_PRIORITY = {
    "critical": 3,
    "warn": 2,
    "info": 1,
}


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _resolve_risk_band(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "watch"
    return "low"


def _build_alerts(signals: dict[str, Any]) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    velocity_drop_ratio = _safe_float(signals.get("chat_velocity_drop_ratio"))
    mpm_10m = _safe_float(signals.get("messages_per_minute_10m"))
    mpm_60m = _safe_float(signals.get("messages_per_minute_60m"))
    if velocity_drop_ratio >= 0.35 and mpm_60m >= 0.2:
        alerts.append(
            {
                "id": "chat_velocity_drop",
                "severity": "critical" if velocity_drop_ratio >= 0.6 else "warn",
                "title": "Queda de ritmo no chat",
                "message": (
                    f"Ritmo em 10m caiu para {mpm_10m:.2f} msg/min (base 60m: {mpm_60m:.2f})."
                ),
                "tactic": "Dispare pergunta curta com CTA e resposta em ate 20s.",
            }
        )

    active_drop_ratio = _safe_float(signals.get("active_chatter_drop_ratio"))
    active_10m = _safe_int(signals.get("active_chatters_10m"))
    active_60m = _safe_int(signals.get("active_chatters_60m"))
    if active_drop_ratio >= 0.35 and active_60m >= 4:
        alerts.append(
            {
                "id": "retention_drop",
                "severity": "critical" if active_drop_ratio >= 0.6 else "warn",
                "title": "Retencao de viewers em queda",
                "message": f"Ativos 10m {active_10m} vs referencia 60m {active_60m}.",
                "tactic": "Puxe enquete relampago e cite viewers nominais ativos.",
            }
        )

    ignored_rate = _safe_float(signals.get("ignored_rate_60m"))
    llm_interactions = _safe_int(signals.get("llm_interactions_60m"))
    if ignored_rate >= 35.0 and llm_interactions >= 4:
        alerts.append(
            {
                "id": "agent_relevance_drop",
                "severity": "warn",
                "title": "Relevancia do agente em risco",
                "message": f"Ignored rate em 60m: {ignored_rate:.1f}%.",
                "tactic": "Troque para resposta objetiva com contexto atual da live.",
            }
        )

    sentiment_avg = _safe_float(signals.get("sentiment_avg"))
    sentiment_count = _safe_int(signals.get("sentiment_count"))
    if sentiment_avg <= -0.45 and sentiment_count >= 8:
        alerts.append(
            {
                "id": "sentiment_cooling",
                "severity": "warn",
                "title": "Sentimento esfriando",
                "message": f"Media de sentimento: {sentiment_avg:.2f}.",
                "tactic": "Aplique call positiva curta e valide feedback do chat.",
            }
        )

    fallback_pressure = _safe_float(signals.get("fallback_pressure"))
    if fallback_pressure >= 0.3 and llm_interactions >= 4:
        alerts.append(
            {
                "id": "quality_fallback_pressure",
                "severity": "warn",
                "title": "Pressao de fallback",
                "message": (
                    f"Fallback/LLM em 60m acima do ideal ({fallback_pressure * 100:.1f}%)."
                ),
                "tactic": "Reduza escopo das respostas para manter precisao operacional.",
            }
        )

    stream_health_score = _safe_int(signals.get("stream_health_score"))
    if stream_health_score <= 45:
        alerts.append(
            {
                "id": "stream_health_critical",
                "severity": "critical",
                "title": "Stream health em faixa critica",
                "message": f"Score atual de stream health: {stream_health_score}/100.",
                "tactic": "Priorize estabilidade: ritmo curto, menos fallback e CTA claro.",
            }
        )

    alerts.sort(
        key=lambda item: (
            -int(_SEVERITY_PRIORITY.get(str(item.get("severity") or "info"), 0)),
            str(item.get("id") or ""),
        )
    )
    return alerts[:_MAX_ALERTS]


def build_viewer_churn_payload(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    safe_snapshot = dict(snapshot or {})
    chat_analytics = dict(safe_snapshot.get("chat_analytics") or {})
    chatters = dict(safe_snapshot.get("chatters") or {})
    outcomes = dict(safe_snapshot.get("agent_outcomes") or {})
    sentiment = dict(safe_snapshot.get("sentiment") or {})
    stream_health = dict(safe_snapshot.get("stream_health") or {})

    messages_per_minute_10m = max(0.0, _safe_float(chat_analytics.get("messages_per_minute_10m")))
    messages_per_minute_60m = max(0.0, _safe_float(chat_analytics.get("messages_per_minute_60m")))
    active_chatters_10m = max(0, _safe_int(chatters.get("active_10m")))
    active_chatters_60m = max(0, _safe_int(chatters.get("active_60m")))
    ignored_rate_60m = _clamp(_safe_float(outcomes.get("ignored_rate_60m")), 0.0, 100.0)
    llm_interactions_60m = max(0, _safe_int(outcomes.get("llm_interactions_60m")))
    fallback_60m = max(0, _safe_int(outcomes.get("quality_fallback_60m")))
    sentiment_avg = _clamp(_safe_float(sentiment.get("avg")), -2.0, 2.0)
    sentiment_count = max(0, _safe_int(sentiment.get("count")))
    stream_health_score = _clamp(_safe_float(stream_health.get("score")), 0.0, 100.0)

    if messages_per_minute_60m > 0:
        velocity_drop_ratio = _clamp(
            (messages_per_minute_60m - messages_per_minute_10m) / messages_per_minute_60m,
            0.0,
            1.0,
        )
    else:
        velocity_drop_ratio = 0.0

    if active_chatters_60m > 0:
        active_drop_ratio = _clamp(
            (active_chatters_60m - active_chatters_10m) / active_chatters_60m,
            0.0,
            1.0,
        )
    else:
        active_drop_ratio = 0.0

    sentiment_pressure = _clamp((0.0 - sentiment_avg) / 2.0, 0.0, 1.0)
    ignored_pressure = _clamp(ignored_rate_60m / 100.0, 0.0, 1.0)
    fallback_pressure = _clamp(fallback_60m / max(llm_interactions_60m, 1), 0.0, 1.0)
    health_pressure = _clamp((65.0 - stream_health_score) / 65.0, 0.0, 1.0)

    risk_score = round(
        (
            velocity_drop_ratio * 0.30
            + active_drop_ratio * 0.25
            + sentiment_pressure * 0.15
            + ignored_pressure * 0.15
            + fallback_pressure * 0.10
            + health_pressure * 0.05
        )
        * 100.0
    )
    risk_score = int(_clamp(float(risk_score), 0.0, 100.0))
    risk_band = _resolve_risk_band(risk_score)

    signals = {
        "messages_per_minute_10m": round(messages_per_minute_10m, 2),
        "messages_per_minute_60m": round(messages_per_minute_60m, 2),
        "chat_velocity_drop_ratio": round(velocity_drop_ratio, 3),
        "active_chatters_10m": int(active_chatters_10m),
        "active_chatters_60m": int(active_chatters_60m),
        "active_chatter_drop_ratio": round(active_drop_ratio, 3),
        "ignored_rate_60m": round(ignored_rate_60m, 1),
        "llm_interactions_60m": int(llm_interactions_60m),
        "quality_fallback_60m": int(fallback_60m),
        "fallback_pressure": round(fallback_pressure, 3),
        "sentiment_avg": round(sentiment_avg, 3),
        "sentiment_count": int(sentiment_count),
        "stream_health_score": round(stream_health_score),
    }
    alerts = _build_alerts(signals)

    return {
        "version": CHURN_RISK_VERSION,
        "risk_score": risk_score,
        "risk_band": risk_band,
        "has_alerts": bool(alerts),
        "primary_alert": alerts[0] if alerts else None,
        "signals": signals,
        "alerts": alerts,
    }


def build_coaching_signature(payload: dict[str, Any] | None) -> str:
    safe_payload = dict(payload or {})
    risk_band = str(safe_payload.get("risk_band") or "low").strip().lower() or "low"
    risk_score = int(_clamp(_safe_float(safe_payload.get("risk_score")), 0.0, 100.0))
    score_bucket = int(risk_score // 5)
    alert_ids = ",".join(
        str(item.get("id") or "") for item in list(safe_payload.get("alerts") or [])[:_MAX_ALERTS]
    )
    return f"{risk_band}:{score_bucket}:{alert_ids}"


__all__ = [
    "CHURN_RISK_VERSION",
    "build_coaching_signature",
    "build_viewer_churn_payload",
]
