"""Runtime configuration for the bot.

This module provides backward compatibility for imports.
New code should use bot.config instead.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from bot.config import config

# Load .env from project root before any env access
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env", override=False)

from openai import OpenAI

from bot import byte_semantics
from bot.channel_control import IrcChannelControlBridge


def env_flag(name: str, default: str = "false") -> bool:
    value = os.environ.get(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def env_text(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ByteBot")

# Backward compatibility: re-export from config
CLIENT_ID = config.TWITCH_CLIENT_ID
BOT_ID = config.TWITCH_BOT_ID
EDITOR_ID = config.EDITOR_ID
OWNER_ID = config.OWNER_ID
CHANNEL_ID = config.CHANNEL_ID
TWITCH_CHAT_MODE = config.TWITCH_CHAT_MODE
ENABLE_LIVE_CONTEXT_LEARNING = config.ENABLE_LIVE_CONTEXT_LEARNING
TWITCH_CHANNEL_LOGIN = config.TWITCH_CHANNEL_LOGIN
TWITCH_CHANNEL_LOGINS_RAW = config.TWITCH_CHANNEL_LOGINS_RAW
TWITCH_BOT_LOGIN = config.TWITCH_BOT_LOGIN
TWITCH_USER_TOKEN = config.TWITCH_USER_TOKEN
TWITCH_REFRESH_TOKEN = config.TWITCH_REFRESH_TOKEN
TWITCH_CLIENT_SECRET_INLINE = config.TWITCH_CLIENT_SECRET_INLINE
TWITCH_CLIENT_SECRET_NAME = config.TWITCH_CLIENT_SECRET_NAME
TWITCH_IRC_HOST = config.TWITCH_IRC_HOST
TWITCH_IRC_PORT = config.TWITCH_IRC_PORT
TWITCH_IRC_TLS = config.TWITCH_IRC_TLS
TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS = config.TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS
TWITCH_TOKEN_REFRESH_MARGIN_SECONDS = config.TWITCH_TOKEN_REFRESH_MARGIN_SECONDS
TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS = config.TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS
TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS = config.TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS
BYTE_DASHBOARD_ADMIN_TOKEN = config.BYTE_DASHBOARD_ADMIN_TOKEN
METADATA_CACHE_TTL_SECONDS = config.METADATA_CACHE_TTL_SECONDS
METADATA_TIMEOUT_SECONDS = config.METADATA_TIMEOUT_SECONDS
AUTO_SCENE_REQUIRE_METADATA = config.AUTO_SCENE_REQUIRE_METADATA

# Nebius configuration
NEBIUS_API_KEY = config.NEBIUS_API_KEY
NEBIUS_BASE_URL = config.NEBIUS_BASE_URL
NEBIUS_MODEL_DEFAULT = config.NEBIUS_MODEL_DEFAULT
NEBIUS_MODEL_SEARCH = config.NEBIUS_MODEL_SEARCH
NEBIUS_MODEL_REASONING = config.NEBIUS_MODEL_REASONING
NEBIUS_MODEL_VISION = config.NEBIUS_MODEL_VISION
NEBIUS_MODEL = config.NEBIUS_MODEL

# Cliente Nebius (OpenAI-compatible)
client = OpenAI(api_key=NEBIUS_API_KEY, base_url=NEBIUS_BASE_URL)

BYTE_VERSION = config.BYTE_VERSION
BYTE_HELP_MESSAGE = byte_semantics.BYTE_HELP_MESSAGE
MAX_CHAT_MESSAGE_LENGTH = byte_semantics.MAX_CHAT_MESSAGE_LENGTH
MULTIPART_SEPARATOR = byte_semantics.MULTIPART_SEPARATOR
SERIOUS_REPLY_MAX_LINES = byte_semantics.SERIOUS_REPLY_MAX_LINES
SERIOUS_REPLY_MAX_LENGTH = byte_semantics.SERIOUS_REPLY_MAX_LENGTH
QUALITY_SAFE_FALLBACK = byte_semantics.QUALITY_SAFE_FALLBACK
BYTE_INTRO_TEMPLATES = byte_semantics.BYTE_INTRO_TEMPLATES

PROJECT_ROOT = config.PROJECT_ROOT
DASHBOARD_DIR = config.DASHBOARD_DIR

irc_channel_control = IrcChannelControlBridge()
