import os
import unittest
from unittest.mock import patch

import bot.bootstrap_runtime as bootstrap


class TestBootstrapRuntimeV3(unittest.TestCase):
    def test_get_secret_fail(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as cm:
                bootstrap.get_secret("missing-secret")
            self.assertIn("MISSING_SECRET", str(cm.exception))

    def test_require_env_fail(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as cm:
                bootstrap.require_env("REQUIRED_VAR")
            self.assertIn("REQUIRED_VAR", str(cm.exception))

    def test_resolve_irc_channel_logins_all_missing(self):
        with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", None):
            with patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", None):
                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaises(RuntimeError):
                        bootstrap.resolve_irc_channel_logins()

    @patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", None)
    @patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_NAME", "my-secret")
    def test_resolve_client_secret_for_irc_refresh_exception(self):
        with patch("bot.bootstrap_runtime.get_secret", side_effect=Exception("boom")):
            res = bootstrap.resolve_client_secret_for_irc_refresh()
            self.assertEqual(res, "")

    @patch("bot.bootstrap_runtime.TWITCH_REFRESH_TOKEN", "rt")
    @patch("bot.bootstrap_runtime.TWITCH_USER_TOKEN", "ut")
    @patch("bot.bootstrap_runtime.CLIENT_ID", "cid")
    def test_build_irc_token_manager_no_secret_warning(self):
        with patch("bot.bootstrap_runtime.resolve_client_secret_for_irc_refresh", return_value=""):
            with patch("bot.bootstrap_runtime.logger.warning") as mock_warn:
                tm = bootstrap.build_irc_token_manager()
                self.assertEqual(tm.client_secret, "")
                mock_warn.assert_called()

    @patch("bot.bootstrap_runtime.TWITCH_USER_TOKEN", "ut")
    def test_build_irc_token_manager_no_refresh(self):
        with patch("bot.bootstrap_runtime.TWITCH_REFRESH_TOKEN", ""):
            tm = bootstrap.build_irc_token_manager()
            self.assertEqual(tm.refresh_token, "")
