from __future__ import annotations

from collections import Counter
from typing import Any

from bot.observability_history_contract import normalize_observability_history_point
from bot.persistence_utils import normalize_channel_id, utc_iso_now

REPORT_VERSION = "post_stream_intelligence_v1"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_band(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"excellent", "stable", "watch", "critical"}:
        return normalized
    return "critical"


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _build_recommendations(
    *,
    ignored_rate_60m: float,
    stream_health_band: str,
    errors_total: int,
    estimated_cost_usd_60m: float,
    replies_total: int,
    chat_messages_total: int,
    approval_rate_60m: float,
) -> list[str]:
    recommendations: list[str] = []
    if ignored_rate_60m >= 30.0:
        recommendations.append(
            "Reduzir backlog pendente da action queue e priorizar decisões em até 15 minutos."
        )
    if stream_health_band in {"watch", "critical"}:
        recommendations.append(
            "Ajustar ritmo de resposta para estabilizar o chat (mais respostas curtas e contexto objetivo)."
        )
    if errors_total > 0:
        recommendations.append(
            "Investigar falhas recentes no runtime antes da próxima live para evitar degradação."
        )
    if estimated_cost_usd_60m >= 0.35:
        recommendations.append(
            "Aplicar teto operacional de custo por hora (limitar follow-ups longos quando o chat acelerar)."
        )
    if chat_messages_total >= 20 and replies_total == 0:
        recommendations.append(
            "Abrir com call-to-action simples no início da próxima sessão para recuperar engajamento."
        )
    if approval_rate_60m < 35.0 and chat_messages_total > 0:
        recommendations.append(
            "Recalibrar critérios da autonomia para aumentar taxa de ações aprovadas sem elevar risco."
        )
    if not recommendations:
        recommendations.append(
            "Manter estratégia atual e repetir baseline operacional na próxima sessão."
        )
    return recommendations[:4]


