import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse
import bot.dashboard_server_routes_post as routes_post

class TestDashboardRoutesPost(unittest.TestCase):
    def setUp(self):
        self.handler = MagicMock()
        self.handler._dashboard_authorized.return_value = True

    def test_handle_post_not_found(self):
        self.handler.path = "/api/missing"
        routes_post.handle_post(self.handler)
        self.handler._send_text.assert_called_with("Not Found", status_code=404)

    def test_handle_channel_control_authorized(self):
        self.handler.path = "/api/channel-control"
        self.handler._read_json_payload.return_value = {"command": "list"}
        self.handler._handle_channel_control.return_value = ({"ok": True}, 200)
        
        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called_with({"ok": True}, status_code=200)

    @patch("bot.dashboard_server_routes_post.autonomy_runtime")
    def test_handle_autonomy_tick_success(self, mock_runtime):
        self.handler.path = "/api/autonomy/tick"
        self.handler._read_json_payload.return_value = {"force": True}
        mock_runtime.run_manual_tick.return_value = {"ok": True}
        
        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called_with({"ok": True}, status_code=200)

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_action_decision_success(self, mock_cp):
        self.handler.path = "/api/action-queue/123/decision"
        self.handler._read_json_payload.return_value = {"decision": "allow"}
        mock_cp.decide_action.return_value = {"id": "123", "status": "allowed"}
        
        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called()
        args = self.handler._send_json.call_args[0]
        self.assertTrue(args[0]["ok"])
        self.assertEqual(args[0]["item"]["id"], "123")

    @patch("bot.dashboard_server_routes_post.vision_runtime")
    def test_handle_vision_ingest_success(self, mock_vision):
        self.handler.path = "/api/vision/ingest"
        self.handler.headers = {"Content-Type": "image/jpeg", "Content-Length": "10"}
        self.handler.rfile.read.return_value = b"fakeimage"
        mock_vision.ingest_frame.return_value = {"ok": True}
        
        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called_with({"ok": True}, status_code=200)

    def test_handle_vision_ingest_invalid_type(self):
        self.handler.path = "/api/vision/ingest"
        self.handler.headers = {"Content-Type": "text/plain"}
        
        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_content_type", "message": "Use image/jpeg, image/png or image/webp."},
            status_code=400
        )
