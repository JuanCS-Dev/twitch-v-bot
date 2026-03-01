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


def _generate_twitch_braille_true(image_bytes: bytes, width: int = 24) -> list[str]:
    """Gera ASCII usando matriz Braille 2x4 (Verdadeira silhueta detalhada)."""
    try:
        from PIL import Image, ImageChops, ImageStat

        img = Image.open(BytesIO(image_bytes)).convert("RGBA")

        # Fundo branco para garantir que PNGs transparentes não fiquem invertidos
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img).convert("L")

        # Corta espaços em branco (Auto-crop)
        inv = Image.eval(img, lambda p: 255 - p)
        bbox = inv.getbbox()
        if bbox:
            img = img.crop(bbox)

        pixel_width = width * 2
        # Fator 0.75 para lidar com a altura de linha do chat da Twitch (que achata a arte)
        aspect_ratio = img.height / img.width
        pixel_height = int(pixel_width * aspect_ratio * 0.75)

        img = img.resize((pixel_width, pixel_height), Image.Resampling.LANCZOS)

        # Calcula um threshold dinâmico para pegar tons médios também
        stat = ImageStat.Stat(img)
        mean = stat.mean[0]
        threshold = min(200, max(50, mean - 20))

        braille_map = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]

        lines = []
        char_height = pixel_height // 4 + (1 if pixel_height % 4 != 0 else 0)

        for y in range(min(char_height, ASCII_ART_MAX_LINES)):
            line = ""
            for x in range(width):
                char_val = 0
                for dy in range(4):
                    for dx in range(2):
                        px = x * 2 + dx
                        py = y * 4 + dy
                        if px < pixel_width and py < pixel_height:
                            if img.getpixel((px, py)) < threshold:
                                char_val += braille_map[dy][dx]

                # Se não tem ponto nenhum, usa espaço comum para evitar glitches de layout
                if char_val == 0:
                    line += " "
                else:
                    line += chr(0x2800 + char_val)
            lines.append(line.rstrip())

        # Filtra linhas vazias
        final_lines = [ln for ln in lines if ln.strip()]
        return final_lines[:ASCII_ART_MAX_LINES]

    except Exception as e:
        logger.warning("Erro no gerador Braille ASCII: %s", e)
        return []


def _generate_ascii_with_lib(image_bytes: bytes, width: int = 24) -> list[str]:
    # Removido ascii_magic porque ele engasga com nulos e a renderização do Braille é infinitamente superior.
    # Redirecionamos para a nossa própria engine de rendering nativa.
    return _generate_twitch_braille_true(image_bytes, width)


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

    # Gera ASCII usando a nova engine de silhueta Braille (Fase 23 Upgrade)
    # Largura padrão para chat Twitch é idealmente entre 24 e 28 chars
    lines = _generate_ascii_with_lib(image_bytes, width=28)

    if not lines:
        return AsciiArtResult(
            lines=[],
            source=image_url,
            subject=subject,
            success=False,
            error_message="Não consegui converter a imagem em arte ASCII.",
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
    await asyncio.sleep(0.45)  # Throttle inicial

    for line in result.lines:
        await reply_raw_fn(line)
        await asyncio.sleep(0.45)  # Throttle entre linhas para evitar rate-limit

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
