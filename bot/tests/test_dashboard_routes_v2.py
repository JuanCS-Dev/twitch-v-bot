import unittest
from unittest.mock import patch, MagicMock
from bot.dashboard_server_routes_post import handle_post
from bot.dashboard_server_routes import handle_get, handle_put

class TestDashboardRoutesV2(unittest.TestCase):
    def setUp(self):
        self.handler = MagicMock()
        self.handler._dashboard_authorized.return_value = True

    def test_post_not_found(self):
        self.handler.path = "/api/unknown"
        handle_post(self.handler)
        self.handler._send_text.assert_called_with("Not Found", status_code=404)

    def test_post_unauthorized(self):
        self.handler._dashboard_authorized.return_value = False
        self.handler.path = "/api/channel-control"
        handle_post(self.handler)
        self.handler._send_forbidden.assert_called_once()

    def test_post_invalid_json(self):
        self.handler.path = "/api/channel-control"
        self.handler._read_json_payload.side_effect = ValueError("bad json")
        handle_post(self.handler)
        self.handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_request", "message": "bad json"},
            status_code=400
        )

    def test_action_decision_not_found(self):
        self.handler.path = "/api/action-queue/missing/decision"
        with patch("bot.dashboard_server_routes_post.control_plane.decide_action", side_effect=KeyError()):
            handle_post(self.handler)
            self.handler._send_json.assert_called_with(
                {"ok": False, "error": "action_not_found", "message": "Action nao encontrada."},
                status_code=404
            )

    def test_action_decision_not_pending(self):
        self.handler.path = "/api/action-queue/123/decision"
        with patch("bot.dashboard_server_routes_post.control_plane.decide_action", side_effect=RuntimeError("busy")):
            handle_post(self.handler)
            self.handler._send_json.assert_called_with(
                {"ok": False, "error": "action_not_pending", "message": "busy"},
                status_code=409
            )

    def test_vision_ingest_invalid_type(self):
        self.handler.path = "/api/vision/ingest"
        self.handler.headers = {"Content-Type": "text/plain"}
        handle_post(self.handler)
        self.handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_content_type", "message": "Use image/jpeg, image/png or image/webp."},
            status_code=400
        )

    def test_get_action_queue_invalid_limit(self):
        self.handler.path = "/api/action-queue?limit=abc"
        handle_get(self.handler)
        # Should call list_actions with limit=80 (default in except block)
        self.handler._send_json.assert_called()

    def test_get_hud_messages_invalid_since(self):
        self.handler.path = "/api/hud/messages?since=garbage"
        handle_get(self.handler)
        self.handler._send_json.assert_called()

    def test_put_control_plane_invalid_config(self):
        self.handler.path = "/api/control-plane"
        with patch("bot.dashboard_server_routes.control_plane.update_config", side_effect=ValueError("bad config")):
            handle_put(self.handler)
            self.handler._send_json.assert_called_with(
                {"ok": False, "error": "invalid_request", "message": "bad config"},
                status_code=400
            )
            
    def test_autonomy_tick_timeout(self):
        self.handler.path = "/api/autonomy/tick"
        with patch("bot.dashboard_server_routes_post.autonomy_runtime.run_manual_tick", side_effect=TimeoutError("slow")):
            handle_post(self.handler)
            self.handler._send_json.assert_called_with(
                {"ok": False, "error": "timeout", "message": "slow"},
                status_code=503
            )
