import os
import re

from bot.logic import BOT_BRAND, MAX_REPLY_LINES, enforce_reply_limits

BYTE_TRIGGER = os.environ.get("BYTE_TRIGGER", BOT_BRAND).strip().lower() or "byte"
BYTE_HELP_MESSAGE = (
    "Byte entende chat natural. Acione com byte/@byte/!byte + pergunta. Atalhos: ajuda | se apresente | ficha tecnica <filme> | status."
)
BYTE_TRIGGER_PATTERN = re.compile(rf"^\s*[@!]?(?:{re.escape(BYTE_TRIGGER)})\b[\s,:-]*(.*)$", re.IGNORECASE)
MOVIE_FACT_SHEET_PATTERN = re.compile(r"ficha\s*t[eé]cnica", re.IGNORECASE)
MOVIE_TITLE_QUOTE_PATTERN = re.compile(r"[\"'`](?P<title>[^\"'`]{2,120})[\"'`]")
CURRENT_EVENTS_HINT_TERMS = (
    "situacao atual",
    "situação atual",
    "como esta",
    "como está",
    "atualizacao",
    "atualização",
    "agora",
    "hoje",
)
FOLLOW_UP_HINT_TERMS = (
    "e agora",
    "e ai",
    "e aí",
    "e ele",
    "e ela",
    "e isso",
    "e esse",
    "e essa",
    "sobre isso",
    "sobre ele",
    "sobre ela",
    "detalha isso",
    "resume isso",
    "resuma isso",
)
BRIEF_STYLE_TERMS = ("resuma", "resumo", "curto", "curta", "1 linha", "uma linha", "tl;dr", "tldr")
ANALYTICAL_STYLE_TERMS = ("detalha", "aprofunda", "analisa", "compare", "comparar", "vs", "diferen", "prons", "contras")
PLAYFUL_STYLE_TERMS = ("zoa", "zoeira", "meme", "engracad", "brinca", "tirada")
QUESTION_OPENING_TERMS = (
    "existe",
    "tem",
    "ha",
    "há",
    "qual",
    "quais",
    "como",
    "porque",
    "por que",
    "onde",
    "quando",
    "quem",
    "pode",
    "vale",
    "compensa",
    "recomenda",
    "recomendacao",
    "recomendação",
    "indica",
)
EXISTENCE_QUESTION_TERMS = ("existe", "tem", "ha", "há")
RECOMMENDATION_HINT_TERMS = ("recomenda", "recomendacao", "recomendação", "indica", "sugere", "lista", "melhores")
SERIOUS_TECH_TERMS = (
    "laminina",
    "parapleg",
    "medicina",
    "saude",
    "tratamento",
    "terapia",
    "pesquisa",
    "estudo",
    "cient",
    "neurolog",
    "biolog",
    "genet",
    "clinico",
    "evidencia",
    "paper",
)
COMPLEX_TECH_HINT_TERMS = (
    "como funciona",
    "mecanismo",
    "explica tecnicamente",
    "base cientifica",
    "protocolo",
    "metodologia",
    "efeitos",
    "riscos",
    "limites",
)
RELEVANCE_HINT_TERMS = (
    "relevante",
    "impacto",
    "hoje",
    "agora",
    "atual",
    "urgente",
    "importante",
    "cura",
)
MAX_CHAT_MESSAGE_LENGTH = 460
MULTIPART_SEPARATOR = "[BYTE_SPLIT]"
SERIOUS_REPLY_MAX_LINES = (MAX_REPLY_LINES * 2) + 1
SERIOUS_REPLY_MAX_LENGTH = (MAX_CHAT_MESSAGE_LENGTH * 2) + len(MULTIPART_SEPARATOR) + 2
BYTE_INTRO_TEMPLATES = (
    "Sou Byte: IA premium da live. Latencia baixa, cerebro afiado e zoeira calibrada. Digita 'byte ajuda'.",
    "Byte on. Modo high-tech + caos controlado: resposta rapida, precisa e sem textao. Usa 'byte ajuda'.",
    "Copiloto oficial do chat: contexto em tempo real, ficha tecnica na veia e humor fino. Manda 'byte ajuda'.",
    "Byte na pista. Se a pergunta vier torta, eu devolvo reta com classe e zoeira. Comandos em 'byte ajuda'.",
)

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
    return compact_message(enforce_reply_limits(text), max_len=MAX_CHAT_MESSAGE_LENGTH)


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


def build_verifiable_prompt(prompt: str, concise_mode: bool = True) -> str:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return clean_prompt

    is_current_events = is_current_events_prompt(clean_prompt)
    if not concise_mode:
        return (
            f"{clean_prompt}\n"
            "Instrucoes obrigatorias de confiabilidade: priorize fatos recentes e verificaveis. "
            f"{'Considere prioridade alta para acontecimentos de hoje/agora. ' if is_current_events else ''}"
            "Diferencie o que esta confirmado do que ainda e hipotese. "
            "Se houver ambiguidade no nome (ex.: Push/Punch/Posh), avise explicitamente e peca 1 link para confirmar. "
            "Se nao houver confirmacao forte, diga isso com clareza e solicite fonte."
        )

    if not is_current_events:
        return clean_prompt

    return (
        f"{clean_prompt}\n"
        "Instrucoes obrigatorias de confiabilidade: responda em ate 3 linhas e ate 280 caracteres. "
        "Use apenas fatos com confirmacao recente em fontes confiaveis. "
        "Se houver ambiguidade no nome (ex.: Push/Punch/Posh), avise explicitamente e peca 1 link para confirmar. "
        "Se nao houver confirmacao forte, responda exatamente: "
        "'Nao consegui verificar com confianca agora. Me manda 1 link/fonte no chat e eu resumo em 2 linhas.'"
    )


