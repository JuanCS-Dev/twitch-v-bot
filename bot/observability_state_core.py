import time
from typing import Any

from bot.observability_helpers import (
    BYTE_TRIGGER_EVENTS_RETENTION_SECONDS,
    CHAT_EVENTS_RETENTION_SECONDS,
    TIMELINE_RETENTION_MINUTES,
    clip_preview,
    utc_iso,
)


def resolve_now(timestamp: float | None) -> float:
    return time.time() if timestamp is None else float(timestamp)


def touch_bucket_locked(state: Any, now: float) -> dict[str, int]:
    minute_key = int(now // 60)
    bucket = state._minute_buckets.get(minute_key)
    if bucket is None:
        bucket = {
            "chat_messages": 0,
            "byte_triggers": 0,
            "replies_sent": 0,
            "llm_requests": 0,
            "errors": 0,
        }
        state._minute_buckets[minute_key] = bucket
    return bucket


def bump_timeline_locked(state: Any, now: float, **increments: int) -> None:
    bucket = touch_bucket_locked(state, now)
    for key, amount in increments.items():
        if amount > 0:
            bucket[key] = bucket.get(key, 0) + int(amount)


def append_event_locked(state: Any, now: float, level: str, event: str, message: str) -> None:
    state._recent_events.append(
        {
            "ts": utc_iso(now),
            "level": level,
            "event": event,
            "message": clip_preview(message, max_chars=180),
        }
    )


def prune_locked(state: Any, now: float) -> None:
    oldest_minute = int(now // 60) - TIMELINE_RETENTION_MINUTES
    for minute_key in list(state._minute_buckets):
        if minute_key < oldest_minute:
            del state._minute_buckets[minute_key]

    oldest_chatter_cutoff = now - 86400
    for chatter, last_seen in list(state._chatter_last_seen.items()):
        if last_seen < oldest_chatter_cutoff:
            del state._chatter_last_seen[chatter]

    chat_cutoff = now - CHAT_EVENTS_RETENTION_SECONDS
    while state._chat_events and float(state._chat_events[0].get("ts", 0.0)) < chat_cutoff:
        state._chat_events.popleft()

    trigger_cutoff = now - BYTE_TRIGGER_EVENTS_RETENTION_SECONDS
    while state._byte_trigger_events and float(state._byte_trigger_events[0].get("ts", 0.0)) < trigger_cutoff:
        state._byte_trigger_events.popleft()
    while state._interaction_events and float(state._interaction_events[0].get("ts", 0.0)) < trigger_cutoff:
        state._interaction_events.popleft()
    while state._quality_events and float(state._quality_events[0].get("ts", 0.0)) < trigger_cutoff:
        state._quality_events.popleft()
    while state._token_usage_events and float(state._token_usage_events[0].get("ts", 0.0)) < trigger_cutoff:
        state._token_usage_events.popleft()
    while state._autonomy_goal_events and float(state._autonomy_goal_events[0].get("ts", 0.0)) < trigger_cutoff:
        state._autonomy_goal_events.popleft()

