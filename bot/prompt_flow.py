import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

ReplyFn = Callable[[str], Awaitable[None]]
InferenceFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class BytePromptRuntime:
    agent_inference: InferenceFn
    client: Any
    context: Any
    observability: Any
    logger: Any
    byte_help_message: str
    max_reply_lines: int
    max_chat_message_length: int
    serious_reply_max_lines: int
    serious_reply_max_length: int
    quality_safe_fallback: str
    format_chat_reply: Callable[[str], str]
    is_serious_technical_prompt: Callable[[str], bool]
    is_follow_up_prompt: Callable[[str], bool]
    is_current_events_prompt: Callable[[str], bool]
    is_high_risk_current_events_prompt: Callable[[str], bool]
    build_server_time_anchor_instruction: Callable[[], str]
    is_intro_prompt: Callable[[str], bool]
    build_intro_reply: Callable[[], str]
    is_movie_fact_sheet_prompt: Callable[[str], bool]
    extract_movie_title: Callable[[str], str]
    build_movie_fact_sheet_query: Callable[[str], str]
    build_llm_enhanced_prompt: Callable[..., str]
    has_grounding_signal: Callable[[Mapping[str, Any] | None], bool]
    normalize_current_events_reply_contract: Callable[..., str]
    is_low_quality_answer: Callable[[str, str], tuple[bool, str]]
    build_quality_rewrite_prompt: Callable[..., str]
    build_current_events_safe_fallback_reply: Callable[..., str]
    extract_multi_reply_parts: Callable[..., list[str]]
    enable_live_context_learning: bool


def unwrap_inference_result(result: Any) -> tuple[str, dict | None]:
    if isinstance(result, tuple) and len(result) == 2:
        text_result, metadata_result = result
        safe_text = text_result if isinstance(text_result, str) else str(text_result or "")
        safe_metadata = metadata_result if isinstance(metadata_result, dict) else None
        return safe_text, safe_metadata

    if isinstance(result, str):
        return result, None
    return str(result or ""), None


async def handle_movie_fact_sheet_prompt(
    prompt: str,
    author_name: str,
    reply_fn: ReplyFn,
    *,
    runtime: BytePromptRuntime,
) -> None:
    movie_title_from_prompt = runtime.extract_movie_title(prompt)
    if movie_title_from_prompt:
        runtime.context.update_content("movie", movie_title_from_prompt)

    active_movie = runtime.context.live_observability.get("movie", "").strip()
    movie_title = movie_title_from_prompt or active_movie
    if not movie_title:
        await reply_fn("Preciso do nome do filme. Ex.: byte ficha tecnica de Duna Parte 2")
        return

    query = runtime.build_movie_fact_sheet_query(movie_title)
    answer = await runtime.agent_inference(
        query,
        author_name,
        runtime.client,
        runtime.context,
        enable_live_context=runtime.enable_live_context_learning,
    )
    await reply_fn(runtime.format_chat_reply(answer))


