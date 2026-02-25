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
from bot.utils.retry import retry_async
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
    if "\n" in clean:
        clean = clean.split("\n")[0].strip()
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


async def _fetch_search_results(
    user_msg: str, enable_grounding: bool
) -> tuple[list[Any], GroundingMetadata]:
    """Fetch search results and build grounding metadata.

    Returns tuple of (search_results, grounding_metadata).
    """
    search_results: list[Any] = []
    if enable_grounding:
        search_query = _extract_search_query(user_msg)
        search_results = await search_web(search_query)

    grounding_metadata = _build_grounding_metadata(search_results, enabled=enable_grounding)
    return search_results, grounding_metadata


def _build_messages(
    user_msg: str,
    author_name: str,
    context: Any,
    enable_live_context: bool,
    search_results: list[Any],
) -> list[dict[str, str]]:
    """Build the message payload for the LLM API."""
    system_instr = build_system_instruction(context)
    user_prompt = build_dynamic_prompt(
        user_msg,
        author_name,
        context,
        include_live_context=enable_live_context,
    )

    if search_results:
        search_context = format_search_context(search_results)
        system_instr += f"\n\n{search_context}"

    return [
        {"role": "system", "content": system_instr},
        {"role": "user", "content": user_prompt},
    ]


def _record_token_usage(response: Any) -> None:
    """Record token usage metrics to observability."""
    from bot.logic_constants import MODEL_INPUT_COST_PER_1M_USD, MODEL_OUTPUT_COST_PER_1M_USD

    input_tokens, output_tokens = _extract_usage(response)
    if input_tokens > 0 or output_tokens > 0:
        cost = (input_tokens / 1_000_000.0) * MODEL_INPUT_COST_PER_1M_USD + (
            output_tokens / 1_000_000.0
        ) * MODEL_OUTPUT_COST_PER_1M_USD

        observability.record_token_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
        )


async def _execute_inference(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> Any:
    """Execute a single inference call to the LLM."""
    return await asyncio.wait_for(
        asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=messages,
            temperature=MODEL_TEMPERATURE,
            max_tokens=2048,
        ),
        timeout=120.0,
    )


def _is_retryable_inference_error(error: Exception) -> bool:
    """Check if an inference error should trigger a retry."""
    if is_timeout_inference_error(error):
        return True
    if is_rate_limited_inference_error(error):
        return True
    return False


def _on_retry_log(error: Exception, attempt: int) -> None:
    """Log retry attempts for inference errors."""
    if is_rate_limited_inference_error(error):
        backoff = MODEL_RATE_LIMIT_BACKOFF_SECONDS * attempt
        logger.warning(
            "Inference rate-limited. Retrying in %.2fs (%d/%d).",
            backoff,
            attempt,
            MODEL_RATE_LIMIT_MAX_RETRIES + 1,
        )
    else:
        logger.warning("Inference timeout (attempt %d, model=?).", attempt)


async def _execute_inference_with_retry(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> Any:
    """Execute inference with retry logic for rate limits and timeouts."""
    last_error: Exception | None = None

    for attempt in range(MODEL_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            response = await _execute_inference(client, model, messages)
            _record_token_usage(response)
            return response
        except Exception as e:
            last_error = e

            if not _is_retryable_inference_error(e):
                raise

            if attempt >= MODEL_RATE_LIMIT_MAX_RETRIES:
                break

            delay = MODEL_RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
            _on_retry_log(e, attempt + 1)
            await asyncio.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("Unexpected error in inference retry loop")


def _process_response(
    response: Any,
    max_lines: int,
    max_length: int,
) -> str | None:
    """Process the LLM response and extract the reply text."""
    if not response.choices:
        logger.warning("Nebius retornou resposta sem escolhas.")
        return None

    reply_text = response.choices[0].message.content
    if reply_text:
        return enforce_reply_limits(reply_text, max_lines=max_lines, max_length=max_length)
    return None


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
    """Execute AI inference with optional web search grounding.

    This is the main entry point for AI-powered responses.
    The function has been refactored into smaller, focused helper functions:
    - _fetch_search_results: handles web search and grounding metadata
    - _build_messages: constructs the prompt payload
    - _execute_inference_with_retry: handles API calls with retry logic
    - _process_response: extracts and formats the reply text
    """
    if not user_msg:
        if return_metadata:
            return "", empty_grounding_metadata(enabled=False)
        return ""

    search_results, grounding_metadata = await _fetch_search_results(user_msg, enable_grounding)

    is_serious = not enable_grounding and len(user_msg) >= 40
    model = _select_model(enable_grounding, is_serious)

    messages = _build_messages(user_msg, author_name, context, enable_live_context, search_results)

    try:
        response = await _execute_inference_with_retry(client, model, messages)
        reply = _process_response(response, max_lines, max_length)

        if reply:
            if return_metadata:
                return reply, grounding_metadata
            return reply

    except Exception as error:
        logger.error("Inference Error (model=%s): %s", model, error)
        if return_metadata:
            return UNSTABLE_CONNECTION_FALLBACK, empty_grounding_metadata(enabled=False)
        return UNSTABLE_CONNECTION_FALLBACK

    if return_metadata:
        return EMPTY_RESPONSE_FALLBACK, empty_grounding_metadata(enabled=False)
    return EMPTY_RESPONSE_FALLBACK
