import re

from bot.byte_semantics_base import (
    is_current_events_prompt,
    is_follow_up_prompt,
    is_high_risk_current_events_prompt,
    is_serious_technical_prompt,
)
from bot.byte_semantics_constants import (
    ANALYTICAL_STYLE_TERMS,
    BRIEF_STYLE_TERMS,
    EXISTENCE_QUESTION_TERMS,
    GENERIC_RESPONSE_HINT_TERMS,
    OVERCONFIDENT_HINT_TERMS,
    PLAYFUL_STYLE_TERMS,
    QUALITY_SAFE_FALLBACK,
    QUALITY_STOPWORDS,
    QUESTION_OPENING_TERMS,
    RECOMMENDATION_HINT_TERMS,
    REWRITE_REASON_GUIDANCE,
)
from bot.byte_semantics_current_events import (
    build_server_time_anchor_instruction,
    build_verifiable_prompt,
    has_current_events_confidence_label,
    has_current_events_source_anchor,
    has_current_events_temporal_anchor,
    has_current_events_uncertainty,
    is_canonical_high_risk_fallback,
)


def build_research_priority_instruction(prompt: str) -> str:
    if not is_serious_technical_prompt(prompt):
        return ""
    return (
        "Instrucoes de pesquisa aprofundada: priorize evidencia recente (2025-2026) e fontes confiaveis "
        "(universidades, orgaos de saude, journals). "
        "Quando existir contexto em alta relacionado ao tema, incorpore esse contexto explicitamente. "
        "Se houver contribuicao relevante do Brasil no tema, mencione de forma objetiva."
    )


