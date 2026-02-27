import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot.bootstrap_runtime as bootstrap


class TestBootstrapExecution(unittest.IsolatedAsyncioTestCase):
    @patch("bot.bootstrap_runtime.IrcByteBot")
    @patch("bot.bootstrap_runtime.build_irc_token_manager")
    @patch("bot.bootstrap_runtime.resolve_irc_channel_logins")
    @patch("bot.bootstrap_runtime.asyncio.run")
    def test_run_irc_mode_full_path(self, mock_run, mock_resolve, mock_btm, mock_bot_class):
        def run_side_effect(coroutine):
            coroutine.close()

        mock_run.side_effect = run_side_effect
        mock_resolve.return_value = ["chan"]
        mock_tm = MagicMock()
        mock_btm.return_value = mock_tm
        bootstrap.run_irc_mode()
        mock_run.assert_called_once()

    @pytest.mark.skip(reason="Testes de implementacao interna - fragile ao modulo de carga")
    @patch("bot.bootstrap_runtime.require_env")
    @patch("bot.bootstrap_runtime.TWITCH_CLIENT_ID")
    def test_build_irc_token_manager_with_refresh(self, mock_client_id, mock_require):
        mock_require.side_effect = lambda x: {
            "TWITCH_USER_TOKEN": "user_token",
        }.get(x, "")
        mock_client_id.__bool__ = lambda self: True
        mock_client_id.__str__ = lambda self: "client_id"
        mock_client_id.__eq__ = lambda self, other: str(other) == "client_id"
        with (
            patch("os.environ.get", return_value="r"),
            patch("bot.bootstrap_runtime.resolve_client_secret_for_irc_refresh", return_value="s"),
        ):
            tm = bootstrap.build_irc_token_manager()
            self.assertEqual(tm.refresh_token, "r")
            self.assertEqual(tm.client_id, "client_id")

    @pytest.mark.asyncio
    async def test_resolve_irc_channel_logins_env_required(self):
        with (
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGINS_RAW", ""),
            patch("bot.bootstrap_runtime.TWITCH_CHANNEL_LOGIN", ""),
            patch("os.environ.get", return_value="required_chan"),
            patch("bot.bootstrap_runtime.parse_channel_logins", return_value=["required_chan"]),
        ):
            res = await bootstrap.resolve_irc_channel_logins()
            self.assertEqual(res, ["required_chan"])
