import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.irc_connection import IrcConnectionMixin


class MockBot(IrcConnectionMixin):
    def __init__(self):
        self.host = "localhost"
        self.port = 6667
        self.use_tls = False
        self.bot_login = "bot"
        self.channel_logins = ["chan"]
        self.token_manager = MagicMock()
        # Use AsyncMock for the token manager's async method
        self.token_manager.ensure_token_for_connection = AsyncMock(return_value="token")
        self.reader = None
        self.writer = None


class TestIrcConnectionV2(unittest.IsolatedAsyncioTestCase):
    async def test_connect_timeout(self):
        bot = MockBot()
        with patch("asyncio.open_connection", side_effect=TimeoutError()):
            with self.assertRaises(asyncio.TimeoutError):
                await bot._connect()

    async def test_await_login_confirmation_timeout(self):
        bot = MockBot()
        bot.reader = AsyncMock()
        bot.reader.readline.side_effect = TimeoutError()
        with self.assertRaises(asyncio.TimeoutError):
            await bot._await_login_confirmation(timeout_seconds=0.1)

    async def test_await_login_confirmation_auth_failure(self):
        bot = MockBot()
        bot.reader = AsyncMock()
        bot.reader.readline.return_value = (
            b":tmi.twitch.tv NOTICE * :Login authentication failed\r\n"
        )
        with self.assertRaises(RuntimeError) as cm:
            await bot._await_login_confirmation()
        self.assertIn("authentication failed", str(cm.exception))

    async def test_send_raw_no_writer_error(self):
        bot = MockBot()
        bot.writer = None
        # The code explicitly raises RuntimeError if writer is None
        with self.assertRaises(RuntimeError):
            await bot._send_raw("PING")

    @patch("bot.irc_connection.asyncio.open_connection")
    async def test_connect_generic_error(self, mock_open):
        bot = MockBot()
        mock_open.side_effect = Exception("Connection refused")
        with self.assertRaises(Exception):
            await bot._connect()