def build_anti_generic_contract_instruction(prompt: str) -> str:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return ""
    return (
        "Contrato anti-generico: responda o caso especifico da pergunta, sem texto enciclopedico amplo. "
        "Nao use frases vagas como 'depende', 'em geral' ou 'cada caso' sem antes entregar resposta objetiva."
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
        return "Estilo de resposta: analise pratica em ate 4 linhas, com 2 ou 3 pontos claros."
    if any(term in lowered for term in PLAYFUL_STYLE_TERMS):
        return "Estilo de resposta: humor leve e inteligente, sem perder precisao factual."
    return ""


def _quality_tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    normalized: list[str] = []
    for token in tokens:
        if len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        normalized.append(token)
    return normalized


def _extract_focus_terms(prompt: str, max_terms: int = 10) -> list[str]:
    terms: list[str] = []
    for token in _quality_tokenize(prompt):
        if token in QUALITY_STOPWORDS:
            continue
        if token.isdigit() and len(token) < 4:
            continue
        if token in terms:
            continue
        terms.append(token)
        if len(terms) >= max_terms:
            break
    return terms


def _count_focus_overlap(focus_terms: list[str], answer_tokens: set[str]) -> int:
    if not focus_terms or not answer_tokens:
        return 0
    overlap = 0
    for focus_term in focus_terms:
        if focus_term in answer_tokens:
            overlap += 1
            continue
        focus_prefix = focus_term[:5]
        if len(focus_prefix) < 4:
            continue
        if any(
            token.startswith(focus_prefix) or focus_term.startswith(token[:5])
            for token in answer_tokens
            if len(token) >= 4
        ):
            overlap += 1
    return overlap


def build_quality_prompt_script(prompt: str, server_time_instruction: str | None = None) -> str:
    clean_prompt = (prompt or "").strip()
    is_current = is_current_events_prompt(clean_prompt)
    is_high_risk_current = is_high_risk_current_events_prompt(clean_prompt)
    active_server_time_instruction = (
        server_time_instruction or build_server_time_anchor_instruction()
    )
    lines = [
        "Script de qualidade obrigatorio:\n"
        "1) Responda a pergunta principal na primeira linha, sem introducao.\n"
        "2) Inclua 1 ou 2 detalhes concretos ligados ao pedido (nome, data, local, obra ou numero).\n"
        "3) Maximize densidade informacional: cada linha precisa trazer dado novo.\n"
        "4) Corte frases vagas/repetitivas que nao agregam informacao.\n"
        "5) Se houver baixa confianca, admita incerteza de forma explicita e peca 1 fonte."
    ]
    if is_current:
        lines.append(f"6) {active_server_time_instruction}")
        lines.append(
            "7) Para tema atual, separe explicitamente o que esta confirmado agora e o que ainda e rumor."
        )
        if is_high_risk_current:
            lines.append(
                "8) Para noticia/anuncio atual, inclua as linhas finais: 'Confianca: alta|media|baixa' e 'Fonte: ...'."
            )
            lines.append(
                f"9) Se faltar confirmacao robusta, use exatamente: '{QUALITY_SAFE_FALLBACK}'"
            )
        else:
            lines.append(
                f"8) Se faltar confirmacao robusta, use exatamente: '{QUALITY_SAFE_FALLBACK}'"
            )
    else:
        lines.append("6) Mantenha foco total no objeto perguntado.")
        lines.append("7) Evite qualquer afirmacao absoluta sem base verificavel.")
    lines.append(
        "10) Nao termine com pergunta aberta, exceto se faltar dado essencial para responder."
    )
    return "\n".join(lines)


def is_low_quality_answer(prompt: str, answer: str) -> tuple[bool, str]:
    clean_prompt = " ".join((prompt or "").split()).strip()
    answer_lines = [
        line.strip()
        for line in (answer or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    if not answer_lines:
        return True, "resposta_vazia"
    clean_answer = "\n".join(answer_lines)
    compact_answer = " ".join(clean_answer.split()).strip()
    if not compact_answer:
        return True, "resposta_vazia"

    normalized_prompt = " ".join(clean_prompt.lower().split()).strip(" ?!.,:")
    lowered_answer = clean_answer.lower()
    lowered_compact_answer = compact_answer.lower()
    generic_hits = sum(1 for term in GENERIC_RESPONSE_HINT_TERMS if term in lowered_answer)
    overconfident_hits = sum(1 for term in OVERCONFIDENT_HINT_TERMS if term in lowered_answer)
    has_uncertainty = has_current_events_uncertainty(clean_answer)
    has_temporal_anchor = has_current_events_temporal_anchor(clean_answer)
    has_source_anchor = has_current_events_source_anchor(clean_answer)
    has_confidence_label = has_current_events_confidence_label(clean_answer)

    focus_terms = _extract_focus_terms(clean_prompt)
    answer_tokens = set(_quality_tokenize(compact_answer))
    overlap_count = _count_focus_overlap(focus_terms, answer_tokens)
    first_line = answer_lines[0].strip().lower()

    starts_too_generic = lowered_answer.startswith(
        ("depende", "em geral", "de forma geral", "geralmente", "na maioria dos casos")
    )
    prompt_is_complex = len(clean_prompt) >= 40
    answer_is_short = len(clean_answer) < 70
    follow_up_prompt = is_follow_up_prompt(clean_prompt)
    current_events_prompt = is_current_events_prompt(clean_prompt)
    current_events_high_risk = is_high_risk_current_events_prompt(clean_prompt)
    existence_question = normalized_prompt.startswith(EXISTENCE_QUESTION_TERMS)

    if (
        "conexao com o modelo instavel" in lowered_answer
        or "conexão com o modelo instável" in lowered_answer
    ):
        return True, "modelo_indisponivel"
    if generic_hits >= 2 and overlap_count <= 1:
        return True, "resposta_generica"
    if starts_too_generic and overlap_count <= 1:
        return True, "abertura_generica"
    if existence_question and not first_line.startswith(
        ("sim", "nao", "não", "existe", "tem", "ha ", "há ")
    ):
        return True, "resposta_existencia_sem_posicao"
    if prompt_is_complex and answer_is_short and overlap_count <= 1:
        return True, "resposta_curta_sem_substancia"
    if len(focus_terms) >= 3 and overlap_count == 0 and (generic_hits > 0 or answer_is_short):
        return True, "off_topic"
    if (
        current_events_prompt
        and not follow_up_prompt
        and len(clean_prompt) >= 18
        and not has_temporal_anchor
        and not has_uncertainty
    ):
        return True, "tema_atual_sem_ancora_temporal"
    if (
        current_events_high_risk
        and has_uncertainty
        and not is_canonical_high_risk_fallback(clean_answer)
    ):
        return True, "incerteza_fora_fallback_canonico"
    if current_events_high_risk and not follow_up_prompt and not has_confidence_label:
        return True, "tema_atual_sem_confianca_explicita"
    if (
        current_events_high_risk
        and not follow_up_prompt
        and not has_uncertainty
        and not has_source_anchor
        and len(clean_answer) >= 120
    ):
        return True, "tema_atual_sem_base_verificavel"
    if (
        current_events_prompt
        and has_uncertainty
        and "link/fonte" not in lowered_answer
        and "fonte" not in lowered_answer
    ):
        return True, "incerteza_sem_pedido_de_fonte"
    if lowered_compact_answer.endswith("?") and not has_uncertainty and not follow_up_prompt:
        return True, "termina_com_pergunta_aberta"
    if overconfident_hits > 0 and not has_temporal_anchor and not has_uncertainty:
        return True, "confianca_absoluta_sem_base"
    return False, ""


def build_quality_rewrite_prompt(
    prompt: str, draft_answer: str, reason: str, server_time_instruction: str | None = None
) -> str:
    clean_prompt = (prompt or "").strip()
    clean_draft = (draft_answer or "").strip()
    safe_reason = (reason or "qualidade_insuficiente").strip()
    active_server_time_instruction = (
        server_time_instruction or build_server_time_anchor_instruction()
    )
    reason_fix = REWRITE_REASON_GUIDANCE.get(
        safe_reason, "Ajuste a resposta para ficar objetiva, verificavel e aderente a pergunta."
    )
    return (
        f"Pergunta original: {clean_prompt}\n"
        f"Rascunho anterior reprovado ({safe_reason}): {clean_draft}\n"
        "Reescreva para chat Twitch com as regras:\n"
        f"- {active_server_time_instruction}\n"
        f"- Correcao alvo: {reason_fix}\n"
        "- Primeira linha responde direto.\n"
        "- No maximo 4 linhas.\n"
        "- Alta densidade: cada linha deve adicionar informacao nova.\n"
        "- Inclua 1 ou 2 fatos concretos e relevantes.\n"
        "- Para tema atual, diferencie confirmado agora vs rumor.\n"
        "- Nao termine com pergunta aberta.\n"
        "- Nao use frase vaga/generica.\n"
        "- Se nao der para confirmar, use exatamente: "
        f"'{QUALITY_SAFE_FALLBACK}'"
    )


def build_llm_enhanced_prompt(prompt: str, server_time_instruction: str | None = None) -> str:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return ""

    serious_mode = is_serious_technical_prompt(clean_prompt)
    active_server_time_instruction = (
        server_time_instruction or build_server_time_anchor_instruction()
    )
    enriched_prompt = build_verifiable_prompt(
        clean_prompt,
        concise_mode=not serious_mode,
        server_time_instruction=active_server_time_instruction,
    )
    extra_instructions: list[str] = []
    if active_server_time_instruction not in enriched_prompt:
        extra_instructions.append(active_server_time_instruction)

    anti_generic_instruction = build_anti_generic_contract_instruction(clean_prompt)
    if anti_generic_instruction:
        extra_instructions.append(anti_generic_instruction)
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
            "Para tema tecnico serio e relevante, responda em uma unica mensagem. "
            "Contrato obrigatorio: no maximo 4 linhas, alta densidade, sem separador de multiparte."
        )

    if not is_current_events_prompt(clean_prompt):
        adaptive_instruction = build_adaptive_ai_instruction(clean_prompt)
        if adaptive_instruction:
            extra_instructions.append(adaptive_instruction)

    quality_script = build_quality_prompt_script(
        clean_prompt, server_time_instruction=active_server_time_instruction
    )
    if quality_script:
        extra_instructions.append(quality_script)

    if not extra_instructions:
        return enriched_prompt
    return f"{enriched_prompt}\n" + "\n".join(extra_instructions)
