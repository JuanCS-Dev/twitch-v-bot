"""Configuration management for the bot.

This module provides a ConfigManager class that encapsulates all configuration
values, replacing module-level globals with a singleton pattern.

Usage:
    from bot.config import config

    # Access config values
    client_id = config.TWITCH_CLIENT_ID
    model = config.nebius_model_default

    # Check feature flags
    if config.enable_live_context:
        ...
"""

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger("ByteBot")


def _env_flag(name: str, default: str = "false") -> bool:
    value = os.environ.get(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_text(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


class ConfigManager:
    """Singleton configuration manager for the bot.

    This class encapsulates all environment-based configuration,
    replacing module-level globals with a clean API.
    """

    _instance: "ConfigManager | None" = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._load_env()
        self._initialized = True

    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        project_root = Path(__file__).resolve().parent.parent
        load_dotenv(project_root / ".env", override=False)

        # Twitch Auth
        self.TWITCH_CLIENT_ID = _env_text("TWITCH_CLIENT_ID")
        self.TWITCH_BOT_ID = _env_text("TWITCH_BOT_ID")
        self.EDITOR_ID = _env_text("TWITCH_EDITOR_ID") or _env_text("TWITCH_BOT_ID")
        self.OWNER_ID = _env_text("TWITCH_OWNER_ID")
        self.CHANNEL_ID = _env_text("TWITCH_CHANNEL_ID")

        # Twitch Chat
        self.TWITCH_CHAT_MODE = _env_text("TWITCH_CHAT_MODE", "eventsub").lower() or "eventsub"
        self.ENABLE_LIVE_CONTEXT_LEARNING = _env_flag("ENABLE_LIVE_CONTEXT_LEARNING")

        # Twitch Channel
        self.TWITCH_CHANNEL_LOGIN = _env_text("TWITCH_CHANNEL_LOGIN").lstrip("#").lower()
        self.TWITCH_CHANNEL_LOGINS_RAW = _env_text("TWITCH_CHANNEL_LOGINS")
        self.TWITCH_BOT_LOGIN = _env_text("TWITCH_BOT_LOGIN").lower()

        # Twitch Tokens
        self.TWITCH_USER_TOKEN = _env_text("TWITCH_USER_TOKEN").removeprefix("oauth:")
        self.TWITCH_REFRESH_TOKEN = _env_text("TWITCH_REFRESH_TOKEN")
        self.TWITCH_CLIENT_SECRET_INLINE = _env_text("TWITCH_CLIENT_SECRET")
        self.TWITCH_CLIENT_SECRET_NAME = _env_text(
            "TWITCH_CLIENT_SECRET_SECRET_NAME", "twitch-client-secret"
        )

        # Twitch IRC
        self.TWITCH_IRC_HOST = (
            _env_text("TWITCH_IRC_HOST", "irc.chat.twitch.tv") or "irc.chat.twitch.tv"
        )
        self.TWITCH_IRC_PORT = int(_env_text("TWITCH_IRC_PORT", "6697"))
        self.TWITCH_IRC_TLS = _env_flag("TWITCH_IRC_TLS", "true")
        self.TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS = float(
            _env_text("TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS", "12.0")
        )

        # Token Refresh
        self.TWITCH_TOKEN_REFRESH_MARGIN_SECONDS = int(
            _env_text("TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", "300")
        )
        self.TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS = float(
            _env_text("TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS", "5.0")
        )
        self.TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS = float(
            _env_text("TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS", "8.0")
        )

        # Dashboard
        self.BYTE_DASHBOARD_ADMIN_TOKEN = _env_text("BYTE_DASHBOARD_ADMIN_TOKEN")
        if self.BYTE_DASHBOARD_ADMIN_TOKEN:
            logger.info(
                "Configuracao: Dashboard Admin Token ativo (comprimento: %d)",
                len(self.BYTE_DASHBOARD_ADMIN_TOKEN),
            )
        else:
            logger.warning(
                "Configuracao: Dashboard Admin Token NAO definido. Dashboard operando sem seguranca!"
            )

        # Metadata Cache
        self.METADATA_CACHE_TTL_SECONDS = int(_env_text("AUTO_SCENE_CACHE_TTL_SECONDS", "900"))
        self.METADATA_TIMEOUT_SECONDS = float(
            _env_text("AUTO_SCENE_METADATA_TIMEOUT_SECONDS", "3.0")
        )
        self.AUTO_SCENE_REQUIRE_METADATA = _env_flag("AUTO_SCENE_REQUIRE_METADATA", "true")

        # Nebius AI
        self.NEBIUS_API_KEY = _env_text("NEBIUS_API_KEY")
        self.NEBIUS_BASE_URL = _env_text("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1")
        self.NEBIUS_MODEL_DEFAULT = _env_text("NEBIUS_MODEL_DEFAULT", "moonshotai/Kimi-K2.5")
        self.NEBIUS_MODEL_SEARCH = _env_text("NEBIUS_MODEL_SEARCH", "moonshotai/Kimi-K2.5")
        self.NEBIUS_MODEL_REASONING = _env_text(
            "NEBIUS_MODEL_REASONING", "moonshotai/Kimi-K2-Thinking"
        )
        self.NEBIUS_MODEL_VISION = _env_text("NEBIUS_MODEL_VISION", "moonshotai/Kimi-K2.5")
        self.NEBIUS_MODEL = _env_text("NEBIUS_MODEL") or self.NEBIUS_MODEL_DEFAULT

        # Version
        self.BYTE_VERSION = "1.4"

        # Paths
        self.PROJECT_ROOT = Path(__file__).resolve().parent.parent
        self.DASHBOARD_DIR = self.PROJECT_ROOT / "dashboard"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        return getattr(self, key, default)

    def __repr__(self) -> str:
        return f"<ConfigManager {self.BYTE_VERSION}>"


# Singleton instance
config = ConfigManager()


# Backward compatibility: expose key globals as module-level for existing imports
# These delegate to the config singleton
def __getattr__(name: str) -> Any:
    """Backward compatibility for module-level globals."""
    compat_map = {
        "CLIENT_ID": "TWITCH_CLIENT_ID",
        "BOT_ID": "TWITCH_BOT_ID",
        "EDITOR_ID": "EDITOR_ID",
        "OWNER_ID": "OWNER_ID",
        "CHANNEL_ID": "CHANNEL_ID",
        "TWITCH_CHAT_MODE": "TWITCH_CHAT_MODE",
        "ENABLE_LIVE_CONTEXT_LEARNING": "ENABLE_LIVE_CONTEXT_LEARNING",
        "TWITCH_CHANNEL_LOGIN": "TWITCH_CHANNEL_LOGIN",
        "TWITCH_CHANNEL_LOGINS_RAW": "TWITCH_CHANNEL_LOGINS_RAW",
        "TWITCH_BOT_LOGIN": "TWITCH_BOT_LOGIN",
        "TWITCH_USER_TOKEN": "TWITCH_USER_TOKEN",
        "TWITCH_REFRESH_TOKEN": "TWITCH_REFRESH_TOKEN",
        "TWITCH_CLIENT_SECRET_INLINE": "TWITCH_CLIENT_SECRET_INLINE",
        "TWITCH_CLIENT_SECRET_NAME": "TWITCH_CLIENT_SECRET_NAME",
        "TWITCH_IRC_HOST": "TWITCH_IRC_HOST",
        "TWITCH_IRC_PORT": "TWITCH_IRC_PORT",
        "TWITCH_IRC_TLS": "TWITCH_IRC_TLS",
        "TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS": "TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS",
        "TWITCH_TOKEN_REFRESH_MARGIN_SECONDS": "TWITCH_TOKEN_REFRESH_MARGIN_SECONDS",
        "TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS": "TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS",
        "TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS": "TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS",
        "BYTE_DASHBOARD_ADMIN_TOKEN": "BYTE_DASHBOARD_ADMIN_TOKEN",
        "METADATA_CACHE_TTL_SECONDS": "METADATA_CACHE_TTL_SECONDS",
        "METADATA_TIMEOUT_SECONDS": "METADATA_TIMEOUT_SECONDS",
        "AUTO_SCENE_REQUIRE_METADATA": "AUTO_SCENE_REQUIRE_METADATA",
        "NEBIUS_API_KEY": "NEBIUS_API_KEY",
        "NEBIUS_BASE_URL": "NEBIUS_BASE_URL",
        "NEBIUS_MODEL_DEFAULT": "NEBIUS_MODEL_DEFAULT",
        "NEBIUS_MODEL_SEARCH": "NEBIUS_MODEL_SEARCH",
        "NEBIUS_MODEL_REASONING": "NEBIUS_MODEL_REASONING",
        "NEBIUS_MODEL_VISION": "NEBIUS_MODEL_VISION",
        "NEBIUS_MODEL": "NEBIUS_MODEL",
        "BYTE_VERSION": "BYTE_VERSION",
        "PROJECT_ROOT": "PROJECT_ROOT",
        "DASHBOARD_DIR": "DASHBOARD_DIR",
    }

    if name in compat_map:
        return getattr(config, compat_map[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
