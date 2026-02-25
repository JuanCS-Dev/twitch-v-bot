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

    def update_clips_auth_status(
        self, *, token_valid: bool, scope_ok: bool, timestamp: float | None = None
    ) -> None:
        with self._lock:
            self._clips_status["token_valid"] = bool(token_valid)
            self._clips_status["scope_ok"] = bool(scope_ok)
            # We could record an event here if needed, but the requirement is just status.

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

    def record_reply(self, *, text: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_reply_locked(self, now=now, text=text)

    def record_quality_gate(
        self, *, outcome: str, reason: str, timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_quality_gate_locked(self, now=now, outcome=outcome, reason=reason)

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

    def record_auto_scene_update(
        self, *, update_types: list[str], timestamp: float | None = None
    ) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_auto_scene_update_locked(self, now=now, update_types=update_types)

    def record_token_refresh(self, *, reason: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_token_refresh_locked(self, now=now, reason=reason)

    def record_auth_failure(self, *, details: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_auth_failure_locked(self, now=now, details=details)

    def record_error(self, *, category: str, details: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_error_locked(self, now=now, category=category, details=details)

    def record_vision_frame(self, *, analysis: str, timestamp: float | None = None) -> None:
        now = resolve_now(timestamp)
        with self._lock:
            record_vision_frame_locked(self, now=now, analysis=analysis)

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
            return build_observability_snapshot(
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
