import unittest
from unittest.mock import MagicMock, patch

import bot.bootstrap_runtime as bootstrap


class TestBootstrapExecution(unittest.IsolatedAsyncioTestCase):
    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    @patch("bot.bootstrap_runtime.resolve_irc_channel_logins")
    @patch("bot.bootstrap_runtime.asyncio.run")
    def test_run_irc_mode_full_path(self, mock_run, mock_resolve, mock_btm, mock_bot_class):
        mock_resolve.return_value = ["chan"]
        mock_tm = MagicMock()
        mock_btm.return_value = mock_tm
        bootstrap.run_irc_mode()
        mock_run.assert_called_once()

    @patch("bot.bootstrap_runtime.require_env")
    def test_build_irc_token_manager_with_refresh(self, mock_req):
        mock_req.side_effect = ["user_token", "client_id"]
        # FIXED: Added parentheses for multi-line with
        with (
            patch("bot.bootstrap_runtime.TWITCH_USER_TOKEN", "t"),
            patch("bot.bootstrap_runtime.TWITCH_REFRESH_TOKEN", "r"),
            patch("bot.bootstrap_runtime.CLIENT_ID", "c"),
            patch("bot.bootstrap_runtime.resolve_client_secret_for_irc_refresh", return_value="s"),
        ):
            tm = bootstrap.build_irc_token_manager()
            self.assertEqual(tm.refresh_token, "r")
            self.assertEqual(tm.client_id, "c")

    def test_resolve_irc_channel_logins_env_required(self):
        with (
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""),
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", ""),
            patch("os.environ.get", return_value="required_chan"),
            patch("bot.bootstrap_runtime.parse_channel_logins", return_value=["required_chan"]),
        ):
            res = bootstrap.resolve_irc_channel_logins()
            self.assertEqual(res, ["required_chan"])
