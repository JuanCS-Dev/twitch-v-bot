import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.irc_handlers import IrcLineHandlersMixin
from bot.twitch_tokens import TwitchAuthError


class DummyHandlers(IrcLineHandlersMixin):
    def __init__(self):
        self.bot_login = "bytebot"
        self.joined_channels = {"channel1"}
        self._pending_join_events = {"channel2": asyncio.Event()}
        self._pending_part_events = {"channel1": asyncio.Event()}
        self.token_manager = AsyncMock()

    def _mark_channel_joined(self, channel_login: str) -> bool:
        return True

    def _mark_channel_parted(self, channel_login: str) -> bool:
        return True

    def _signal_pending_channel_action(self, pending_map, channel_login: str) -> None:
        pass

    async def _handle_channel_management_prompt(
        self, prompt: str, author, source_channel: str
    ) -> bool:
        return False

    async def send_reply(self, text: str, channel_login: str | None = None) -> None:
        pass

    def build_status_line(self) -> str:
        return "status"


class TestIrcHandlersV3:
    @pytest.mark.asyncio
    async def test_handle_membership_event_join(self):
        handler = DummyHandlers()
        handler._mark_channel_joined = MagicMock(return_value=True)
        handler._signal_pending_channel_action = MagicMock()

        line = ":bytebot!bytebot@bytebot.tmi.twitch.tv JOIN #channel2"
        await handler._handle_membership_event(line)

        handler._mark_channel_joined.assert_called_with("channel2")
        handler._signal_pending_channel_action.assert_called_with(
            handler._pending_join_events, "channel2"
        )

    @pytest.mark.asyncio
    async def test_handle_membership_event_part(self):
        handler = DummyHandlers()
        handler._mark_channel_parted = MagicMock(return_value=True)
        handler._signal_pending_channel_action = MagicMock()

        line = ":bytebot!bytebot@bytebot.tmi.twitch.tv PART #channel1"
        await handler._handle_membership_event(line)

        handler._mark_channel_parted.assert_called_with("channel1")
        handler._signal_pending_channel_action.assert_called_with(
            handler._pending_part_events, "channel1"
        )

    @pytest.mark.asyncio
    async def test_handle_notice_line(self):
        handler = DummyHandlers()
        with patch("bot.irc_handlers.is_irc_notice_delivery_block", return_value=True):
            with patch("bot.irc_handlers.observability.record_error") as mock_record:
                line = "@msg-id=msg_banned :tmi.twitch.tv NOTICE #channel1 :You are banned from chatting in this channel."
                await handler._handle_notice_line(line)
                mock_record.assert_called_once()
                assert "msg_banned" in mock_record.call_args[1]["details"]

    @pytest.mark.asyncio
    async def test_handle_privmsg_ignore_not_joined(self):
        handler = DummyHandlers()
        line = "@user-type= :user!user@user.tmi.twitch.tv PRIVMSG #notjoined :hello"
        await handler._handle_privmsg(line)
        # Should return early, no exception, nothing called

    @pytest.mark.asyncio
    async def test_handle_privmsg_ignore_own_message(self):
        handler = DummyHandlers()
        line = "@user-type= :bytebot!bytebot@bytebot.tmi.twitch.tv PRIVMSG #channel1 :hello"
        await handler._handle_privmsg(line)
        # Should return early

    @pytest.mark.asyncio
    @patch("bot.irc_handlers.ENABLE_LIVE_CONTEXT_LEARNING", True)
    @patch("bot.irc_handlers.context.remember_user_message")
    @patch("bot.irc_handlers.auto_update_scene_from_message", new_callable=AsyncMock)
    @patch("bot.irc_handlers.handle_byte_prompt_text", new_callable=AsyncMock)
    async def test_handle_privmsg_byte_prompt(
        self, mock_handle_text, mock_auto_update, mock_remember
    ):
        handler = DummyHandlers()
        mock_auto_update.return_value = ["movie"]
        line = "@display-name=User :user!user@user.tmi.twitch.tv PRIVMSG #channel1 :byte hello"

        await handler._handle_privmsg(line)

        mock_remember.assert_called_with("User", "byte hello")
        mock_auto_update.assert_called_once()
        mock_handle_text.assert_called_once()
        assert mock_handle_text.call_args[0][0] == "hello"  # byte_prompt

    @pytest.mark.asyncio
    async def test_recover_authentication_success(self):
        handler = DummyHandlers()
        assert await handler._recover_authentication(Exception("test")) is True
        handler.token_manager.force_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_recover_authentication_failure(self):
        handler = DummyHandlers()
        handler.token_manager.force_refresh.side_effect = Exception("refresh failed")
        assert await handler._recover_authentication(Exception("test")) is False

    def test_raise_auth_error(self):
        handler = DummyHandlers()
        with pytest.raises(TwitchAuthError):
            handler._raise_auth_error("failed")
