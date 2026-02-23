# ruff: noqa: F401

import asyncio
import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.byte_semantics import normalize_current_events_reply_contract
from bot.logic import MAX_REPLY_LINES
from bot.main import (
    AgentComponent,
    ByteBot,
    HealthHandler,
    IrcByteBot,
    MAX_CHAT_MESSAGE_LENGTH,
    QUALITY_SAFE_FALLBACK,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
    TwitchTokenManager,
    auto_update_scene_from_message,
    build_direct_answer_instruction,
    build_intro_reply,
    build_irc_token_manager,
    build_llm_enhanced_prompt,
    build_quality_rewrite_prompt,
    build_status_line,
    build_verifiable_prompt,
    context,
    extract_movie_title,
    extract_multi_reply_parts,
    get_secret,
    handle_byte_prompt_text,
    is_current_events_prompt,
    is_follow_up_prompt,
    is_intro_prompt,
    is_irc_auth_failure_line,
    is_irc_notice_delivery_block,
    is_low_quality_answer,
    is_serious_technical_prompt,
    parse_byte_prompt,
    resolve_irc_channel_logins,
)


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
        context.current_game = "N/A"
        context.stream_vibe = "Conversa"
        context.last_event = "Bot Online"
        context.style_profile = (
            "Tom generalista, claro e natural em PT-BR, sem giria gamer forcada."
        )
        for content_type in context.live_observability:
            context.live_observability[content_type] = ""
        context.recent_chat_entries = []
        context.last_byte_reply = ""

    def tearDown(self):
        self.loop.close()
