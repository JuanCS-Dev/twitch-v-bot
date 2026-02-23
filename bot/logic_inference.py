import asyncio
import logging
from typing import Any, Literal, overload

from bot.logic_constants import (
    EMPTY_RESPONSE_FALLBACK,
    MAX_REPLY_LENGTH,
    MAX_REPLY_LINES,
    MODEL_RATE_LIMIT_BACKOFF_SECONDS,
    MODEL_RATE_LIMIT_MAX_RETRIES,
    MODEL_TEMPERATURE,
    UNSTABLE_CONNECTION_FALLBACK,
)
from bot.logic_context import build_dynamic_prompt, build_system_instruction, enforce_reply_limits
from bot.logic_grounding import (
    GroundingMetadata,
    empty_grounding_metadata,
)
from bot.observability import observability
from bot.web_search import format_search_context, search_web

logger = logging.getLogger("ByteBot")


def is_rate_limited_inference_error(error: Exception) -> bool:
    message = str(error).lower()
    return "429" in message or "rate limit" in message


def is_timeout_inference_error(error: Exception) -> bool:
    if isinstance(error, asyncio.TimeoutError):
        return True
    message = str(error).lower()
    return "timed out" in message or "timeout" in message


def _extract_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)


def _select_model(enable_grounding: bool, is_serious: bool) -> str:
    """Select the optimal Nebius model for the request type."""
    from bot.runtime_config import NEBIUS_MODEL_DEFAULT, NEBIUS_MODEL_REASONING, NEBIUS_MODEL_SEARCH

    if enable_grounding:
        return NEBIUS_MODEL_SEARCH
    if is_serious:
        return NEBIUS_MODEL_REASONING
    return NEBIUS_MODEL_DEFAULT


def _extract_search_query(user_msg: str) -> str:
    """Extract a clean search query from the user message.

    Strips LLM instruction noise, keeps the factual question core.
    """
    clean = (user_msg or "").strip()
    # If the message has embedded instructions (from build_llm_enhanced_prompt),
    # use only the first line which is the actual user question.
    if "\n" in clean:
        clean = clean.split("\n")[0].strip()
    # Cap length for DDG
    if len(clean) > 200:
        clean = clean[:200].rsplit(" ", 1)[0]
    return clean


def _build_grounding_metadata(
    results: list[Any],
    enabled: bool,
) -> GroundingMetadata:
    """Build real grounding metadata from DDG search results."""
    if not results:
        return empty_grounding_metadata(enabled=enabled)
    return {
        "enabled": enabled,
        "has_grounding_signal": True,
        "query_count": 1,
        "source_count": len(results),
        "chunk_count": len(results),
        "web_search_queries": [results[0].snippet[:80] if results else ""],
        "source_urls": [r.url for r in results if r.url],
    }


@overload
async def agent_inference(
    user_msg: str,
    author_name: str,
    client: Any,
    context: Any,
    enable_grounding: bool = False,
    enable_live_context: bool = True,
    max_lines: int = MAX_REPLY_LINES,
    max_length: int = MAX_REPLY_LENGTH,
    return_metadata: Literal[False] = False,
) -> str: ...


@overload
async def agent_inference(
    user_msg: str,
    author_name: str,
    client: Any,
    context: Any,
    enable_grounding: bool = False,
    enable_live_context: bool = True,
    max_lines: int = MAX_REPLY_LINES,
    max_length: int = MAX_REPLY_LENGTH,
    *,
    return_metadata: Literal[True],
) -> tuple[str, GroundingMetadata]: ...


async def agent_inference(
    user_msg: str,
    author_name: str,
    client: Any,
    context: Any,
    enable_grounding: bool = False,
    enable_live_context: bool = True,
    max_lines: int = MAX_REPLY_LINES,
    max_length: int = MAX_REPLY_LENGTH,
    return_metadata: bool = False,
) -> str | tuple[str, GroundingMetadata]:
    from bot.logic_constants import MODEL_INPUT_COST_PER_1M_USD, MODEL_OUTPUT_COST_PER_1M_USD

    if not user_msg:
        if return_metadata:
            return "", empty_grounding_metadata(enabled=False)
        return ""

    # --- Web Search (DDG) para current events ---
    search_results: list[Any] = []
    if enable_grounding:
        search_query = _extract_search_query(user_msg)
        search_results = await search_web(search_query)

    grounding_metadata = _build_grounding_metadata(search_results, enabled=enable_grounding)

    # --- Model selection ---
    is_serious = not enable_grounding and len(user_msg) >= 40
    model = _select_model(enable_grounding, is_serious)

    # --- Build messages ---
    system_instr = build_system_instruction(context)
    user_prompt = build_dynamic_prompt(
        user_msg,
        author_name,
        context,
        include_live_context=enable_live_context,
    )

    # Inject search context into system prompt
    if search_results:
        search_context = format_search_context(search_results)
        system_instr += f"\n\n{search_context}"

    messages = [
        {"role": "system", "content": system_instr},
        {"role": "user", "content": user_prompt}
    ]

    for attempt in range(MODEL_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat.completions.create,
                    model=model,
                    messages=messages,
                    temperature=MODEL_TEMPERATURE,
                    max_tokens=2048,
                ),
                timeout=120.0,
            )

            input_tokens, output_tokens = _extract_usage(response)
            if input_tokens > 0 or output_tokens > 0:
                cost = (input_tokens / 1_000_000.0) * MODEL_INPUT_COST_PER_1M_USD + \
                       (output_tokens / 1_000_000.0) * MODEL_OUTPUT_COST_PER_1M_USD

                observability.record_token_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=cost,
                )

            if not response.choices:
                logger.warning("Nebius retornou resposta sem escolhas (model=%s).", model)
                break

            reply_text = response.choices[0].message.content
            if reply_text:
                final_reply = enforce_reply_limits(reply_text, max_lines=max_lines, max_length=max_length)
                if return_metadata:
                    return final_reply, grounding_metadata
                return final_reply

            break
        except Exception as error:
            if is_timeout_inference_error(error):
                logger.warning("Inference timeout (attempt %d, model=%s).", attempt + 1, model)
                if attempt >= MODEL_RATE_LIMIT_MAX_RETRIES:
                    if return_metadata:
                        return UNSTABLE_CONNECTION_FALLBACK, empty_grounding_metadata(enabled=False)
                    return UNSTABLE_CONNECTION_FALLBACK
                continue

            if is_rate_limited_inference_error(error) and attempt < MODEL_RATE_LIMIT_MAX_RETRIES:
                backoff_seconds = MODEL_RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
                logger.warning("Inference rate-limited. Retrying in %.2fs (%d/%d).", backoff_seconds, attempt + 1, MODEL_RATE_LIMIT_MAX_RETRIES + 1)
                await asyncio.sleep(backoff_seconds)
                continue

            logger.error("Inference Error (model=%s): %s", model, error)
            if return_metadata:
                return UNSTABLE_CONNECTION_FALLBACK, empty_grounding_metadata(enabled=False)
            return UNSTABLE_CONNECTION_FALLBACK

    if return_metadata:
        return EMPTY_RESPONSE_FALLBACK, empty_grounding_metadata(enabled=False)
    return EMPTY_RESPONSE_FALLBACK
