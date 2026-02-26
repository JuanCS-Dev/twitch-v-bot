# ruff: noqa: F401

import asyncio
import json
import time
import unittest
from typing import Any
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
from bot.status_runtime import build_status_line as _build_status_line_async


async def build_status_line(*args, **kwargs):
    return await _build_status_line_async(*args, **kwargs)


from bot.twitch_tokens import TwitchTokenManager, is_irc_auth_failure_line


class ContextProxy:
    """
    Proxy de compatibilidade para testes que acessam 'context' diretamente.
    Utiliza get_sync para garantir acesso imediato em testes legados.
    """

    def __getattr__(self, name):
        ctx = context_manager.get_sync("default")
        return getattr(ctx, name)

    def __setattr__(self, name, value):
        ctx = context_manager.get_sync("default")
        setattr(ctx, name, value)


# Símbolo global usado por centenas de testes legados
context = ContextProxy()


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


class ScientificTestCase(unittest.IsolatedAsyncioTestCase):
    """Base para testes científicos, 100% Async Aware e retrocompatível."""

    async def asyncSetUp(self):
        # Resolve o loop atual e injeta no manager
        self.loop = asyncio.get_running_loop()
        context_manager.set_main_loop(self.loop)

        # Reset total do estado
        from bot.logic_context import StreamContext

        context_manager._contexts = {}
        ctx = StreamContext()
        ctx.channel_id = "default"
        context_manager._contexts["default"] = ctx

    async def asyncTearDown(self):
        pass
