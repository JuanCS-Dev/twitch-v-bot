import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.irc_connection import IrcConnectionMixin
from bot.twitch_tokens import TwitchAuthError


class DummyConnection(IrcConnectionMixin):
    def __init__(self):
        self.writer = None
        self.reader = None
        self.token_manager = AsyncMock()
        self.use_tls = False
        self.host = "irc.chat.twitch.tv"
        self.port = 6667
        self.bot_login = "testbot"
        self.channel_logins = ["testchannel"]
        self._pending_join_events = {}
        self._pending_part_events = {}

    async def _handle_membership_event(self, line):
        pass

    async def _handle_notice_line(self, line):
        pass

    async def _handle_privmsg(self, line):
        pass

    async def _recover_authentication(self, auth_error):
        return False

    def _raise_auth_error(self, line):
        raise TwitchAuthError(line)


class TestIrcConnectionV3:
    @pytest.mark.asyncio
    async def test_send_raw(self):
        conn = DummyConnection()
        conn.writer = AsyncMock()
        await conn._send_raw("PING")
        conn.writer.write.assert_called_with(b"PING\r\n")

    @pytest.mark.asyncio
    async def test_await_login_confirmation_timeout(self):
        conn = DummyConnection()
        conn.reader = AsyncMock()
        # Sleep to simulate timeout
        conn.reader.readline = AsyncMock(side_effect=TimeoutError())
        with pytest.raises(TimeoutError):
            await conn._await_login_confirmation(timeout_seconds=0.1)

    @pytest.mark.asyncio
    async def test_await_login_confirmation_success(self):
        conn = DummyConnection()
        conn.reader = AsyncMock()
        conn.reader.readline.side_effect = [b":tmi.twitch.tv 001 testbot :Welcome, GLHF!\r\n"]
        await conn._await_login_confirmation(timeout_seconds=1.0)
        # Should return without exception

    @pytest.mark.asyncio
    async def test_connect(self):
        conn = DummyConnection()
        conn.token_manager.ensure_token_for_connection.return_value = "token123"
        conn._await_login_confirmation = AsyncMock()

        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open:
            mock_open.return_value = (AsyncMock(), AsyncMock())
            await conn._connect()
            mock_open.assert_called_once()
            conn.writer.write.assert_called()  # Sent CAP, PASS, NICK, JOIN

    @pytest.mark.asyncio
    async def test_close(self):
        conn = DummyConnection()
        writer_mock = AsyncMock()
        conn.writer = writer_mock
        await conn._close()
        writer_mock.close.assert_called_once()
        assert conn.writer is None
        assert conn.reader is None

    @pytest.mark.asyncio
    async def test_run_forever_cancellation(self):
        conn = DummyConnection()
        conn._connect = AsyncMock(side_effect=asyncio.CancelledError())
        with pytest.raises(asyncio.CancelledError):
            await conn.run_forever()

    @pytest.mark.asyncio
    async def test_run_forever_reader_none(self):
        conn = DummyConnection()
        conn._connect = AsyncMock()
        # To break the outer while True, we mock asyncio.sleep to raise CancelledError
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
            with pytest.raises(asyncio.CancelledError):
                await conn.run_forever()

    @pytest.mark.asyncio
    async def test_run_forever_auth_error_recovery(self):
        conn = DummyConnection()
        conn._connect = AsyncMock()
        conn.reader = AsyncMock()
        conn.reader.readline.side_effect = [
            b"PING :tmi.twitch.tv\r\n",
            b":tmi.twitch.tv NOTICE * :Login authentication failed\r\n",
        ]
        conn._send_raw = AsyncMock()
        conn._recover_authentication = AsyncMock(return_value=True)

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
            with pytest.raises(asyncio.CancelledError):
                await conn.run_forever()

        conn._recover_authentication.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_forever_reconnect_and_handlers(self):
        conn = DummyConnection()
        conn._connect = AsyncMock()
        conn.reader = AsyncMock()
        conn.reader.readline.side_effect = [
            b":user!user@user.tmi.twitch.tv JOIN #channel\r\n",
            b":user!user@user.tmi.twitch.tv PRIVMSG #channel :hello\r\n",
            b"@msg-id=123 :tmi.twitch.tv NOTICE #channel :test\r\n",
            b"RECONNECT\r\n",
        ]
        conn._handle_membership_event = AsyncMock()
        conn._handle_privmsg = AsyncMock()
        conn._handle_notice_line = AsyncMock()

        with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
            with pytest.raises(asyncio.CancelledError):
                await conn.run_forever()

        conn._handle_membership_event.assert_called()
        conn._handle_privmsg.assert_called()
        conn._handle_notice_line.assert_called()
