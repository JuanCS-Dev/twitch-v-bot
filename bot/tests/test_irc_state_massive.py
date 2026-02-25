import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from bot.irc_state import IrcChannelStateMixin

class MockBot(IrcChannelStateMixin):
    def __init__(self):
        self.channel_logins = ["primary"]
        self.joined_channels = {"primary"}
        self.primary_channel_login = "primary"
        self.reader = MagicMock()
        self._line_reader_running = True
        self._line_reader_task = None
        self._pending_join_events = {}
        self._pending_part_events = {}
        self.writer = AsyncMock()

    async def _send_raw(self, line: str):
        pass

class TestIrcStateMassive(unittest.IsolatedAsyncioTestCase):
    async def test_send_reply_normalization_fail(self):
        bot = MockBot()
        with patch("bot.irc_state.normalize_channel_login", return_value=""):
            with patch.object(bot, "_send_raw", new_callable=AsyncMock) as mock_send:
                await bot.send_reply("hello", channel_login="invalid")
                mock_send.assert_called_with("PRIVMSG #primary :hello")

    def test_mark_channel_joined_already_present(self):
        bot = MockBot()
        res = bot._mark_channel_joined("primary")
        self.assertFalse(res)

    def test_mark_channel_parted_normalization_fail(self):
        bot = MockBot()
        with patch("bot.irc_state.normalize_channel_login", return_value=""):
            self.assertFalse(bot._mark_channel_parted("any"))

    async def test_wait_for_confirmation_timeout(self):
        bot = MockBot()
        event = asyncio.Event()
        bot._pending_join_events["chan"] = event
        
        with patch("bot.irc_state.TWITCH_IRC_CHANNEL_ACTION_TIMEOUT_SECONDS", 0.01):
            res = await bot._wait_for_channel_confirmation(
                channel_login="chan",
                action="JOIN",
                pending_map=bot._pending_join_events
            )
            self.assertFalse(res)

    async def test_can_wait_recursion_prevention(self):
        bot = MockBot()
        # Run inside loop to have current_task
        bot._line_reader_task = asyncio.current_task()
        self.assertFalse(bot._can_wait_for_channel_confirmation())

    async def test_join_channel_already_joined(self):
        bot = MockBot()
        bot.joined_channels = {"chan"}
        res = await bot._join_channel("chan", force=False)
        self.assertFalse(res)

    async def test_part_channel_last_one_restriction(self):
        bot = MockBot()
        bot.channel_logins = ["last"]
        bot.joined_channels = {"last"}
        res = await bot._part_channel("last", force=False)
        self.assertFalse(res)

    async def test_admin_part_channel_not_connected(self):
        bot = MockBot()
        bot.joined_channels = set()
        ok, msg, chans = await bot.admin_part_channel("missing")
        self.assertFalse(ok)
        self.assertIn("not connected", msg)
