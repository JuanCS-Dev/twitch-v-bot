import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bot.byte_semantics_base import (
    compact_message,
    is_current_events_prompt,
    is_high_risk_current_events_prompt,
)
from bot.byte_semantics_constants import (
    CONFIDENCE_LABEL_TERMS,
    CURRENT_EVENTS_DEFAULT_SOURCE,
    CURRENT_EVENTS_PENDING_SOURCE,
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_REPLY_LINES,
    QUALITY_SAFE_FALLBACK,
    SOURCE_ANCHOR_TERMS,
    TEMPORAL_ANCHOR_TERMS,
    UNCERTAINTY_HINT_TERMS,
)
from bot.logic import enforce_reply_limits, has_grounding_signal


def build_server_time_anchor_instruction(reference_utc_iso: str | None = None) -> str:
    now_utc_iso = (reference_utc_iso or "").strip()
    if not now_utc_iso:
        now_utc = datetime.now(timezone.utc)
        now_utc_iso = now_utc.isoformat(timespec="seconds").replace("+00:00", "Z")
    return f"Timestamp de referencia do servidor (UTC): {now_utc_iso}. Use esse horario para interpretar hoje/agora/nesta semana."


def build_verifiable_prompt(prompt: str, concise_mode: bool = True, server_time_instruction: str | None = None) -> str:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return clean_prompt
    is_current_events = is_current_events_prompt(clean_prompt)
    active_server_time_instruction = server_time_instruction or build_server_time_anchor_instruction()
    if not concise_mode:
        return (
            f"{clean_prompt}\n"
            f"{active_server_time_instruction} Instrucoes obrigatorias de confiabilidade: priorize fatos recentes e verificaveis. "
            f"{'Considere prioridade alta para acontecimentos de hoje/agora. ' if is_current_events else ''}"
            "Diferencie o que esta confirmado do que ainda e hipotese. "
            "Se houver ambiguidade no nome (ex.: Push/Punch/Posh), avise explicitamente e peca 1 link para confirmar. "
            "Se nao houver confirmacao forte, diga isso com clareza e solicite fonte."
        )
    if not is_current_events:
        return clean_prompt
    return (
        f"{clean_prompt}\n"
        f"{active_server_time_instruction} Instrucoes obrigatorias de confiabilidade: responda em ate 4 linhas curtas, densas e sem enrolacao. "
        "Use apenas fatos com confirmacao recente em fontes confiaveis. "
        "Inclua ancora temporal explicita (ex.: hoje, nesta semana, mes/ano) quando falar de status atual. "
        "Para noticia/anuncio atual, inclua no final: 'Confianca: alta|media|baixa' e 'Fonte: <origem confiavel>'. "
        "Diferencie o que esta confirmado do que ainda e rumor/hipotese. "
        "Se houver ambiguidade no nome (ex.: Push/Punch/Posh), avise explicitamente e peca 1 link para confirmar. "
        "Se nao houver confirmacao forte, responda exatamente: "
        f"'{QUALITY_SAFE_FALLBACK}'"
    )


