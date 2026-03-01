"""Testes focados para Fase 23: ASCII Art Runtime (Versão Braille Pro)."""

import asyncio
import io
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

# Importa módulos a serem testados
from bot.ascii_art_runtime import (
    AsciiArtCooldown,
    AsciiArtResult,
    _generate_ascii_with_lib,
    _sanitize_ascii_lines,
    generate_ascii_art,
    get_cooldown_status,
    handle_ascii_art_prompt,
    reset_cooldown,
)
from bot.byte_semantics_base import (
    _normalize_ascii_prompt,
    extract_ascii_subject,
    is_ascii_art_prompt,
)


class TestAsciiArtCooldown:
    def test_cooldown_flow(self):
        cd = AsciiArtCooldown(cooldown_seconds=1.0)
        channel = "test_chan"

        can, rem = cd.can_use(channel)
        assert can is True

        cd.mark_used(channel)
        can, rem = cd.can_use(channel)
        assert can is False
        assert rem > 0.0

        time.sleep(1.1)
        can, rem = cd.can_use(channel)
        assert can is True


class TestAsciiSemantics:
    def test_detection(self):
        assert is_ascii_art_prompt("byte arte ascii de goku") is True
        assert is_ascii_art_prompt("byte ascii batman") is True
        assert is_ascii_art_prompt("oi byte") is False

    def test_extraction(self):
        assert extract_ascii_subject("byte arte ascii de goku") == "goku"
        assert extract_ascii_subject("byte ascii batman") == "batman"


class TestAsciiGeneration:
    def _get_valid_image_bytes(self):
        img = Image.new("RGB", (10, 10), color="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @pytest.mark.asyncio
    async def test_generate_ascii_success(self):
        reset_cooldown("test_channel_success")
        mock_image = self._get_valid_image_bytes()

        with (
            patch("bot.ascii_art_runtime._search_image", return_value="http://img.com/1.png"),
            patch("bot.ascii_art_runtime._download_image", return_value=mock_image),
        ):
            result = await generate_ascii_art("goku", "test_channel_success")
            assert result.success is True
            assert len(result.lines) > 0
            # Check for Braille dots
            has_braille = any(ord(c) >= 0x2800 for line in result.lines for c in line)
            assert has_braille is True

    @pytest.mark.asyncio
    async def test_generate_ascii_no_image(self):
        reset_cooldown("test_channel_fail")
        with patch("bot.ascii_art_runtime._search_image", return_value=None):
            result = await generate_ascii_art("nao_existe_isso", "test_channel_fail")
            assert result.success is False
            assert "Não encontrei" in result.error_message


class TestHandleAsciiArtPrompt:
    @pytest.mark.asyncio
    async def test_handle_flow(self):
        reset_cooldown("test_chan_handle")
        reply_mock = AsyncMock()
        img = Image.new("RGB", (10, 10), color="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        mock_image = buf.getvalue()

        with (
            patch("bot.ascii_art_runtime._search_image", return_value="http://img.com/1.png"),
            patch("bot.ascii_art_runtime._download_image", return_value=mock_image),
        ):
            success = await handle_ascii_art_prompt("gato", "user", reply_mock, "test_chan_handle")
            assert success is True
            assert reply_mock.call_count > 0
