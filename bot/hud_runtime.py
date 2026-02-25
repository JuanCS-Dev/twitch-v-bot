import threading
import time
from collections import deque
from typing import Any

MAX_HUD_MESSAGES = 20
HUD_MESSAGE_TTL_SECONDS = 600.0  # 10 minutos


class HudRuntime:
    """Buffer FIFO de mensagens privadas para o streamer (HUD overlay)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: deque[dict[str, Any]] = deque(maxlen=MAX_HUD_MESSAGES)

    def push_message(self, text: str, source: str = "autonomy") -> dict[str, Any]:
        if not text or not text.strip():
            return {"ok": False, "reason": "empty_message"}

        now = time.time()
        entry: dict[str, Any] = {
            "ts": now,
            "text": text.strip()[:300],
            "source": (source or "autonomy").strip().lower(),
        }
        with self._lock:
            self._messages.append(entry)
        return {"ok": True, "entry": entry}

    def get_messages(self, since: float = 0.0) -> list[dict[str, Any]]:
        now = time.time()
        cutoff = max(since, now - HUD_MESSAGE_TTL_SECONDS)
        with self._lock:
            return [m for m in self._messages if float(m.get("ts", 0)) > cutoff]

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._messages),
                "max": MAX_HUD_MESSAGES,
            }


hud_runtime = HudRuntime()

__all__ = ["MAX_HUD_MESSAGES", "HudRuntime", "hud_runtime"]
