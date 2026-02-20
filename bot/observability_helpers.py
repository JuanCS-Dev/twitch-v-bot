from datetime import datetime, timezone

TIMELINE_RETENTION_MINUTES = 180
TIMELINE_WINDOW_MINUTES = 30
EVENT_LOG_MAX_ITEMS = 120
LATENCY_WINDOW_MAX_ITEMS = 300
CHAT_EVENTS_RETENTION_SECONDS = 6 * 3600
BYTE_TRIGGER_EVENTS_RETENTION_SECONDS = 6 * 3600
CHAT_EVENTS_MAX_ITEMS = 30_000
BYTE_TRIGGER_EVENTS_MAX_ITEMS = 12_000
LEADERBOARD_LIMIT = 8


def utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clip_preview(text: str, max_chars: int = 120) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def compute_p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(0.95 * (len(ordered) - 1))
    return round(ordered[index], 1)


def percentage(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 1)
