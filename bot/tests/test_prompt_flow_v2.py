import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.prompt_flow import (
    BytePromptRuntime,
    handle_byte_prompt_text,
    handle_movie_fact_sheet_prompt,
    unwrap_inference_result,
)


class TestPromptFlowV2:
    def test_unwrap_inference_result(self):
        assert unwrap_inference_result(("text", {"meta": "data"})) == ("text", {"meta": "data"})
        assert unwrap_inference_result("only text") == ("only text", None)
        assert unwrap_inference_result(None) == ("", None)
        assert unwrap_inference_result((123, None)) == ("123", None)

    @pytest.fixture
    def runtime_mock(self):
        rt = MagicMock(spec=BytePromptRuntime)
        rt.agent_inference = AsyncMock()
        rt.client = MagicMock()
        rt.context = MagicMock()
        rt.context.live_observability = {}
        rt.context.channel_id = "canal_a"
        rt.observability = MagicMock()
        rt.logger = MagicMock()
        rt.byte_help_message = "Help message"
        rt.max_reply_lines = 5
        rt.max_chat_message_length = 500
        rt.serious_reply_max_lines = 10
        rt.serious_reply_max_length = 1000
        rt.quality_safe_fallback = "Safe Fallback"

        rt.format_chat_reply = lambda x: f"Formatted: {x}" if x else ""
        rt.is_serious_technical_prompt = MagicMock(return_value=False)
        rt.is_follow_up_prompt = MagicMock(return_value=False)
        rt.is_current_events_prompt = MagicMock(return_value=False)
        rt.is_high_risk_current_events_prompt = MagicMock(return_value=False)
        rt.build_server_time_anchor_instruction = MagicMock(return_value="Time anchor")
        rt.is_intro_prompt = MagicMock(return_value=False)
        rt.build_intro_reply = MagicMock(return_value="Intro")
        rt.is_movie_fact_sheet_prompt = MagicMock(return_value=False)
        rt.extract_movie_title = MagicMock(return_value="")
        rt.build_movie_fact_sheet_query = MagicMock(return_value="Movie Query")
        rt.build_llm_enhanced_prompt = MagicMock(return_value="Enhanced")
        rt.has_grounding_signal = MagicMock(return_value=False)
        rt.normalize_current_events_reply_contract = MagicMock(side_effect=lambda a, b, **kw: b)
        rt.is_low_quality_answer = MagicMock(return_value=(False, "ok"))
        rt.build_quality_rewrite_prompt = MagicMock(return_value="Rewrite")
        rt.build_current_events_safe_fallback_reply = MagicMock(return_value="Fallback")
        rt.extract_multi_reply_parts = MagicMock(return_value=["part1"])
        rt.enable_live_context_learning = False
        return rt

    @pytest.mark.asyncio
    async def test_handle_movie_fact_sheet_prompt_success(self, runtime_mock):
        runtime_mock.extract_movie_title.return_value = "Dune 2"
        runtime_mock.agent_inference.return_value = "Movie facts"

        reply_fn = AsyncMock()
        await handle_movie_fact_sheet_prompt(
            "byte movie Dune 2", "user", reply_fn, runtime=runtime_mock
        )

        runtime_mock.context.update_content.assert_called_with("movie", "Dune 2")
        runtime_mock.build_movie_fact_sheet_query.assert_called_with("Dune 2")
        reply_fn.assert_called_once_with("Formatted: Movie facts")

    @pytest.mark.asyncio
    async def test_handle_movie_fact_sheet_prompt_missing(self, runtime_mock):
        runtime_mock.extract_movie_title.return_value = ""
        runtime_mock.context.live_observability = {}

        reply_fn = AsyncMock()
        await handle_movie_fact_sheet_prompt("byte movie", "user", reply_fn, runtime=runtime_mock)

        reply_fn.assert_called_once()
        assert "Preciso do nome" in reply_fn.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_help(self, runtime_mock):
        reply_fn = AsyncMock()
        await handle_byte_prompt_text("help", "user", reply_fn, runtime=runtime_mock)
        reply_fn.assert_called_with("Formatted: Help message")
        runtime_mock.observability.record_reply.assert_called_once_with(
            text="Formatted: Help message",
            channel_id="canal_a",
        )
        runtime_mock.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_intro(self, runtime_mock):
        runtime_mock.is_intro_prompt.return_value = True
        reply_fn = AsyncMock()
        await handle_byte_prompt_text("hello", "user", reply_fn, runtime=runtime_mock)
        reply_fn.assert_called_with("Formatted: Intro")

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_status(self, runtime_mock):
        reply_fn = AsyncMock()
        status_line_factory = MagicMock(return_value="My Status")
        await handle_byte_prompt_text(
            "status check",
            "user",
            reply_fn,
            runtime=runtime_mock,
            status_line_factory=status_line_factory,
        )
        reply_fn.assert_called_with("Formatted: My Status")

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_status_fail(self, runtime_mock):
        reply_fn = AsyncMock()
        status_line_factory = MagicMock(side_effect=Exception("Failed status"))
        await handle_byte_prompt_text(
            "status check",
            "user",
            reply_fn,
            runtime=runtime_mock,
            status_line_factory=status_line_factory,
        )
        reply_fn.assert_called_with("Formatted: status indisponivel")

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_movie_delegation(self, runtime_mock):
        runtime_mock.is_movie_fact_sheet_prompt.return_value = True
        runtime_mock.extract_movie_title.return_value = "Matrix"
        runtime_mock.agent_inference.return_value = "Matrix is a movie."
        reply_fn = AsyncMock()
        await handle_byte_prompt_text("matrix info", "user", reply_fn, runtime=runtime_mock)
        reply_fn.assert_called_with("Formatted: Formatted: Matrix is a movie.")

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_llm_inference_high_risk(self, runtime_mock):
        runtime_mock.is_current_events_prompt.return_value = True
        runtime_mock.is_high_risk_current_events_prompt.return_value = True
        runtime_mock.agent_inference.return_value = "The news is..."

        reply_fn = AsyncMock()
        await handle_byte_prompt_text("what is happening", "user", reply_fn, runtime=runtime_mock)

        # Check if high risk instruction was appended
        call_args = runtime_mock.agent_inference.call_args[0]
        assert "Instrucao tecnica obrigatoria:" in call_args[0]
        reply_fn.assert_called_with("Formatted: The news is...")

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_llm_inference_quality_retry_success(self, runtime_mock):
        # First call fails quality, second passes
        runtime_mock.is_low_quality_answer.side_effect = [(True, "too short"), (False, "ok")]
        runtime_mock.agent_inference.side_effect = ["Bad answer", "Better answer"]

        reply_fn = AsyncMock()
        await handle_byte_prompt_text("tell me", "user", reply_fn, runtime=runtime_mock)

        assert runtime_mock.agent_inference.call_count == 2
        reply_fn.assert_called_with("Formatted: Better answer")
        runtime_mock.observability.record_quality_gate.assert_any_call(
            outcome="retry",
            reason="too short",
            channel_id="canal_a",
        )
        runtime_mock.observability.record_quality_gate.assert_any_call(
            outcome="retry_success",
            reason="too short",
            channel_id="canal_a",
        )

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_llm_inference_quality_retry_fail(self, runtime_mock):
        # Both calls fail quality
        runtime_mock.is_low_quality_answer.side_effect = [(True, "too short"), (True, "still bad")]
        runtime_mock.agent_inference.side_effect = ["Bad answer", "Still bad"]

        reply_fn = AsyncMock()
        await handle_byte_prompt_text("tell me", "user", reply_fn, runtime=runtime_mock)

        assert runtime_mock.agent_inference.call_count == 2
        reply_fn.assert_called_with("Formatted: Fallback")
        runtime_mock.observability.record_quality_gate.assert_any_call(
            outcome="fallback",
            reason="still bad",
            channel_id="canal_a",
        )

    @pytest.mark.asyncio
    async def test_handle_byte_prompt_llm_inference_serious_mode(self, runtime_mock):
        runtime_mock.is_serious_technical_prompt.return_value = True
        runtime_mock.agent_inference.return_value = "Serious answer"

        reply_fn = AsyncMock()
        await handle_byte_prompt_text("technical details", "user", reply_fn, runtime=runtime_mock)

        kwargs = runtime_mock.agent_inference.call_args[1]
        assert kwargs["enable_grounding"] is True
        assert kwargs["max_lines"] == 10
        assert kwargs["max_length"] == 1000
        reply_fn.assert_called_with("Formatted: Serious answer")
