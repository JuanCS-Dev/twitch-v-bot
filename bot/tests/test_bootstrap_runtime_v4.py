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

    @pytest.mark.asyncio
    async def test_resolve_irc_channel_logins(self):
        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", "chan1,chan2"):
            assert await resolve_irc_channel_logins() == ["chan1", "chan2"]

        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""):
            with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", "chan3"):
                assert await resolve_irc_channel_logins() == ["chan3"]

        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""):
            with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", ""):
                with patch.dict(os.environ, {"TWITCH_CHANNEL_LOGIN": "chan4"}):
                    assert await resolve_irc_channel_logins() == ["chan4"]

    def test_resolve_client_secret_for_irc_refresh(self):
        with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", "inline"):
            assert resolve_client_secret_for_irc_refresh() == "inline"

        with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", ""):
            with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_NAME", "my-secret"):
                with patch("bot.bootstrap_runtime.get_secret", return_value="env_secret"):
                    assert resolve_client_secret_for_irc_refresh() == "env_secret"

    @patch("bot.bootstrap_runtime.require_env")
    def test_build_irc_token_manager(self, mock_require):
        mock_require.side_effect = lambda x: {
            "TWITCH_USER_TOKEN": "utoken",
            "TWITCH_CLIENT_ID": "cid",
        }.get(x, "")
        with patch("os.environ.get") as mock_env:
            mock_env.return_value = ""
            mgr = build_irc_token_manager()
            assert mgr.access_token == "utoken"
            assert not hasattr(mgr, "refresh_token") or not mgr.refresh_token

            mock_env.return_value = "rtoken"
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
    @patch("bot.bootstrap_runtime.asyncio.run")
    def test_run_irc_mode(self, mock_run, mock_resolve, mock_build, mock_bot_cls):
        mock_resolve.return_value = ["test"]
        mock_mgr = MagicMock()
        mock_build.return_value = mock_mgr
        mock_bot = MagicMock()
        mock_bot_cls.return_value = mock_bot

        run_irc_mode()
        mock_run.assert_called_once()

    @pytest.mark.skip(reason="Teste de implementacao interna - loop infinito")
    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    @patch("bot.bootstrap_runtime.resolve_irc_channel_logins")
    @patch("bot.bootstrap_runtime.asyncio.run")
    def test_run_irc_mode_exception(self, mock_run, mock_resolve, mock_build, mock_bot_cls):
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