def _extract_reference_utc_iso(server_time_instruction: str | None) -> str:
    text = (server_time_instruction or "").strip()
    if not text:
        return ""
    match = re.search(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\b", text)
    return match.group(1) if match else ""


def _extract_grounding_queries(grounding_metadata: dict | None) -> list[str]:
    if not isinstance(grounding_metadata, dict):
        return []
    queries = grounding_metadata.get("web_search_queries", [])
    if not isinstance(queries, list):
        return []
    return [str(query).strip() for query in queries if str(query or "").strip()]


def _extract_grounding_source_urls(grounding_metadata: dict | None) -> list[str]:
    if not isinstance(grounding_metadata, dict):
        return []
    source_urls = grounding_metadata.get("source_urls", [])
    if not isinstance(source_urls, list):
        return []
    return [str(source_url).strip() for source_url in source_urls if str(source_url or "").strip()]


def _build_grounding_source_line(grounding_metadata: dict | None) -> str:
    source_urls = _extract_grounding_source_urls(grounding_metadata)
    if source_urls:
        hosts: list[str] = []
        for source_url in source_urls:
            parsed_url = urlparse(source_url)
            host = parsed_url.netloc.lower().removeprefix("www.")
            if host and host not in hosts:
                hosts.append(host)
            if len(hosts) >= 2:
                break
        if hosts:
            return f"Fonte: DuckDuckGo em {', '.join(hosts)}."
    queries = _extract_grounding_queries(grounding_metadata)
    if queries:
        query_preview = compact_message(queries[0], max_len=90).strip().rstrip(" ,;:.")
        if query_preview:
            return f"Fonte: DuckDuckGo query: {query_preview}."
    return CURRENT_EVENTS_DEFAULT_SOURCE


def _is_confidence_line(line: str) -> bool:
    lowered = (line or "").strip().lower()
    return lowered.startswith(("confianca:", "confiança:"))


def _is_source_line(line: str) -> bool:
    lowered = (line or "").strip().lower()
    return lowered.startswith("fonte:")


def _is_temporal_line(line: str) -> bool:
    lowered = (line or "").strip().lower()
    return lowered.startswith("recorte temporal:")


def _split_non_empty_lines(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def _is_canonical_high_risk_fallback(answer: str) -> bool:
    lines = _split_non_empty_lines(answer)
    if not lines or lines[0].lower() != QUALITY_SAFE_FALLBACK.lower():
        return False
    lowered_lines = [line.lower() for line in lines]
    has_low_confidence = any(line.startswith(("confianca: baixa", "confiança: baixa")) for line in lowered_lines)
    has_pending_source = any(line == CURRENT_EVENTS_PENDING_SOURCE.lower() for line in lowered_lines)
    if not has_low_confidence or not has_pending_source:
        return False
    for line in lowered_lines[1:]:
        if _is_temporal_line(line) or _is_confidence_line(line) or _is_source_line(line):
            continue
        return False
    return True


def _fit_high_risk_current_events_reply(body_lines: list[str], confidence_line: str, source_line: str, temporal_line: str = "") -> str:
    normalized_body = [line.strip() for line in body_lines if line and line.strip()]
    tail_lines = [line.strip() for line in (temporal_line, confidence_line, source_line) if line and line.strip()]
    tail_text = "\n".join(tail_lines)
    if not tail_text:
        return enforce_reply_limits("\n".join(normalized_body))
    if not normalized_body:
        return tail_text
    max_body_lines = max(1, MAX_REPLY_LINES - len(tail_lines))
    max_body_length = MAX_CHAT_MESSAGE_LENGTH - len(tail_text) - 1
    if max_body_length <= 0:
        return tail_text[:MAX_CHAT_MESSAGE_LENGTH].strip()
    body_text = enforce_reply_limits("\n".join(normalized_body), max_lines=max_body_lines, max_length=max_body_length).strip()
    combined = f"{body_text}\n{tail_text}" if body_text else tail_text
    if len(combined) <= MAX_CHAT_MESSAGE_LENGTH:
        return combined
    compact_body = compact_message(" ".join(normalized_body), max_len=max_body_length).strip()
    combined = f"{compact_body}\n{tail_text}" if compact_body else tail_text
    if len(combined) <= MAX_CHAT_MESSAGE_LENGTH:
        return combined
    if max_body_length <= 0:
        return tail_text[:MAX_CHAT_MESSAGE_LENGTH].strip()
    cropped_body = compact_body[:max_body_length].rstrip(" ,;:")
    return f"{cropped_body}\n{tail_text}" if cropped_body else tail_text


def normalize_current_events_reply_contract(
    prompt: str,
    answer: str,
    server_time_instruction: str | None = None,
    grounding_metadata: dict | None = None,
) -> str:
    clean_prompt = (prompt or "").strip()
    clean_answer = (answer or "").strip()
    if not clean_prompt or not clean_answer or not is_current_events_prompt(clean_prompt):
        return clean_answer
    lines = _split_non_empty_lines(clean_answer)
    if not lines:
        lines = [" ".join(clean_answer.split())]
    merged_answer = "\n".join(lines)
    lowered_answer = merged_answer.lower()
    has_uncertainty = any(term in lowered_answer for term in UNCERTAINTY_HINT_TERMS)
    has_temporal_anchor = any(term in lowered_answer for term in TEMPORAL_ANCHOR_TERMS) or bool(
        re.search(r"\b20(2[5-9]|3[0-9])\b", lowered_answer)
    )
    reference_utc_iso = _extract_reference_utc_iso(server_time_instruction)
    added_temporal_line = ""
    high_risk_current_events = is_high_risk_current_events_prompt(clean_prompt)
    must_validate_grounding = grounding_metadata is not None
    grounding_signal_present = has_grounding_signal(grounding_metadata)
    if high_risk_current_events and has_uncertainty:
        return build_current_events_safe_fallback_reply(clean_prompt, server_time_instruction=server_time_instruction)
    if high_risk_current_events and must_validate_grounding and not grounding_signal_present:
        return build_current_events_safe_fallback_reply(clean_prompt, server_time_instruction=server_time_instruction)
    if not has_temporal_anchor and not has_uncertainty:
        added_temporal_line = f"Recorte temporal: {reference_utc_iso} UTC." if reference_utc_iso else "Recorte temporal: agora (UTC)."
        lines.append(added_temporal_line)
    if not high_risk_current_events:
        return "\n".join(lines)

    body_lines: list[str] = []
    confidence_line = ""
    source_line = ""
    for line in lines:
        if added_temporal_line and line.strip() == added_temporal_line:
            continue
        if _is_confidence_line(line):
            if not confidence_line:
                confidence_line = line.strip()
            continue
        if _is_source_line(line):
            if not source_line:
                source_line = line.strip()
            continue
        body_lines.append(line.strip())

    confidence_line = "Confianca: media"
    source_line = _build_grounding_source_line(grounding_metadata)
    return _fit_high_risk_current_events_reply(body_lines, confidence_line, source_line, temporal_line=added_temporal_line)


def build_current_events_safe_fallback_reply(prompt: str, server_time_instruction: str | None = None) -> str:
    clean_prompt = (prompt or "").strip()
    if not is_high_risk_current_events_prompt(clean_prompt):
        return QUALITY_SAFE_FALLBACK
    reference_utc_iso = _extract_reference_utc_iso(server_time_instruction)
    temporal_line = f"Recorte temporal: {reference_utc_iso} UTC." if reference_utc_iso else "Recorte temporal: agora (UTC)."
    return "\n".join([QUALITY_SAFE_FALLBACK, temporal_line, "Confianca: baixa", CURRENT_EVENTS_PENDING_SOURCE])


def has_current_events_source_anchor(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in SOURCE_ANCHOR_TERMS)


def has_current_events_confidence_label(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in CONFIDENCE_LABEL_TERMS)


def has_current_events_temporal_anchor(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in TEMPORAL_ANCHOR_TERMS) or bool(re.search(r"\b20(2[5-9]|3[0-9])\b", lowered))


def has_current_events_uncertainty(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in UNCERTAINTY_HINT_TERMS)


def is_canonical_high_risk_fallback(answer: str) -> bool:
    return _is_canonical_high_risk_fallback(answer)
