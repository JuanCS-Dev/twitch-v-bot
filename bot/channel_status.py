import re

TWITCH_CHANNEL_LOGIN_PATTERN = re.compile(r"^[a-z0-9_]{3,25}$")


def normalize_channel_login(
    channel_login: str, *, pattern: re.Pattern[str] = TWITCH_CHANNEL_LOGIN_PATTERN
) -> str:
    normalized = (channel_login or "").strip().lstrip("#").lower()
    if not normalized:
        return ""
    if not pattern.fullmatch(normalized):
        return ""
    return normalized


def parse_channel_logins(
    raw_value: str, *, pattern: re.Pattern[str] = TWITCH_CHANNEL_LOGIN_PATTERN
) -> list[str]:
    unique_logins: list[str] = []
    seen: set[str] = set()
    for token in re.split(r"[,\s]+", raw_value or ""):
        normalized = normalize_channel_login(token, pattern=pattern)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_logins.append(normalized)
    return unique_logins


def format_status_channels(
    channel_logins: list[str] | None = None,
    *,
    fallback_channels: list[str] | None = None,
    fallback_mode: str = "eventsub",
    max_items: int = 3,
    pattern: re.Pattern[str] = TWITCH_CHANNEL_LOGIN_PATTERN,
) -> str:
    resolved = [normalize_channel_login(login, pattern=pattern) for login in (channel_logins or [])]
    resolved = [login for login in resolved if login]
    if not resolved:
        resolved = [
            normalize_channel_login(login, pattern=pattern) for login in (fallback_channels or [])
        ]
        resolved = [login for login in resolved if login]
    if not resolved:
        return "eventsub" if fallback_mode == "eventsub" else "n/a"

    visible = resolved[: max(1, max_items)]
    if len(resolved) <= len(visible):
        return ", ".join(visible)
    return f"{', '.join(visible)} +{len(resolved) - len(visible)}"


def compose_status_line(
    *,
    bot_brand: str,
    bot_version: str,
    uptime_minutes: int,
    channels_label: str,
    chat_messages_10m: int,
    active_chatters_10m: int,
    triggers_10m: int,
    p95_latency_ms: float,
) -> str:
    return (
        f"{bot_brand} v{bot_version} | Uptime: {uptime_minutes}min | Canais: {channels_label} | "
        f"Chat 10m: {chat_messages_10m} msgs/{active_chatters_10m} ativos | Triggers 10m: {triggers_10m} | "
        f"P95: {p95_latency_ms:.1f}ms | Privacidade: metricas agregadas"
    )
