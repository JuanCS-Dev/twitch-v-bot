"""DuckDuckGo web search module for current events grounding."""

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger("ByteBot")

WEB_SEARCH_TIMEOUT_SECONDS = 8.0
WEB_SEARCH_MAX_RESULTS = 3


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    snippet: str
    url: str


async def search_web(
    query: str,
    max_results: int = WEB_SEARCH_MAX_RESULTS,
) -> list[WebSearchResult]:
    """Search DuckDuckGo for current information. Returns empty list on failure."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_ddg_search_sync, clean_query, max_results),
            timeout=WEB_SEARCH_TIMEOUT_SECONDS,
        )
        return results
    except asyncio.TimeoutError:
        logger.warning("DDG search timeout for query: %.80s", clean_query)
        return []
    except Exception as error:
        logger.warning("DDG search error: %s", error)
        return []


def _ddg_search_sync(query: str, max_results: int) -> list[WebSearchResult]:
    """Synchronous DDG search wrapper (runs in thread).

    Strategy:
    1. news() — best for current events, works with PT-BR
    2. text() fallback — if news returns empty
    3. Rate limit handling — catches RatelimitException gracefully
    """
    from duckduckgo_search import DDGS  # lazy import

    results: list[WebSearchResult] = []
    try:
        with DDGS() as ddgs:
            # Primary: news search (works with PT-BR + current events)
            for item in ddgs.news(query, max_results=max_results):
                title = (item.get("title") or "").strip()
                snippet = (item.get("body") or "").strip()
                url = (item.get("url") or item.get("href") or "").strip()
                if snippet:
                    results.append(WebSearchResult(title=title, snippet=snippet, url=url))
    except Exception as e:
        logger.warning("DDG news() failed: %s", e)

    # Fallback: text search if news returned nothing
    if not results:
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    title = (item.get("title") or "").strip()
                    snippet = (item.get("body") or "").strip()
                    url = (item.get("href") or "").strip()
                    if snippet:
                        results.append(WebSearchResult(title=title, snippet=snippet, url=url))
        except Exception as e:
            logger.warning("DDG text() fallback failed: %s", e)

    return results


def format_search_context(results: list[WebSearchResult]) -> str:
    """Format search results for injection into LLM prompt."""
    if not results:
        return ""

    lines = [
        "[CONTEXTO WEB ATUALIZADO — OBRIGATORIO USAR ESTES DADOS NA RESPOSTA]",
        "Os dados abaixo foram obtidos via DuckDuckGo agora e sao a fonte mais recente disponivel.",
    ]
    for i, result in enumerate(results, 1):
        source = result.url.split("/")[2] if "/" in result.url else result.url
        lines.append(f"{i}. {result.snippet} (Fonte: {source})")
    lines.append(
        "[FIM DO CONTEXTO WEB — RESPONDA USANDO EXCLUSIVAMENTE ESTES DADOS. "
        "NAO USE SEU KNOWLEDGE CUTOFF.]"
    )
    return "\n".join(lines)
