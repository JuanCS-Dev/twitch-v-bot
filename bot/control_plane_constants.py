import copy
from datetime import UTC, datetime
from typing import Any

RISK_AUTO_CHAT = "auto_chat"
RISK_SUGGEST_STREAMER = "suggest_streamer"
RISK_MODERATION_ACTION = "moderation_action"
RISK_CLIP_CANDIDATE = "clip_candidate"
SUPPORTED_RISK_LEVELS = {
    RISK_AUTO_CHAT,
    RISK_SUGGEST_STREAMER,
    RISK_MODERATION_ACTION,
    RISK_CLIP_CANDIDATE,
}
SUPPORTED_DECISIONS = {"approve", "reject"}

DEFAULT_GOALS = [
    {
        "id": "chat_pulse",
        "name": "Pulso do chat",
        "prompt": "Resumo autonomo curto com o momento atual da live e um insight util.",
        "risk": RISK_AUTO_CHAT,
        "interval_seconds": 900,
        "enabled": True,
    },
    {
        "id": "streamer_hint",
        "name": "Sugestao ao streamer",
        "prompt": "Sugestao objetiva para aumentar clareza, ritmo ou engajamento da live.",
        "risk": RISK_SUGGEST_STREAMER,
        "interval_seconds": 600,
        "enabled": True,
    },
    {
        "id": "safety_watch",
        "name": "Watch de moderacao",
        "prompt": "Sinalize padroes de risco no chat e recomende acao moderativa conservadora.",
        "risk": RISK_MODERATION_ACTION,
        "interval_seconds": 300,
        "enabled": True,
    },
    {
        "id": "detect_clip",
        "name": "Deteccao de clips",
        "prompt": "Analise o contexto recente (chat e eventos) e identifique um momento digno de clipe.",
        "risk": RISK_CLIP_CANDIDATE,
        "interval_seconds": 600,
        "enabled": False,
    },
]


def utc_iso(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def clip_text(text: str, max_chars: int = 360) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def to_int(value: Any, *, minimum: int, maximum: int, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def default_goals_copy() -> list[dict[str, Any]]:
    return copy.deepcopy(DEFAULT_GOALS)
