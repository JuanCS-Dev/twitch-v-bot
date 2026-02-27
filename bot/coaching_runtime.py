from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from bot.coaching_churn_risk import build_coaching_signature, build_viewer_churn_payload
from bot.hud_runtime import hud_runtime
from bot.observability_helpers import utc_iso

_HUD_EMIT_BANDS = {"high", "critical"}


@dataclass
class _CoachingEmissionState:
    last_signature: str = ""
    last_emitted_at: float = 0.0
    suppressed_total: int = 0


class CoachingRuntime:
    def __init__(self, *, cooldown_seconds: float = 120.0) -> None:
        self._lock = threading.Lock()
        self._cooldown_seconds = max(10.0, float(cooldown_seconds))
        self._channel_state: dict[str, _CoachingEmissionState] = {}

    @staticmethod
    def _normalize_channel_id(channel_id: str | None) -> str:
        normalized = str(channel_id or "").strip().lower()
        return normalized or "default"

    @staticmethod
    def _build_hud_message(channel_id: str, payload: dict[str, Any]) -> str:
        risk_band = str(payload.get("risk_band") or "low").strip().lower() or "low"
        risk_score = int(payload.get("risk_score") or 0)
        alert = payload.get("primary_alert") or {}
        title = str(alert.get("title") or "Sinal de churn")
        tactic = str(alert.get("tactic") or "Aplique CTA curto e valide resposta do chat.")
        text = f"[COACHING {risk_band.upper()} {risk_score}/100] #{channel_id}: {title}. Acao: {tactic}"
        return text[:300]

    def reset(self) -> None:
        with self._lock:
            self._channel_state.clear()

    def evaluate_and_emit(
        self,
        snapshot: dict[str, Any] | None,
        *,
        channel_id: str | None = None,
        now: float | None = None,
        emit_hud: bool = True,
    ) -> dict[str, Any]:
        safe_channel_id = self._normalize_channel_id(channel_id)
        current_now = float(now) if isinstance(now, int | float) else time.time()
        payload = build_viewer_churn_payload(snapshot)
        signature = build_coaching_signature(payload)

        emitted = False
        suppressed = False
        should_emit = (
            emit_hud
            and bool(payload.get("has_alerts"))
            and str(payload.get("risk_band") or "").strip().lower() in _HUD_EMIT_BANDS
        )
        message_text = ""

        with self._lock:
            state = self._channel_state.setdefault(safe_channel_id, _CoachingEmissionState())
            if should_emit:
                repeated_signature = state.last_signature == signature
                cooldown_active = (current_now - state.last_emitted_at) < self._cooldown_seconds
                if repeated_signature and cooldown_active:
                    suppressed = True
                    state.suppressed_total += 1
                else:
                    emitted = True
                    state.last_signature = signature
                    state.last_emitted_at = current_now
                    message_text = self._build_hud_message(safe_channel_id, payload)

            hud_payload = {
                "emitted": emitted,
                "suppressed": suppressed,
                "cooldown_seconds": int(self._cooldown_seconds),
                "last_emitted_at": utc_iso(state.last_emitted_at) if state.last_emitted_at else "",
                "suppressed_total": int(state.suppressed_total),
                "signature": state.last_signature,
            }

        if emitted and message_text:
            hud_runtime.push_message(message_text, source="coaching")

        return {
            **payload,
            "channel_id": safe_channel_id,
            "hud": hud_payload,
        }


coaching_runtime = CoachingRuntime()

__all__ = ["CoachingRuntime", "coaching_runtime"]
