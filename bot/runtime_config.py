import logging
import os
from pathlib import Path

from dotenv import load_dotenv

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

CLIENT_ID = env_text("TWITCH_CLIENT_ID")
BOT_ID = env_text("TWITCH_BOT_ID")
# editor_id para POST /helix/videos/clips — normalmente e o BOT_ID (usuario autenticado).
# Pode ser sobrescrito via TWITCH_EDITOR_ID se o token pertencer a outro usuario.
EDITOR_ID = env_text("TWITCH_EDITOR_ID") or env_text("TWITCH_BOT_ID")
OWNER_ID = env_text("TWITCH_OWNER_ID")
CHANNEL_ID = env_text("TWITCH_CHANNEL_ID")
TWITCH_CHAT_MODE = env_text("TWITCH_CHAT_MODE", "eventsub").lower() or "eventsub"
ENABLE_LIVE_CONTEXT_LEARNING = env_flag("ENABLE_LIVE_CONTEXT_LEARNING")

TWITCH_CHANNEL_LOGIN = env_text("TWITCH_CHANNEL_LOGIN").lstrip("#").lower()
TWITCH_CHANNEL_LOGINS_RAW = env_text("TWITCH_CHANNEL_LOGINS")
TWITCH_BOT_LOGIN = env_text("TWITCH_BOT_LOGIN").lower()

TWITCH_USER_TOKEN = env_text("TWITCH_USER_TOKEN").removeprefix("oauth:")
TWITCH_REFRESH_TOKEN = env_text("TWITCH_REFRESH_TOKEN")
TWITCH_CLIENT_SECRET_INLINE = env_text("TWITCH_CLIENT_SECRET")
TWITCH_CLIENT_SECRET_NAME = env_text("TWITCH_CLIENT_SECRET_SECRET_NAME", "twitch-client-secret")

TWITCH_IRC_HOST = env_text("TWITCH_IRC_HOST", "irc.chat.twitch.tv") or "irc.chat.twitch.tv"
TWITCH_IRC_PORT = int(env_text("TWITCH_IRC_PORT", "6697"))
TWITCH_IRC_TLS = env_flag("TWITCH_IRC_TLS", "true")
TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS = float(
    env_text("TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS", "12.0")
)

TWITCH_TOKEN_REFRESH_MARGIN_SECONDS = int(env_text("TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", "300"))
TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS = float(
    env_text("TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS", "5.0")
)
TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS = float(
    env_text("TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS", "8.0")
)

BYTE_DASHBOARD_ADMIN_TOKEN = env_text("BYTE_DASHBOARD_ADMIN_TOKEN")
if BYTE_DASHBOARD_ADMIN_TOKEN:
    logger.info(
        "Configuracao: Dashboard Admin Token ativo (comprimento: %d)",
        len(BYTE_DASHBOARD_ADMIN_TOKEN),
    )
else:
    logger.warning(
        "Configuracao: Dashboard Admin Token NAO definido. Dashboard operando sem seguranca!"
    )

METADATA_CACHE_TTL_SECONDS = int(env_text("AUTO_SCENE_CACHE_TTL_SECONDS", "900"))
METADATA_TIMEOUT_SECONDS = float(env_text("AUTO_SCENE_METADATA_TIMEOUT_SECONDS", "3.0"))
AUTO_SCENE_REQUIRE_METADATA = env_flag("AUTO_SCENE_REQUIRE_METADATA", "true")

# Nebius Token Factory — inference provider
NEBIUS_API_KEY = env_text("NEBIUS_API_KEY")
NEBIUS_BASE_URL = env_text("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1")

# Multi-modelo: cada tipo de requisicao usa o modelo otimizado
# Default (chat geral): rapido, barato, bom para conversa casual
NEBIUS_MODEL_DEFAULT = env_text("NEBIUS_MODEL_DEFAULT", "moonshotai/Kimi-K2.5")
# Search (current events com DDG): rapido + bom em seguir instrucoes com contexto injetado
NEBIUS_MODEL_SEARCH = env_text("NEBIUS_MODEL_SEARCH", "moonshotai/Kimi-K2.5")
# Reasoning (perguntas tecnicas serias): pensamento profundo
NEBIUS_MODEL_REASONING = env_text("NEBIUS_MODEL_REASONING", "moonshotai/Kimi-K2-Thinking")
# Vision (multimodal para imagens e frames) - Kimi 2.5 eh State of the Art nativo Multimodal
NEBIUS_MODEL_VISION = env_text("NEBIUS_MODEL_VISION", "moonshotai/Kimi-K2.5")
# Backward compatible: NEBIUS_MODEL sobrescreve DEFAULT se definido
NEBIUS_MODEL = env_text("NEBIUS_MODEL") or NEBIUS_MODEL_DEFAULT

# Cliente Nebius (OpenAI-compatible)
client = OpenAI(api_key=NEBIUS_API_KEY, base_url=NEBIUS_BASE_URL)

BYTE_VERSION = "1.4"
BYTE_HELP_MESSAGE = byte_semantics.BYTE_HELP_MESSAGE
MAX_CHAT_MESSAGE_LENGTH = byte_semantics.MAX_CHAT_MESSAGE_LENGTH
MULTIPART_SEPARATOR = byte_semantics.MULTIPART_SEPARATOR
SERIOUS_REPLY_MAX_LINES = byte_semantics.SERIOUS_REPLY_MAX_LINES
SERIOUS_REPLY_MAX_LENGTH = byte_semantics.SERIOUS_REPLY_MAX_LENGTH
QUALITY_SAFE_FALLBACK = byte_semantics.QUALITY_SAFE_FALLBACK
BYTE_INTRO_TEMPLATES = byte_semantics.BYTE_INTRO_TEMPLATES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

irc_channel_control = IrcChannelControlBridge()
