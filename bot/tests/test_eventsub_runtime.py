import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import bot.eventsub_runtime as es_runtime


class TestEventSubHelpers(unittest.TestCase):
    def test_get_ctx_message_text(self):
        ctx = MagicMock()
        ctx.message.text = "hello"
        self.assertEqual(es_runtime.get_ctx_message_text(ctx), "hello")


class TestAgentComponent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.comp = es_runtime.AgentComponent(self.bot)

    @patch("bot.eventsub_runtime.agent_inference", new_callable=AsyncMock)
    async def test_ask_command(self, mock_infer):
        mock_infer.return_value = "Answer"
        ctx = MagicMock()
        ctx.message.text = "!ask what time is it?"
        ctx.message.author.name = "juan"
        ctx.reply = AsyncMock()
        await self.comp.ask._callback(self.comp, ctx)
        ctx.reply.assert_called()

    @patch("bot.eventsub_runtime.is_owner", return_value=True)
    async def test_vibe_command_owner(self, mock_owner):
        ctx = MagicMock()
        ctx.message.text = "!vibe high energy"
        ctx.reply = AsyncMock()
        with patch("bot.eventsub_runtime.context") as mock_context:
            await self.comp.vibe._callback(self.comp, ctx)
            self.assertEqual(mock_context.stream_vibe, "high energy")
            ctx.reply.assert_called()


class TestByteBot(unittest.IsolatedAsyncioTestCase):
    @patch("bot.eventsub_runtime.commands.Bot.__init__")
    def test_init(self, mock_super):
        with patch.dict(
            os.environ,
            {"TWITCH_CLIENT_ID": "cid", "TWITCH_BOT_ID": "bid", "TWITCH_CHANNEL_ID": "chid"},
        ):
            with (
                patch("bot.eventsub_runtime.BOT_ID", None),
                patch("bot.eventsub_runtime.CLIENT_ID", None),
            ):
                bot = es_runtime.ByteBot(client_secret="sec")
                mock_super.assert_called_once()

    async def test_event_ready(self):
        with patch("bot.eventsub_runtime.commands.Bot.__init__", return_value=None):
            with patch.dict(os.environ, {"TWITCH_BOT_ID": "123"}):
                bot = es_runtime.ByteBot(client_secret="s")
                # Use patch.object to set the bot_id property if it's read-only
                with patch.object(es_runtime.ByteBot, "bot_id", "123"):
                    await bot.event_ready()

    @patch("bot.eventsub_runtime.autonomy_runtime")
    async def test_close(self, mock_runtime):
        with patch("bot.eventsub_runtime.commands.Bot.__init__", return_value=None):
            with patch.dict(os.environ, {"TWITCH_BOT_ID": "123"}):
                bot = es_runtime.ByteBot(client_secret="s")
                with patch("bot.eventsub_runtime.commands.Bot.close", new_callable=AsyncMock):
                    await bot.close()
                    mock_runtime.unbind.assert_called_once()

    async def test_event_message_echo(self):
        with patch("bot.eventsub_runtime.commands.Bot.__init__", return_value=None):
            with patch.dict(os.environ, {"TWITCH_BOT_ID": "123"}):
                bot = es_runtime.ByteBot(client_secret="s")
                payload = MagicMock()
                payload.echo = True
                await bot.event_message(payload)  # Should return immediately
