import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import bot.irc_connection as irc_connection
from bot.twitch_tokens import TwitchAuthError

class MockBot(irc_connection.IrcConnectionMixin):
    def __init__(self):
        self.host = "irc.twitch.tv"
        self.port = 6667
        self.use_tls = False
        self.bot_login = "testbot"
        self.channel_logins = ["chan1"]
        self.reader = None
        self.writer = None
        self.token_manager = AsyncMock()
        self._line_reader_running = False
        self._line_reader_task = None
        self._pending_join_events = {}
        self._pending_part_events = {}
    
    async def _handle_membership_event(self, line): pass
    async def _handle_notice_line(self, line): pass
    async def _handle_privmsg(self, line): pass
    async def _recover_authentication(self, auth_error): return True
    def _raise_auth_error(self, line): raise TwitchAuthError(line)

class TestIrcConnection(unittest.IsolatedAsyncioTestCase):
    async def test_send_raw_no_writer(self):
        bot = MockBot()
        with self.assertRaises(RuntimeError):
            await bot._send_raw("PING")

    async def test_send_raw_success(self):
        bot = MockBot()
        bot.writer = AsyncMock()
        await bot._send_raw("PING")
        bot.writer.write.assert_called_with(b"PING\r\n")
        bot.writer.drain.assert_called_once()

    @patch("bot.irc_connection.IRC_WELCOME_PATTERN")
    async def test_await_login_confirmation_success(self, mock_pattern):
        bot = MockBot()
        bot.reader = MagicMock()
        bot.writer = AsyncMock()
        
        # Setup responses
        responses = [
            b"PING :123\r\n",
            b":tmi.twitch.tv 001 testbot :Welcome\r\n"
        ]
        
        async def mock_readline():
            if responses:
                return responses.pop(0)
            # Return something that doesn't trigger ConnectionError immediately
            # but allows the loop to continue if needed, or just block.
            return b":dummy line\r\n"
            
        bot.reader.readline = mock_readline
        mock_pattern.search.side_effect = [None, True]
        
        await bot._await_login_confirmation(timeout_seconds=2.0)
        bot.writer.write.assert_any_call(b"PONG :123\r\n")

    async def test_await_login_confirmation_timeout(self):
        bot = MockBot()
        bot.reader = MagicMock()
        async def slow_readline():
            await asyncio.sleep(1)
            return b"too late"
        bot.reader.readline = slow_readline
        
        with self.assertRaises(asyncio.TimeoutError):
            await bot._await_login_confirmation(timeout_seconds=0.1)

    @patch("asyncio.open_connection")
    @patch.object(irc_connection.IrcConnectionMixin, "_await_login_confirmation", new_callable=AsyncMock)
    async def test_connect_sequence(self, mock_await, mock_open):
        bot = MockBot()
        bot.token_manager.ensure_token_for_connection.return_value = "fake-token"
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open.return_value = (mock_reader, mock_writer)
        
        await bot._connect()
        
        self.assertEqual(bot.reader, mock_reader)
        self.assertEqual(bot.writer, mock_writer)
        mock_writer.write.assert_any_call(b"PASS oauth:fake-token\r\n")
        mock_writer.write.assert_any_call(b"JOIN #chan1\r\n")

    async def test_run_forever_reconnect_on_error(self):
        bot = MockBot()
        with patch.object(bot, "_connect", side_effect=[Exception("First fail"), asyncio.CancelledError()]):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                try:
                    await bot.run_forever()
                except asyncio.CancelledError:
                    pass
                mock_sleep.assert_called_with(5)
