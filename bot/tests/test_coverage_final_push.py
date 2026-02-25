import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import bot.twitch_clips_api as clips_api
from bot.twitch_tokens import TwitchAuthError, TwitchTokenManager


class TestCoverageFinalPush(unittest.TestCase):
    def test_token_manager_sync_errors_injected(self):
        mock_urlopen = MagicMock()
        mock_err_500 = HTTPError("u", 500, "Server", {}, MagicMock(read=lambda: b"error"))
        mock_urlopen.side_effect = mock_err_500

        tm = TwitchTokenManager(
            access_token="v",
            client_id="c",
            client_secret="s",
            refresh_token="r",
            urlopen_fn=mock_urlopen,
        )

        with self.assertRaises(TwitchAuthError):
            tm._validate_token_sync()
        with self.assertRaises(TwitchAuthError):
            tm._refresh_token_sync()

    def test_token_manager_invalid_json_refresh(self):
        mock_urlopen = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"invalid json {"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        tm = TwitchTokenManager(
            access_token="v",
            client_id="c",
            client_secret="s",
            refresh_token="r",
            urlopen_fn=mock_urlopen,
        )
        with self.assertRaises(TwitchAuthError) as cm:
            tm._refresh_token_sync()
        self.assertIn("Resposta invalida", str(cm.exception))

    def test_token_manager_expiration_logic(self):
        tm = TwitchTokenManager(access_token="v", refresh_margin_seconds=300)
        tm._set_expiration(None)
        self.assertFalse(tm._is_expiring_soon())
        tm.expires_at_monotonic = time.monotonic() + 100
        self.assertTrue(tm._is_expiring_soon())
        tm.expires_at_monotonic = time.monotonic() + 1000
        self.assertFalse(tm._is_expiring_soon())

    def test_token_manager_can_refresh_variants(self):
        tm = TwitchTokenManager(access_token="v")
        self.assertFalse(tm.can_refresh)
        tm.refresh_token = "r"
        tm.client_id = "c"
        tm.client_secret = "s"
        self.assertTrue(tm.can_refresh)

    def test_clips_api_sync_handle_errors(self):
        err_403 = HTTPError("u", 403, "Forbidden", {}, None)
        with self.assertRaises(clips_api.TwitchClipAuthError):
            clips_api._handle_http_error(err_403)
        err_404 = HTTPError("u", 404, "Not Found", {}, None)
        with self.assertRaises(clips_api.TwitchClipNotFoundError):
            clips_api._handle_http_error(err_404)
        err_429 = HTTPError("u", 429, "Limit", {"Ratelimit-Reset": "garbage"}, None)
        with self.assertRaises(clips_api.TwitchClipRateLimitError):
            clips_api._handle_http_error(err_429)

    def test_dashboard_server_assets_logic(self):
        from bot.dashboard_server import HealthHandler

        tmp_dir = Path("/tmp/byte_test_dash_real_final_final")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        test_file = tmp_dir / "test.js"
        test_file.write_text("alert(1)")

        with patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None):
            instance = HealthHandler()
            instance._send_text = MagicMock()
            instance._send_bytes = MagicMock()
            with patch("bot.dashboard_server.DASHBOARD_DIR", tmp_dir):
                instance._send_dashboard_asset("test.js", "application/javascript")
                instance._send_bytes.assert_called()
                instance._send_dashboard_asset("../secret.txt", "text/plain")
                instance._send_text.assert_called_with("Invalid path", status_code=400)
