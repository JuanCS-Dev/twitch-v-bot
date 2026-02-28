"""ASCII Art Runtime - Geração de arte ASCII a partir de busca de imagens."""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO

import requests

logger = logging.getLogger("ByteBot")

# Configurações do contrato ASCII para Twitch 2026
ASCII_ART_MAX_LINES = 12
ASCII_ART_MAX_CHARS_PER_LINE = 80
ASCII_ART_COOLDOWN_SECONDS = 30.0
ASCII_ART_TIMEOUT_SECONDS = 10.0
ASCII_ART_IMAGE_MAX_SIZE = (400, 400)

# Caracteres ASCII do mais escuro ao mais claro (para melhor contraste)
ASCII_CHARS = "@#%*+=-:. "


@dataclass(frozen=True)
class AsciiArtResult:
    """Resultado da geração de arte ASCII."""

    lines: list[str]
    source: str
    subject: str
    success: bool
    error_message: str = ""


class AsciiArtCooldown:
    """Gerenciador de cooldown/throttle para comando ASCII."""

    def __init__(self, cooldown_seconds: float = ASCII_ART_COOLDOWN_SECONDS):
        self._cooldown_seconds = cooldown_seconds
        self._last_usage: dict[str, float] = {}

    def can_use(self, channel_id: str) -> tuple[bool, float]:
        """Verifica se o comando pode ser usado no canal. Retorna (pode_usar, tempo_restante)."""
        now = time.monotonic()
        last = self._last_usage.get(channel_id, 0)
        elapsed = now - last
        if elapsed >= self._cooldown_seconds:
            return True, 0.0
        return False, self._cooldown_seconds - elapsed

    def mark_used(self, channel_id: str) -> None:
        """Marca o comando como usado no canal."""
        self._last_usage[channel_id] = time.monotonic()


# Instância global de cooldown
_ascii_cooldown = AsciiArtCooldown()


def _search_image_sync(subject: str) -> str | None:
    """Busca imagem usando DuckDuckGo (síncrono, roda em thread)."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            # Busca por imagens
            results = list(ddgs.images(f"{subject}", max_results=3))
            for item in results:
                url = item.get("image") or item.get("url") or item.get("thumbnail")
                if url:
                    return url
    except Exception as e:
        logger.warning("Erro ao buscar imagem para ASCII art '%s': %s", subject, e)
    return None


async def _search_image(subject: str) -> str | None:
    """Busca imagem de forma assíncrona."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_search_image_sync, subject),
            timeout=ASCII_ART_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning("Timeout ao buscar imagem para ASCII art: %s", subject)
        return None
    except Exception as e:
        logger.warning("Erro na busca de imagem ASCII: %s", e)
        return None


