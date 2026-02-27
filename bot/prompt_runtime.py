import asyncio
from typing import Any

from bot import byte_semantics
from bot.logic import MAX_REPLY_LINES, agent_inference, context_manager, has_grounding_signal
from bot.observability import observability
from bot.prompt_flow import (
    BytePromptRuntime,
)
from bot.prompt_flow import (
    handle_byte_prompt_text as handle_byte_prompt_text_impl,
)
from bot.prompt_flow import (
    handle_movie_fact_sheet_prompt as handle_movie_fact_sheet_prompt_impl,
)
from bot.prompt_flow import (
    unwrap_inference_result as unwrap_inference_result_impl,
)
from bot.runtime_config import (
    BYTE_HELP_MESSAGE,
    BYTE_INTRO_TEMPLATES,
    ENABLE_LIVE_CONTEXT_LEARNING,
    MAX_CHAT_MESSAGE_LENGTH,
    QUALITY_SAFE_FALLBACK,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
    client,
    logger,
)
from bot.status_runtime import build_status_line

compact_message = byte_semantics.compact_message
format_chat_reply = byte_semantics.format_chat_reply
build_intro_reply_templates = byte_semantics.BYTE_INTRO_TEMPLATES
is_intro_prompt = byte_semantics.is_intro_prompt
is_movie_fact_sheet_prompt = byte_semantics.is_movie_fact_sheet_prompt
is_current_events_prompt = byte_semantics.is_current_events_prompt
is_high_risk_current_events_prompt = byte_semantics.is_high_risk_current_events_prompt
build_verifiable_prompt = byte_semantics.build_verifiable_prompt
is_serious_technical_prompt = byte_semantics.is_serious_technical_prompt
is_follow_up_prompt = byte_semantics.is_follow_up_prompt
build_direct_answer_instruction = byte_semantics.build_direct_answer_instruction
build_llm_enhanced_prompt = byte_semantics.build_llm_enhanced_prompt
is_low_quality_answer = byte_semantics.is_low_quality_answer
build_quality_rewrite_prompt = byte_semantics.build_quality_rewrite_prompt
build_server_time_anchor_instruction = byte_semantics.build_server_time_anchor_instruction
normalize_current_events_reply_contract = byte_semantics.normalize_current_events_reply_contract
build_current_events_safe_fallback_reply = byte_semantics.build_current_events_safe_fallback_reply
extract_multi_reply_parts = byte_semantics.extract_multi_reply_parts
extract_movie_title = byte_semantics.extract_movie_title
build_movie_fact_sheet_query = byte_semantics.build_movie_fact_sheet_query

intro_template_index = 0


def build_intro_reply() -> str:
    global intro_template_index
    template = BYTE_INTRO_TEMPLATES[intro_template_index % len(BYTE_INTRO_TEMPLATES)]
    intro_template_index += 1
    return template


def unwrap_inference_result(result: Any) -> tuple[str, dict | None]:
    return unwrap_inference_result_impl(result)


def _resolve_channel_context(channel_id: str | None = None) -> Any:
    ctx = context_manager.get(channel_id)
    try:
        ctx = context_manager.ensure_channel_config_loaded(channel_id)
    except Exception as error:
        logger.warning(
            "Falha ao restaurar channel_config de %s: %s", channel_id or "default", error
        )
    return ctx


def _is_channel_paused(ctx: Any) -> bool:
    return bool(getattr(ctx, "channel_paused", False))


def _record_channel_paused_skip(prompt: str, author_name: str, route: str) -> None:
    observability.record_byte_interaction(
        route=route,
        author_name=author_name,
        prompt_chars=len(prompt),
        reply_parts=0,
        reply_chars=0,
        serious=False,
        follow_up=False,
        current_events=False,
        latency_ms=0.0,
    )


