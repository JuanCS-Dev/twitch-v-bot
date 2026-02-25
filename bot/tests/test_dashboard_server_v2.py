import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.dashboard_server import HealthHandler, run_server


class TestDashboardServerV2:
    @patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None)
    def test_dashboard_authorized(self, mock_init):
        handler = HealthHandler(MagicMock(), MagicMock(), MagicMock())
        handler.headers = {}
        handler.path = "/api/v1/test?auth=invalid"
        handler.client_address = ("127.0.0.1", 12345)
        handler.address_string = MagicMock(return_value="127.0.0.1")

        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", ""):
            assert handler._dashboard_authorized() is True

        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "secret"):
            with patch("bot.dashboard_server.is_dashboard_admin_authorized", return_value=False):
                assert handler._dashboard_authorized() is False

        # With valid token in query
        handler.path = "/api/v1/test?auth=secret"
        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "secret"):
            with patch("bot.dashboard_server.is_dashboard_admin_authorized", return_value=False):
                assert handler._dashboard_authorized() is True

    @patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None)
    def test_send_dashboard_auth_challenge(self, mock_init):
        handler = HealthHandler(MagicMock(), MagicMock(), MagicMock())
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()

        handler._send_dashboard_auth_challenge()
        handler.send_response.assert_called_once_with(401)
        handler.wfile.write.assert_called_once_with(b"Unauthorized")

    @patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None)
    def test_send_forbidden(self, mock_init):
        handler = HealthHandler(MagicMock(), MagicMock(), MagicMock())
        handler._send_json = MagicMock()
        handler._send_forbidden()
        handler._send_json.assert_called_once()

    @patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None)
    def test_read_json_payload_valid(self, mock_init):
        handler = HealthHandler(MagicMock(), MagicMock(), MagicMock())
        handler.headers = {"Content-Length": "15"}
        handler.rfile = MagicMock()
        handler.rfile.read.return_value = b'{"key": "value"}'

        payload = handler._read_json_payload()
        assert payload == {"key": "value"}

    @patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None)
    def test_handle_channel_control_irc_mode_list(self, mock_init):
        handler = HealthHandler(MagicMock(), MagicMock(), MagicMock())
        with patch("bot.dashboard_server.TWITCH_CHAT_MODE", "eventsub"):
            res, code = handler._handle_channel_control({"action": "list"})
            assert code == 200
            assert res["action"] == "list"

    @patch("bot.dashboard_server.HTTPServer")
    def test_run_server(self, mock_server):
        with patch.dict(os.environ, {"PORT": "8081"}):
            run_server()
            mock_server.assert_called_once()
            mock_server.return_value.serve_forever.assert_called_once()
