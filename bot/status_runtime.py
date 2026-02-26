from bot.channel_status import (
    TWITCH_CHANNEL_LOGIN_PATTERN,
    compose_status_line,
)
from bot.channel_status import (
    format_status_channels as format_status_channels_impl,
)
from bot.channel_status import (
    normalize_channel_login as normalize_channel_login_impl,
)
from bot.channel_status import (
    parse_channel_logins as parse_channel_logins_impl,
)
from bot.logic import BOT_BRAND, context_manager
from bot.observability import observability
from bot.runtime_config import (
    BYTE_VERSION,
    TWITCH_CHANNEL_LOGIN,
    TWITCH_CHANNEL_LOGINS_RAW,
    TWITCH_CHAT_MODE,
)


def normalize_channel_login(channel_login: str) -> str:
    return normalize_channel_login_impl(channel_login, pattern=TWITCH_CHANNEL_LOGIN_PATTERN)


def parse_channel_logins(raw_value: str) -> list[str]:
    return parse_channel_logins_impl(raw_value, pattern=TWITCH_CHANNEL_LOGIN_PATTERN)


def format_status_channels(channel_logins: list[str] | None = None, max_items: int = 3) -> str:
    fallback = parse_channel_logins(TWITCH_CHANNEL_LOGINS_RAW) or parse_channel_logins(
        TWITCH_CHANNEL_LOGIN
    )
    return format_status_channels_impl(
        channel_logins,
        fallback_channels=fallback,
        fallback_mode=TWITCH_CHAT_MODE,
        max_items=max_items,
        pattern=TWITCH_CHANNEL_LOGIN_PATTERN,
    )


async def build_status_line(channel_logins: list[str] | None = None) -> str:
    ctx = context_manager.get()
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=ctx,
    )
    metrics = snapshot.get("metrics", {})
    chatters = snapshot.get("chatters", {})
    chat_analytics = snapshot.get("chat_analytics", {})
    uptime = int(snapshot.get("bot", {}).get("uptime_minutes", ctx.get_uptime_minutes()))
    chat_10m = int(chat_analytics.get("messages_10m", 0))
    active_10m = int(chatters.get("active_10m", 0))
    triggers_10m = int(chat_analytics.get("byte_triggers_10m", 0))
    p95_latency_ms = float(metrics.get("p95_latency_ms", 0.0))
    channels_label = format_status_channels(channel_logins=channel_logins)
    return compose_status_line(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        uptime_minutes=uptime,
        channels_label=channels_label,
        chat_messages_10m=chat_10m,
        active_chatters_10m=active_10m,
        triggers_10m=triggers_10m,
        p95_latency_ms=p95_latency_ms,
    )
