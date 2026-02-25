import json
import unittest
from unittest.mock import MagicMock, patch

from bot.dashboard_server import HealthHandler


class TestDashboardServerExtra(unittest.TestCase):
    @patch("bot.dashboard_server.BaseHTTPRequestHandler.__init__", return_value=None)
    def setUp(self, mock_init):
        self.handler = HealthHandler(MagicMock(), MagicMock(), MagicMock())
        self.handler.headers = {}
        self.handler.rfile = MagicMock()
        self.handler.wfile = MagicMock()
        self.handler._send_json = MagicMock()
        self.handler._send_text = MagicMock()
        self.handler._send_bytes = MagicMock()

    def test_read_json_payload_empty_header(self):
        with self.assertRaises(ValueError):
            self.handler._read_json_payload()

    def test_read_json_payload_too_large(self):
        self.handler.headers = {"Content-Length": "5000"}
        with self.assertRaises(ValueError) as e:
            self.handler._read_json_payload()
        self.assertEqual(str(e.exception), "Request body is too large.")

    def test_read_json_payload_empty_body(self):
        self.handler.headers = {"Content-Length": "10"}
        self.handler.rfile.read.return_value = b""
        with self.assertRaises(ValueError) as e:
            self.handler._read_json_payload()
        self.assertEqual(str(e.exception), "Request body is empty.")

    def test_read_json_payload_invalid_json(self):
        self.handler.headers = {"Content-Length": "10"}
        self.handler.rfile.read.return_value = b"not json"
        with self.assertRaises(ValueError) as e:
            self.handler._read_json_payload()
        self.assertEqual(str(e.exception), "Invalid JSON payload.")

    def test_read_json_payload_not_dict(self):
        self.handler.headers = {"Content-Length": "10"}
        self.handler.rfile.read.return_value = b'["a"]'
        with self.assertRaises(ValueError) as e:
            self.handler._read_json_payload()
        self.assertEqual(str(e.exception), "JSON payload must be an object.")

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "eventsub")
    def test_handle_channel_control_unsupported_mode(self):
        result, code = self.handler._handle_channel_control({"action": "join", "channel": "test"})
        self.assertEqual(code, 409)
        self.assertFalse(result["ok"])

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "eventsub")
    def test_handle_channel_control_list_mode(self):
        result, code = self.handler._handle_channel_control({"action": "list"})
        self.assertEqual(code, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "list")

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "irc")
    @patch("bot.dashboard_server.irc_channel_control")
    def test_handle_channel_control_irc_success(self, mock_control):
        mock_control.execute.return_value = {"ok": True}
        result, code = self.handler._handle_channel_control({"action": "join", "channel": "test"})
        self.assertEqual(code, 200)
        self.assertTrue(result["ok"])

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "irc")
    @patch("bot.dashboard_server.irc_channel_control")
    def test_handle_channel_control_irc_runtime_unavailable(self, mock_control):
        mock_control.execute.return_value = {"ok": False, "error": "runtime_unavailable"}
        result, code = self.handler._handle_channel_control({"action": "join", "channel": "test"})
        self.assertEqual(code, 503)

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "irc")
    @patch("bot.dashboard_server.irc_channel_control")
    def test_handle_channel_control_irc_runtime_error(self, mock_control):
        mock_control.execute.return_value = {"ok": False, "error": "runtime_error"}
        result, code = self.handler._handle_channel_control({"action": "join", "channel": "test"})
        self.assertEqual(code, 500)

    @patch("bot.dashboard_server.TWITCH_CHAT_MODE", "irc")
    @patch("bot.dashboard_server.irc_channel_control")
    def test_handle_channel_control_irc_bad_request(self, mock_control):
        mock_control.execute.return_value = {"ok": False, "error": "invalid_channel"}
        result, code = self.handler._handle_channel_control({"action": "join", "channel": "test"})
        self.assertEqual(code, 400)

    def test_do_options(self):
        self.handler.requestline = "OPTIONS / HTTP/1.1"
        self.handler.request_version = "HTTP/1.1"
        self.handler.do_OPTIONS()
        self.handler.wfile.write.assert_called()
