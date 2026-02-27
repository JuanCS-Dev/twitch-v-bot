import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.prompt_runtime import handle_byte_prompt_text, handle_movie_fact_sheet_prompt


class TestPromptRuntimeChannelPause(unittest.IsolatedAsyncioTestCase):
    async def test_handle_byte_prompt_text_skips_when_channel_is_paused(self):
        ctx = MagicMock(channel_paused=True)
        reply_fn = AsyncMock()

        with (
            patch("bot.prompt_runtime.context_manager.get", return_value=ctx),
            patch(
                "bot.prompt_runtime.context_manager.ensure_channel_config_loaded",
                return_value=ctx,
            ),
            patch(
                "bot.prompt_runtime.handle_byte_prompt_text_impl", new_callable=AsyncMock
            ) as mock_impl,
            patch("bot.prompt_runtime.observability") as mock_observability,
        ):
            await handle_byte_prompt_text("oi chat", "viewer", reply_fn, channel_id="canal_a")

        mock_impl.assert_not_awaited()
        reply_fn.assert_not_awaited()
        mock_observability.record_byte_interaction.assert_called_once()
        self.assertEqual(
            mock_observability.record_byte_interaction.call_args.kwargs["route"],
            "channel_paused",
        )

    async def test_handle_byte_prompt_text_runs_when_channel_is_not_paused(self):
        ctx = MagicMock(channel_paused=False)
        reply_fn = AsyncMock()

        with (
            patch("bot.prompt_runtime.context_manager.get", return_value=ctx),
            patch(
                "bot.prompt_runtime.context_manager.ensure_channel_config_loaded",
                return_value=ctx,
            ),
            patch(
                "bot.prompt_runtime.handle_byte_prompt_text_impl", new_callable=AsyncMock
            ) as mock_impl,
        ):
            await handle_byte_prompt_text("oi chat", "viewer", reply_fn, channel_id="canal_a")

        mock_impl.assert_awaited_once()

    async def test_handle_movie_fact_sheet_prompt_skips_when_channel_is_paused(self):
        ctx = MagicMock(channel_paused=True)
        reply_fn = AsyncMock()

        with (
            patch("bot.prompt_runtime.context_manager.get", return_value=ctx),
            patch(
                "bot.prompt_runtime.context_manager.ensure_channel_config_loaded",
                return_value=ctx,
            ),
            patch(
                "bot.prompt_runtime.handle_movie_fact_sheet_prompt_impl",
                new_callable=AsyncMock,
            ) as mock_impl,
            patch("bot.prompt_runtime.observability") as mock_observability,
        ):
            await handle_movie_fact_sheet_prompt(
                "matrix",
                "viewer",
                reply_fn,
                channel_id="canal_a",
            )

        mock_impl.assert_not_awaited()
        reply_fn.assert_not_awaited()
        mock_observability.record_byte_interaction.assert_called_once()
        self.assertEqual(
            mock_observability.record_byte_interaction.call_args.kwargs["route"],
            "channel_paused_movie_fact",
        )
