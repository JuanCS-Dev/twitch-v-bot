import re

from bot.byte_semantics_base import compact_message, format_chat_reply, normalize_text_for_scene
from bot.byte_semantics_constants import (
    MAX_CHAT_MESSAGE_LENGTH,
    MOVIE_TITLE_QUOTE_PATTERN,
    MULTIPART_SEPARATOR,
)


def split_text_for_chat(text: str, max_len: int = MAX_CHAT_MESSAGE_LENGTH, max_parts: int = 2) -> list[str]:
    clean_text = (text or "").strip()
    if not clean_text:
        return []
    if len(clean_text) <= max_len:
        return [clean_text]

    parts: list[str] = []
    remaining = clean_text
    while remaining and len(parts) < max_parts:
        if len(remaining) <= max_len:
            parts.append(remaining.strip())
            remaining = ""
            break

        cut = remaining.rfind("\n", 0, max_len + 1)
        if cut < int(max_len * 0.5):
            sentence_cuts = [remaining.rfind(symbol, 0, max_len + 1) for symbol in (". ", "? ", "! ")]
            cut = max(sentence_cuts)
        if cut < int(max_len * 0.5):
            cut = remaining.rfind(" ", 0, max_len + 1)
        if cut <= 0:
            cut = max_len

        chunk = remaining[:cut].strip()
        if chunk:
            parts.append(chunk)
        remaining = remaining[cut:].strip()

    if remaining:
        if parts:
            parts[-1] = compact_message(f"{parts[-1]} {remaining}", max_len=max_len)
        else:
            parts.append(compact_message(remaining, max_len=max_len))

    return [part for part in parts if part][:max_parts]


def extract_multi_reply_parts(answer_text: str, max_parts: int = 2) -> list[str]:
    if not answer_text:
        return []

    raw_parts = [segment.strip() for segment in answer_text.split(MULTIPART_SEPARATOR) if segment.strip()]
    if len(raw_parts) >= 2:
        normalized = [format_chat_reply(part) for part in raw_parts[:max_parts]]
        return [part for part in normalized if part]

    chunks = split_text_for_chat(answer_text, max_len=MAX_CHAT_MESSAGE_LENGTH, max_parts=max_parts)
    normalized = [format_chat_reply(chunk) for chunk in chunks]
    return [part for part in normalized if part]


def extract_movie_title(prompt: str) -> str:
    quote_match = MOVIE_TITLE_QUOTE_PATTERN.search(prompt or "")
    if quote_match:
        return normalize_text_for_scene(quote_match.group("title"), max_len=80)

    candidate_match = re.search(
        r"ficha\s*t[eé]cnica(?:\s+(?:do|da|de)\s+filme)?(?:\s+(?:do|da|de))?\s+(?P<title>.+)$",
        prompt or "",
        re.IGNORECASE,
    )
    if not candidate_match:
        return ""

    candidate = candidate_match.group("title").strip(" ?!.:,;")
    if not candidate:
        return ""

    lowered = candidate.lower()
    generic_fragments = (
        "que estamos vendo",
        "que estamos assistindo",
        "que estamos assistindo hoje",
        "agora",
    )
    if any(fragment in lowered for fragment in generic_fragments):
        return ""
    if lowered in {"filme", "hoje", "agora"}:
        return ""

    return normalize_text_for_scene(candidate, max_len=80)


def build_movie_fact_sheet_query(movie_title: str) -> str:
    return (
        f"Monte uma ficha tecnica objetiva do filme '{movie_title}'. "
        "Responda em no maximo 8 linhas, sem markdown, com uma linha por campo no formato Campo: valor. "
        "Use nesta ordem: Titulo, Ano, Direcao, Elenco principal, Genero, Duracao, Pais, Nota media. "
        "Se nao houver confianca em algum dado, escreva N/D."
    )
