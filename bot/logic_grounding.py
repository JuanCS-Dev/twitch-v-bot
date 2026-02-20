from typing import Any, TypedDict

from bot.logic_constants import MAX_GROUNDING_QUERIES, MAX_GROUNDING_URLS


class GroundingMetadata(TypedDict):
    enabled: bool
    has_grounding_signal: bool
    query_count: int
    source_count: int
    chunk_count: int
    web_search_queries: list[str]
    source_urls: list[str]


def empty_grounding_metadata(enabled: bool = False) -> GroundingMetadata:
    return {
        "enabled": bool(enabled),
        "has_grounding_signal": False,
        "query_count": 0,
        "source_count": 0,
        "chunk_count": 0,
        "web_search_queries": [],
        "source_urls": [],
    }


def _read_field(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _append_unique_text(values: list[str], raw_value: Any, max_items: int) -> None:
    normalized = " ".join(str(raw_value or "").split()).strip()
    if not normalized:
        return
    if normalized in values:
        return
    values.append(normalized)
    if len(values) > max_items:
        del values[max_items:]


def extract_grounding_metadata(response: Any, use_grounding: bool) -> GroundingMetadata:
    metadata = empty_grounding_metadata(enabled=use_grounding)
    candidates = _read_field(response, "candidates", []) or []
    if not candidates:
        return metadata

    web_search_queries: list[str] = []
    source_urls: list[str] = []
    chunk_count = 0

    for candidate in candidates:
        grounding = _read_field(candidate, "grounding_metadata")
        if grounding is not None:
            for query in _read_field(grounding, "web_search_queries", []) or []:
                _append_unique_text(web_search_queries, query, max_items=MAX_GROUNDING_QUERIES)

            grounding_chunks = _read_field(grounding, "grounding_chunks", []) or []
            chunk_count += len(grounding_chunks)
            for chunk in grounding_chunks:
                web_chunk = _read_field(chunk, "web")
                uri = _read_field(web_chunk, "uri", "") if web_chunk is not None else ""
                _append_unique_text(source_urls, uri, max_items=MAX_GROUNDING_URLS)

        citation_metadata = _read_field(candidate, "citation_metadata")
        citations = _read_field(citation_metadata, "citations", []) if citation_metadata is not None else []
        for citation in citations or []:
            _append_unique_text(source_urls, _read_field(citation, "uri", ""), max_items=MAX_GROUNDING_URLS)

    metadata["web_search_queries"] = web_search_queries
    metadata["source_urls"] = source_urls
    metadata["chunk_count"] = max(0, int(chunk_count))
    metadata["query_count"] = len(web_search_queries)
    metadata["source_count"] = len(source_urls)
    metadata["has_grounding_signal"] = bool(web_search_queries or source_urls or chunk_count > 0)
    return metadata


def has_grounding_signal(metadata: dict[str, Any] | None) -> bool:
    if not metadata:
        return False
    if bool(metadata.get("has_grounding_signal")):
        return True
    return bool(
        metadata.get("web_search_queries")
        or metadata.get("source_urls")
        or int(metadata.get("chunk_count", 0) or 0) > 0
    )


def extract_response_text(response: Any) -> str:
    direct_text = getattr(response, "text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        text_parts = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                text_parts.append(part_text.strip())
        if text_parts:
            return "\n".join(text_parts).strip()
    return ""
