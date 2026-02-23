import threading

from bot import byte_semantics
from bot.bootstrap_runtime import (
    build_irc_token_manager,
    get_secret,
    resolve_irc_channel_logins,
    run_eventsub_mode,
    run_irc_mode,
)
from bot.dashboard_server import HealthHandler, run_server
from bot.eventsub_runtime import AgentComponent, ByteBot
from bot.irc_protocol import is_irc_notice_delivery_block
from bot.irc_runtime import IrcByteBot
from bot.logic import context
from bot.observability import observability
from bot.prompt_runtime import (
    build_intro_reply,
    build_quality_rewrite_prompt,
    build_verifiable_prompt,
    extract_movie_title,
    handle_byte_prompt_text,
    is_current_events_prompt,
    is_follow_up_prompt,
    is_intro_prompt,
    is_low_quality_answer,
    is_serious_technical_prompt,
)
from bot.runtime_config import (
    AUTO_SCENE_REQUIRE_METADATA,
    BOT_ID,
    BYTE_DASHBOARD_ADMIN_TOKEN,
    BYTE_HELP_MESSAGE,
    BYTE_INTRO_TEMPLATES,
    BYTE_VERSION,
    CHANNEL_ID,
    CLIENT_ID,
    ENABLE_LIVE_CONTEXT_LEARNING,
    MAX_CHAT_MESSAGE_LENGTH,
    MULTIPART_SEPARATOR,
    OWNER_ID,
    QUALITY_SAFE_FALLBACK,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
    TWITCH_BOT_LOGIN,
    TWITCH_CHANNEL_LOGIN,
    TWITCH_CHANNEL_LOGINS_RAW,
    TWITCH_CHAT_MODE,
    TWITCH_CLIENT_SECRET_INLINE,
    TWITCH_CLIENT_SECRET_NAME,
    TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS,
    TWITCH_IRC_HOST,
    TWITCH_IRC_PORT,
    TWITCH_IRC_TLS,
    TWITCH_REFRESH_TOKEN,
    TWITCH_TOKEN_REFRESH_MARGIN_SECONDS,
    TWITCH_USER_TOKEN,
    irc_channel_control,
    logger,
)
from bot.scene_runtime import auto_update_scene_from_message, resolve_scene_metadata
from bot.status_runtime import build_status_line
from bot.twitch_tokens import TwitchTokenManager, is_irc_auth_failure_line

parse_byte_prompt = byte_semantics.parse_byte_prompt
build_llm_enhanced_prompt = byte_semantics.build_llm_enhanced_prompt
build_direct_answer_instruction = byte_semantics.build_direct_answer_instruction
extract_multi_reply_parts = byte_semantics.extract_multi_reply_parts

__all__ = [
    "main",
    "run_server",
    "run_eventsub_mode",
    "run_irc_mode",
    "get_secret",
    "build_irc_token_manager",
    "resolve_irc_channel_logins",
    "HealthHandler",
    "AgentComponent",
    "ByteBot",
    "IrcByteBot",
    "context",
    "observability",
    "build_intro_reply",
    "build_quality_rewrite_prompt",
    "build_verifiable_prompt",
    "extract_movie_title",
    "handle_byte_prompt_text",
    "is_current_events_prompt",
    "is_follow_up_prompt",
    "is_intro_prompt",
    "is_low_quality_answer",
    "is_serious_technical_prompt",
    "auto_update_scene_from_message",
    "resolve_scene_metadata",
    "build_status_line",
    "TwitchTokenManager",
    "is_irc_auth_failure_line",
    "is_irc_notice_delivery_block",
    "parse_byte_prompt",
    "build_llm_enhanced_prompt",
    "build_direct_answer_instruction",
    "extract_multi_reply_parts",
    "AUTO_SCENE_REQUIRE_METADATA",
    "BOT_ID",
    "BYTE_DASHBOARD_ADMIN_TOKEN",
    "BYTE_HELP_MESSAGE",
    "BYTE_INTRO_TEMPLATES",
    "BYTE_VERSION",
    "CHANNEL_ID",
    "CLIENT_ID",
    "ENABLE_LIVE_CONTEXT_LEARNING",
    "MAX_CHAT_MESSAGE_LENGTH",
    "MULTIPART_SEPARATOR",
    "OWNER_ID",
    "QUALITY_SAFE_FALLBACK",
    "SERIOUS_REPLY_MAX_LENGTH",
    "SERIOUS_REPLY_MAX_LINES",
    "TWITCH_BOT_LOGIN",
    "TWITCH_CHANNEL_LOGIN",
    "TWITCH_CHANNEL_LOGINS_RAW",
    "TWITCH_CHAT_MODE",
    "TWITCH_CLIENT_SECRET_INLINE",
    "TWITCH_CLIENT_SECRET_NAME",
    "TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS",
    "TWITCH_IRC_HOST",
    "TWITCH_IRC_PORT",
    "TWITCH_IRC_TLS",
    "TWITCH_REFRESH_TOKEN",
    "TWITCH_TOKEN_REFRESH_MARGIN_SECONDS",
    "TWITCH_USER_TOKEN",
    "irc_channel_control",
    "logger",
]


def main() -> None:
    from bot.heartbeat import start_heartbeat

    start_heartbeat()
    threading.Thread(target=run_server, daemon=True).start()
    try:
        if TWITCH_CHAT_MODE == "irc":
            run_irc_mode()
        else:
            run_eventsub_mode()
    except Exception as error:
        logger.critical("Fatal Byte Error: %s", error)
        observability.record_error(category="fatal", details=str(error))


if __name__ == "__main__":
    main()
