import asyncio
import logging
from typing import Any

from google.genai import types

from bot.logic_constants import (
    EMPTY_RESPONSE_FALLBACK,
    MAX_REPLY_LENGTH,
    MAX_REPLY_LINES,
    MODEL_MAX_OUTPUT_TOKENS,
    MODEL_NAME,
    MODEL_RATE_LIMIT_BACKOFF_SECONDS,
    MODEL_RATE_LIMIT_MAX_RETRIES,
    MODEL_TEMPERATURE,
    UNSTABLE_CONNECTION_FALLBACK,
)
from bot.logic_context import build_dynamic_prompt, build_system_instruction, enforce_reply_limits
from bot.logic_grounding import empty_grounding_metadata, extract_grounding_metadata, extract_response_text

logger = logging.getLogger("ByteBot")


def is_rate_limited_inference_error(error: Exception) -> bool:
    message = str(error).lower()
    return "429" in message or "resource_exhausted" in message or "resource exhausted" in message


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
):
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
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=MODEL_NAME,
                    contents=dynamic_prompt,
                    config=config,
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
