from unittest.mock import MagicMock, patch

import pytest

from bot.dashboard_server_routes import _dashboard_asset_route, handle_get, handle_get_config_js
from bot.dashboard_server_routes_post import (
    _handle_action_decision,
    _handle_autonomy_tick,
    _handle_channel_control_post,
    _handle_vision_ingest,
    handle_post,
)


class DummyHandler:
    def __init__(self, path="/", headers=None, auth=True):
        self.path = path
        self.headers = headers or {}
        self.rfile = MagicMock()
        self._auth = auth

    def _dashboard_authorized(self):
        return self._auth

    def _send_dashboard_asset(self, path, ctype):
        pass

    def _send_text(self, text, status_code=200):
        pass

    def _send_forbidden(self):
        pass

    def _send_json(self, payload, status_code=200):
        pass

    def _send_bytes(self, payload, content_type, status_code=200):
        pass

    def _build_observability_payload(self):
        return {"obs": True}

    def _handle_channel_control(self, payload):
        return {"ctrl": True}, 200

    def _read_json_payload(self, allow_empty=False):
        return {"json": True}


class TestDashboardRoutesV3:
    def test_dashboard_asset_route(self):
        handler = MagicMock()
        assert _dashboard_asset_route(handler, "/") is True
        handler._send_dashboard_asset.assert_called_with("index.html", "text/html; charset=utf-8")

        handler.reset_mock()
        assert _dashboard_asset_route(handler, "/dashboard/app.js") is True
        handler._send_dashboard_asset.assert_called_with(
            "app.js", "application/javascript; charset=utf-8"
        )

        handler.reset_mock()
        assert _dashboard_asset_route(handler, "/dashboard/style.css") is True
        handler._send_dashboard_asset.assert_called_with("style.css", "text/css; charset=utf-8")

        handler.reset_mock()
        assert _dashboard_asset_route(handler, "/api/something") is False

    @patch("bot.dashboard_server_routes.control_plane")
    def test_handle_get_api_control_plane(self, mock_cp):
        mock_cp.get_config.return_value = {"cfg": 1}
        mock_cp.runtime_snapshot.return_value = {"snap": 1}
        mock_cp.build_capabilities.return_value = {"cap": 1}
        handler = MagicMock(path="/api/control-plane")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["ok"] is True

    @patch("bot.dashboard_server_routes.control_plane")
    def test_handle_get_api_action_queue(self, mock_cp):
        mock_cp.list_actions.return_value = {"items": []}
        handler = MagicMock(path="/api/action-queue?status=pending&limit=10")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        mock_cp.list_actions.assert_called_with(status="pending", limit=10)
        handler._send_json.assert_called_once()

    @patch("bot.dashboard_server_routes.clip_jobs")
    def test_handle_get_api_clip_jobs(self, mock_cj):
        mock_cj.get_jobs.return_value = [{"job": 1}]
        handler = MagicMock(path="/api/clip-jobs")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["items"] == [{"job": 1}]

    @patch("bot.dashboard_server_routes.hud_runtime")
    def test_handle_get_api_hud(self, mock_hud):
        mock_hud.get_messages.return_value = ["msg"]
        handler = MagicMock(path="/api/hud/messages?since=123.45")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        mock_hud.get_messages.assert_called_with(since=123.45)
        handler._send_json.assert_called_once()

    @patch("bot.dashboard_server_routes.sentiment_engine")
    def test_handle_get_api_sentiment(self, mock_sent):
        mock_sent.get_scores.return_value = {"score": 1}
        mock_sent.get_vibe.return_value = "chill"
        handler = MagicMock(path="/api/sentiment/scores")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["vibe"] == "chill"

    @patch("bot.dashboard_server_routes.vision_runtime")
    def test_handle_get_api_vision(self, mock_vis):
        mock_vis.get_status.return_value = {"status": "ok"}
        handler = MagicMock(path="/api/vision/status")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["status"] == "ok"

    def test_handle_get_api_unauthorized(self):
        handler = MagicMock(path="/api/control-plane")
        handler._dashboard_authorized.return_value = False
        handle_get(handler)
        handler._send_forbidden.assert_called_once()

    @patch("bot.runtime_config.BYTE_DASHBOARD_ADMIN_TOKEN", "supersecret")
    def test_handle_get_config_js(self):
        handler = MagicMock(path="/dashboard/config.js")
        handler._dashboard_authorized.return_value = True
        handle_get(handler)
        handler._send_bytes.assert_called_once()
        content = handler._send_bytes.call_args[0][0]
        assert b"supersecret" in content

    # --- POST Routes Tests ---

    def test_handle_post_routing(self):
        handler = MagicMock()
        handler.path = "/api/unknown"
        handle_post(handler)
        handler._send_text.assert_called_with("Not Found", status_code=404)

    def test_handle_channel_control_post_unauthorized(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = False
        _handle_channel_control_post(handler)
        handler._send_forbidden.assert_called_once()

    def test_handle_channel_control_post_invalid_json(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.side_effect = ValueError("bad json")
        _handle_channel_control_post(handler)
        handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_request", "message": "bad json"}, status_code=400
        )

    def test_handle_channel_control_post_invalid_command(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {}
        handler._handle_channel_control.side_effect = ValueError("bad command")
        _handle_channel_control_post(handler)
        handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_command", "message": "bad command"}, status_code=400
        )

    def test_handle_channel_control_post_success(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {}
        handler._handle_channel_control.return_value = ({"success": True}, 200)
        _handle_channel_control_post(handler)
        handler._send_json.assert_called_with({"success": True}, status_code=200)

    @patch("bot.dashboard_server_routes_post.autonomy_runtime")
    def test_handle_autonomy_tick_success(self, mock_auto):
        mock_auto.run_manual_tick.return_value = {"ticked": True}
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {"force": False, "reason": "test"}
        _handle_autonomy_tick(handler)
        mock_auto.run_manual_tick.assert_called_with(force=False, reason="test")
        handler._send_json.assert_called_with({"ticked": True}, status_code=200)

    @patch("bot.dashboard_server_routes_post.autonomy_runtime")
    def test_handle_autonomy_tick_timeout(self, mock_auto):
        mock_auto.run_manual_tick.side_effect = TimeoutError("too slow")
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {}
        _handle_autonomy_tick(handler)
        handler._send_json.assert_called_with(
            {"ok": False, "error": "timeout", "message": "too slow"}, status_code=503
        )

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_action_decision_success(self, mock_cp):
        mock_cp.decide_action.return_value = {"updated": True}
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {"decision": "approve", "note": "ok"}
        _handle_action_decision(handler, "/api/action-queue/act123/decision")
        mock_cp.decide_action.assert_called_with(action_id="act123", decision="approve", note="ok")
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["ok"] is True
        assert handler._send_json.call_args[0][0]["item"] == {"updated": True}

    def test_handle_action_decision_missing_id(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        _handle_action_decision(handler, "/api/action-queue//decision")
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["error"] == "invalid_request"

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_action_decision_not_found(self, mock_cp):
        mock_cp.decide_action.side_effect = KeyError("not found")
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {"decision": "approve"}
        _handle_action_decision(handler, "/api/action-queue/act123/decision")
        handler._send_json.assert_called_with(
            {"ok": False, "error": "action_not_found", "message": "Action nao encontrada."},
            status_code=404,
        )

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_action_decision_not_pending(self, mock_cp):
        mock_cp.decide_action.side_effect = RuntimeError("not pending")
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.return_value = {"decision": "approve"}
        _handle_action_decision(handler, "/api/action-queue/act123/decision")
        handler._send_json.assert_called_with(
            {"ok": False, "error": "action_not_pending", "message": "not pending"}, status_code=409
        )

    @patch("bot.dashboard_server_routes_post.vision_runtime")
    def test_handle_vision_ingest_success(self, mock_vis):
        mock_vis.ingest_frame.return_value = {"ok": True}
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler.headers = {"Content-Type": "image/jpeg", "Content-Length": "100"}
        handler.rfile.read.return_value = b"image data"
        _handle_vision_ingest(handler)
        mock_vis.ingest_frame.assert_called_with(b"image data", mime_type="image/jpeg")
        handler._send_json.assert_called_with({"ok": True}, status_code=200)

    def test_handle_vision_ingest_invalid_type(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler.headers = {"Content-Type": "application/json", "Content-Length": "100"}
        _handle_vision_ingest(handler)
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["error"] == "invalid_content_type"
        assert handler._send_json.call_args[1]["status_code"] == 400

    def test_handle_vision_ingest_empty_body(self):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler.headers = {"Content-Type": "image/png", "Content-Length": "0"}
        _handle_vision_ingest(handler)
        handler._send_json.assert_called_once()
        assert handler._send_json.call_args[0][0]["error"] == "empty_body"
        assert handler._send_json.call_args[1]["status_code"] == 400
