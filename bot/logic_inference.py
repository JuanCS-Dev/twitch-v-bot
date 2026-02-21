import asyncio
import logging
from typing import Any, Literal, overload

from google.genai import types  # pyright: ignore[reportMissingImports]

from bot.logic_constants import (
    EMPTY_RESPONSE_FALLBACK,
    MAX_REPLY_LENGTH,
    MAX_REPLY_LINES,
    MODEL_INPUT_COST_PER_1M_USD,
    MODEL_INFERENCE_TIMEOUT_SECONDS,
    MODEL_MAX_OUTPUT_TOKENS,
    MODEL_NAME,
    MODEL_OUTPUT_COST_PER_1M_USD,
    MODEL_RATE_LIMIT_BACKOFF_SECONDS,
    MODEL_RATE_LIMIT_MAX_RETRIES,
    MODEL_TEMPERATURE,
    UNSTABLE_CONNECTION_FALLBACK,
)
from bot.logic_context import build_dynamic_prompt, build_system_instruction, enforce_reply_limits
from bot.logic_grounding import (
    GroundingMetadata,
    empty_grounding_metadata,
    extract_grounding_metadata,
    extract_response_text,
)
from bot.observability import observability

logger = logging.getLogger("ByteBot")


def is_rate_limited_inference_error(error: Exception) -> bool:
    message = str(error).lower()
    return "429" in message or "resource_exhausted" in message or "resource exhausted" in message


def is_timeout_inference_error(error: Exception) -> bool:
    if isinstance(error, TimeoutError):
        return True
    message = str(error).lower()
    return "timed out" in message or "timeout" in message


def _read_field(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _first_int(source: Any, keys: tuple[str, ...]) -> int:
    for key in keys:
        raw_value = _read_field(source, key)
        if raw_value is None:
            continue
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return 0


def _extract_usage(response: Any) -> tuple[int, int]:
    usage = _read_field(response, "usage_metadata")
    if usage is None:
        usage = _read_field(response, "usageMetadata")
    if usage is None:
        return 0, 0

    input_tokens = _first_int(
        usage,
        (
            "prompt_token_count",
            "input_token_count",
            "promptTokenCount",
            "inputTokenCount",
        ),
    )
    output_tokens = _first_int(
        usage,
        (
            "candidates_token_count",
            "output_token_count",
            "candidatesTokenCount",
            "outputTokenCount",
        ),
    )
    total_tokens = _first_int(
        usage,
        (
            "total_token_count",
            "totalTokenCount",
        ),
    )
    if output_tokens == 0 and total_tokens > input_tokens:
        output_tokens = max(0, total_tokens - input_tokens)
    return input_tokens, output_tokens


def _estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        (max(0, input_tokens) / 1_000_000.0) * MODEL_INPUT_COST_PER_1M_USD
        + (max(0, output_tokens) / 1_000_000.0) * MODEL_OUTPUT_COST_PER_1M_USD
    )


@overload
async def agent_inference(
    user_msg: str,
    author_name: str,
    client: Any,
    context: Any,
    enable_grounding: bool = True,
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
    enable_grounding: bool = True,
    enable_live_context: bool = True,
    max_lines: int = MAX_REPLY_LINES,
    max_length: int = MAX_REPLY_LENGTH,
    return_metadata: Literal[True] = True,
) -> tuple[str, GroundingMetadata]: ...


async def agent_inference(
    user_msg: str,
    author_name: str,
    client: Any,
    context: Any,
    enable_grounding: bool = True,
    enable_live_context: bool = True,
    max_lines: int = MAX_REPLY_LINES,
    max_length: int = MAX_REPLY_LENGTH,
    return_metadata: bool = False,
) -> str | tuple[str, GroundingMetadata]:
    if not user_msg:
        if return_metadata:
            return "", empty_grounding_metadata(enabled=enable_grounding)
        return ""

    dynamic_prompt = build_dynamic_prompt(
        user_msg,
        author_name,
        context,
        include_live_context=enable_live_context,
    )
    grounding_modes = [enable_grounding]
    if enable_grounding:
        grounding_modes.append(False)

    for use_grounding in grounding_modes:
        tools: types.ToolListUnion = [types.Tool(google_search=types.GoogleSearch())] if use_grounding else []
        config = types.GenerateContentConfig(
            system_instruction=build_system_instruction(context),
            tools=tools,
            temperature=MODEL_TEMPERATURE,
            max_output_tokens=MODEL_MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(
                include_thoughts=False,
                thinking_level=types.ThinkingLevel.MINIMAL,
            ),
        )

        for attempt in range(MODEL_RATE_LIMIT_MAX_RETRIES + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=MODEL_NAME,
                        contents=dynamic_prompt,
                        config=config,
                    ),
                    timeout=MODEL_INFERENCE_TIMEOUT_SECONDS,
                )
                input_tokens, output_tokens = _extract_usage(response)
                if input_tokens > 0 or output_tokens > 0:
                    observability.record_token_usage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_usd=_estimate_cost_usd(input_tokens, output_tokens),
                    )
                grounding_metadata = extract_grounding_metadata(response, use_grounding=use_grounding)
                reply_text = extract_response_text(response)
                if reply_text:
                    final_reply = enforce_reply_limits(reply_text, max_lines=max_lines, max_length=max_length)
                    if return_metadata:
                        return final_reply, grounding_metadata
                    return final_reply

                logger.warning(
                    "Gemini retornou resposta sem texto (grounding=%s, queries=%d, sources=%d, chunks=%d).",
                    use_grounding,
                    grounding_metadata["query_count"],
                    grounding_metadata["source_count"],
                    grounding_metadata["chunk_count"],
                )
                break
            except Exception as error:
                if is_timeout_inference_error(error):
                    logger.warning(
                        "Inference timeout (grounding=%s, timeout=%.1fs).",
                        use_grounding,
                        MODEL_INFERENCE_TIMEOUT_SECONDS,
                    )
                    if not use_grounding:
                        if return_metadata:
                            return UNSTABLE_CONNECTION_FALLBACK, empty_grounding_metadata(enabled=False)
                        return UNSTABLE_CONNECTION_FALLBACK
                    break

                if is_rate_limited_inference_error(error) and attempt < MODEL_RATE_LIMIT_MAX_RETRIES:
                    backoff_seconds = MODEL_RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning(
                        "Inference rate-limited (grounding=%s). Retrying in %.2fs (%d/%d).",
                        use_grounding,
                        backoff_seconds,
                        attempt + 1,
                        MODEL_RATE_LIMIT_MAX_RETRIES + 1,
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue

                logger.error("Inference Error (grounding=%s): %s", use_grounding, error)
                if not use_grounding:
                    if return_metadata:
                        return UNSTABLE_CONNECTION_FALLBACK, empty_grounding_metadata(enabled=False)
                    return UNSTABLE_CONNECTION_FALLBACK
                break

    if return_metadata:
        return EMPTY_RESPONSE_FALLBACK, empty_grounding_metadata(enabled=False)
    return EMPTY_RESPONSE_FALLBACK
