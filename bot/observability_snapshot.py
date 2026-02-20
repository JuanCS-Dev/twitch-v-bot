from collections import Counter
from datetime import datetime, timezone
from typing import Any

from bot.observability_helpers import (
    LEADERBOARD_LIMIT,
    TIMELINE_WINDOW_MINUTES,
    clip_preview,
    compute_p95,
    percentage,
    utc_iso,
)


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
    chatter_message_totals: dict[str, int],
    trigger_user_totals: dict[str, int],
    unique_chatters_total: int,
    last_prompt: str,
    last_reply: str,
    bot_brand: str,
    bot_version: str,
    bot_mode: str,
    stream_context: Any,
) -> dict[str, Any]:
    active_chatters_10m = sum(1 for value in chatter_last_seen.values() if now - value <= 600)
    active_chatters_60m = sum(1 for value in chatter_last_seen.values() if now - value <= 3600)
    avg_latency_ms = round(sum(latencies_ms) / len(latencies_ms), 1) if latencies_ms else 0.0
    p95_latency_ms = compute_p95(latencies_ms)

    chat_10m_cutoff = now - 600
    chat_60m_cutoff = now - 3600
    chat_events_10m = [event for event in chat_events if float(event.get("ts", 0.0)) >= chat_10m_cutoff]
    chat_events_60m = [event for event in chat_events if float(event.get("ts", 0.0)) >= chat_60m_cutoff]
    chat_count_10m = len(chat_events_10m)
    chat_count_60m = len(chat_events_60m)
    command_count_60m = sum(1 for event in chat_events_60m if bool(event.get("is_command", False)))
    url_count_60m = sum(1 for event in chat_events_60m if bool(event.get("has_url", False)))
    average_length_10m = round(
        sum(int(event.get("length", 0)) for event in chat_events_10m) / chat_count_10m,
        1,
    ) if chat_count_10m else 0.0
    average_length_60m = round(
        sum(int(event.get("length", 0)) for event in chat_events_60m) / chat_count_60m,
        1,
    ) if chat_count_60m else 0.0

    source_counts_60m: Counter[str] = Counter()
    chatter_counts_60m: Counter[str] = Counter()
    for event in chat_events_60m:
        source_name = str(event.get("source", "unknown") or "unknown")
        source_counts_60m[source_name] += 1
        author_name = str(event.get("author", "") or "").strip().lower()
        if author_name:
            chatter_counts_60m[author_name] += 1

    trigger_events_10m = [event for event in byte_trigger_events if float(event.get("ts", 0.0)) >= chat_10m_cutoff]
    trigger_events_60m = [event for event in byte_trigger_events if float(event.get("ts", 0.0)) >= chat_60m_cutoff]
    trigger_users_60m: Counter[str] = Counter()
    for event in trigger_events_60m:
        author_name = str(event.get("author", "") or "").strip().lower()
        if author_name:
            trigger_users_60m[author_name] += 1

    top_chatters_60m_rows = [
        {"author": author, "messages": count}
        for author, count in chatter_counts_60m.most_common(LEADERBOARD_LIMIT)
    ]
    top_chatters_total_rows = [
        {"author": author, "messages": count}
        for author, count in Counter(chatter_message_totals).most_common(LEADERBOARD_LIMIT)
    ]
    top_trigger_users_60m_rows = [
        {"author": author, "triggers": count}
        for author, count in trigger_users_60m.most_common(LEADERBOARD_LIMIT)
    ]
    top_trigger_users_total_rows = [
        {"author": author, "triggers": count}
        for author, count in Counter(trigger_user_totals).most_common(LEADERBOARD_LIMIT)
    ]

    context_vibe = str(getattr(stream_context, "stream_vibe", "Conversa") or "Conversa")
    context_last_event = str(getattr(stream_context, "last_event", "Bot Online") or "Bot Online")
    raw_observability = getattr(stream_context, "live_observability", {}) or {}
    context_items = {str(key): str(value) for key, value in dict(raw_observability).items() if str(value).strip()}
    context_active_count = len(context_items)

    get_uptime_minutes = getattr(stream_context, "get_uptime_minutes", None)
    if callable(get_uptime_minutes):
        uptime_minutes = max(0, int(get_uptime_minutes()))
    else:
        uptime_minutes = max(0, int((now - started_at) / 60))

    now_minute = int(now // 60)
    timeline = []
    for minute_key in range(now_minute - TIMELINE_WINDOW_MINUTES + 1, now_minute + 1):
        bucket = minute_buckets.get(minute_key, {})
        timeline.append(
            {
                "minute_epoch": minute_key * 60,
                "label": datetime.fromtimestamp(minute_key * 60, tz=timezone.utc).strftime("%H:%M"),
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
            "current_events_interactions_total": int(counters.get("current_events_interactions_total", 0)),
            "follow_up_interactions_total": int(counters.get("follow_up_interactions_total", 0)),
            "quality_checks_total": int(counters.get("quality_checks_total", 0)),
            "quality_retry_total": int(counters.get("quality_retry_total", 0)),
            "quality_retry_success_total": int(counters.get("quality_retry_success_total", 0)),
            "quality_fallback_total": int(counters.get("quality_fallback_total", 0)),
            "auto_scene_updates_total": int(counters.get("auto_scene_updates_total", 0)),
            "token_refreshes_total": int(counters.get("token_refreshes_total", 0)),
            "auth_failures_total": int(counters.get("auth_failures_total", 0)),
            "errors_total": int(counters.get("errors_total", 0)),
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
        },
        "chatters": {
            "unique_total": unique_chatters_total,
            "active_10m": active_chatters_10m,
            "active_60m": active_chatters_60m,
        },
        "chat_analytics": {
            "messages_10m": chat_count_10m,
            "messages_60m": chat_count_60m,
            "messages_per_minute_10m": round(chat_count_10m / 10, 2),
            "messages_per_minute_60m": round(chat_count_60m / 60, 2),
            "avg_message_length_10m": average_length_10m,
            "avg_message_length_60m": average_length_60m,
            "prefixed_commands_60m": command_count_60m,
            "prefixed_command_ratio_60m": percentage(command_count_60m, chat_count_60m),
            "url_messages_60m": url_count_60m,
            "url_ratio_60m": percentage(url_count_60m, chat_count_60m),
            "source_counts_60m": {
                "irc": int(source_counts_60m.get("irc", 0)),
                "eventsub": int(source_counts_60m.get("eventsub", 0)),
                "unknown": int(source_counts_60m.get("unknown", 0)),
            },
            "byte_triggers_10m": len(trigger_events_10m),
            "byte_triggers_60m": len(trigger_events_60m),
        },
        "leaderboards": {
            "top_chatters_60m": top_chatters_60m_rows,
            "top_chatters_total": top_chatters_total_rows,
            "top_trigger_users_60m": top_trigger_users_60m_rows,
            "top_trigger_users_total": top_trigger_users_total_rows,
        },
        "context": {
            "stream_vibe": context_vibe,
            "last_event": context_last_event,
            "active_contexts": context_active_count,
            "items": context_items,
            "last_prompt": clip_preview(last_prompt, max_chars=120),
            "last_reply": clip_preview(last_reply, max_chars=140),
        },
        "routes": route_rows,
        "timeline": timeline,
        "recent_events": events_desc,
    }