def build_prompt_runtime(ctx: Any = None) -> BytePromptRuntime:
    effective_ctx = ctx or context_manager.get()
    return BytePromptRuntime(
        agent_inference=agent_inference,
        client=client,
        context=effective_ctx,
        observability=observability,
        logger=logger,
        byte_help_message=BYTE_HELP_MESSAGE,
        max_reply_lines=MAX_REPLY_LINES,
        max_chat_message_length=MAX_CHAT_MESSAGE_LENGTH,
        serious_reply_max_lines=SERIOUS_REPLY_MAX_LINES,
        serious_reply_max_length=SERIOUS_REPLY_MAX_LENGTH,
        quality_safe_fallback=QUALITY_SAFE_FALLBACK,
        format_chat_reply=format_chat_reply,
        is_serious_technical_prompt=is_serious_technical_prompt,
        is_follow_up_prompt=is_follow_up_prompt,
        is_current_events_prompt=is_current_events_prompt,
        is_high_risk_current_events_prompt=is_high_risk_current_events_prompt,
        build_server_time_anchor_instruction=build_server_time_anchor_instruction,
        is_intro_prompt=is_intro_prompt,
        build_intro_reply=build_intro_reply,
        is_movie_fact_sheet_prompt=is_movie_fact_sheet_prompt,
        extract_movie_title=extract_movie_title,
        build_movie_fact_sheet_query=build_movie_fact_sheet_query,
        build_llm_enhanced_prompt=build_llm_enhanced_prompt,
        has_grounding_signal=has_grounding_signal,
        normalize_current_events_reply_contract=normalize_current_events_reply_contract,
        is_low_quality_answer=is_low_quality_answer,
        build_quality_rewrite_prompt=build_quality_rewrite_prompt,
        build_current_events_safe_fallback_reply=build_current_events_safe_fallback_reply,
        extract_multi_reply_parts=extract_multi_reply_parts,
        enable_live_context_learning=ENABLE_LIVE_CONTEXT_LEARNING,
    )


async def handle_movie_fact_sheet_prompt(
    prompt: str,
    author_name: str,
    reply_fn,
    channel_id: str | None = None,
) -> None:
    ctx = _resolve_channel_context(channel_id)
    if _is_channel_paused(ctx):
        _record_channel_paused_skip(prompt, author_name, route="channel_paused_movie_fact")
        return
    await handle_movie_fact_sheet_prompt_impl(
        prompt,
        author_name,
        reply_fn,
        runtime=build_prompt_runtime(ctx),
    )


async def handle_byte_prompt_text(
    prompt: str,
    author_name: str,
    reply_fn,
    status_line_factory=None,
    channel_id: str | None = None,
) -> None:
    ctx = _resolve_channel_context(channel_id)
    if _is_channel_paused(ctx):
        _record_channel_paused_skip(prompt, author_name, route="channel_paused")
        return
    # Recap detection — short-circuit to recap engine
    from bot.recap_engine import generate_recap, is_recap_prompt

    if is_recap_prompt(prompt):
        recap_text = await generate_recap(channel_id=channel_id)
        formatted = format_chat_reply(recap_text)
        if formatted:
            await reply_fn(formatted)
            observability.record_byte_interaction(
                route="recap",
                author_name=author_name,
                prompt_chars=len(prompt),
                reply_parts=1,
                reply_chars=len(formatted),
                serious=False,
                follow_up=False,
                current_events=False,
                latency_ms=0.0,
            )
        return

    if callable(status_line_factory):

        async def effective_status_factory() -> str:
            try:
                result = status_line_factory()
                if asyncio.iscoroutine(result):
                    return str(await result)
                return str(result)
            except Exception as error:
                logger.warning("Falha ao montar status customizado: %s", error)
                return await build_status_line()

    else:
        effective_status_factory = status_line_factory

    await handle_byte_prompt_text_impl(
        prompt,
        author_name,
        reply_fn,
        runtime=build_prompt_runtime(ctx),
        status_line_factory=effective_status_factory,
    )
