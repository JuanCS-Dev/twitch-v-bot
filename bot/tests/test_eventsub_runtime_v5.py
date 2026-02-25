import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.eventsub_runtime import (
    AgentComponent,
    ByteBot,
    _require_env,
    get_ctx_author,
    get_ctx_message_text,
)


class TestEventSubRuntimeV5:
    def test_require_env(self):
        with patch.dict(os.environ, {"TEST_ENV_VAR": "val"}):
            assert _require_env("TEST_ENV_VAR") == "val"
        with patch.dict(os.environ, clear=True):
            with pytest.raises(RuntimeError):
                _require_env("TEST_ENV_VAR")

    def test_get_ctx_helpers(self):
        ctx = MagicMock()
        ctx.message.text = "hello"
        ctx.message.author.name = "user1"
        assert get_ctx_message_text(ctx) == "hello"
        assert get_ctx_author(ctx).name == "user1"

        assert get_ctx_message_text(MagicMock(message=None)) == ""

    @pytest.mark.asyncio
    async def test_agent_component_ask(self):
        bot = MagicMock()
        comp = AgentComponent(bot)
        ctx = AsyncMock()
        ctx.message.text = "!ask hello"
        ctx.message.author.name = "user1"
        with patch("bot.eventsub_runtime.agent_inference", new_callable=AsyncMock) as mock_inf:
            mock_inf.return_value = "response"
            await comp.ask._callback(comp, ctx)
            mock_inf.assert_called_once()
            ctx.reply.assert_called_once()

        # Empty query
        ctx.message.text = "!ask  "
        await comp.ask._callback(comp, ctx)
        assert ctx.reply.call_count == 1  # not called again

    @pytest.mark.asyncio
    async def test_agent_component_vibe_owner(self):
        comp = AgentComponent(MagicMock())
        ctx = AsyncMock()
        ctx.message.text = "!vibe chill"
        ctx.message.author.id = "owner_id"
        with patch("bot.eventsub_runtime.is_owner", return_value=True):
            with patch("bot.eventsub_runtime.context") as mock_ctx:
                await comp.vibe._callback(comp, ctx)
                ctx.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_component_style_owner(self):
        comp = AgentComponent(MagicMock())
        ctx = AsyncMock()
        ctx.message.text = "!style formal"
        ctx.message.author.id = "owner_id"
        with patch("bot.eventsub_runtime.is_owner", return_value=True):
            with patch("bot.eventsub_runtime.context") as mock_ctx:
                await comp.style._callback(comp, ctx)
                ctx.reply.assert_called_once()
                assert mock_ctx.style_profile == "formal"

        # Empty style
        ctx.message.text = "!style  "
        ctx.reply.reset_mock()
        with patch("bot.eventsub_runtime.is_owner", return_value=True):
            with patch("bot.eventsub_runtime.context") as mock_ctx:
                await comp.style._callback(comp, ctx)
                ctx.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_component_scene_owner(self):
        comp = AgentComponent(MagicMock())
        ctx = AsyncMock()
        ctx.message.text = "!scene movie Dune"
        ctx.message.author.id = "owner_id"
        with patch("bot.eventsub_runtime.is_owner", return_value=True):
            with patch("bot.eventsub_runtime.context") as mock_ctx:
                mock_ctx.update_content.return_value = True
                await comp.scene._callback(comp, ctx)
                ctx.reply.assert_called_once()

        # Empty payload
        ctx.message.text = "!scene "
        ctx.reply.reset_mock()
        with patch("bot.eventsub_runtime.context") as mock_ctx:
            await comp.scene._callback(comp, ctx)
            ctx.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_component_scene_clear(self):
        comp = AgentComponent(MagicMock())
        ctx = AsyncMock()
        ctx.message.text = "!scene clear movie"
        ctx.message.author.id = "owner_id"
        with patch("bot.eventsub_runtime.is_owner", return_value=True):
            with patch("bot.eventsub_runtime.context") as mock_ctx:
                mock_ctx.clear_content.return_value = True
                await comp.scene._callback(comp, ctx)
                ctx.reply.assert_called_once()

        # clear missing arg
        ctx.message.text = "!scene clear"
        ctx.reply.reset_mock()
        with patch("bot.eventsub_runtime.is_owner", return_value=True):
            await comp.scene._callback(comp, ctx)
            ctx.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_component_status(self):
        comp = AgentComponent(MagicMock())
        ctx = AsyncMock()
        comp.bot.build_status_line.return_value = "status ok"
        await comp.status._callback(comp, ctx)
        ctx.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_bytebot_init_and_setup(self):
        with patch("bot.eventsub_runtime.CLIENT_ID", "123"):
            with patch("bot.eventsub_runtime.BOT_ID", "456"):
                bot = ByteBot("secret")
                with patch("bot.eventsub_runtime.CHANNEL_ID", "789"):
                    bot.add_component = AsyncMock()
                    bot.subscribe_websocket = AsyncMock()
                    await bot.setup_hook()
                    bot.add_component.assert_called_once()
                    bot.subscribe_websocket.assert_called_once()

                # Missing channel ID
                with patch("bot.eventsub_runtime.CHANNEL_ID", ""):
                    with pytest.raises(RuntimeError):
                        await bot.setup_hook()

    @pytest.mark.asyncio
    async def test_bytebot_event_message(self):
        with patch("bot.eventsub_runtime.CLIENT_ID", "123"):
            with patch("bot.eventsub_runtime.BOT_ID", "456"):
                bot = ByteBot("secret")
                msg = MagicMock()
                msg.echo = False
                msg.text = "!ask something"
                bot.handle_commands = AsyncMock()

                with patch("bot.eventsub_runtime.parse_byte_prompt", return_value="something"):
                    bot.handle_byte_prompt = AsyncMock()
                    await bot.event_message(msg)
                    bot.handle_byte_prompt.assert_called_once()

                msg.text = "!testcmd"
                with patch("bot.eventsub_runtime.parse_byte_prompt", return_value=None):
                    await bot.event_message(msg)
                    bot.handle_commands.assert_called()

                # Echo
                msg.echo = True
                bot.handle_commands.reset_mock()
                await bot.event_message(msg)
                bot.handle_commands.assert_not_called()

    @pytest.mark.asyncio
    async def test_bytebot_event_ready(self):
        with (
            patch("bot.eventsub_runtime.CLIENT_ID", "123"),
            patch("bot.eventsub_runtime.BOT_ID", "456"),
        ):
            bot = ByteBot("secret")
            with patch("bot.eventsub_runtime.logger.info") as mock_logger:
                await bot.event_ready()
                mock_logger.assert_called()

    @pytest.mark.asyncio
    async def test_bytebot_handle_byte_prompt(self):
        with (
            patch("bot.eventsub_runtime.CLIENT_ID", "123"),
            patch("bot.eventsub_runtime.BOT_ID", "456"),
        ):
            bot = ByteBot("secret")
            msg = MagicMock()
            msg.reply = AsyncMock()
            with patch(
                "bot.eventsub_runtime.handle_byte_prompt_text", new_callable=AsyncMock
            ) as mock_handle:
                await bot.handle_byte_prompt(msg, "hello")
                mock_handle.assert_called_once()
