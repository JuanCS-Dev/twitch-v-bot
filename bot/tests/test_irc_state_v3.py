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
    def test_build_status_line(self):
        state = DummyState()
        with patch("bot.irc_state.build_status_line", return_value="status"):
            assert state.build_status_line() == "status"

    def test_channel_action_timeout_seconds(self):
        state = DummyState()
        with patch("bot.irc_state.TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS", 1.0):
            assert state.channel_action_timeout_seconds == 1.0

    @pytest.mark.asyncio
    async def test_send_reply(self):
        state = DummyState()
        await state.send_reply("hello", "channel1")
        state._send_raw_mock.assert_called_with("PRIVMSG #channel1 :hello")

        # Test fallback to primary
        state._send_raw_mock.reset_mock()
        await state.send_reply("hello", "notjoined")
        state._send_raw_mock.assert_called_with("PRIVMSG #channel1 :hello")

    @pytest.mark.asyncio
    async def test_send_tracked_channel_reply(self):
        state = DummyState()
        with (
            patch("bot.irc_state.context.remember_bot_reply"),
            patch("bot.irc_state.observability.record_reply"),
        ):
            await state._send_tracked_channel_reply("channel1", "tracked")
            state._send_raw_mock.assert_called_with("PRIVMSG #channel1 :tracked")

            state._send_raw_mock.reset_mock()
            await state._send_tracked_channel_reply("notjoined", "tracked")
            state._send_raw_mock.assert_not_called()

    def test_mark_channel_joined(self):
        state = DummyState()
        assert state._mark_channel_joined("channel2") is True
        assert "channel2" in state.joined_channels
        assert "channel2" in state.channel_logins

        # Already joined
        assert state._mark_channel_joined("channel1") is False

    def test_mark_channel_parted(self):
        state = DummyState()
        state._mark_channel_joined("channel2")

        assert state._mark_channel_parted("channel1") is True
        assert "channel1" not in state.joined_channels
        assert state.primary_channel_login == "channel2"

        # Already parted
        assert state._mark_channel_parted("channel1") is False

    def test_signal_pending_channel_action(self):
        state = DummyState()
        event = asyncio.Event()
        pending = {"ch": event}
        state._signal_pending_channel_action(pending, "ch")
        assert event.is_set()

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
        assert "ch" not in pending

    @pytest.mark.asyncio
    async def test_wait_for_channel_confirmation_timeout(self):
        state = DummyState()
        event = asyncio.Event()
        pending = {"ch": event}
        with patch("bot.irc_state.IrcChannelStateMixin.channel_action_timeout_seconds", 0.01):
            assert (
                await state._wait_for_channel_confirmation(
                    channel_login="ch", action="JOIN", pending_map=pending
                )
                is False
            )

    @pytest.mark.asyncio
    async def test_join_channel(self):
        state = DummyState()
        # Already joined
        assert await state._join_channel("channel1") is False

        with patch.object(state, "_wait_for_channel_confirmation", return_value=True) as mock_wait:
            assert await state._join_channel("channel2") is True
            state._send_raw_mock.assert_called_with("JOIN #channel2")
            mock_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_part_channel(self):
        state = DummyState()
        state.joined_channels.add("channel2")
        state.channel_logins.append("channel2")

        # Already parted
        assert await state._part_channel("notjoined") is False

        with patch.object(state, "_wait_for_channel_confirmation", return_value=True) as mock_wait:
            assert await state._part_channel("channel2") is True
            state._send_raw_mock.assert_called_with("PART #channel2")
            mock_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_list_channels(self):
        state = DummyState()
        assert await state.admin_list_channels() == ["channel1"]

    @pytest.mark.asyncio
    async def test_admin_join_channel(self):
        state = DummyState()
        # Already joined
        res, msg, channels = await state.admin_join_channel("channel1")
        assert res is True

        with patch("asyncio.create_task") as mock_task:
            res, msg, channels = await state.admin_join_channel("channel2")
            assert res is True
            assert "channel2" in state.joined_channels
            mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_part_channel(self):
        state = DummyState()
        state.joined_channels.add("channel2")
        state.channel_logins.append("channel2")

        # Not joined
        res, msg, channels = await state.admin_part_channel("channel3")
        assert res is False

        with patch("asyncio.create_task") as mock_task:
            res, msg, channels = await state.admin_part_channel("channel2")
            assert res is True
            assert "channel2" not in state.joined_channels
            mock_task.assert_called_once()
