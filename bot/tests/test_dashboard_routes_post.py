import unittest
from unittest.mock import MagicMock, patch

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
    def test_handle_agent_suspend_success(self, mock_cp):
        self.handler.path = "/api/agent/suspend"
        self.handler._read_json_payload.return_value = {"reason": "panic_button"}
        mock_cp.get_config.return_value = {"agent_suspended": True}
        mock_cp.runtime_snapshot.return_value = {"suspended": True}
        mock_cp.build_capabilities.return_value = {"autonomy": {"suspended": True}}

        routes_post.handle_post(self.handler)
        mock_cp.suspend_agent.assert_called_with(reason="panic_button")
        self.handler._send_json.assert_called_once()
        payload = self.handler._send_json.call_args.args[0]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "suspend")
        self.assertEqual(payload["reason"], "panic_button")
        self.assertEqual(payload["mode"], routes_post.TWITCH_CHAT_MODE)
        self.assertIn("config", payload)
        self.assertIn("autonomy", payload)
        self.assertIn("capabilities", payload)
        self.assertIn("agent_suspended", payload["config"])
        self.assertIn("suspended", payload["autonomy"])
        self.assertIn("autonomy", payload["capabilities"])
        self.assertEqual(self.handler._send_json.call_args.kwargs["status_code"], 200)

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_agent_resume_success_uses_default_reason(self, mock_cp):
        self.handler.path = "/api/agent/resume"
        self.handler._read_json_payload.return_value = {}
        mock_cp.get_config.return_value = {"agent_suspended": False}
        mock_cp.runtime_snapshot.return_value = {"suspended": False}
        mock_cp.build_capabilities.return_value = {"autonomy": {"suspended": False}}

        routes_post.handle_post(self.handler)
        mock_cp.resume_agent.assert_called_with(reason="manual_dashboard")
        self.handler._send_json.assert_called_once()
        payload = self.handler._send_json.call_args.args[0]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "resume")
        self.assertEqual(payload["reason"], "manual_dashboard")
        self.assertEqual(payload["mode"], routes_post.TWITCH_CHAT_MODE)
        self.assertIn("config", payload)
        self.assertIn("autonomy", payload)
        self.assertIn("capabilities", payload)
        self.assertIn("agent_suspended", payload["config"])
        self.assertIn("suspended", payload["autonomy"])
        self.assertIn("autonomy", payload["capabilities"])
        self.assertEqual(self.handler._send_json.call_args.kwargs["status_code"], 200)

    def test_handle_agent_suspend_invalid_json(self):
        self.handler.path = "/api/agent/suspend"
        self.handler._read_json_payload.side_effect = ValueError("bad json")

        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_request", "message": "bad json"},
            status_code=400,
        )

    def test_handle_agent_resume_unauthorized(self):
        self.handler.path = "/api/agent/resume"
        self.handler._dashboard_authorized.return_value = False

        routes_post.handle_post(self.handler)
        self.handler._send_forbidden.assert_called_once()

    def test_handle_agent_suspend_unauthorized(self):
        self.handler.path = "/api/agent/suspend"
        self.handler._dashboard_authorized.return_value = False

        routes_post.handle_post(self.handler)
        self.handler._send_forbidden.assert_called_once()

    def test_handle_agent_resume_invalid_json(self):
        self.handler.path = "/api/agent/resume"
        self.handler._read_json_payload.side_effect = ValueError("bad json")

        routes_post.handle_post(self.handler)
        self.handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_request", "message": "bad json"},
            status_code=400,
        )

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

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_ops_playbook_trigger_success(self, mock_cp):
        self.handler.path = "/api/ops-playbooks/trigger"
        self.handler._read_json_payload.return_value = {
            "playbook_id": "queue_backlog_recovery",
            "channel_id": "Canal_A",
            "reason": "manual_test",
            "force": True,
        }
        mock_cp.trigger_ops_playbook.return_value = {
            "enabled": True,
            "summary": {"total": 2, "awaiting_decision": 1},
            "playbooks": [],
        }

        routes_post.handle_post(self.handler)

        mock_cp.trigger_ops_playbook.assert_called_with(
            playbook_id="queue_backlog_recovery",
            channel_id="canal_a",
            reason="manual_test",
            force=True,
        )
        self.handler._send_json.assert_called_with(
            {
                "ok": True,
                "mode": routes_post.TWITCH_CHAT_MODE,
                "selected_channel": "canal_a",
                "enabled": True,
                "summary": {"total": 2, "awaiting_decision": 1},
                "playbooks": [],
            },
            status_code=200,
        )

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_ops_playbook_trigger_not_found(self, mock_cp):
        self.handler.path = "/api/ops-playbooks/trigger"
        self.handler._read_json_payload.return_value = {"playbook_id": "unknown"}
        mock_cp.trigger_ops_playbook.side_effect = KeyError("playbook_not_found")

        routes_post.handle_post(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "playbook_not_found",
                "message": "Playbook nao encontrado.",
            },
            status_code=404,
        )

    @patch("bot.dashboard_server_routes_post.control_plane")
    def test_handle_ops_playbook_trigger_conflict(self, mock_cp):
        self.handler.path = "/api/ops-playbooks/trigger"
        self.handler._read_json_payload.return_value = {"playbook_id": "queue_backlog_recovery"}
        mock_cp.trigger_ops_playbook.side_effect = RuntimeError("playbook_cooldown")

        routes_post.handle_post(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "playbook_cooldown",
                "message": "playbook_cooldown",
            },
            status_code=409,
        )

    def test_handle_ops_playbook_trigger_invalid_request(self):
        self.handler.path = "/api/ops-playbooks/trigger"
        self.handler._read_json_payload.return_value = {}

        routes_post.handle_post(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "invalid_request",
                "message": "playbook_id obrigatorio.",
            },
            status_code=400,
        )

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
            {
                "ok": False,
                "error": "invalid_content_type",
                "message": "Use image/jpeg, image/png or image/webp.",
            },
            status_code=400,
        )
