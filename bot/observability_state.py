import threading
import time
from collections import Counter, deque
from typing import Any

from bot.observability_helpers import (
    BYTE_TRIGGER_EVENTS_MAX_ITEMS,
    CHAT_EVENTS_MAX_ITEMS,
    EVENT_LOG_MAX_ITEMS,
    LATENCY_WINDOW_MAX_ITEMS,
)
from bot.observability_snapshot import build_observability_snapshot
from bot.observability_state_core import prune_locked, resolve_now
from bot.observability_state_recorders import (
    record_auth_failure_locked,
    record_auto_scene_update_locked,
    record_autonomy_goal_locked,
    record_byte_interaction_locked,
    record_byte_trigger_locked,
    record_chat_message_locked,
    record_error_locked,
    record_quality_gate_locked,
    record_reply_locked,
    record_token_refresh_locked,
    record_token_usage_locked,
    record_vision_frame_locked,
)


class ObservabilityState:
    def __init__(
        self,
        *,
        persistence_layer: Any | None = None,
        persist_interval_seconds: float = 15.0,
    ) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._persistence = persistence_layer
        self._persist_interval_seconds = max(0.0, float(persist_interval_seconds))
        self._last_persisted_monotonic = 0.0
        self._dirty = False
        self._persistence_source = "memory"
        self._persistence_updated_at = ""
        self._restored_from_persistence = False
        self._counters: Counter[str] = Counter()
        self._route_counts: Counter[str] = Counter()
        self._minute_buckets: dict[int, dict[str, int]] = {}
        self._latencies_ms: deque[float] = deque(maxlen=LATENCY_WINDOW_MAX_ITEMS)
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=EVENT_LOG_MAX_ITEMS)
        self._chatter_last_seen: dict[str, float] = {}
        self._known_chatters: set[str] = set()
        self._chat_events: deque[dict[str, Any]] = deque(maxlen=CHAT_EVENTS_MAX_ITEMS)
        self._byte_trigger_events: deque[dict[str, Any]] = deque(
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS
        )
        self._interaction_events: deque[dict[str, Any]] = deque(
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS
        )
        self._quality_events: deque[dict[str, Any]] = deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
        self._token_usage_events: deque[dict[str, Any]] = deque(
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS
        )
        self._autonomy_goal_events: deque[dict[str, Any]] = deque(
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS
        )
        self._chatter_message_totals: Counter[str] = Counter()
        self._trigger_user_totals: Counter[str] = Counter()
        self._last_prompt = ""
        self._last_reply = ""
        self._estimated_cost_usd_total = 0.0
        self._clips_status: dict[str, bool] = {
            "token_valid": False,
            "scope_ok": False,
        }
        self._restore_from_persistence()

    def _build_rollup_payload_locked(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "counters": {key: int(value) for key, value in self._counters.items()},
            "route_counts": {key: int(value) for key, value in self._route_counts.items()},
            "minute_buckets": {
                str(key): {name: int(amount) for name, amount in bucket.items()}
                for key, bucket in self._minute_buckets.items()
            },
            "latencies_ms": [float(value) for value in self._latencies_ms],
            "recent_events": list(self._recent_events),
            "chatter_last_seen": {
                str(key): float(value) for key, value in self._chatter_last_seen.items()
            },
            "known_chatters": sorted(self._known_chatters),
            "chat_events": list(self._chat_events),
            "byte_trigger_events": list(self._byte_trigger_events),
            "interaction_events": list(self._interaction_events),
            "quality_events": list(self._quality_events),
            "token_usage_events": list(self._token_usage_events),
            "autonomy_goal_events": list(self._autonomy_goal_events),
            "chatter_message_totals": {
                key: int(value) for key, value in self._chatter_message_totals.items()
            },
            "trigger_user_totals": {
                key: int(value) for key, value in self._trigger_user_totals.items()
            },
            "last_prompt": str(self._last_prompt or ""),
            "last_reply": str(self._last_reply or ""),
            "estimated_cost_usd_total": float(self._estimated_cost_usd_total or 0.0),
            "clips_status": {
                "token_valid": bool(self._clips_status.get("token_valid", False)),
                "scope_ok": bool(self._clips_status.get("scope_ok", False)),
            },
        }

    def _restore_from_persistence(self) -> None:
        if not self._persistence:
            return
        try:
            persisted = self._persistence.load_observability_rollup_sync()
        except Exception:
            return
        if not persisted:
            return
        state = dict(persisted.get("state") or {})
        with self._lock:
            self._counters = Counter(
                {str(key): int(value) for key, value in dict(state.get("counters") or {}).items()}
            )
            self._route_counts = Counter(
                {
                    str(key): int(value)
                    for key, value in dict(state.get("route_counts") or {}).items()
                }
            )
            self._minute_buckets = {
                int(key): {
                    str(bucket_key): int(bucket_value)
                    for bucket_key, bucket_value in dict(bucket or {}).items()
                }
                for key, bucket in dict(state.get("minute_buckets") or {}).items()
                if str(key).lstrip("-").isdigit()
            }
            self._latencies_ms = deque(
                [float(value) for value in list(state.get("latencies_ms") or [])],
                maxlen=LATENCY_WINDOW_MAX_ITEMS,
            )
            self._recent_events = deque(
                list(state.get("recent_events") or []),
                maxlen=EVENT_LOG_MAX_ITEMS,
            )
            self._chatter_last_seen = {
                str(key): float(value)
                for key, value in dict(state.get("chatter_last_seen") or {}).items()
            }
            self._known_chatters = {
                str(value).strip().lower()
                for value in list(state.get("known_chatters") or [])
                if str(value).strip()
            }
            self._chat_events = deque(
                list(state.get("chat_events") or []),
                maxlen=CHAT_EVENTS_MAX_ITEMS,
            )
            self._byte_trigger_events = deque(
                list(state.get("byte_trigger_events") or []),
                maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
            )
            self._interaction_events = deque(
                list(state.get("interaction_events") or []),
                maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
            )
            self._quality_events = deque(
                list(state.get("quality_events") or []),
                maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
            )
            self._token_usage_events = deque(
                list(state.get("token_usage_events") or []),
                maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
            )
            self._autonomy_goal_events = deque(
                list(state.get("autonomy_goal_events") or []),
                maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
            )
            self._chatter_message_totals = Counter(
                {
                    str(key): int(value)
                    for key, value in dict(state.get("chatter_message_totals") or {}).items()
                }
            )
            self._trigger_user_totals = Counter(
                {
                    str(key): int(value)
                    for key, value in dict(state.get("trigger_user_totals") or {}).items()
                }
            )
            self._last_prompt = str(state.get("last_prompt") or "")
            self._last_reply = str(state.get("last_reply") or "")
            self._estimated_cost_usd_total = float(state.get("estimated_cost_usd_total") or 0.0)
            restored_clips_status = dict(state.get("clips_status") or {})
            self._clips_status = {
                "token_valid": bool(restored_clips_status.get("token_valid", False)),
                "scope_ok": bool(restored_clips_status.get("scope_ok", False)),
            }
            self._restored_from_persistence = True
            self._persistence_source = str(persisted.get("source") or "memory")
            self._persistence_updated_at = str(persisted.get("updated_at") or "")

    def _persist_if_needed_locked(self, now: float, *, force: bool = False) -> None:
        if not self._persistence or not self._dirty:
            return
        monotonic_now = time.monotonic()
        if (
            not force
            and self._persist_interval_seconds > 0
            and monotonic_now - self._last_persisted_monotonic < self._persist_interval_seconds
        ):
            return
        try:
            persisted = self._persistence.save_observability_rollup_sync(
                self._build_rollup_payload_locked()
            )
        except Exception:
            return
        self._dirty = False
        self._restored_from_persistence = True
        self._last_persisted_monotonic = monotonic_now
        self._persistence_source = str((persisted or {}).get("source") or "memory")
        self._persistence_updated_at = str((persisted or {}).get("updated_at") or "")

    def _mark_dirty_locked(self, now: float) -> None:
        self._dirty = True
        self._persist_if_needed_locked(now, force=False)

    def update_clips_auth_status(
        self, *, token_valid: bool, scope_ok: bool, timestamp: float | None = None
    ) -> None:
        with self._lock:
            self._clips_status["token_valid"] = bool(token_valid)
            self._clips_status["scope_ok"] = bool(scope_ok)
            self._mark_dirty_locked(resolve_now(timestamp))

    def record_chat_message(
        self, *, author_name: str, source: str, text: str = "", timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_chat_message_locked(
                self,
                now=now,
                author_name=author_name,
                source=source,
                text=text,
            )
            self._mark_dirty_locked(now)

    def record_byte_trigger(
        self, *, prompt: str, source: str, author_name: str = "", timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_byte_trigger_locked(
                self,
                now=now,
                prompt=prompt,
                source=source,
                author_name=author_name,
            )
            self._mark_dirty_locked(now)

    def record_reply(self, *, text: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_reply_locked(self, now=now, text=text)
            self._mark_dirty_locked(now)

    def record_quality_gate(
        self, *, outcome: str, reason: str, timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_quality_gate_locked(self, now=now, outcome=outcome, reason=reason)
            self._mark_dirty_locked(now)

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
        now = resolve_now(timestamp)
        with self._lock:
            record_byte_interaction_locked(
                self,
                now=now,
                route=route,
                author_name=author_name,
                prompt_chars=prompt_chars,
                reply_parts=reply_parts,
                reply_chars=reply_chars,
                serious=serious,
                follow_up=follow_up,
                current_events=current_events,
                latency_ms=latency_ms,
            )
            self._mark_dirty_locked(now)

    def record_token_usage(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_token_usage_locked(
                self,
                now=now,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost_usd,
            )
            self._mark_dirty_locked(now)

    def record_autonomy_goal(
        self,
        *,
        risk: str,
        outcome: str,
        details: str = "",
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_autonomy_goal_locked(
                self,
                now=now,
                risk=risk,
                outcome=outcome,
                details=details,
            )
            self._mark_dirty_locked(now)

    def record_auto_scene_update(
        self, *, update_types: list[str], timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_auto_scene_update_locked(self, now=now, update_types=update_types)
            self._mark_dirty_locked(now)

    def record_token_refresh(self, *, reason: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_token_refresh_locked(self, now=now, reason=reason)
            self._mark_dirty_locked(now)

    def record_auth_failure(self, *, details: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_auth_failure_locked(self, now=now, details=details)
            self._mark_dirty_locked(now)

    def record_error(self, *, category: str, details: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_error_locked(self, now=now, category=category, details=details)
            self._mark_dirty_locked(now)

    def record_vision_frame(self, *, analysis: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_vision_frame_locked(self, now=now, analysis=analysis)
            self._mark_dirty_locked(now)

    def snapshot(
        self,
        *,
        bot_brand: str,
        bot_version: str,
        bot_mode: str,
        stream_context: Any,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = resolve_now(timestamp)
        with self._lock:
            prune_locked(self, now)
            self._persist_if_needed_locked(now, force=True)
            snapshot = build_observability_snapshot(
                now=now,
                started_at=self._started_at,
                counters=dict(self._counters),
                route_counts=dict(self._route_counts),
                latencies_ms=list(self._latencies_ms),
                minute_buckets={key: value.copy() for key, value in self._minute_buckets.items()},
                recent_events=list(self._recent_events),
                chatter_last_seen=dict(self._chatter_last_seen),
                chat_events=list(self._chat_events),
                byte_trigger_events=list(self._byte_trigger_events),
                interaction_events=list(self._interaction_events),
                quality_events=list(self._quality_events),
                token_usage_events=list(self._token_usage_events),
                autonomy_goal_events=list(self._autonomy_goal_events),
                chatter_message_totals=dict(self._chatter_message_totals),
                trigger_user_totals=dict(self._trigger_user_totals),
                unique_chatters_total=len(self._known_chatters),
                last_prompt=self._last_prompt,
                last_reply=self._last_reply,
                estimated_cost_usd_total=float(self._estimated_cost_usd_total),
                clips_status=dict(self._clips_status),
                bot_brand=bot_brand,
                bot_version=bot_version,
                bot_mode=bot_mode,
                stream_context=stream_context,
            )
            snapshot["persistence"] = {
                "enabled": bool(self._persistence),
                "restored": bool(self._restored_from_persistence),
                "source": str(self._persistence_source or "memory"),
                "updated_at": str(self._persistence_updated_at or ""),
                "dirty": bool(self._dirty),
                "persist_interval_seconds": float(self._persist_interval_seconds),
            }
            return snapshot
