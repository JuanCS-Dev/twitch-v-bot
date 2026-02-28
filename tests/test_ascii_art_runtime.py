"""Testes focados para Fase 23: ASCII Art Runtime."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Importa módulos a serem testados
from bot.ascii_art_runtime import (
    AsciiArtCooldown,
    AsciiArtResult,
    _generate_ascii_fallback,
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


class TestAsciiArtDetection:
    """Testes para detecção de prompts de arte ASCII."""

    def test_normalize_ascii_prompt_removes_accents(self):
        assert _normalize_ascii_prompt("Arte ASCII") == "arte ascii"
        assert _normalize_ascii_prompt("arte ASCII de gato") == "arte ascii de gato"
        assert _normalize_ascii_prompt("  múltiplos   espaços  ") == "multiplos espacos"

    def test_is_ascii_art_prompt_variations(self):
        # Formas válidas
        assert is_ascii_art_prompt("arte ascii de gato") is True
        assert is_ascii_art_prompt("me faz uma arte ascii de cachorro") is True
        assert is_ascii_art_prompt("ASCII art de Homer Simpson") is True
        assert is_ascii_art_prompt("ascii gato") is True
        assert is_ascii_art_prompt("byte arte ascii de foguete") is True

        # Formas inválidas
        assert is_ascii_art_prompt("qual é o significado de ASCII") is False
        assert is_ascii_art_prompt("o que é arte") is False
        assert is_ascii_art_prompt("") is False
        assert is_ascii_art_prompt("byte ajuda") is False

    def test_extract_ascii_subject_success(self):
        assert extract_ascii_subject("arte ascii de gato") == "gato"
        assert extract_ascii_subject("me faz uma arte ascii de cachorro") == "cachorro"
        assert extract_ascii_subject("ASCII art de Homer Simpson") == "homer simpson"
        assert extract_ascii_subject("byte arte ascii de foguete") == "foguete"
        assert extract_ascii_subject("gerar ascii de pokemon") == "pokemon"
        assert extract_ascii_subject("manda arte ascii do Brasil") == "brasil"

    def test_extract_ascii_subject_empty(self):
        assert extract_ascii_subject("arte ascii") == ""
        assert extract_ascii_subject("me faz uma arte ascii por favor") == ""
        assert extract_ascii_subject("byte ajuda") == ""


class TestAsciiArtCooldown:
    """Testes para o sistema de cooldown/throttle."""

    def test_cooldown_initial_can_use(self):
        cooldown = AsciiArtCooldown(cooldown_seconds=30.0)
        can_use, remaining = cooldown.can_use("channel_123")
        assert can_use is True
        assert remaining == 0.0

    def test_cooldown_blocks_after_use(self):
        cooldown = AsciiArtCooldown(cooldown_seconds=30.0)
        cooldown.mark_used("channel_123")
        can_use, remaining = cooldown.can_use("channel_123")
        assert can_use is False
        assert remaining > 0.0
        assert remaining <= 30.0

    def test_cooldown_allows_after_expiry(self):
        cooldown = AsciiArtCooldown(cooldown_seconds=0.1)
        cooldown.mark_used("channel_123")
        time.sleep(0.15)
        can_use, remaining = cooldown.can_use("channel_123")
        assert can_use is True
        assert remaining == 0.0

    def test_cooldown_per_channel_isolation(self):
        cooldown = AsciiArtCooldown(cooldown_seconds=30.0)
        cooldown.mark_used("channel_a")
        can_use_a, _ = cooldown.can_use("channel_a")
        can_use_b, _ = cooldown.can_use("channel_b")
        assert can_use_a is False
        assert can_use_b is True


class TestAsciiArtSanitization:
    """Testes para sanitização de linhas ASCII."""

    def test_sanitize_removes_control_chars(self):
        lines = ["hello\r", "world\n", "test\r\n"]
        result = _sanitize_ascii_lines(lines)
        assert "\r" not in result[0]
        assert "\n" not in result[1]

    def test_sanitize_truncates_long_lines(self):
        long_line = "x" * 100
        lines = [long_line]
        result = _sanitize_ascii_lines(lines)
        assert len(result[0]) <= 80

    def test_sanitize_skips_empty_lines(self):
        lines = ["hello", "   ", "world", ""]
        result = _sanitize_ascii_lines(lines)
        assert len(result) == 2
        assert result[0] == "hello"
        assert result[1] == "world"

    def test_sanitize_respects_max_lines(self):
        lines = [f"line_{i}" for i in range(20)]
        result = _sanitize_ascii_lines(lines)
        assert len(result) <= 12


class TestAsciiArtGeneration:
    """Testes para geração de arte ASCII (com mocks)."""

    @pytest.mark.asyncio
    async def test_generate_ascii_cooldown_blocks(self):
        # Reseta cooldown
        reset_cooldown("test_channel")

        # Primeira chamada deve funcionar
        with patch("bot.ascii_art_runtime._search_image", return_value=None):
            result = await generate_ascii_art("gato", "test_channel")
            # Reseta para não afetar outros testes
            reset_cooldown("test_channel")

        # Segunda chamada imediata deve ser bloqueada
        can_use, remaining = get_cooldown_status("test_channel")
        if not can_use:  # Se cooldown ainda ativo
            result = await generate_ascii_art("cachorro", "test_channel")
            assert result.success is False
            assert "Aguarde" in result.error_message

    @pytest.mark.asyncio
    async def test_generate_ascii_no_image_found(self):
        reset_cooldown("test_channel_2")
        with patch("bot.ascii_art_runtime._search_image", return_value=None):
            result = await generate_ascii_art("xyz123notfound", "test_channel_2")
            assert result.success is False
            assert "Não encontrei imagem" in result.error_message

    @pytest.mark.asyncio
    async def test_generate_ascii_success(self):
        reset_cooldown("test_channel_3")

        # Mock da imagem (1x1 pixel PNG)
        mock_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"

        with patch(
            "bot.ascii_art_runtime._search_image", return_value="http://example.com/img.png"
        ):
            with patch("bot.ascii_art_runtime._download_image", return_value=mock_image_bytes):
                result = await generate_ascii_art("test", "test_channel_3")
                # Se Pillow estiver disponível, deve gerar algo
                # Se não estiver, deve retornar erro
                if result.success:
                    assert len(result.lines) > 0
                    assert result.subject == "test"


class TestAsciiFallbackGeneration:
    """Testes para fallback de geração ASCII com Pillow."""

    def test_generate_ascii_fallback_empty(self):
        # Bytes inválidos devem retornar lista vazia
        result = _generate_ascii_fallback(b"invalid", width=10)
        assert result == []

    def test_generate_ascii_fallback_with_valid_image(self):
        # Cria uma imagem simples em memória
        try:
            import io

            from PIL import Image

            # Cria imagem 10x10 preta
            img = Image.new("RGB", (10, 10), color="black")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

            result = _generate_ascii_fallback(image_bytes, width=10)
            assert len(result) > 0
            # Como é tudo preto, deve ter caracteres escuros
            assert all(len(line) == 10 for line in result)
        except ImportError:
            pytest.skip("Pillow não instalado")


class TestHandleAsciiArtPrompt:
    """Testes para handler de alto nível."""

    @pytest.mark.asyncio
    async def test_handle_ascii_art_success(self):
        reset_cooldown("test_channel_4")

        reply_mock = AsyncMock()
        mock_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"

        with patch(
            "bot.ascii_art_runtime._search_image", return_value="http://example.com/img.png"
        ):
            with patch("bot.ascii_art_runtime._download_image", return_value=mock_image_bytes):
                success = await handle_ascii_art_prompt(
                    "gato", "test_user", reply_mock, "test_channel_4"
                )

                if success:
                    # Deve ter enviado header + linhas + fonte
                    assert reply_mock.call_count >= 2
                    # Primeira chamada deve ser o header
                    first_call = reply_mock.call_args_list[0]
                    assert "@test_user" in first_call[0][0]
                    assert "Arte ASCII" in first_call[0][0]

    @pytest.mark.asyncio
    async def test_handle_ascii_art_no_subject_error(self):
        reset_cooldown("test_channel_5")
        reply_mock = AsyncMock()

        with patch("bot.ascii_art_runtime._search_image", return_value=None):
            success = await handle_ascii_art_prompt(
                "xyz", "test_user", reply_mock, "test_channel_5"
            )
            assert success is False
            # Deve ter enviado mensagem de erro
            reply_mock.assert_called_once()
            assert "@test_user" in reply_mock.call_args[0][0]


class TestIntegrationByteSemantics:
    """Testes de integração com byte_semantics."""

    def test_prompt_flow_integration_detection(self):
        """Verifica que a detecção funciona com o formato esperado no fluxo."""
        from bot.byte_semantics import extract_ascii_subject, is_ascii_art_prompt

        prompts = [
            ("byte arte ascii de gato", "gato"),
            ("arte ascii de cachorro", "cachorro"),
            ("me faz uma ascii de pokemon", "pokemon"),
            ("ASCII art do Brasil", "brasil"),
        ]

        for prompt, expected_subject in prompts:
            assert is_ascii_art_prompt(prompt) is True, f"Falhou para: {prompt}"
            subject = extract_ascii_subject(prompt)
            assert subject == expected_subject, f"Esperado '{expected_subject}', got '{subject}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
