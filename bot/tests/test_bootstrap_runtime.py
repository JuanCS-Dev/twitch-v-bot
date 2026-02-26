import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import bot.bootstrap_runtime as bootstrap


class TestBootstrapRuntime(unittest.IsolatedAsyncioTestCase):
    @patch("bot.bootstrap_runtime.os.environ.get")
    def test_get_secret_success(self, mock_env):
        mock_env.return_value = "hush"
        self.assertEqual(bootstrap.get_secret(), "hush")

    def test_require_env_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                bootstrap.require_env("MISSING_VAR")

    @patch("bot.bootstrap_runtime.TWITCH_CLIENT_SECRET_INLINE", "inline")
    def test_resolve_client_secret_refresh(self):
        self.assertEqual(bootstrap.resolve_client_secret_for_irc_refresh(), "inline")

    @patch("bot.bootstrap_runtime.parse_channel_logins")
    @patch("bot.bootstrap_runtime.persistence.get_active_channels", new_callable=AsyncMock)
    async def test_resolve_irc_channel_logins_fallback(self, mock_get_db, mock_parse):
        # 1. Supabase falha (retorna vazio)
        mock_get_db.return_value = []
        mock_parse.return_value = ["canal_env"]

        with patch.dict(os.environ, {"TWITCH_CHANNEL_LOGINS": "canal_env"}):
            res = await bootstrap.resolve_irc_channel_logins()
            self.assertEqual(res, ["canal_env"])

    @patch("bot.bootstrap_runtime.asyncio.run")
    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    def test_run_irc_mode_orchestration(self, mock_build_token, mock_bot, mock_run):
        # Apenas valida que o asyncio.run é chamado (o que dispara o loop interno)
        bootstrap.run_irc_mode()
        self.assertTrue(mock_run.called)

    @patch("bot.bootstrap_runtime.asyncio.run")
    @patch("bot.bootstrap_runtime.ByteBot")
    def test_run_eventsub_mode(self, mock_bot, mock_run):
        bootstrap.run_eventsub_mode()
        self.assertTrue(mock_run.called)


if __name__ == "__main__":
    unittest.main()
