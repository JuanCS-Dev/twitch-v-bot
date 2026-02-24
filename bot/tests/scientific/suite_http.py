from bot.tests.scientific_shared import (
    HealthHandler,
    MagicMock,
    ScientificTestCase,
    get_secret,
    patch,
)


class ScientificHttpTestsMixin(ScientificTestCase):
    def test_health_server_response(self):
        mock_handler = MagicMock()
        mock_handler.path = "/health"
        mock_handler._send_text = MagicMock()

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_text.assert_called_with("AGENT_ONLINE", status_code=200)

    def test_health_server_alias_routes(self):
        for route in ("/health", "/health/", "/healthz", "/healthz/"):
            with self.subTest(route=route):
                mock_handler = MagicMock()
                mock_handler.path = route
                mock_handler._send_text = MagicMock()

                HealthHandler.do_GET(mock_handler)

                mock_handler._send_text.assert_called_with("AGENT_ONLINE", status_code=200)

    def test_health_server_observability_endpoint(self):
        observability_payload = {
            "ok": True,
            "bot": {"mode": "irc"},
            "metrics": {"chat_messages_total": 3},
        }
        mock_handler = MagicMock()
        mock_handler.path = "/api/observability"
        mock_handler._build_observability_payload = MagicMock(
            return_value=observability_payload
        )
        mock_handler._send_json = MagicMock()

        HealthHandler.do_GET(mock_handler)

        mock_handler._build_observability_payload.assert_called_once()
        mock_handler._send_json.assert_called_with(observability_payload, status_code=200)

    def test_health_server_dashboard_route(self):
        mock_handler = MagicMock()
        mock_handler.path = "/dashboard"
        mock_handler._send_dashboard_asset = MagicMock(return_value=True)

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_dashboard_asset.assert_called_with(
            "index.html", "text/html; charset=utf-8"
        )

    def test_health_server_dashboard_main_asset_route(self):
        mock_handler = MagicMock()
        mock_handler.path = "/dashboard/main.js"
        mock_handler._send_dashboard_asset = MagicMock(return_value=True)

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_dashboard_asset.assert_called_with(
            "main.js",
            "application/javascript; charset=utf-8",
        )

    def test_health_server_not_found_route(self):
        mock_handler = MagicMock()
        mock_handler.path = "/does-not-exist"
        mock_handler._send_text = MagicMock()

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_text.assert_called_with("Not Found", status_code=404)

    def test_health_server_channel_control_post_requires_admin_token(self):
        mock_handler = MagicMock()
        mock_handler.path = "/api/channel-control"
        mock_handler.headers = {}
        mock_handler._dashboard_authorized = MagicMock(return_value=False)
        mock_handler._send_forbidden = MagicMock()
        mock_handler._send_json = MagicMock()

        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "secret-token"):
            HealthHandler.do_POST(mock_handler)

        mock_handler._send_forbidden.assert_called_once()
        mock_handler._send_json.assert_not_called()

    @patch("bot.dashboard_server.irc_channel_control.execute")
    def test_health_server_channel_control_post_executes_list_command(self, mock_execute):
        mock_execute.return_value = {
            "ok": True,
            "action": "list",
            "channels": ["oisakura", "canal_b"],
            "message": "Connected channels: #oisakura, #canal_b.",
        }
        mock_handler = MagicMock()
        mock_handler.path = "/api/channel-control"
        mock_handler.headers = {"X-Byte-Admin-Token": "secret-token"}
        mock_handler.CHANNEL_CONTROL_IRC_ONLY_ACTIONS = (
            HealthHandler.CHANNEL_CONTROL_IRC_ONLY_ACTIONS
        )
        mock_handler._dashboard_authorized = MagicMock(return_value=True)
        mock_handler._handle_channel_control = (
            lambda payload: HealthHandler._handle_channel_control(mock_handler, payload)
        )
        mock_handler._read_json_payload = MagicMock(return_value={"command": "list"})
        mock_handler._send_json = MagicMock()

        with patch("bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "secret-token"), patch(
            "bot.dashboard_server.TWITCH_CHAT_MODE", "irc"
        ):
            HealthHandler.do_POST(mock_handler)

        mock_execute.assert_called_with(action="list", channel_login="")
        args, kwargs = mock_handler._send_json.call_args
        payload = args[0]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "list")
        self.assertEqual(payload["mode"], "irc")
        self.assertEqual(kwargs["status_code"], 200)

    @patch("bot.dashboard_server.irc_channel_control.execute")
    def test_health_server_channel_control_post_maps_runtime_errors(self, mock_execute):
        cases = [
            ("timeout", 503),
            ("runtime_unavailable", 503),
            ("runtime_error", 500),
            ("invalid_action", 400),
        ]
        for error_code, expected_status in cases:
            with self.subTest(error_code=error_code):
                mock_execute.return_value = {
                    "ok": False,
                    "error": error_code,
                    "message": "failure",
                }
                mock_handler = MagicMock()
                mock_handler.path = "/api/channel-control"
                mock_handler.headers = {"X-Byte-Admin-Token": "secret-token"}
                mock_handler.CHANNEL_CONTROL_IRC_ONLY_ACTIONS = (
                    HealthHandler.CHANNEL_CONTROL_IRC_ONLY_ACTIONS
                )
                mock_handler._dashboard_authorized = MagicMock(return_value=True)
                mock_handler._handle_channel_control = (
                    lambda payload: HealthHandler._handle_channel_control(
                        mock_handler, payload
                    )
                )
                mock_handler._read_json_payload = MagicMock(
                    return_value={"command": "list"}
                )
                mock_handler._send_json = MagicMock()

                with patch(
                    "bot.dashboard_server.BYTE_DASHBOARD_ADMIN_TOKEN", "secret-token"
                ), patch("bot.dashboard_server.TWITCH_CHAT_MODE", "irc"):
                    HealthHandler.do_POST(mock_handler)

                mock_handler._send_json.assert_called_with(
                    {
                        "ok": False,
                        "error": error_code,
                        "message": "failure",
                        "mode": "irc",
                    },
                    status_code=expected_status,
                )

    def test_health_server_channel_control_join_blocked_outside_irc(self):
        mock_handler = MagicMock()
        mock_handler.path = "/api/channel-control"
        mock_handler.headers = {}
        mock_handler.CHANNEL_CONTROL_IRC_ONLY_ACTIONS = (
            HealthHandler.CHANNEL_CONTROL_IRC_ONLY_ACTIONS
        )
        mock_handler._dashboard_authorized = MagicMock(return_value=True)
        mock_handler._handle_channel_control = (
            lambda payload: HealthHandler._handle_channel_control(mock_handler, payload)
        )
        mock_handler._read_json_payload = MagicMock(
            return_value={"action": "join", "channel": "canal_a"}
        )
        mock_handler._send_json = MagicMock()

        with patch("bot.dashboard_server.TWITCH_CHAT_MODE", "eventsub"):
            HealthHandler.do_POST(mock_handler)

        args, kwargs = mock_handler._send_json.call_args
        payload = args[0]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "unsupported_mode")
        self.assertEqual(payload["mode"], "eventsub")
        self.assertEqual(kwargs["status_code"], 409)

    def test_health_server_control_plane_get_returns_runtime_contract(self):
        mock_handler = MagicMock()
        mock_handler.path = "/api/control-plane"
        mock_handler._send_json = MagicMock()

        HealthHandler.do_GET(mock_handler)

        args, kwargs = mock_handler._send_json.call_args
        payload = args[0]
        self.assertTrue(payload["ok"])
        self.assertIn("config", payload)
        self.assertIn("autonomy", payload)
        self.assertIn("capabilities", payload)
        self.assertEqual(kwargs["status_code"], 200)

    def test_get_secret_coverage(self):
        with patch.dict("os.environ", {"TWITCH_CLIENT_SECRET": "hf_secret"}):
            res = get_secret()
            self.assertEqual(res, "hf_secret")
