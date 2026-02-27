from datetime import UTC, datetime
from typing import Any

from bot.observability_analytics import (
    compute_autonomy_metrics,
    compute_chat_metrics,
    compute_interaction_metrics,
    compute_leaderboards,
    compute_quality_metrics,
    compute_token_metrics,
)
from bot.observability_helpers import (
    TIMELINE_WINDOW_MINUTES,
    clip_preview,
    compute_p95,
    utc_iso,
)
from bot.stream_health_score import build_stream_health_score


def build_observability_snapshot(
    *,
    now: float,
    started_at: float,
    counters: dict[str, int],
    route_counts: dict[str, int],
    latencies_ms: list[float],
    minute_buckets: dict[int, dict[str, int]],
    recent_events: list[dict[str, Any]],
    chatter_last_seen: dict[str, float],
    chat_events: list[dict[str, Any]],
    byte_trigger_events: list[dict[str, Any]],
    interaction_events: list[dict[str, Any]],
    quality_events: list[dict[str, Any]],
    token_usage_events: list[dict[str, Any]],
    autonomy_goal_events: list[dict[str, Any]],
    chatter_message_totals: dict[str, int],
    trigger_user_totals: dict[str, int],
    unique_chatters_total: int,
    last_prompt: str,
    last_reply: str,
    estimated_cost_usd_total: float,
    clips_status: dict[str, bool],
    bot_brand: str,
    bot_version: str,
    bot_mode: str,
    stream_context: Any,
    channel_id: str = "default",
) -> dict[str, Any]:
    # Active users
    active_chatters_10m = sum(1 for value in chatter_last_seen.values() if now - value <= 600)
    active_chatters_60m = sum(1 for value in chatter_last_seen.values() if now - value <= 3600)

    # Latency
    avg_latency_ms = round(sum(latencies_ms) / len(latencies_ms), 1) if latencies_ms else 0.0
    p95_latency_ms = compute_p95(latencies_ms)

    # Analytics
    chat_metrics = compute_chat_metrics(chat_events, now)
    interaction_metrics = compute_interaction_metrics(interaction_events, now)
    quality_metrics = compute_quality_metrics(
        quality_events, interaction_metrics["llm_interactions_60m"], now
    )
    token_metrics = compute_token_metrics(token_usage_events, now)
    autonomy_metrics = compute_autonomy_metrics(autonomy_goal_events, now)

    # Leaderboards
    # Need byte_trigger_events filtered for 60m first
    cutoff_60m = now - 3600
    trigger_events_60m = [e for e in byte_trigger_events if float(e.get("ts", 0.0)) >= cutoff_60m]

    leaderboards = compute_leaderboards(
        chat_metrics.pop("events_60m"),  # Pop to remove from result dict
        trigger_events_60m,
        chatter_message_totals,
        trigger_user_totals,
    )

    source_counts = leaderboards.pop("source_counts_60m")
    chat_metrics["source_counts_60m"] = {
        "irc": int(source_counts.get("irc", 0)),
        "eventsub": int(source_counts.get("eventsub", 0)),
        "unknown": int(source_counts.get("unknown", 0)),
    }
    chat_metrics["byte_triggers_10m"] = len(
        [e for e in byte_trigger_events if float(e.get("ts", 0.0)) >= now - 600]
    )
    chat_metrics["byte_triggers_60m"] = len(trigger_events_60m)

    # Context
    context_vibe = str(getattr(stream_context, "stream_vibe", "Conversa") or "Conversa")
    context_last_event = str(getattr(stream_context, "last_event", "Bot Online") or "Bot Online")
    raw_observability = getattr(stream_context, "live_observability", {}) or {}
    context_items = {
        str(key): str(value) for key, value in dict(raw_observability).items() if str(value).strip()
    }
    context_active_count = len(context_items)

    get_uptime_minutes = getattr(stream_context, "get_uptime_minutes", None)
    if callable(get_uptime_minutes):
        uptime_value = get_uptime_minutes()
        if isinstance(uptime_value, int | float | str):
            uptime_minutes = max(0, int(uptime_value))
        else:
            uptime_minutes = max(0, int((now - started_at) / 60))
    else:
        uptime_minutes = max(0, int((now - started_at) / 60))

    # Timeline
    now_minute = int(now // 60)
    timeline = []
    for minute_key in range(now_minute - TIMELINE_WINDOW_MINUTES + 1, now_minute + 1):
        bucket: dict[str, int] = minute_buckets.get(minute_key) or {}
        timeline.append(
            {
                "minute_epoch": minute_key * 60,
                "label": datetime.fromtimestamp(minute_key * 60, tz=UTC).strftime("%H:%M"),
                "chat_messages": int(bucket.get("chat_messages", 0)),
                "byte_triggers": int(bucket.get("byte_triggers", 0)),
                "replies_sent": int(bucket.get("replies_sent", 0)),
                "llm_requests": int(bucket.get("llm_requests", 0)),
                "errors": int(bucket.get("errors", 0)),
            }
        )

    sorted_routes = sorted(route_counts.items(), key=lambda item: item[1], reverse=True)
    route_rows = [{"route": route, "count": count} for route, count in sorted_routes]
    events_desc = list(reversed(recent_events[-40:]))
    sentiment_block = _build_sentiment_block(channel_id)
    agent_outcomes = {
        **interaction_metrics,
        **quality_metrics,
        **autonomy_metrics,
        "token_input_total": int(counters.get("token_input_total", 0)),
        "token_output_total": int(counters.get("token_output_total", 0)),
        **token_metrics,
        "estimated_cost_usd_total": round(max(0.0, float(estimated_cost_usd_total or 0.0)), 6),
    }
    stream_health = build_stream_health_score(
        sentiment=sentiment_block,
        chat_analytics=chat_metrics,
        agent_outcomes=agent_outcomes,
        timeline=timeline,
    )

    return {
        "timestamp": utc_iso(now),
        "bot": {
            "brand": bot_brand,
            "version": bot_version,
            "mode": bot_mode,
            "status": "online",
            "uptime_minutes": uptime_minutes,
        },
        "metrics": {
            "chat_messages_total": int(counters.get("chat_messages_total", 0)),
            "chat_messages_irc_total": int(counters.get("chat_messages_irc", 0)),
            "chat_messages_eventsub_total": int(counters.get("chat_messages_eventsub", 0)),
            "chat_prefixed_messages_total": int(counters.get("chat_prefixed_messages", 0)),
            "chat_messages_with_url_total": int(counters.get("chat_messages_with_url", 0)),
            "byte_triggers_total": int(counters.get("byte_triggers_total", 0)),
            "interactions_total": int(counters.get("interactions_total", 0)),
            "replies_total": int(counters.get("replies_total", 0)),
            "llm_interactions_total": int(counters.get("llm_interactions_total", 0)),
            "serious_interactions_total": int(counters.get("serious_interactions_total", 0)),
            "current_events_interactions_total": int(
                counters.get("current_events_interactions_total", 0)
            ),
            "follow_up_interactions_total": int(counters.get("follow_up_interactions_total", 0)),
            "quality_checks_total": int(counters.get("quality_checks_total", 0)),
            "quality_retry_total": int(counters.get("quality_retry_total", 0)),
            "quality_retry_success_total": int(counters.get("quality_retry_success_total", 0)),
            "quality_fallback_total": int(counters.get("quality_fallback_total", 0)),
            "auto_scene_updates_total": int(counters.get("auto_scene_updates_total", 0)),
            "token_input_total": int(counters.get("token_input_total", 0)),
            "token_output_total": int(counters.get("token_output_total", 0)),
            "estimated_cost_usd_total": round(max(0.0, float(estimated_cost_usd_total or 0.0)), 6),
            "token_refreshes_total": int(counters.get("token_refreshes_total", 0)),
            "auth_failures_total": int(counters.get("auth_failures_total", 0)),
            "errors_total": int(counters.get("errors_total", 0)),
            "vision_frames_total": int(counters.get("vision_frames_total", 0)),
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
        },
        "chatters": {
            "unique_total": unique_chatters_total,
            "active_10m": active_chatters_10m,
            "active_60m": active_chatters_60m,
        },
        "chat_analytics": chat_metrics,
        "leaderboards": leaderboards,
        "agent_outcomes": agent_outcomes,
        "context": {
            "stream_vibe": context_vibe,
            "last_event": context_last_event,
            "active_contexts": context_active_count,
            "items": context_items,
            "last_prompt": clip_preview(last_prompt, max_chars=120),
            "last_reply": clip_preview(last_reply, max_chars=140),
            "clips_status": clips_status,
        },
        "counters": {key: int(value) for key, value in counters.items()},
        "routes": route_rows,
        "timeline": timeline,
        "recent_events": events_desc,
        "sentiment": sentiment_block,
        "stream_health": stream_health,
        "vision": _build_vision_block(),
    }


def _build_sentiment_block(channel_id: str = "default") -> dict[str, Any]:
    from bot.sentiment_engine import sentiment_engine  # lazy: avoid circular

    scores = sentiment_engine.get_scores(channel_id)
    return {
        "vibe": sentiment_engine.get_vibe(channel_id),
        "avg": scores["avg"],
        "count": scores["count"],
        "positive": scores["positive"],
        "negative": scores["negative"],
    }


def _build_vision_block() -> dict[str, Any]:
    from bot.vision_runtime import vision_runtime  # lazy: avoid circular

    return vision_runtime.get_status()
