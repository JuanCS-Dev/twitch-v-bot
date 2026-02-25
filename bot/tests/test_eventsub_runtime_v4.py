import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.eventsub_runtime import ByteBot


class MockMessage:
    def __init__(self, text, author_name="user", echo=False):
        self.text = text
        self.echo = echo
        self.author = MagicMock()
        self.author.name = author_name
        self.reply = AsyncMock()


class TestEventsubRuntimeV4(unittest.IsolatedAsyncioTestCase):
    @patch("bot.eventsub_runtime.CLIENT_ID", "c")
    @patch("bot.eventsub_runtime.BOT_ID", "b")
    async def test_byte_bot_event_message_trigger(self):
        bot = ByteBot(client_secret="s")
        # Mock handle_byte_prompt to avoid network/inference
        bot.handle_byte_prompt = AsyncMock()

        msg = MockMessage("@byte qual o seu nome?")
        await bot.event_message(msg)

        bot.handle_byte_prompt.assert_called_once()

    @patch("bot.eventsub_runtime.CLIENT_ID", "c")
    @patch("bot.eventsub_runtime.BOT_ID", "b")
    async def test_byte_bot_event_message_command(self):
        bot = ByteBot(client_secret="s")
        bot.handle_commands = AsyncMock()

        msg = MockMessage("!ask algo")
        await bot.event_message(msg)

        bot.handle_commands.assert_called_once()

    @patch("bot.eventsub_runtime.CLIENT_ID", "c")
    @patch("bot.eventsub_runtime.BOT_ID", "b")
    async def test_byte_bot_event_message_echo(self):
        bot = ByteBot(client_secret="s")
        bot.handle_commands = AsyncMock()

        msg = MockMessage("!ask algo", echo=True)
        await bot.event_message(msg)

        bot.handle_commands.assert_not_called()
