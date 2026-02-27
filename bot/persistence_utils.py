import time
from typing import Any


def normalize_channel_id(channel_id: str) -> str:
    return str(channel_id or "").strip().lower()


def utc_iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_optional_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    field_name: str,
) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} invalido.") from error
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} fora do intervalo permitido.")
    return round(parsed, 4)


def normalize_optional_text(
    value: Any,
    *,
    field_name: str,
    max_length: int,
) -> str:
    if value in (None, ""):
        return ""
    normalized = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    trimmed_lines = [line.rstrip() for line in normalized.split("\n")]
    cleaned = "\n".join(trimmed_lines).strip()
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} excede o tamanho permitido.")
    return cleaned


def normalize_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in (0, 0.0):
            return False
        if value in (1, 1.0):
            return True
    if value in (None, ""):
        return False
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"{field_name} invalido.")


def coerce_history_limit(limit: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return default
    if parsed < 1:
        return 1
    return min(parsed, maximum)
