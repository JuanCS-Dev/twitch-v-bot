import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.irc_state import IrcChannelStateMixin


class DummyState(IrcChannelStateMixin):
    def __init__(self):
        self.channel_logins = ["channel1"]
        self.joined_channels = {"channel1"}
        self.primary_channel_login = "channel1"
        self.reader = AsyncMock()
        self._line_reader_running = True
        self._line_reader_task = None
        self._pending_join_events = {}
        self._pending_part_events = {}
        self._send_raw_mock = AsyncMock()

    async def _send_raw(self, line: str) -> None:
        await self._send_raw_mock(line)


class TestIrcStateV3:
    @pytest.mark.asyncio
    async def test_build_status_line(self):
        state = DummyState()
        with patch("bot.irc_state.build_status_line", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = "status"
            res = await state.build_status_line()
            assert res == "status"

    def test_channel_action_timeout_seconds(self):
        state = DummyState()
        with patch("bot.irc_state.TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS", 1.0):
            assert state.channel_action_timeout_seconds == 1.0

    @pytest.mark.asyncio
    async def test_send_reply(self):
        state = DummyState()
        await state.send_reply("hello", "channel1")
        state._send_raw_mock.assert_called_with("PRIVMSG #channel1 :hello")

    @pytest.mark.asyncio
    async def test_send_tracked_channel_reply(self):
        state = DummyState()
        mock_ctx = MagicMock()
        with (
            patch("bot.irc_state.context_manager.get", return_value=mock_ctx),
            patch("bot.irc_state.observability.record_reply"),
        ):
            await state._send_tracked_channel_reply("channel1", "tracked")
            state._send_raw_mock.assert_called_with("PRIVMSG #channel1 :tracked")
            mock_ctx.remember_bot_reply.assert_called_with("tracked")

    def test_mark_channel_joined(self):
        state = DummyState()
        assert state._mark_channel_joined("channel2") is True
        assert "channel2" in state.joined_channels

    def test_mark_channel_parted(self):
        state = DummyState()
        state._mark_channel_joined("channel2")
        assert state._mark_channel_parted("channel1") is True
        assert "channel1" not in state.joined_channels

    @pytest.mark.asyncio
    async def test_wait_for_channel_confirmation(self):
        state = DummyState()
        event = asyncio.Event()
        event.set()
        pending = {"ch": event}
        assert (
            await state._wait_for_channel_confirmation(
                channel_login="ch", action="JOIN", pending_map=pending
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_admin_join_channel(self):
        state = DummyState()

        def create_task_side_effect(coroutine):
            coroutine.close()
            return MagicMock()

        with patch("asyncio.create_task", side_effect=create_task_side_effect):
            res, msg, channels = await state.admin_join_channel("channel2")
            assert res is True
            assert "channel2" in state.joined_channels

    @pytest.mark.asyncio
    async def test_admin_part_channel(self):
        state = DummyState()
        state.joined_channels.add("channel2")
        state.channel_logins.append("channel2")

        def create_task_side_effect(coroutine):
            coroutine.close()
            return MagicMock()

        with patch("asyncio.create_task", side_effect=create_task_side_effect):
            res, msg, channels = await state.admin_part_channel("channel2")
            assert res is True
            assert "channel2" not in state.joined_channels
