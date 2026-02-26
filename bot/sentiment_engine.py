import threading
import time
from collections import deque
from typing import Any

from bot.sentiment_constants import (
    ANTI_BOREDOM_THRESHOLD,
    ANTI_BOREDOM_WINDOW_SECONDS,
    ANTI_CONFUSION_THRESHOLD,
    EMOTE_SCORES,
    KEYWORD_SCORES,
    SENTIMENT_MAX_EVENTS,
    SENTIMENT_WINDOW_SECONDS,
    VIBE_DEFAULT,
    VIBE_THRESHOLDS,
)


def _score_message(text: str) -> float:
    if not text:
        return 0.0
    score = 0.0
    tokens = text.split()
    for token in tokens:
        # Tratamento especial para o emote de confusão "???" para não ser limpo pelo strip
        if token == "???":
            clean = "???"
        else:
            clean = token.strip(".,!?;:()")

        if clean in EMOTE_SCORES:
            score += EMOTE_SCORES[clean]

    lower = text.lower()
    for keyword, kw_score in KEYWORD_SCORES.items():
        if keyword in lower:
            score += kw_score
    return score


class SentimentEngine:
    """Engine NLP leve para analise de sentimento do chat isolada por canal."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channel_events: dict[str, deque[tuple[float, float]]] = {}
        self._last_activity: dict[str, float] = {}

    def _get_or_create_events(self, channel_id: str) -> deque[tuple[float, float]]:
        key = channel_id.strip().lower()
        self._last_activity[key] = time.time()
        if key not in self._channel_events:
            self._channel_events[key] = deque(maxlen=SENTIMENT_MAX_EVENTS)
        return self._channel_events[key]

    def ingest_message(self, channel_id: str, text: str) -> float:
        score = _score_message(text)
        now = time.time()
        with self._lock:
            events = self._get_or_create_events(channel_id)
            events.append((now, score))
        return score

    def get_scores(
        self, channel_id: str, window_seconds: float = SENTIMENT_WINDOW_SECONDS
    ) -> dict[str, Any]:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            events = self._get_or_create_events(channel_id)
            recent = [(ts, s) for ts, s in events if ts >= cutoff]

        if not recent:
            return {"avg": 0.0, "total": 0.0, "count": 0, "positive": 0, "negative": 0}
        total = sum(s for _, s in recent)
        avg = total / len(recent)
        positive = sum(1 for _, s in recent if s > 0)
        negative = sum(1 for _, s in recent if s < 0)
        return {
            "avg": round(avg, 3),
            "total": round(total, 2),
            "count": len(recent),
            "positive": positive,
            "negative": negative,
        }

    def get_vibe(self, channel_id: str) -> str:
        """Calcula a vibe usando lógica de proximidade e direção (Cura Sistêmica)."""
        scores = self.get_scores(channel_id)
        avg = float(scores.get("avg", 0.0))
        count = int(scores.get("count", 0))

        if count == 0:
            return "Chill"

        # A CURA: Ordenamos os thresholds para garantir que o 'mais extremo'
        # (seja positivo ou negativo) capture o valor primeiro.
        # Ex: Se avg é -5.0, ele deve bater em -1.0 (Confuso) antes de cair em -0.3 (Chill)

        # Separamos em positivos e negativos
        positives = sorted(
            [t for t in VIBE_THRESHOLDS if t[0] >= 0], key=lambda x: x[0], reverse=True
        )
        negatives = sorted(
            [t for t in VIBE_THRESHOLDS if t[0] < 0], key=lambda x: x[0], reverse=False
        )

        if avg >= 0:
            for threshold, label in positives:
                if avg >= threshold:
                    return label
        else:
            for threshold, label in negatives:
                if avg <= threshold:  # Se é mais negativo que o limite (ex: -2.0 <= -1.0)
                    return label

        return VIBE_DEFAULT

    def cleanup_inactive(self, max_age_seconds: float = 7200) -> int:
        """Remove dados de canais inativos (Cura de Memória)."""
        now = time.time()
        with self._lock:
            to_remove = [
                ch for ch, last_ts in self._last_activity.items() if now - last_ts > max_age_seconds
            ]
            for ch in to_remove:
                self._channel_events.pop(ch, None)
                self._last_activity.pop(ch, None)
            return len(to_remove)

    def should_trigger_anti_boredom(self, channel_id: str) -> bool:
        scores_5m = self.get_scores(channel_id, window_seconds=ANTI_BOREDOM_WINDOW_SECONDS)
        count = scores_5m["count"]
        if count < 5:
            return False
        positive_ratio = scores_5m["positive"] / count if count else 0
        return positive_ratio < ANTI_BOREDOM_THRESHOLD

    def should_trigger_anti_confusion(self, channel_id: str) -> bool:
        scores = self.get_scores(channel_id)
        count = scores["count"]
        if count < 3:
            return False
        negative_ratio = scores["negative"] / count if count else 0
        return negative_ratio > ANTI_CONFUSION_THRESHOLD


sentiment_engine = SentimentEngine()

__all__ = ["SentimentEngine", "sentiment_engine"]
