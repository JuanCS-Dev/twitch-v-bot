import copy
import threading
import time
from collections import Counter, deque
from typing import Any

from bot.control_plane_constants import (
    RISK_SUGGEST_STREAMER,
    SUPPORTED_DECISIONS,
    SUPPORTED_RISK_LEVELS,
    clip_text,
    utc_iso,
)


class ControlPlaneActionQueue:
    def __init__(self, *, max_items: int = 600) -> None:
        self._lock = threading.Lock()
        self._max_items = max(10, int(max_items))
        self._action_items: dict[str, dict[str, Any]] = {}
        self._action_order: deque[str] = deque(maxlen=self._max_items)
        self._action_counter = 0

    def _expire_pending_actions_locked(
        self, now: float, ignore_after_seconds: int
    ) -> list[dict[str, Any]]:
        expired: list[dict[str, Any]] = []
        for action_id in list(self._action_order):
            item = self._action_items.get(action_id)
            if not item or item.get("status") != "pending":
                continue
            created_epoch = float(item.get("created_epoch", now))
            if now - created_epoch < ignore_after_seconds:
                continue
            item["status"] = "ignored"
            item["decision"] = "auto_ignore"
            item["decision_note"] = "Sem decisao dentro da janela configurada."
            item["updated_epoch"] = now
            item["updated_at"] = utc_iso(now)
            item["audit"].append(
                {
                    "ts": item["updated_at"],
                    "event": "ignored_timeout",
                    "by": "system",
                    "note": item["decision_note"],
                }
            )
            expired.append(copy.deepcopy(item))
        return expired

    def _summary_locked(self) -> dict[str, int]:
        summary_counter: Counter[str] = Counter(
            str(self._action_items[action_id].get("status", "pending"))
            for action_id in self._action_order
            if action_id in self._action_items
        )
        return {
            "pending": int(summary_counter.get("pending", 0)),
            "approved": int(summary_counter.get("approved", 0)),
            "rejected": int(summary_counter.get("rejected", 0)),
            "ignored": int(summary_counter.get("ignored", 0)),
            "total": int(sum(summary_counter.values())),
        }

    def enqueue_action(
        self,
        *,
        kind: str,
        risk: str,
        title: str,
        body: str,
        payload: dict[str, Any] | None = None,
        created_by: str = "autonomy",
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_risk = (risk or RISK_SUGGEST_STREAMER).strip().lower()
        if safe_risk not in SUPPORTED_RISK_LEVELS:
            safe_risk = RISK_SUGGEST_STREAMER

        with self._lock:
            self._action_counter += 1
            action_id = f"act_{int(now * 1000)}_{self._action_counter}"
            created_at = utc_iso(now)
            item = {
                "id": action_id,
                "kind": clip_text(kind or "goal", max_chars=60),
                "risk": safe_risk,
                "title": clip_text(title or "Acao sem titulo", max_chars=80),
                "body": clip_text(body or "", max_chars=420),
                "payload": payload or {},
                "status": "pending",
                "decision": "",
                "decision_note": "",
                "created_at": created_at,
                "updated_at": created_at,
                "created_epoch": now,
                "updated_epoch": now,
                "audit": [
                    {
                        "ts": created_at,
                        "event": "created",
                        "by": clip_text(created_by or "autonomy", max_chars=40),
                        "note": "",
                    }
                ],
            }

            max_queue_size = self._action_order.maxlen
            if max_queue_size is not None and len(self._action_order) >= max_queue_size:
                oldest_id = self._action_order.popleft()
                self._action_items.pop(oldest_id, None)

            self._action_order.append(action_id)
            self._action_items[action_id] = item
            return copy.deepcopy(item)

    def decide_action(
        self,
        *,
        action_id: str,
        decision: str,
        note: str = "",
        decided_by: str = "dashboard",
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        safe_action_id = (action_id or "").strip()
        if not safe_action_id:
            raise ValueError("action_id obrigatorio.")

        safe_decision = (decision or "").strip().lower()
        if safe_decision not in SUPPORTED_DECISIONS:
            raise ValueError("Decision invalida. Use: approve ou reject.")

        now = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            item = self._action_items.get(safe_action_id)
            if not item:
                raise KeyError("action_not_found")
            if item.get("status") != "pending":
                raise RuntimeError("action_not_pending")

            item["decision"] = safe_decision
            item["decision_note"] = clip_text(note or "", max_chars=240)
            item["status"] = "approved" if safe_decision == "approve" else "rejected"
            item["updated_epoch"] = now
            item["updated_at"] = utc_iso(now)
            item["audit"].append(
                {
                    "ts": item["updated_at"],
                    "event": item["status"],
                    "by": clip_text(decided_by or "dashboard", max_chars=40),
                    "note": item["decision_note"],
                }
            )
            return copy.deepcopy(item)

    def list_actions(
        self,
        *,
        status: str | None = None,
        limit: int = 80,
        ignore_after_seconds: int = 900,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        safe_limit = max(1, min(300, int(limit)))
        safe_status = (status or "").strip().lower()
        ttl_seconds = max(60, int(ignore_after_seconds))

        with self._lock:
            expired = self._expire_pending_actions_locked(now, ttl_seconds)
            items: list[dict[str, Any]] = []
            for action_id in reversed(self._action_order):
                item = self._action_items.get(action_id)
                if not item:
                    continue
                if safe_status and item.get("status") != safe_status:
                    continue
                items.append(copy.deepcopy(item))
                if len(items) >= safe_limit:
                    break

            return {
                "items": items,
                "summary": self._summary_locked(),
                "expired": expired,
            }

    def runtime_snapshot(
        self,
        *,
        ignore_after_seconds: int = 900,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if timestamp is None else float(timestamp)
        ttl_seconds = max(60, int(ignore_after_seconds))
        window_cutoff = now - 3600

        with self._lock:
            self._expire_pending_actions_locked(now, ttl_seconds)
            summary = self._summary_locked()

            decisions_window_counter: Counter[str] = Counter()
            pending_created_60m = 0
            for action_id in self._action_order:
                item = self._action_items.get(action_id)
                if not item:
                    continue
                status = str(item.get("status", "pending"))
                created_epoch = float(item.get("created_epoch", 0.0))
                updated_epoch = float(item.get("updated_epoch", 0.0))
                if status == "pending" and created_epoch >= window_cutoff:
                    pending_created_60m += 1
                if status in {"approved", "rejected", "ignored"} and updated_epoch >= window_cutoff:
                    decisions_window_counter[status] += 1

        decisions_total_60m = int(sum(decisions_window_counter.values()))
        ignored_60m = int(decisions_window_counter.get("ignored", 0))
        ignored_rate_60m = (
            round((ignored_60m / decisions_total_60m) * 100.0, 1)
            if decisions_total_60m > 0
            else 0.0
        )
        return {
            "queue": summary,
            "queue_window_60m": {
                "pending_created": int(pending_created_60m),
                "approved": int(decisions_window_counter.get("approved", 0)),
                "rejected": int(decisions_window_counter.get("rejected", 0)),
                "ignored": ignored_60m,
                "decisions_total": decisions_total_60m,
                "ignored_rate": ignored_rate_60m,
            },
        }