def build_post_stream_report(
    *,
    channel_id: str,
    history_points: list[dict[str, Any]],
    observability_snapshot: dict[str, Any],
    generated_at: str | None = None,
    trigger: str = "manual_dashboard",
) -> dict[str, Any]:
    safe_channel_id = normalize_channel_id(channel_id) or "default"
    safe_snapshot = dict(observability_snapshot or {})

    normalized_history = [
        normalize_observability_history_point(point, default_channel_id=safe_channel_id)
        for point in list(history_points or [])
    ]
    ordered_history = sorted(
        normalized_history,
        key=lambda item: str(item.get("captured_at") or ""),
    )

    points_count = len(ordered_history)
    first_point = ordered_history[0] if ordered_history else {}
    last_point = ordered_history[-1] if ordered_history else {}

    first_metrics = dict(first_point.get("metrics") or {})
    last_metrics = dict(last_point.get("metrics") or {})
    last_chatters = dict(last_point.get("chatters") or {})
    last_sentiment = dict(last_point.get("sentiment") or {})
    last_stream_health = dict(last_point.get("stream_health") or {})

    snapshot_metrics = dict(safe_snapshot.get("metrics") or {})
    snapshot_chatters = dict(safe_snapshot.get("chatters") or {})
    snapshot_sentiment = dict(safe_snapshot.get("sentiment") or {})
    snapshot_stream_health = dict(safe_snapshot.get("stream_health") or {})
    snapshot_outcomes = dict(safe_snapshot.get("agent_outcomes") or {})

    chat_messages_total = (
        _safe_int(last_metrics.get("chat_messages_total"))
        if points_count > 0
        else _safe_int(snapshot_metrics.get("chat_messages_total"))
    )
    replies_total = (
        _safe_int(last_metrics.get("replies_total"))
        if points_count > 0
        else _safe_int(snapshot_metrics.get("replies_total"))
    )
    errors_total = (
        _safe_int(last_metrics.get("errors_total"))
        if points_count > 0
        else _safe_int(snapshot_metrics.get("errors_total"))
    )
    llm_interactions_total = (
        _safe_int(last_metrics.get("llm_interactions_total"))
        if points_count > 0
        else _safe_int(snapshot_metrics.get("llm_interactions_total"))
    )
    active_chatters_60m = (
        _safe_int(last_chatters.get("active_60m"))
        if points_count > 0
        else _safe_int(snapshot_chatters.get("active_60m"))
    )
    unique_chatters_total = (
        _safe_int(last_chatters.get("unique_total"))
        if points_count > 0
        else _safe_int(snapshot_chatters.get("unique_total"))
    )

    chat_messages_delta = (
        max(
            0,
            _safe_int(last_metrics.get("chat_messages_total"))
            - _safe_int(first_metrics.get("chat_messages_total")),
        )
        if points_count > 0
        else chat_messages_total
    )
    replies_delta = (
        max(
            0,
            _safe_int(last_metrics.get("replies_total"))
            - _safe_int(first_metrics.get("replies_total")),
        )
        if points_count > 0
        else replies_total
    )
    errors_delta = (
        max(
            0,
            _safe_int(last_metrics.get("errors_total"))
            - _safe_int(first_metrics.get("errors_total")),
        )
        if points_count > 0
        else errors_total
    )

    health_samples = [
        _safe_float(dict(point.get("stream_health") or {}).get("score"))
        for point in ordered_history
    ]
    avg_stream_health_score = (
        round(_average(health_samples), 1)
        if health_samples
        else round(_safe_float(snapshot_stream_health.get("score")), 1)
    )
    latest_stream_health_score = (
        _safe_int(last_stream_health.get("score"))
        if points_count > 0
        else _safe_int(snapshot_stream_health.get("score"))
    )
    latest_stream_health_band = _safe_band(
        last_stream_health.get("band") if points_count > 0 else snapshot_stream_health.get("band")
    )

    sentiment_samples = [
        _safe_float(dict(point.get("sentiment") or {}).get("avg")) for point in ordered_history
    ]
    avg_sentiment = (
        round(_average(sentiment_samples), 2)
        if sentiment_samples
        else round(_safe_float(snapshot_sentiment.get("avg")), 2)
    )
    vibe_counter = Counter(
        str(dict(point.get("sentiment") or {}).get("vibe") or "").strip()
        for point in ordered_history
    )
    dominant_vibe = (
        vibe_counter.most_common(1)[0][0]
        if vibe_counter
        else str(snapshot_sentiment.get("vibe") or "Chill")
    )

    decisions_total_60m = _safe_int(snapshot_outcomes.get("decisions_total_60m"))
    approved_total_60m = _safe_int(snapshot_outcomes.get("approved_total_60m"))
    rejected_total_60m = _safe_int(snapshot_outcomes.get("rejected_total_60m"))
    ignored_total_60m = _safe_int(snapshot_outcomes.get("ignored_total_60m"))
    ignored_rate_60m = round(_safe_float(snapshot_outcomes.get("ignored_rate_60m")), 1)
    useful_engagement_rate_60m = round(
        _safe_float(snapshot_outcomes.get("useful_engagement_rate_60m")), 1
    )
    approval_rate_60m = (
        round((approved_total_60m / float(decisions_total_60m)) * 100.0, 1)
        if decisions_total_60m > 0
        else 0.0
    )
    rejection_rate_60m = (
        round((rejected_total_60m / float(decisions_total_60m)) * 100.0, 1)
        if decisions_total_60m > 0
        else 0.0
    )

    estimated_cost_usd_60m = round(
        max(0.0, _safe_float(snapshot_outcomes.get("estimated_cost_usd_60m"))), 6
    )
    estimated_cost_usd_total = round(
        max(
            0.0,
            _safe_float(
                snapshot_outcomes.get(
                    "estimated_cost_usd_total",
                    snapshot_metrics.get("estimated_cost_usd_total"),
                )
            ),
        ),
        6,
    )
    token_input_60m = _safe_int(snapshot_outcomes.get("token_input_60m"))
    token_output_60m = _safe_int(snapshot_outcomes.get("token_output_60m"))

    peak_active_60m = (
        max(
            _safe_int(dict(point.get("chatters") or {}).get("active_60m"))
            for point in ordered_history
        )
        if points_count > 0
        else active_chatters_60m
    )

    recommendations = _build_recommendations(
        ignored_rate_60m=ignored_rate_60m,
        stream_health_band=latest_stream_health_band,
        errors_total=errors_total,
        estimated_cost_usd_60m=estimated_cost_usd_60m,
        replies_total=replies_total,
        chat_messages_total=chat_messages_total,
        approval_rate_60m=approval_rate_60m,
    )
    narrative = (
        f"Canal #{safe_channel_id} encerrou com stream health {latest_stream_health_score}/100 "
        f"({latest_stream_health_band}), {chat_messages_total} mensagens e {replies_total} respostas "
        f"acumuladas no histórico persistido. Action queue (60m): {decisions_total_60m} decisões "
        f"({approved_total_60m} aprovadas, {rejected_total_60m} rejeitadas, {ignored_total_60m} ignoradas). "
        f"Custo estimado: US$ {estimated_cost_usd_total:.4f} total, US$ {estimated_cost_usd_60m:.4f} em 60m."
    )

    return {
        "report_version": REPORT_VERSION,
        "channel_id": safe_channel_id,
        "generated_at": str(generated_at or utc_iso_now()),
        "trigger": str(trigger or "manual_dashboard").strip().lower() or "manual_dashboard",
        "history_window": {
            "points": points_count,
            "first_captured_at": str(first_point.get("captured_at") or ""),
            "last_captured_at": str(last_point.get("captured_at") or ""),
        },
        "traffic": {
            "chat_messages_total": chat_messages_total,
            "chat_messages_delta": chat_messages_delta,
            "replies_total": replies_total,
            "replies_delta": replies_delta,
            "llm_interactions_total": llm_interactions_total,
            "errors_total": errors_total,
            "errors_delta": errors_delta,
            "active_chatters_60m": active_chatters_60m,
            "unique_chatters_total": unique_chatters_total,
            "peak_active_chatters_60m": peak_active_60m,
        },
        "stream_health": {
            "latest_score": latest_stream_health_score,
            "latest_band": latest_stream_health_band,
            "average_score": avg_stream_health_score,
        },
        "sentiment": {
            "dominant_vibe": dominant_vibe or "Chill",
            "average_score": avg_sentiment,
        },
        "decisions_60m": {
            "total": decisions_total_60m,
            "approved": approved_total_60m,
            "rejected": rejected_total_60m,
            "ignored": ignored_total_60m,
            "approval_rate": approval_rate_60m,
            "rejection_rate": rejection_rate_60m,
            "ignored_rate": ignored_rate_60m,
            "useful_engagement_rate": useful_engagement_rate_60m,
        },
        "cost": {
            "estimated_cost_usd_60m": estimated_cost_usd_60m,
            "estimated_cost_usd_total": estimated_cost_usd_total,
            "token_input_60m": token_input_60m,
            "token_output_60m": token_output_60m,
        },
        "narrative": narrative,
        "recommendations": recommendations,
    }
