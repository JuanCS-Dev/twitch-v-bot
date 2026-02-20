import threading
import time
from collections import Counter, deque
from typing import Any

from bot.observability_helpers import (
    BYTE_TRIGGER_EVENTS_MAX_ITEMS,
    BYTE_TRIGGER_EVENTS_RETENTION_SECONDS,
    CHAT_EVENTS_MAX_ITEMS,
    CHAT_EVENTS_RETENTION_SECONDS,
    EVENT_LOG_MAX_ITEMS,
    LATENCY_WINDOW_MAX_ITEMS,
    TIMELINE_RETENTION_MINUTES,
    clip_preview,
    utc_iso,
)
from bot.observability_snapshot import build_observability_snapshot


class ObservabilityState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._counters: Counter[str] = Counter()
        self._route_counts: Counter[str] = Counter()
        self._minute_buckets: dict[int, dict[str, int]] = {}
        self._latencies_ms: deque[float] = deque(maxlen=LATENCY_WINDOW_MAX_ITEMS)
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=EVENT_LOG_MAX_ITEMS)
        self._chatter_last_seen: dict[str, float] = {}
        self._known_chatters: set[str] = set()
        self._chat_events: deque[dict[str, Any]] = deque(maxlen=CHAT_EVENTS_MAX_ITEMS)
        self._byte_trigger_events: deque[dict[str, Any]] = deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
        self._chatter_message_totals: Counter[str] = Counter()
        self._trigger_user_totals: Counter[str] = Counter()
        self._last_prompt = ""
        self._last_reply = ""

    def _resolve_now(self, timestamp: float | None) -> float:
        return time.time() if timestamp is None else float(timestamp)

    def _touch_bucket_locked(self, now: float) -> dict[str, int]:
        minute_key = int(now // 60)
        bucket = self._minute_buckets.get(minute_key)
        if bucket is None:
            bucket = {"chat_messages": 0, "byte_triggers": 0, "replies_sent": 0, "llm_requests": 0, "errors": 0}
            self._minute_buckets[minute_key] = bucket
        return bucket

    def _bump_timeline_locked(self, now: float, **increments: int) -> None:
        bucket = self._touch_bucket_locked(now)
        for key, amount in increments.items():
            if amount > 0:
                bucket[key] = bucket.get(key, 0) + int(amount)

    def _append_event_locked(self, now: float, level: str, event: str, message: str) -> None:
        self._recent_events.append({"ts": utc_iso(now), "level": level, "event": event, "message": clip_preview(message, max_chars=180)})

    def _prune_locked(self, now: float) -> None:
        oldest_minute = int(now // 60) - TIMELINE_RETENTION_MINUTES
        for minute_key in list(self._minute_buckets):
            if minute_key < oldest_minute:
                del self._minute_buckets[minute_key]
        oldest_chatter_cutoff = now - 86400
        for chatter, last_seen in list(self._chatter_last_seen.items()):
            if last_seen < oldest_chatter_cutoff:
                del self._chatter_last_seen[chatter]
        chat_cutoff = now - CHAT_EVENTS_RETENTION_SECONDS
        while self._chat_events and float(self._chat_events[0].get("ts", 0.0)) < chat_cutoff:
            self._chat_events.popleft()
        trigger_cutoff = now - BYTE_TRIGGER_EVENTS_RETENTION_SECONDS
        while self._byte_trigger_events and float(self._byte_trigger_events[0].get("ts", 0.0)) < trigger_cutoff:
            self._byte_trigger_events.popleft()

    def record_chat_message(self, *, author_name: str, source: str, text: str = "", timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        safe_source = (source or "unknown").strip().lower() or "unknown"
        safe_author = (author_name or "").strip().lower()
        message_text = (text or "").strip()
        is_command = bool(message_text.startswith("!"))
        lowered_text = message_text.lower()
        has_url = "http://" in lowered_text or "https://" in lowered_text
        with self._lock:
            self._counters["chat_messages_total"] += 1
            self._counters[f"chat_messages_{safe_source}"] += 1
            self._bump_timeline_locked(now, chat_messages=1)
            self._chat_events.append({
                "ts": now,
                "source": safe_source,
                "author": safe_author,
                "length": len(message_text),
                "is_command": is_command,
                "has_url": has_url,
            })
            if safe_author:
                self._known_chatters.add(safe_author)
                self._chatter_last_seen[safe_author] = now
                self._chatter_message_totals[safe_author] += 1
            if is_command:
                self._counters["chat_prefixed_messages"] += 1
            if has_url:
                self._counters["chat_messages_with_url"] += 1
            self._prune_locked(now)

    def record_byte_trigger(self, *, prompt: str, source: str, author_name: str = "", timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        safe_source = (source or "unknown").strip().lower() or "unknown"
        safe_author_key = (author_name or "").strip().lower() or "viewer"
        safe_author = clip_preview(author_name or "viewer", max_chars=32)
        prompt_preview = clip_preview(prompt or "(empty prompt)", max_chars=120)
        with self._lock:
            self._counters["byte_triggers_total"] += 1
            self._counters[f"byte_triggers_{safe_source}"] += 1
            self._trigger_user_totals[safe_author_key] += 1
            self._byte_trigger_events.append({"ts": now, "author": safe_author_key, "source": safe_source})
            self._last_prompt = prompt_preview
            self._bump_timeline_locked(now, byte_triggers=1)
            self._append_event_locked(now, "INFO", "byte_trigger", f"{safe_author}: {prompt_preview}")
            self._prune_locked(now)

    def record_reply(self, *, text: str, timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        reply_preview = clip_preview(text or "", max_chars=140)
        if not reply_preview:
            return
        with self._lock:
            self._counters["replies_total"] += 1
            self._counters["reply_chars_total"] += len(reply_preview)
            self._last_reply = reply_preview
            self._bump_timeline_locked(now, replies_sent=1)
            self._prune_locked(now)

    def record_quality_gate(self, *, outcome: str, reason: str, timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        safe_outcome = (outcome or "unknown").strip().lower() or "unknown"
        safe_reason = clip_preview(reason or "n/a", max_chars=120)
        event_level = "WARN" if safe_outcome in {"retry", "fallback"} else "INFO"
        with self._lock:
            self._counters["quality_checks_total"] += 1
            self._counters[f"quality_{safe_outcome}_total"] += 1
            self._append_event_locked(now, event_level, "quality_gate", f"{safe_outcome}: {safe_reason}")
            self._prune_locked(now)

    def record_byte_interaction(
        self,
        *,
        route: str,
        author_name: str,
        prompt_chars: int,
        reply_parts: int,
        reply_chars: int,
        serious: bool,
        follow_up: bool,
        current_events: bool,
        latency_ms: float,
        timestamp: float | None = None,
    ) -> None:
        now = self._resolve_now(timestamp)
        safe_route = (route or "unknown").strip().lower() or "unknown"
        safe_author = clip_preview(author_name or "viewer", max_chars=32)
        with self._lock:
            self._counters["interactions_total"] += 1
            self._route_counts[safe_route] += 1
            self._counters["prompt_chars_total"] += max(0, int(prompt_chars))
            self._counters["interaction_reply_parts_total"] += max(0, int(reply_parts))
            self._counters["interaction_reply_chars_total"] += max(0, int(reply_chars))
            if safe_route.startswith("llm"):
                self._counters["llm_interactions_total"] += 1
                self._bump_timeline_locked(now, llm_requests=1)
            if serious:
                self._counters["serious_interactions_total"] += 1
            if follow_up:
                self._counters["follow_up_interactions_total"] += 1
            if current_events:
                self._counters["current_events_interactions_total"] += 1
            if latency_ms >= 0:
                self._latencies_ms.append(float(latency_ms))
            details = (
                f"{safe_route} by {safe_author} | prompt={max(0, int(prompt_chars))} chars | "
                f"replies={max(0, int(reply_parts))} | latency={round(max(0.0, latency_ms), 1)}ms"
            )
            self._append_event_locked(now, "INFO", "byte_interaction", details)
            self._prune_locked(now)

    def record_auto_scene_update(self, *, update_types: list[str], timestamp: float | None = None) -> None:
        if not update_types:
            return
        now = self._resolve_now(timestamp)
        safe_types = sorted({(item or "").strip().lower() for item in update_types if item})
        if not safe_types:
            return
        with self._lock:
            self._counters["auto_scene_updates_total"] += len(safe_types)
            self._append_event_locked(now, "INFO", "scene_update", f"updated: {', '.join(safe_types)}")
            self._prune_locked(now)

    def record_token_refresh(self, *, reason: str, timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        safe_reason = clip_preview(reason or "n/a", max_chars=100)
        with self._lock:
            self._counters["token_refreshes_total"] += 1
            self._append_event_locked(now, "WARN", "token_refresh", safe_reason)
            self._prune_locked(now)

    def record_auth_failure(self, *, details: str, timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        safe_details = clip_preview(details or "n/a", max_chars=120)
        with self._lock:
            self._counters["auth_failures_total"] += 1
            self._counters["errors_total"] += 1
            self._bump_timeline_locked(now, errors=1)
            self._append_event_locked(now, "ERROR", "auth_failure", safe_details)
            self._prune_locked(now)

    def record_error(self, *, category: str, details: str, timestamp: float | None = None) -> None:
        now = self._resolve_now(timestamp)
        safe_category = (category or "unknown").strip().lower() or "unknown"
        safe_details = clip_preview(details or "n/a", max_chars=140)
        with self._lock:
            self._counters["errors_total"] += 1
            self._counters[f"errors_{safe_category}"] += 1
            self._bump_timeline_locked(now, errors=1)
            self._append_event_locked(now, "ERROR", safe_category, safe_details)
            self._prune_locked(now)

    def snapshot(
        self,
        *,
        bot_brand: str,
        bot_version: str,
        bot_mode: str,
        stream_context: Any,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = self._resolve_now(timestamp)
        with self._lock:
            self._prune_locked(now)
            payload = {
                "started_at": self._started_at,
                "counters": dict(self._counters),
                "route_counts": dict(self._route_counts),
                "latencies_ms": list(self._latencies_ms),
                "minute_buckets": {key: value.copy() for key, value in self._minute_buckets.items()},
                "recent_events": list(self._recent_events),
                "chatter_last_seen": dict(self._chatter_last_seen),
                "chat_events": list(self._chat_events),
                "byte_trigger_events": list(self._byte_trigger_events),
                "chatter_message_totals": dict(self._chatter_message_totals),
                "trigger_user_totals": dict(self._trigger_user_totals),
                "unique_chatters_total": len(self._known_chatters),
                "last_prompt": self._last_prompt,
                "last_reply": self._last_reply,
            }
        return build_observability_snapshot(
            now=now,
            started_at=payload["started_at"],
            counters=payload["counters"],
            route_counts=payload["route_counts"],
            latencies_ms=payload["latencies_ms"],
            minute_buckets=payload["minute_buckets"],
            recent_events=payload["recent_events"],
            chatter_last_seen=payload["chatter_last_seen"],
            chat_events=payload["chat_events"],
            byte_trigger_events=payload["byte_trigger_events"],
            chatter_message_totals=payload["chatter_message_totals"],
            trigger_user_totals=payload["trigger_user_totals"],
            unique_chatters_total=payload["unique_chatters_total"],
            last_prompt=payload["last_prompt"],
            last_reply=payload["last_reply"],
            bot_brand=bot_brand,
            bot_version=bot_version,
            bot_mode=bot_mode,
            stream_context=stream_context,
        )
