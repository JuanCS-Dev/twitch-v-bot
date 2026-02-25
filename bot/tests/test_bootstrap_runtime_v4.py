import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.bootstrap_runtime import (
    build_irc_token_manager,
    get_secret,
    require_env,
    resolve_client_secret_for_irc_refresh,
    resolve_irc_channel_logins,
    run_eventsub_mode,
    run_irc_mode,
)


class TestBootstrapRuntimeV4:
    def test_get_secret(self):
        with patch.dict(os.environ, {"TWITCH_CLIENT_SECRET": "test_secret"}):
            assert get_secret("twitch-client-secret") == "test_secret"

        with patch.dict(os.environ, clear=True):
            with pytest.raises(RuntimeError):
                get_secret("missing")

    def test_require_env(self):
        with patch.dict(os.environ, {"EXISTING": "val"}):
            assert require_env("EXISTING") == "val"
        with patch.dict(os.environ, clear=True):
            with pytest.raises(RuntimeError):
                require_env("MISSING")

    def test_resolve_irc_channel_logins(self):
        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", "chan1,chan2"):
            assert resolve_irc_channel_logins() == ["chan1", "chan2"]

        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""):
            with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", "chan3"):
                assert resolve_irc_channel_logins() == ["chan3"]

        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""):
            with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", ""):
                with patch.dict(os.environ, {"TWITCH_CHANNEL_LOGIN": "chan4"}):
                    assert resolve_irc_channel_logins() == ["chan4"]

    def test_resolve_client_secret_for_irc_refresh(self):
        with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", "inline"):
            assert resolve_client_secret_for_irc_refresh() == "inline"

        with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", ""):
            with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_NAME", "my-secret"):
                with patch.dict(os.environ, {"MY_SECRET": "env_secret"}):
                    assert resolve_client_secret_for_irc_refresh() == "env_secret"

    def test_build_irc_token_manager(self):
        with patch("bot.bootstrap_runtime.TWITCH_USER_TOKEN", "utoken"):
            with patch("bot.bootstrap_runtime.TWITCH_REFRESH_TOKEN", ""):
                mgr = build_irc_token_manager()
                assert mgr.access_token == "utoken"
                assert not hasattr(mgr, "refresh_token") or not mgr.refresh_token

            with patch("bot.bootstrap_runtime.TWITCH_REFRESH_TOKEN", "rtoken"):
                with patch("bot.bootstrap_runtime.CLIENT_ID", "cid"):
                    with patch(
                        "bot.bootstrap_runtime.resolve_client_secret_for_irc_refresh",
                        return_value="csec",
                    ):
                        mgr = build_irc_token_manager()
                        assert mgr.refresh_token == "rtoken"
                        assert mgr.client_secret == "csec"

    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    @patch("bot.bootstrap_runtime.resolve_irc_channel_logins")
    def test_run_irc_mode(self, mock_resolve, mock_build, mock_bot_cls):
        mock_resolve.return_value = ["test"]
        mock_mgr = MagicMock()
        mock_build.return_value = mock_mgr
        mock_bot = MagicMock()
        mock_bot_cls.return_value = mock_bot

        # We need to test the inner asyncio.run which is tricky due to the infinite loops
        # Instead, we just mock the inner run_with_channel_control to return immediately
        with patch("asyncio.run") as mock_run:
            run_irc_mode()
            mock_run.assert_called_once()

    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    @patch("bot.bootstrap_runtime.resolve_irc_channel_logins")
    def test_run_irc_mode_exception(self, mock_resolve, mock_build, mock_bot_cls):
        mock_resolve.return_value = ["test"]
        mock_build.return_value = MagicMock()
        mock_bot_cls.side_effect = Exception("init failed")

        # Should catch and log, not crash
        with patch("bot.bootstrap_runtime.logger.error") as mock_log:
            run_irc_mode()
            mock_log.assert_called()

    @patch("bot.bootstrap_runtime.ByteBot")
    def test_run_eventsub_mode(self, mock_bot_cls):
        with patch.dict(
            os.environ,
            {
                "TWITCH_CLIENT_ID": "cid",
                "TWITCH_BOT_ID": "bid",
                "TWITCH_CHANNEL_ID": "chid",
                "TWITCH_CLIENT_SECRET": "sec",
            },
        ):
            mock_bot = MagicMock()
            mock_bot_cls.return_value = mock_bot
            run_eventsub_mode()
            mock_bot.run.assert_called_once()
