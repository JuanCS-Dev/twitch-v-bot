import unittest
from unittest.mock import MagicMock, patch

from bot.dashboard_server import HealthHandler


class MockWfile:
    def __init__(self):
        self.data = b""

    def write(self, b):
        self.data += b


class TestHealthHandler(unittest.TestCase):
    def test_send_json(self):
        # Use a real instance with mocked BaseHTTPRequestHandler parts
        with patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None):
            instance = HealthHandler()
            instance.wfile = MockWfile()
            instance.send_response = MagicMock()
            instance.send_header = MagicMock()
            instance.end_headers = MagicMock()

            instance._send_json({"foo": "bar"}, status_code=201)

            instance.send_response.assert_called_with(201)
            self.assertIn(b'"foo": "bar"', instance.wfile.data)

    def test_read_json_payload_success(self):
        with patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None):
            instance = HealthHandler()
            instance.headers = {"Content-Length": "18"}
            instance.rfile = MagicMock()
            instance.rfile.read.return_value = b'{"hello": "world"}'
            instance.MAX_CONTROL_BODY_BYTES = 4096

            payload = instance._read_json_payload()
            self.assertEqual(payload["hello"], "world")

    @patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "secret")
    def test_dashboard_authorized_query_param(self):
        with patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None):
            instance = HealthHandler()
            instance.path = "/api/foo?auth=secret"
            instance.headers = {}
            instance.address_string = MagicMock(return_value="127.0.0.1")

            with patch("bot.dashboard_server.is_dashboard_admin_authorized", return_value=False):
                self.assertTrue(instance._dashboard_authorized())

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "eventsub")
    def test_handle_channel_control_unsupported_mode(self):
        with patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None):
            instance = HealthHandler()
            instance.CHANNEL_CONTROL_IRC_ONLY_ACTIONS = {"join"}

            payload = {"action": "join", "channel": "test"}
            res, code = instance._handle_channel_control(payload)

            self.assertEqual(code, 409)
            self.assertEqual(res["error"], "unsupported_mode")