async def handle_byte_prompt_text(
    prompt: str,
    author_name: str,
    reply_fn: ReplyFn,
    *,
    runtime: BytePromptRuntime,
    status_line_factory: Callable[[], str] | None = None,
) -> None:
    normalized_prompt = (prompt or "").strip()
    lowered_prompt = normalized_prompt.lower()
    runtime.logger.info("Handling BytePrompt: '%s' (author=%s)", normalized_prompt, author_name)

    prompt_length = len(normalized_prompt)
    serious_mode = runtime.is_serious_technical_prompt(normalized_prompt)
    follow_up_mode = runtime.is_follow_up_prompt(normalized_prompt)
    current_events_mode = runtime.is_current_events_prompt(normalized_prompt)
    high_risk_current_events_mode = (
        current_events_mode and runtime.is_high_risk_current_events_prompt(normalized_prompt)
    )
    sent_replies: list[str] = []
    interaction_started_at = time.perf_counter()
    server_time_instruction = runtime.build_server_time_anchor_instruction()
    channel_id = str(getattr(runtime.context, "channel_id", "default") or "default")

    async def tracked_reply(text: str) -> None:
        final_text = runtime.format_chat_reply(text)
        if not final_text:
            return
        sent_replies.append(final_text)
        runtime.context.remember_bot_reply(final_text)
        runtime.observability.record_reply(text=final_text, channel_id=channel_id)
        await reply_fn(final_text)

    def log_interaction(route: str) -> None:
        total_reply_chars = sum(len(reply) for reply in sent_replies)
        latency_ms = (time.perf_counter() - interaction_started_at) * 1000
        runtime.logger.info(
            "ByteInteraction route=%s author=%s prompt_chars=%d reply_parts=%d reply_chars=%d serious=%s follow_up=%s current_events=%s latency_ms=%.1f",
            route,
            author_name,
            prompt_length,
            len(sent_replies),
            total_reply_chars,
            serious_mode,
            follow_up_mode,
            current_events_mode,
            latency_ms,
        )
        runtime.observability.record_byte_interaction(
            route=route,
            author_name=author_name,
            prompt_chars=prompt_length,
            reply_parts=len(sent_replies),
            reply_chars=total_reply_chars,
            serious=serious_mode,
            follow_up=follow_up_mode,
            current_events=current_events_mode,
            latency_ms=latency_ms,
            channel_id=channel_id,
        )

    if not normalized_prompt or lowered_prompt in {"ajuda", "help", "comandos"}:
        await tracked_reply(runtime.byte_help_message)
        log_interaction("help")
        return

    if runtime.is_intro_prompt(normalized_prompt) or lowered_prompt.startswith("se apresente"):
        await tracked_reply(runtime.build_intro_reply())
        log_interaction("intro")
        return

    if lowered_prompt.startswith("status"):
        status_text = "status indisponivel"
        if callable(status_line_factory):
            try:
                status_text = str(status_line_factory())
            except Exception as error:
                runtime.logger.warning("Falha ao montar status customizado: %s", error)
        await tracked_reply(str(status_text))
        log_interaction("status")
        return

    if runtime.is_movie_fact_sheet_prompt(normalized_prompt):
        await handle_movie_fact_sheet_prompt(
            normalized_prompt,
            author_name,
            tracked_reply,
            runtime=runtime,
        )
        log_interaction("movie_fact_sheet")
        return

    quality_route_suffix = ""
    inference_prompt = runtime.build_llm_enhanced_prompt(
        normalized_prompt,
        server_time_instruction=server_time_instruction,
    )
    if high_risk_current_events_mode:
        inference_prompt = (
            f"{inference_prompt}\n"
            "Instrucao tecnica obrigatoria: use os dados do contexto web atualizado para responder. "
            f"Se nao houver evidencia verificavel, retorne exatamente: '{runtime.quality_safe_fallback}'"
        )

    # Follow-up curto privilegia continuidade e baixa latencia; grounding fica para temas serios ou evento atual direto.
    enable_grounding = serious_mode or (current_events_mode and not follow_up_mode)
    inference_result = await runtime.agent_inference(
        inference_prompt,
        author_name,
        runtime.client,
        runtime.context,
        enable_live_context=runtime.enable_live_context_learning,
        enable_grounding=enable_grounding,
        max_lines=runtime.serious_reply_max_lines if serious_mode else runtime.max_reply_lines,
        max_length=(
            runtime.serious_reply_max_length if serious_mode else runtime.max_chat_message_length
        ),
        return_metadata=True,
    )
    answer, grounding_metadata = unwrap_inference_result(inference_result)

    answer = runtime.normalize_current_events_reply_contract(
        normalized_prompt,
        answer,
        server_time_instruction=server_time_instruction,
        grounding_metadata=grounding_metadata,
    )
    quality_failed, quality_reason = runtime.is_low_quality_answer(normalized_prompt, answer)
    if quality_failed:
        runtime.observability.record_quality_gate(
            outcome="retry",
            reason=quality_reason,
            channel_id=channel_id,
        )
        retry_prompt = runtime.build_quality_rewrite_prompt(
            normalized_prompt,
            answer,
            quality_reason,
            server_time_instruction=server_time_instruction,
        )
        retry_inference_result = await runtime.agent_inference(
            retry_prompt,
            author_name,
            runtime.client,
            runtime.context,
            enable_live_context=runtime.enable_live_context_learning,
            enable_grounding=enable_grounding,
            max_lines=runtime.serious_reply_max_lines if serious_mode else runtime.max_reply_lines,
            max_length=(
                runtime.serious_reply_max_length
                if serious_mode
                else runtime.max_chat_message_length
            ),
            return_metadata=True,
        )
        retry_answer, retry_grounding_metadata = unwrap_inference_result(retry_inference_result)
        retry_answer = runtime.normalize_current_events_reply_contract(
            normalized_prompt,
            retry_answer,
            server_time_instruction=server_time_instruction,
            grounding_metadata=retry_grounding_metadata,
        )
        retry_failed, retry_reason = runtime.is_low_quality_answer(normalized_prompt, retry_answer)
        if retry_answer and not retry_failed:
            answer = retry_answer
            quality_route_suffix = "_quality_retry"
            runtime.observability.record_quality_gate(
                outcome="retry_success",
                reason=quality_reason,
                channel_id=channel_id,
            )
        else:
            answer = runtime.build_current_events_safe_fallback_reply(
                normalized_prompt,
                server_time_instruction=server_time_instruction,
            )
            quality_route_suffix = "_quality_fallback"
            runtime.observability.record_quality_gate(
                outcome="fallback",
                reason=retry_reason or quality_reason,
                channel_id=channel_id,
            )
    else:
        runtime.observability.record_quality_gate(
            outcome="pass", reason="ok", channel_id=channel_id
        )

    await tracked_reply(answer)
    route_prefix = "llm_serious" if serious_mode else "llm_default"
    log_interaction(f"{route_prefix}{quality_route_suffix}")
