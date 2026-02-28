import re
import unicodedata

from bot.byte_semantics_constants import (
    BYTE_INTRO_TEMPLATES,
    BYTE_TRIGGER,
    BYTE_TRIGGER_PATTERN,
    COMPLEX_TECH_HINT_TERMS,
    CURRENT_EVENTS_HINT_TERMS,
    FOLLOW_UP_HINT_TERMS,
    HIGH_RISK_CURRENT_EVENTS_TERMS,
    MAX_CHAT_MESSAGE_LENGTH,
    MOVIE_FACT_SHEET_PATTERN,
    MULTIPART_SEPARATOR,
    RELEVANCE_HINT_TERMS,
    SERIOUS_TECH_TERMS,
)
from bot.logic_context import enforce_reply_limits

_intro_template_index = 0


def compact_message(text: str, max_len: int = 450) -> str:
    if len(text) <= max_len:
        return text
    head = text[: max_len - 3].rstrip()
    punctuation_positions = [head.rfind(symbol) for symbol in (".", "!", "?", ";", ":")]
    best_punctuation = max(punctuation_positions)
    if best_punctuation >= int(max_len * 0.5):
        return head[: best_punctuation + 1].strip()
    last_space = head.rfind(" ")
    if last_space >= int(max_len * 0.5):
        head = head[:last_space]
    return head.rstrip(" ,;:") + "..."


def normalize_text_for_scene(text: str, max_len: int = 120) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def format_chat_reply(text: str) -> str:
    normalized = str(text or "").replace(MULTIPART_SEPARATOR, "\n")
    return compact_message(
        enforce_reply_limits(normalized),
        max_len=MAX_CHAT_MESSAGE_LENGTH,
    )


def parse_byte_prompt(message_text: str) -> str | None:
    text = (message_text or "").strip()
    if not text:
        return None
    normalized_text = text.lower()
    if normalized_text in {BYTE_TRIGGER, f"!{BYTE_TRIGGER}", f"@{BYTE_TRIGGER}"}:
        return ""
    match = BYTE_TRIGGER_PATTERN.match(text)
    if not match:
        return None
    return match.group(1).strip()


def _normalize_ascii_prompt(prompt: str) -> str:
    lowered = (prompt or "").strip().lower()
    if not lowered:
        return ""
    folded = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(char for char in folded if not unicodedata.combining(char))
    return " ".join(without_accents.split())


def is_ascii_art_prompt(prompt: str) -> bool:
    normalized = _normalize_ascii_prompt(prompt)
    if not normalized:
        return False
    if "arte ascii" in normalized or "ascii art" in normalized:
        return True
    # Detecta "ascii" como palavra isolada (ex: "me faz uma ascii de ...")
    if " ascii " in normalized or normalized.startswith("ascii "):
        return True
    return False


def extract_ascii_subject(prompt: str) -> str:
    normalized = _normalize_ascii_prompt(prompt)
    if not normalized or not is_ascii_art_prompt(normalized):
        return ""

    # Remove prefixo "byte" se presente
    candidate = re.sub(r"^byte\s+", "", normalized, count=1)
    # Remove verbos de pedido
    candidate = re.sub(
        r"^(?:me\s+)?(?:faz(?:er)?|faca|gera(?:r)?|manda|quero)\s+(?:uma\s+)?",
        "",
        candidate,
        count=1,
    )
    # Remove marcadores de arte ASCII
    candidate = re.sub(r"^(?:arte\s+ascii|ascii\s+art|ascii)\b", "", candidate, count=1).strip()
    # Remove preposições
    candidate = re.sub(r"^(?:de|do|da|dos|das|sobre)\b", "", candidate, count=1).strip()
    candidate = candidate.strip(" ?!.,:;")
    if candidate in {"", "pfv", "por favor"}:
        return ""
    return candidate


def is_movie_fact_sheet_prompt(prompt: str) -> bool:
    lowered = (prompt or "").lower()
    return bool(MOVIE_FACT_SHEET_PATTERN.search(lowered))


def is_intro_prompt(prompt: str) -> bool:
    normalized = " ".join((prompt or "").lower().split()).strip(" ?!.,:")
    if not normalized:
        return False
    exact_triggers = {
        "se apresente",
        "apresente se",
        "apresente-se",
        "quem e voce",
        "quem e vc",
        "quem e o byte",
        "o que voce faz",
    }
    if normalized in exact_triggers:
        return True
    return normalized.startswith("se apresente")


def build_intro_reply() -> str:
    global _intro_template_index
    template = BYTE_INTRO_TEMPLATES[_intro_template_index % len(BYTE_INTRO_TEMPLATES)]
    _intro_template_index += 1
    return template


def is_current_events_prompt(prompt: str) -> bool:
    lowered = (prompt or "").lower()
    return any(hint in lowered for hint in CURRENT_EVENTS_HINT_TERMS)


def is_high_risk_current_events_prompt(prompt: str) -> bool:
    lowered = (prompt or "").lower()
    return any(hint in lowered for hint in HIGH_RISK_CURRENT_EVENTS_TERMS)


def is_serious_technical_prompt(prompt: str) -> bool:
    normalized = " ".join((prompt or "").lower().split()).strip(" ?!.,:")
    if len(normalized) < 24:
        return False
    has_technical_signal = any(term in normalized for term in SERIOUS_TECH_TERMS) or any(
        term in normalized for term in COMPLEX_TECH_HINT_TERMS
    )
    if not has_technical_signal:
        return False
    has_relevance_signal = any(
        term in normalized for term in RELEVANCE_HINT_TERMS
    ) or is_current_events_prompt(normalized)
    return has_relevance_signal


def is_follow_up_prompt(prompt: str) -> bool:
    normalized = " ".join((prompt or "").lower().split()).strip(" ?!.,:")
    if not normalized:
        return False
    if normalized in {"e agora", "e ai", "e aí", "e esse", "e essa", "e ele", "e ela"}:
        return True
    for term in FOLLOW_UP_HINT_TERMS:
        boundary_pattern = rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)"
        if re.search(boundary_pattern, normalized):
            return True
    if normalized.startswith(("e ", "entao ", "então ")) and len(normalized.split()) <= 7:
        return True
    words = normalized.split()
    if len(words) <= 5 and any(word in {"isso", "ele", "ela", "esse", "essa"} for word in words):
        return True
    return False
