from unittest.mock import MagicMock, patch

import pytest

from bot.dashboard_server import HealthHandler
from bot.dashboard_server_routes import (
    _dashboard_asset_route,
    build_channel_context_payload,
    build_observability_history_payload,
    handle_get,
    handle_get_config_js,
)
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
        assert _dashboard_asset_route(handler, "/dashboard/hud") is True
        handler._send_dashboard_asset.assert_called_with("hud.html", "text/html; charset=utf-8")

        handler.reset_mock()
        assert _dashboard_asset_route(handler, "/dashboard/app.js") is True
        handler._send_dashboard_asset.assert_called_with(
            "app.js", "application/javascript; charset=utf-8"
        )

        handler.reset_mock()
        assert _dashboard_asset_route(handler, "/api/something") is False

    @patch("bot.dashboard_server_routes._get_context_sync")
    @patch("bot.dashboard_server_routes.observability")
    @patch("bot.dashboard_server_routes.control_plane")
    def test_build_observability_payload(self, mock_cp, mock_obs, mock_get_context):
        from bot.dashboard_server_routes import build_observability_payload

        mock_get_context.return_value = MagicMock(channel_id="canal_a")
        mock_obs.snapshot.return_value = {"agent_outcomes": {}}
        mock_cp.runtime_snapshot.return_value = {"queue_window_60m": {"ignored": 5}}
        mock_cp.build_capabilities.return_value = {"cap": 1}

        res = build_observability_payload("canal_a")
        mock_get_context.assert_called_with("canal_a")
        assert mock_obs.snapshot.call_args.kwargs["channel_id"] == "canal_a"
        assert res["ok"] is True
        assert res["selected_channel"] == "canal_a"
        assert res["agent_outcomes"]["ignored_total_60m"] == 5

    @patch("bot.dashboard_server_routes._get_context_sync")
    @patch("bot.dashboard_server_routes.observability")
    @patch("bot.dashboard_server_routes.control_plane")
    def test_build_observability_payload_uses_context_channel_when_missing_query(
        self,
        mock_cp,
        mock_obs,
        mock_get_context,
    ):
        from bot.dashboard_server_routes import build_observability_payload

        mock_get_context.return_value = MagicMock(channel_id="canal_ctx")
        mock_obs.snapshot.return_value = {"agent_outcomes": {}}
        mock_cp.runtime_snapshot.return_value = {"queue_window_60m": {}}
        mock_cp.build_capabilities.return_value = {"cap": 1}

        res = build_observability_payload(None)

        mock_get_context.assert_called_with(None)
        assert mock_obs.snapshot.call_args.kwargs["channel_id"] == "canal_ctx"
        assert res["selected_channel"] == "canal_ctx"
        assert res["context"]["channel_id"] == "canal_ctx"

    @patch("bot.dashboard_server_routes.persistence")
    @patch("bot.dashboard_server_routes.context_manager")
    def test_build_channel_context_payload(self, mock_context_manager, mock_persistence):
        runtime_ctx = MagicMock(
            channel_id="canal_a",
            current_game="Balatro",
            stream_vibe="Arena",
            last_event="Boss defeat",
            style_profile="Tatico",
            channel_paused=True,
            agent_notes="",
            last_byte_reply="Segura a call.",
            live_observability={"game": "Balatro", "topic": "deck tech"},
            recent_chat_entries=["viewer: hi", "byte: bora"],
        )
        mock_context_manager.list_active_channels.return_value = ["default"]
        mock_context_manager.get.return_value = runtime_ctx
        mock_persistence.load_channel_state_sync.return_value = {
            "channel_id": "canal_a",
            "current_game": "Balatro",
            "stream_vibe": "Arena",
            "last_event": "Boss defeat",
            "style_profile": "Tatico",
            "last_reply": "Segura a call.",
            "updated_at": "2026-02-27T18:00:00Z",
            "observability": {"game": "Balatro"},
        }
        mock_persistence.load_agent_notes_sync.return_value = {
            "channel_id": "canal_a",
            "notes": "Sem spoiler pesado.",
            "has_notes": True,
            "updated_at": "2026-02-27T18:01:00Z",
            "source": "supabase",
        }
        mock_persistence.load_recent_history_sync.return_value = ["viewer: hi", "byte: bora"]

        payload = build_channel_context_payload("canal_a")

        assert payload["ok"] is True
        assert payload["channel"]["channel_id"] == "canal_a"
        assert payload["channel"]["runtime_loaded"] is False
        assert payload["channel"]["runtime"]["channel_paused"] is True
        assert payload["channel"]["has_persisted_state"] is True
        assert payload["channel"]["has_persisted_notes"] is True
        assert payload["channel"]["persisted_state"]["current_game"] == "Balatro"
        assert payload["channel"]["persisted_agent_notes"]["notes"] == "Sem spoiler pesado."
        assert payload["channel"]["persisted_recent_history"] == ["viewer: hi", "byte: bora"]

    @patch("bot.dashboard_server_routes.persistence")
    @patch("bot.dashboard_server_routes.context_manager")
    def test_build_channel_context_payload_without_persisted_data(
        self, mock_context_manager, mock_persistence
    ):
        mock_context_manager.list_active_channels.return_value = ["canal_a"]
        mock_context_manager.get.return_value = MagicMock(
            channel_id="canal_a",
            current_game="N/A",
            stream_vibe="Conversa",
            last_event="Bot Online",
            style_profile="",
            agent_notes="",
            last_byte_reply="",
            live_observability={},
            recent_chat_entries=[],
        )
        mock_persistence.load_channel_state_sync.return_value = None
        mock_persistence.load_agent_notes_sync.return_value = None
        mock_persistence.load_recent_history_sync.return_value = []

        payload = build_channel_context_payload("canal_a")

        assert payload["channel"]["runtime_loaded"] is True
        assert payload["channel"]["has_persisted_state"] is False
        assert payload["channel"]["has_persisted_notes"] is False
        assert payload["channel"]["persisted_state"] is None
        assert payload["channel"]["persisted_agent_notes"] is None
        assert payload["channel"]["persisted_recent_history"] == []

    @patch("bot.dashboard_server_routes.persistence")
    def test_build_observability_history_payload(self, mock_persistence):
        mock_persistence.load_observability_channel_history_sync.return_value = [
            {
                "channel_id": "canal_a",
                "captured_at": "2026-02-27T18:30:00Z",
                "metrics": {
                    "chat_messages_total": 21,
                    "byte_triggers_total": 5,
                    "replies_total": 4,
                    "llm_interactions_total": 4,
                    "errors_total": 0,
                },
                "chatters": {
                    "unique_total": 9,
                    "active_60m": 3,
                },
                "chat_analytics": {
                    "messages_60m": 14,
                    "byte_triggers_60m": 5,
                    "messages_per_minute_60m": 0.23,
                },
                "agent_outcomes": {
                    "useful_engagement_rate_60m": 80.0,
                    "ignored_rate_60m": 20.0,
                },
                "context": {
                    "last_prompt": "status",
                    "last_reply": "online",
                },
            }
        ]
        mock_persistence.load_latest_observability_channel_snapshots_sync.return_value = [
            {
                "channel_id": "canal_b",
                "captured_at": "2026-02-27T18:31:00Z",
                "metrics": {
                    "chat_messages_total": 15,
                    "byte_triggers_total": 2,
                    "replies_total": 2,
                    "llm_interactions_total": 2,
                    "errors_total": 1,
                },
            }
        ]

        payload = build_observability_history_payload("canal_a", limit=12, compare_limit=3)

        assert payload["ok"] is True
        assert payload["selected_channel"] == "canal_a"
        assert payload["has_history"] is True
        assert payload["limits"]["timeline"] == 12
        assert payload["limits"]["comparison"] == 3
        assert payload["timeline"][0]["metrics"]["chat_messages_total"] == 21
        assert payload["comparison"][0]["channel_id"] == "canal_b"
        assert payload["comparison"][1]["channel_id"] == "canal_a"
        mock_persistence.load_observability_channel_history_sync.assert_called_once_with(
            "canal_a",
            limit=12,
        )
        mock_persistence.load_latest_observability_channel_snapshots_sync.assert_called_once_with(
            limit=3
        )

    @patch("bot.dashboard_server_routes.persistence")
    def test_build_observability_history_payload_does_not_use_timestamp_fallback(
        self, mock_persistence
    ):
        mock_persistence.load_observability_channel_history_sync.return_value = [
            {
                "channel_id": "canal_a",
                "timestamp": "2026-02-27T18:35:00Z",
                "metrics": {"chat_messages_total": 1},
            }
        ]
        mock_persistence.load_latest_observability_channel_snapshots_sync.return_value = []

        payload = build_observability_history_payload("canal_a", limit=10, compare_limit=3)

        assert payload["timeline"][0]["captured_at"] == ""
        assert payload["timeline"][0]["channel_id"] == "canal_a"

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

    def test_handle_get_api_channel_context_defaults_to_default(self):
        handler = MagicMock(path="/api/channel-context")
        handler._dashboard_authorized.return_value = True
        with patch("bot.dashboard_server_routes.build_channel_context_payload") as mock_payload:
            mock_payload.return_value = {"ok": True, "channel": {"channel_id": "default"}}
            handle_get(handler)
        mock_payload.assert_called_with("default")
        handler._send_json.assert_called_once()

    def test_handle_get_api_observability_history_defaults(self):
        handler = MagicMock(path="/api/observability/history")
        handler._dashboard_authorized.return_value = True
        with patch(
            "bot.dashboard_server_routes.build_observability_history_payload"
        ) as mock_payload:
            mock_payload.return_value = {"ok": True, "selected_channel": "default"}
            handle_get(handler)

        mock_payload.assert_called_once_with("default", limit=24, compare_limit=6)
        handler._send_json.assert_called_once_with(
            {"ok": True, "selected_channel": "default"},
            status_code=200,
        )

    def test_handle_get_api_observability_history_with_custom_limits(self):
        handler = MagicMock(
            path="/api/observability/history?channel=Canal_A&limit=35&compare_limit=9"
        )
        handler._dashboard_authorized.return_value = True
        with patch(
            "bot.dashboard_server_routes.build_observability_history_payload"
        ) as mock_payload:
            mock_payload.return_value = {"ok": True, "selected_channel": "canal_a"}
            handle_get(handler)

        mock_payload.assert_called_once_with("canal_a", limit=35, compare_limit=9)

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

    @patch("bot.dashboard_server.build_observability_payload")
    def test_health_handler_build_observability_payload_delegates_channel(self, mock_build):
        mock_build.return_value = {"ok": True}
        handler = object.__new__(HealthHandler)

        payload = HealthHandler._build_observability_payload(handler, "canal_a")

        assert payload == {"ok": True}
        mock_build.assert_called_once_with("canal_a")

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

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_action_decision_invalid_payload(self, mock_cp):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = True
        handler._read_json_payload.side_effect = ValueError("invalid json")
        _handle_action_decision(handler, "/api/action-queue/act123/decision")
        handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_request", "message": "invalid json"}, status_code=400
        )

    @patch("bot.dashboard_server_routes_post.autonomy_runtime")
    def test_handle_autonomy_tick_unauthorized(self, mock_auto):
        handler = MagicMock()
        handler._dashboard_authorized.return_value = False
        _handle_autonomy_tick(handler)
        handler._send_forbidden.assert_called_once()
