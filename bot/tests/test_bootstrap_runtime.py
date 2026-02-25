import os
import unittest
from unittest.mock import MagicMock, patch

import bot.bootstrap_runtime as bootstrap


class TestBootstrapRuntime(unittest.TestCase):
    def test_get_secret_success(self):
        with patch.dict(os.environ, {"MY_SECRET": "hush"}):
            self.assertEqual(bootstrap.get_secret("my-secret"), "hush")

    def test_require_env_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                bootstrap.require_env("MISSING")

    def test_resolve_client_secret_refresh(self):
        # Case 1: Inline secret
        with patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", "inline"):
            self.assertEqual(bootstrap.resolve_client_secret_for_irc_refresh(), "inline")

        # Case 2: From secret name
        with (
            patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", ""),
            patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_NAME", "my-sec"),
        ):
            with patch("bot.bootstrap_runtime.get_secret", return_value="secret_val"):
                self.assertEqual(bootstrap.resolve_client_secret_for_irc_refresh(), "secret_val")

    def test_resolve_irc_channel_logins_fallback(self):
        with (
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""),
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", "only_one"),
        ):
            self.assertEqual(bootstrap.resolve_irc_channel_logins(), ["only_one"])

    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    @patch("bot.bootstrap_runtime.resolve_irc_channel_logins")
    @patch("asyncio.run")
    def test_run_irc_mode_orchestration(self, mock_run, mock_resolve, mock_btm, mock_bot_class):
        mock_resolve.return_value = ["c1"]
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot
        bootstrap.run_irc_mode()
        mock_run.assert_called_once()

    @patch("bot.bootstrap_runtime.ByteBot")
    @patch("bot.bootstrap_runtime.get_secret", return_value="sec")
    @patch("bot.bootstrap_runtime.require_env")
    def test_run_eventsub_mode(self, mock_req, mock_sec, mock_bot_class):
        mock_req.return_value = "id"
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot
        bootstrap.run_eventsub_mode()
        mock_bot.run.assert_called_once()