def _download_image_sync(url: str) -> bytes | None:
    """Baixa imagem da URL (síncrono)."""
    try:
        response = requests.get(
            url,
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"},
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.warning("Erro ao baixar imagem %s: %s", url, e)
        return None


async def _download_image(url: str) -> bytes | None:
    """Baixa imagem de forma assíncrona."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_download_image_sync, url),
            timeout=ASCII_ART_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning("Timeout ao baixar imagem ASCII: %s", url)
        return None
    except Exception as e:
        logger.warning("Erro no download de imagem ASCII: %s", e)
        return None


def _generate_ascii_fallback(image_bytes: bytes, width: int = 60) -> list[str]:
    """Gera ASCII art usando Pillow (fallback quando ascii-magic não disponível)."""
    try:
        from PIL import Image

        img = Image.open(BytesIO(image_bytes))
        # Converte para RGB se necessário
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Calcula altura mantendo proporção (caracteres são ~2x mais altos que largos)
        aspect_ratio = img.height / img.width
        height = int(width * aspect_ratio * 0.55)
        height = min(height, ASCII_ART_MAX_LINES)

        img = img.resize((width, height))

        lines = []
        for y in range(height):
            line = ""
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                # Calcula luminância
                luminance = int(0.299 * r + 0.587 * g + 0.114 * b)
                # Mapeia para caractere ASCII
                char_index = int(luminance / 255 * (len(ASCII_CHARS) - 1))
                line += ASCII_CHARS[char_index]
            lines.append(line)

        return lines[:ASCII_ART_MAX_LINES]
    except Exception as e:
        logger.warning("Erro no fallback ASCII Pillow: %s", e)
        return []


def _generate_ascii_with_lib(image_bytes: bytes, width: int = 60) -> list[str]:
    """Tenta gerar ASCII usando ascii-magic biblioteca."""
    try:
        from ascii_magic import AsciiArt

        art = AsciiArt.from_image(BytesIO(image_bytes))
        # Gera ASCII sem cores, com largura específica
        ascii_str = art.to_ascii(columns=width)
        lines = [line for line in ascii_str.split("\n") if line.strip()]
        return lines[:ASCII_ART_MAX_LINES]
    except Exception as e:
        logger.debug("ascii-magic falhou, usando fallback: %s", e)
        return []


def _sanitize_ascii_lines(lines: list[str]) -> list[str]:
    """Sanitiza linhas ASCII para envio seguro no IRC."""
    sanitized = []
    for line in lines:
        # Remove caracteres problemáticos para IRC
        cleaned = line.replace("\r", "").replace("\n", "")
        # Trunca se necessário
        if len(cleaned) > ASCII_ART_MAX_CHARS_PER_LINE:
            cleaned = cleaned[:ASCII_ART_MAX_CHARS_PER_LINE]
        # Só adiciona se tiver conteúdo
        if cleaned.strip():
            sanitized.append(cleaned)
    return sanitized[:ASCII_ART_MAX_LINES]


async def generate_ascii_art(
    subject: str,
    channel_id: str,
) -> AsciiArtResult:
    """Gera arte ASCII a partir de um assunto.

    Args:
        subject: Assunto da arte (ex: "gato", "cachorro", "Homer Simpson")
        channel_id: ID do canal para controle de cooldown

    Returns:
        AsciiArtResult com linhas ASCII ou mensagem de erro
    """
    # Verifica cooldown
    can_use, remaining = _ascii_cooldown.can_use(channel_id)
    if not can_use:
        return AsciiArtResult(
            lines=[],
            source="",
            subject=subject,
            success=False,
            error_message=f"Aguarde {int(remaining)}s para usar arte ASCII novamente.",
        )

    # Busca imagem
    image_url = await _search_image(subject)
    if not image_url:
        return AsciiArtResult(
            lines=[],
            source="",
            subject=subject,
            success=False,
            error_message=f"Não encontrei imagem para '{subject}'. Tente outro termo!",
        )

    # Baixa imagem
    image_bytes = await _download_image(image_url)
    if not image_bytes:
        return AsciiArtResult(
            lines=[],
            source="",
            subject=subject,
            success=False,
            error_message="Erro ao baixar imagem. Tente novamente!",
        )

    # Gera ASCII (tenta biblioteca primeiro, depois fallback)
    lines = _generate_ascii_with_lib(image_bytes, width=60)
    if not lines:
        lines = _generate_ascii_fallback(image_bytes, width=60)

    if not lines:
        return AsciiArtResult(
            lines=[],
            source="",
            subject=subject,
            success=False,
            error_message="Não consegui gerar a arte. Tente outra imagem!",
        )

    # Sanitiza e marca uso
    sanitized_lines = _sanitize_ascii_lines(lines)
    _ascii_cooldown.mark_used(channel_id)

    # Extrai domínio da fonte
    source_domain = image_url.split("/")[2] if "/" in image_url else "desconhecida"

    return AsciiArtResult(
        lines=sanitized_lines,
        source=source_domain,
        subject=subject,
        success=True,
    )


async def handle_ascii_art_prompt(
    subject: str,
    author_name: str,
    reply_raw_fn: Callable[[str], object],
    channel_id: str,
) -> bool:
    """Handler de alto nível para comando de arte ASCII.

    Args:
        subject: Assunto da arte
        author_name: Nome do autor da mensagem
        reply_raw_fn: Função para enviar linha raw (preserva espaços)
        channel_id: ID do canal

    Returns:
        True se arte foi enviada, False se erro/cooldown
    """
    result = await generate_ascii_art(subject, channel_id)

    if not result.success:
        # Envia mensagem de erro normal
        error_reply = f"@{author_name} {result.error_message}"
        await reply_raw_fn(error_reply)
        return False

    # Envia arte linha por linha preservando formatação
    header = f"@{author_name} Arte ASCII: {result.subject}"
    await reply_raw_fn(header)

    for line in result.lines:
        await reply_raw_fn(line)

    # Fonte em linha separada
    if result.source:
        await reply_raw_fn(f"(fonte: {result.source})")

    return True


def get_cooldown_status(channel_id: str) -> tuple[bool, float]:
    """Retorna status do cooldown para um canal.

    Returns:
        (pode_usar, segundos_restantes)
    """
    return _ascii_cooldown.can_use(channel_id)


def reset_cooldown(channel_id: str) -> None:
    """Reseta o cooldown para um canal (útil para testes)."""
    if channel_id in _ascii_cooldown._last_usage:
        del _ascii_cooldown._last_usage[channel_id]
