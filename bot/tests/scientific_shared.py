# ruff: noqa: F401

import asyncio
import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.bootstrap_runtime import build_irc_token_manager, get_secret, resolve_irc_channel_logins
from bot.byte_semantics import (
    build_direct_answer_instruction,
    build_llm_enhanced_prompt,
    extract_multi_reply_parts,
    normalize_current_events_reply_contract,
    parse_byte_prompt,
)
from bot.dashboard_server import HealthHandler
from bot.eventsub_runtime import AgentComponent, ByteBot
from bot.irc_protocol import is_irc_notice_delivery_block
from bot.irc_runtime import IrcByteBot
from bot.logic import BOT_BRAND, MAX_REPLY_LENGTH, MAX_REPLY_LINES, context_manager
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
    MAX_CHAT_MESSAGE_LENGTH,
    QUALITY_SAFE_FALLBACK,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
)
from bot.scene_runtime import auto_update_scene_from_message
from bot.status_runtime import build_status_line
from bot.twitch_tokens import TwitchTokenManager, is_irc_auth_failure_line

# Shim de compatibilidade para suites cientificas legadas
# Ele sempre retorna o contexto 'default' para testes que nao especificam canal
context = context_manager.get("default")


class DummyHTTPResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyIrcWriter:
    def __init__(self):
        self.lines: list[str] = []

    def write(self, payload: bytes):
        self.lines.append(payload.decode("utf-8"))

    async def drain(self):
        return None

    def close(self):
        return None

    async def wait_closed(self):
        return None


class ScientificTestCase(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Reset total do contexto default para cada teste cientifico
        context_manager.cleanup("default")
        ctx = context_manager.get("default")
        ctx.current_game = "N/A"
        ctx.stream_vibe = "Chill"
        ctx.last_event = "Bot Online"
        ctx.style_profile = "Tom generalista, claro e natural em PT-BR, sem giria gamer forcada."
        for content_type in ctx.live_observability:
            ctx.live_observability[content_type] = ""
        ctx.recent_chat_entries = []
        ctx.last_byte_reply = ""

    def tearDown(self):
        self.loop.close()
