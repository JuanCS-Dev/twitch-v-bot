import threading
import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bot.observability_helpers import (
    BYTE_TRIGGER_EVENTS_MAX_ITEMS,
    CHAT_EVENTS_MAX_ITEMS,
    EVENT_LOG_MAX_ITEMS,
    LATENCY_WINDOW_MAX_ITEMS,
    utc_iso,
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


def _normalize_channel_id(channel_id: str | None) -> str:
    normalized = str(channel_id or "").strip().lower()
    return normalized or "default"


@dataclass
class _ObservabilityScope:
    _counters: Counter[str] = field(default_factory=Counter)
    _route_counts: Counter[str] = field(default_factory=Counter)
    _minute_buckets: dict[int, dict[str, int]] = field(default_factory=dict)
    _latencies_ms: deque[float] = field(
        default_factory=lambda: deque(maxlen=LATENCY_WINDOW_MAX_ITEMS)
    )
    _recent_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=EVENT_LOG_MAX_ITEMS)
    )
    _chatter_last_seen: dict[str, float] = field(default_factory=dict)
    _known_chatters: set[str] = field(default_factory=set)
    _chat_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=CHAT_EVENTS_MAX_ITEMS)
    )
    _byte_trigger_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
    )
    _interaction_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
    )
    _quality_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
    )
    _token_usage_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
    )
    _autonomy_goal_events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS)
    )
    _chatter_message_totals: Counter[str] = field(default_factory=Counter)
    _trigger_user_totals: Counter[str] = field(default_factory=Counter)
    _last_prompt: str = ""
    _last_reply: str = ""
    _estimated_cost_usd_total: float = 0.0


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
        self._channel_scopes: dict[str, _ObservabilityScope] = {}
        self._restore_from_persistence()

    def _serialize_scope_locked(self, scope: Any) -> dict[str, Any]:
        return {
            "counters": {key: int(value) for key, value in scope._counters.items()},
            "route_counts": {key: int(value) for key, value in scope._route_counts.items()},
            "minute_buckets": {
                str(key): {name: int(amount) for name, amount in bucket.items()}
                for key, bucket in scope._minute_buckets.items()
            },
            "latencies_ms": [float(value) for value in scope._latencies_ms],
            "recent_events": list(scope._recent_events),
            "chatter_last_seen": {
                str(key): float(value) for key, value in scope._chatter_last_seen.items()
            },
            "known_chatters": sorted(scope._known_chatters),
            "chat_events": list(scope._chat_events),
            "byte_trigger_events": list(scope._byte_trigger_events),
            "interaction_events": list(scope._interaction_events),
            "quality_events": list(scope._quality_events),
            "token_usage_events": list(scope._token_usage_events),
            "autonomy_goal_events": list(scope._autonomy_goal_events),
            "chatter_message_totals": {
                key: int(value) for key, value in scope._chatter_message_totals.items()
            },
            "trigger_user_totals": {
                key: int(value) for key, value in scope._trigger_user_totals.items()
            },
            "last_prompt": str(scope._last_prompt or ""),
            "last_reply": str(scope._last_reply or ""),
            "estimated_cost_usd_total": float(scope._estimated_cost_usd_total or 0.0),
        }

    def _restore_scope_locked(self, scope: Any, raw_state: dict[str, Any]) -> None:
        scope._counters = Counter(
            {str(key): int(value) for key, value in dict(raw_state.get("counters") or {}).items()}
        )
        scope._route_counts = Counter(
            {
                str(key): int(value)
                for key, value in dict(raw_state.get("route_counts") or {}).items()
            }
        )
        scope._minute_buckets = {
            int(key): {
                str(bucket_key): int(bucket_value)
                for bucket_key, bucket_value in dict(bucket or {}).items()
            }
            for key, bucket in dict(raw_state.get("minute_buckets") or {}).items()
            if str(key).lstrip("-").isdigit()
        }
        scope._latencies_ms = deque(
            [float(value) for value in list(raw_state.get("latencies_ms") or [])],
            maxlen=LATENCY_WINDOW_MAX_ITEMS,
        )
        scope._recent_events = deque(
            list(raw_state.get("recent_events") or []),
            maxlen=EVENT_LOG_MAX_ITEMS,
        )
        scope._chatter_last_seen = {
            str(key): float(value)
            for key, value in dict(raw_state.get("chatter_last_seen") or {}).items()
        }
        scope._known_chatters = {
            str(value).strip().lower()
            for value in list(raw_state.get("known_chatters") or [])
            if str(value).strip()
        }
        scope._chat_events = deque(
            list(raw_state.get("chat_events") or []),
            maxlen=CHAT_EVENTS_MAX_ITEMS,
        )
        scope._byte_trigger_events = deque(
            list(raw_state.get("byte_trigger_events") or []),
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
        )
        scope._interaction_events = deque(
            list(raw_state.get("interaction_events") or []),
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
        )
        scope._quality_events = deque(
            list(raw_state.get("quality_events") or []),
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
        )
        scope._token_usage_events = deque(
            list(raw_state.get("token_usage_events") or []),
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
        )
        scope._autonomy_goal_events = deque(
            list(raw_state.get("autonomy_goal_events") or []),
            maxlen=BYTE_TRIGGER_EVENTS_MAX_ITEMS,
        )
        scope._chatter_message_totals = Counter(
            {
                str(key): int(value)
                for key, value in dict(raw_state.get("chatter_message_totals") or {}).items()
            }
        )
        scope._trigger_user_totals = Counter(
            {
                str(key): int(value)
                for key, value in dict(raw_state.get("trigger_user_totals") or {}).items()
            }
        )
        scope._last_prompt = str(raw_state.get("last_prompt") or "")
        scope._last_reply = str(raw_state.get("last_reply") or "")
        scope._estimated_cost_usd_total = float(raw_state.get("estimated_cost_usd_total") or 0.0)

    def _build_rollup_payload_locked(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            **self._serialize_scope_locked(self),
            "clips_status": {
                "token_valid": bool(self._clips_status.get("token_valid", False)),
                "scope_ok": bool(self._clips_status.get("scope_ok", False)),
            },
            "channel_scopes": {
                channel_id: self._serialize_scope_locked(scope)
                for channel_id, scope in self._channel_scopes.items()
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
            self._restore_scope_locked(self, state)
            restored_clips_status = dict(state.get("clips_status") or {})
            self._clips_status = {
                "token_valid": bool(restored_clips_status.get("token_valid", False)),
                "scope_ok": bool(restored_clips_status.get("scope_ok", False)),
            }
            self._channel_scopes = {}
            raw_scopes = dict(state.get("channel_scopes") or {})
            for raw_channel_id, raw_scope_state in raw_scopes.items():
                if not isinstance(raw_scope_state, dict):
                    continue
                channel_id = _normalize_channel_id(str(raw_channel_id))
                scope = _ObservabilityScope()
                self._restore_scope_locked(scope, dict(raw_scope_state))
                self._channel_scopes[channel_id] = scope
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
        history_writer = getattr(self._persistence, "save_observability_channel_history_sync", None)
        if callable(history_writer):
            for channel_id, scope in self._channel_scopes.items():
                if not self._scope_has_activity_locked(scope):
                    continue
                try:
                    history_writer(
                        channel_id,
                        self._build_channel_history_payload_locked(
                            channel_id=channel_id,
                            scope=scope,
                            now=now,
                        ),
                    )
                except Exception:
                    continue
        self._dirty = False
        self._restored_from_persistence = True
        self._last_persisted_monotonic = monotonic_now
        self._persistence_source = str((persisted or {}).get("source") or "memory")
        self._persistence_updated_at = str((persisted or {}).get("updated_at") or "")

    def _mark_dirty_locked(self, now: float) -> None:
        self._dirty = True
        self._persist_if_needed_locked(now, force=False)

    def _get_or_create_channel_scope_locked(self, channel_id: str | None) -> _ObservabilityScope:
        safe_channel_id = _normalize_channel_id(channel_id)
        scope = self._channel_scopes.get(safe_channel_id)
        if scope is None:
            scope = _ObservabilityScope()
            self._channel_scopes[safe_channel_id] = scope
        return scope

    @staticmethod
    def _scope_has_activity_locked(scope: _ObservabilityScope) -> bool:
        return bool(
            scope._counters
            or scope._chat_events
            or scope._byte_trigger_events
            or scope._interaction_events
            or scope._quality_events
            or scope._recent_events
        )

    @staticmethod
    def _count_recent_events_locked(events: deque[dict[str, Any]], *, cutoff: float) -> int:
        return sum(1 for event in events if float(event.get("ts", 0.0)) >= cutoff)

    def _build_channel_history_payload_locked(
        self,
        *,
        channel_id: str,
        scope: _ObservabilityScope,
        now: float,
    ) -> dict[str, Any]:
        cutoff_60m = now - 3600
        messages_60m = self._count_recent_events_locked(scope._chat_events, cutoff=cutoff_60m)
        triggers_60m = self._count_recent_events_locked(
            scope._byte_trigger_events,
            cutoff=cutoff_60m,
        )
        interactions_60m = self._count_recent_events_locked(
            scope._interaction_events,
            cutoff=cutoff_60m,
        )
        ignored_60m = sum(
            1
            for event in scope._quality_events
            if float(event.get("ts", 0.0)) >= cutoff_60m
            and str(event.get("outcome") or "").strip().lower() == "ignored"
        )
        useful_60m = max(0, interactions_60m - ignored_60m)
        useful_rate = (useful_60m / interactions_60m) * 100 if interactions_60m else 0.0
        ignored_rate = (ignored_60m / interactions_60m) * 100 if interactions_60m else 0.0

        active_60m = sum(
            1 for seen in scope._chatter_last_seen.values() if now - float(seen) <= 3600
        )

        return {
            "channel_id": _normalize_channel_id(channel_id),
            "captured_at": utc_iso(now),
            "metrics": {
                "chat_messages_total": int(scope._counters.get("chat_messages_total", 0)),
                "byte_triggers_total": int(scope._counters.get("byte_triggers_total", 0)),
                "replies_total": int(scope._counters.get("replies_total", 0)),
                "llm_interactions_total": int(scope._counters.get("llm_interactions_total", 0)),
                "errors_total": int(scope._counters.get("errors_total", 0)),
            },
            "chatters": {
                "unique_total": int(len(scope._known_chatters)),
                "active_60m": int(active_60m),
            },
            "chat_analytics": {
                "messages_60m": int(messages_60m),
                "byte_triggers_60m": int(triggers_60m),
                "messages_per_minute_60m": round(messages_60m / 60.0, 2),
            },
            "agent_outcomes": {
                "useful_engagement_rate_60m": round(useful_rate, 1),
                "ignored_rate_60m": round(ignored_rate, 1),
            },
            "context": {
                "last_prompt": str(scope._last_prompt or "")[:120],
                "last_reply": str(scope._last_reply or "")[:140],
            },
        }

    def _record_scoped_locked(
        self,
        *,
        channel_id: str | None,
        recorder: Callable[..., None],
        now: float,
        **kwargs: Any,
    ) -> None:
        recorder(self, now=now, **kwargs)
        recorder(self._get_or_create_channel_scope_locked(channel_id), now=now, **kwargs)

    def update_clips_auth_status(
        self, *, token_valid: bool, scope_ok: bool, timestamp: float | None = None
    ) -> None:
        with self._lock:
            self._clips_status["token_valid"] = bool(token_valid)
            self._clips_status["scope_ok"] = bool(scope_ok)
            self._mark_dirty_locked(resolve_now(timestamp))

    def record_chat_message(
        self,
        *,
        author_name: str,
        source: str,
        text: str = "",
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_chat_message_locked,
                now=now,
                author_name=author_name,
                source=source,
                text=text,
            )
            self._mark_dirty_locked(now)

    def record_byte_trigger(
        self,
        *,
        prompt: str,
        source: str,
        author_name: str = "",
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_byte_trigger_locked,
                now=now,
                prompt=prompt,
                source=source,
                author_name=author_name,
            )
            self._mark_dirty_locked(now)

    def record_reply(
        self, *, text: str, channel_id: str | None = None, timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_reply_locked,
                now=now,
                text=text,
            )
            self._mark_dirty_locked(now)

    def record_quality_gate(
        self,
        *,
        outcome: str,
        reason: str,
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_quality_gate_locked,
                now=now,
                outcome=outcome,
                reason=reason,
            )
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
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_byte_interaction_locked,
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
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_token_usage_locked,
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
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_autonomy_goal_locked,
                now=now,
                risk=risk,
                outcome=outcome,
                details=details,
            )
            self._mark_dirty_locked(now)

    def record_auto_scene_update(
        self,
        *,
        update_types: list[str],
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_auto_scene_update_locked,
                now=now,
                update_types=update_types,
            )
            self._mark_dirty_locked(now)

    def record_token_refresh(
        self, *, reason: str, channel_id: str | None = None, timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_token_refresh_locked,
                now=now,
                reason=reason,
            )
            self._mark_dirty_locked(now)

    def record_auth_failure(
        self, *, details: str, channel_id: str | None = None, timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_auth_failure_locked,
                now=now,
                details=details,
            )
            self._mark_dirty_locked(now)

    def record_error(
        self,
        *,
        category: str,
        details: str,
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_error_locked,
                now=now,
                category=category,
                details=details,
            )
            self._mark_dirty_locked(now)

    def record_vision_frame(
        self, *, analysis: str, channel_id: str | None = None, timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            self._record_scoped_locked(
                channel_id=channel_id,
                recorder=record_vision_frame_locked,
                now=now,
                analysis=analysis,
            )
            self._mark_dirty_locked(now)

    def snapshot(
        self,
        *,
        bot_brand: str,
        bot_version: str,
        bot_mode: str,
        stream_context: Any,
        channel_id: str | None = None,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = resolve_now(timestamp)
        with self._lock:
            prune_locked(self, now)
            for scope in self._channel_scopes.values():
                prune_locked(scope, now)
            self._persist_if_needed_locked(now, force=True)
            scope: Any = self
            if channel_id is not None:
                scope = (
                    self._channel_scopes.get(_normalize_channel_id(channel_id))
                    or _ObservabilityScope()
                )
            snapshot = build_observability_snapshot(
                now=now,
                started_at=self._started_at,
                counters=dict(scope._counters),
                route_counts=dict(scope._route_counts),
                latencies_ms=list(scope._latencies_ms),
                minute_buckets={key: value.copy() for key, value in scope._minute_buckets.items()},
                recent_events=list(scope._recent_events),
                chatter_last_seen=dict(scope._chatter_last_seen),
                chat_events=list(scope._chat_events),
                byte_trigger_events=list(scope._byte_trigger_events),
                interaction_events=list(scope._interaction_events),
                quality_events=list(scope._quality_events),
                token_usage_events=list(scope._token_usage_events),
                autonomy_goal_events=list(scope._autonomy_goal_events),
                chatter_message_totals=dict(scope._chatter_message_totals),
                trigger_user_totals=dict(scope._trigger_user_totals),
                unique_chatters_total=len(scope._known_chatters),
                last_prompt=scope._last_prompt,
                last_reply=scope._last_reply,
                estimated_cost_usd_total=float(scope._estimated_cost_usd_total),
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