def is_serious_technical_prompt(prompt: str) -> bool:
    normalized = " ".join((prompt or "").lower().split()).strip(" ?!.,:")
    if len(normalized) < 24:
        return False

    has_technical_signal = any(term in normalized for term in SERIOUS_TECH_TERMS) or any(
        term in normalized for term in COMPLEX_TECH_HINT_TERMS
    )
    if not has_technical_signal:
        return False

    has_relevance_signal = any(term in normalized for term in RELEVANCE_HINT_TERMS) or is_current_events_prompt(normalized)
    return has_relevance_signal


def is_follow_up_prompt(prompt: str) -> bool:
    normalized = " ".join((prompt or "").lower().split()).strip(" ?!.,:")
    if not normalized:
        return False
    if normalized in {"e agora", "e ai", "e aí", "e esse", "e essa", "e ele", "e ela"}:
        return True
    if any(term in normalized for term in FOLLOW_UP_HINT_TERMS):
        return True

    words = normalized.split()
    if len(words) <= 5 and any(word in {"isso", "ele", "ela", "esse", "essa"} for word in words):
        return True
    return False


def build_research_priority_instruction(prompt: str) -> str:
    if not is_serious_technical_prompt(prompt):
        return ""
    return (
        "Instrucoes de pesquisa aprofundada: priorize evidencia recente (2025-2026) e fontes confiaveis "
        "(universidades, orgaos de saude, journals). "
        "Quando existir contexto em alta relacionado ao tema, incorpore esse contexto explicitamente. "
        "Se houver contribuicao relevante do Brasil no tema, mencione de forma objetiva."
    )


def build_direct_answer_instruction(prompt: str) -> str:
    normalized = " ".join((prompt or "").lower().split()).strip(" ?!.,:")
    if not normalized:
        return ""

    is_question = "?" in (prompt or "")
    starts_like_question = normalized.startswith(QUESTION_OPENING_TERMS)
    if not is_question and not starts_like_question:
        return ""

    instructions = [
        "Formato de resposta obrigatorio: responda a pergunta principal na primeira linha, sem introducao."
    ]
    if normalized.startswith(EXISTENCE_QUESTION_TERMS):
        instructions.append("Se for pergunta de existencia, comece com 'Sim,' ou 'Nao,'.")
    if any(term in normalized for term in RECOMMENDATION_HINT_TERMS):
        instructions.append("Se houver opcoes concretas, cite 1 a 3 nomes diretamente relevantes.")
    instructions.append("Evite texto generico e nao desvie do foco da pergunta.")
    return " ".join(instructions)


def build_adaptive_ai_instruction(prompt: str) -> str:
    lowered = (prompt or "").lower()
    if any(term in lowered for term in BRIEF_STYLE_TERMS):
        return "Estilo de resposta: ultra objetivo, no maximo 3 linhas."
    if any(term in lowered for term in ANALYTICAL_STYLE_TERMS):
        return "Estilo de resposta: analise pratica em ate 6 linhas, com 2 ou 3 pontos claros."
    if any(term in lowered for term in PLAYFUL_STYLE_TERMS):
        return "Estilo de resposta: humor leve e inteligente, sem perder precisao factual."
    return ""


def build_llm_enhanced_prompt(prompt: str) -> str:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return ""

    serious_mode = is_serious_technical_prompt(clean_prompt)
    enriched_prompt = build_verifiable_prompt(clean_prompt, concise_mode=not serious_mode)
    extra_instructions: list[str] = []

    direct_answer_instruction = build_direct_answer_instruction(clean_prompt)
    if direct_answer_instruction:
        extra_instructions.append(direct_answer_instruction)

    if is_follow_up_prompt(clean_prompt):
        extra_instructions.append(
            "Instrucoes de continuidade: trate esta pergunta como follow-up e resolva referencias vagas "
            "(ex.: ele, ela, isso) usando o historico recente do chat."
        )

    research_instruction = build_research_priority_instruction(clean_prompt)
    if research_instruction:
        extra_instructions.append(research_instruction)

    if serious_mode:
        extra_instructions.append(
            "Para tema tecnico serio e relevante, voce pode responder em 2 blocos no maximo. "
            f"Se usar 2 blocos, separe exatamente com a linha: {MULTIPART_SEPARATOR}. "
            "Cada bloco deve caber em um comentario de chat."
        )

    if not is_current_events_prompt(clean_prompt):
        adaptive_instruction = build_adaptive_ai_instruction(clean_prompt)
        if adaptive_instruction:
            extra_instructions.append(adaptive_instruction)

    if not extra_instructions:
        return enriched_prompt
    return f"{enriched_prompt}\n" + "\n".join(extra_instructions)


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
