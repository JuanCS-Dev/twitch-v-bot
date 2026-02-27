import unittest
from unittest.mock import MagicMock, patch

import bot.dashboard_server_routes as routes


class TestDashboardRoutes(unittest.TestCase):
    def setUp(self):
        self.handler = MagicMock()
        self.handler._dashboard_authorized.return_value = True

    def test_handle_get_health(self):
        self.handler.path = "/health"
        routes.handle_get(self.handler)
        self.handler._send_text.assert_called_with("AGENT_ONLINE", status_code=200)

    def test_handle_get_api_unauthorized(self):
        self.handler.path = "/api/observability"
        self.handler._dashboard_authorized.return_value = False
        routes.handle_get(self.handler)
        self.handler._send_forbidden.assert_called_once()

    @patch("bot.dashboard_server_routes.observability")
    @patch("bot.dashboard_server_routes.control_plane")
    def test_handle_get_observability(self, mock_cp, mock_obs):
        self.handler.path = "/api/observability"
        mock_obs.snapshot.return_value = {"agent_outcomes": {}}
        mock_cp.runtime_snapshot.return_value = {"queue_window_60m": {}}

        # routes.py calls handler._build_observability_payload()
        # which is likely defined in dashboard_server.py but
        # routes.py also defines build_observability_payload() standalone.
        # Let's mock what the handler expects.
        self.handler._build_observability_payload.return_value = {"ok": True}

        routes.handle_get(self.handler)
        self.handler._send_json.assert_called()
        args = self.handler._send_json.call_args[0]
        self.assertTrue(args[0]["ok"])

    def test_handle_get_observability_resolves_channel_query(self):
        self.handler.path = "/api/observability?channel=Canal_A"
        self.handler._build_observability_payload.return_value = {"ok": True, "channel": "canal_a"}

        routes.handle_get(self.handler)

        self.handler._build_observability_payload.assert_called_with("canal_a")
        self.handler._send_json.assert_called()

    @patch("bot.dashboard_server_routes.control_plane")
    def test_handle_get_action_queue(self, mock_cp):
        self.handler.path = "/api/action-queue?status=pending&limit=10"
        mock_cp.list_actions.return_value = {"items": []}

        routes.handle_get(self.handler)
        mock_cp.list_actions.assert_called_with(status="pending", limit=10)
        self.handler._send_json.assert_called()

    @patch("bot.dashboard_server_routes.control_plane")
    def test_handle_get_ops_playbooks(self, mock_cp):
        self.handler.path = "/api/ops-playbooks?channel=Canal_A"
        mock_cp.ops_playbooks_snapshot.return_value = {
            "enabled": True,
            "updated_at": "2026-02-27T21:00:00Z",
            "summary": {"total": 2, "awaiting_decision": 1},
            "playbooks": [],
        }

        routes.handle_get(self.handler)

        mock_cp.ops_playbooks_snapshot.assert_called_with(channel_id="canal_a")
        self.handler._send_json.assert_called_with(
            {
                "ok": True,
                "mode": routes.TWITCH_CHAT_MODE,
                "selected_channel": "canal_a",
                "enabled": True,
                "updated_at": "2026-02-27T21:00:00Z",
                "summary": {"total": 2, "awaiting_decision": 1},
                "playbooks": [],
            },
            status_code=200,
        )

    @patch("bot.dashboard_server_routes.clip_jobs")
    def test_handle_get_clip_jobs(self, mock_jobs):
        self.handler.path = "/api/clip-jobs"
        mock_jobs.get_jobs.return_value = []
        routes.handle_get(self.handler)
        self.handler._send_json.assert_called()

    def test_handle_get_not_found(self):
        self.handler.path = "/api/nonexistent"
        routes.handle_get(self.handler)
        self.handler._send_text.assert_called_with("Not Found", status_code=404)

    @patch("bot.dashboard_server_routes._dashboard_asset_route", return_value=True)
    def test_handle_get_dashboard_asset_route_returns_early(self, mock_asset_route):
        self.handler.path = "/dashboard/app.js"

        routes.handle_get(self.handler)

        mock_asset_route.assert_called_once_with(self.handler, "/dashboard/app.js")
        self.handler._send_text.assert_not_called()

    @patch("bot.dashboard_server_routes.control_plane")
    def test_handle_put_control_plane_success(self, mock_cp):
        self.handler.path = "/api/control-plane"
        self.handler._read_json_payload.return_value = {"key": "val"}
        mock_cp.update_config.return_value = {"key": "val"}

        routes.handle_put(self.handler)
        mock_cp.update_config.assert_called_with({"key": "val"})
        self.handler._send_json.assert_called()

    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_get_channel_config_success(self, mock_persistence):
        self.handler.path = "/api/channel-config?channel=canal_a"
        mock_persistence.load_channel_config_sync.return_value = {
            "channel_id": "canal_a",
            "temperature": 0.25,
            "top_p": 0.8,
            "agent_paused": False,
            "has_override": True,
            "updated_at": "2026-02-27T12:00:00Z",
            "source": "supabase",
        }
        mock_persistence.load_channel_identity_sync.return_value = {
            "channel_id": "canal_a",
            "persona_name": "Byte Coach",
            "tone": "tatico e objetivo",
            "emote_vocab": ["PogChamp", "LUL"],
            "lore": "Canal focado em analise de gameplay.",
            "has_identity": True,
            "updated_at": "2026-02-27T12:05:00Z",
            "source": "supabase",
        }

        routes.handle_get(self.handler)

        mock_persistence.load_channel_config_sync.assert_called_with("canal_a")
        mock_persistence.load_channel_identity_sync.assert_called_with("canal_a")
        self.handler._send_json.assert_called()

    def test_handle_get_channel_config_missing_channel(self):
        self.handler.path = "/api/channel-config"

        routes.handle_get(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "invalid_request",
                "message": "channel_id obrigatorio.",
            },
            status_code=400,
        )

    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_get_agent_notes_success(self, mock_persistence):
        self.handler.path = "/api/agent-notes?channel=canal_a"
        mock_persistence.load_agent_notes_sync.return_value = {
            "channel_id": "canal_a",
            "notes": "Priorize o host.",
            "has_notes": True,
            "updated_at": "2026-02-27T12:30:00Z",
            "source": "supabase",
        }

        routes.handle_get(self.handler)

        mock_persistence.load_agent_notes_sync.assert_called_with("canal_a")
        self.handler._send_json.assert_called()

    def test_handle_get_agent_notes_missing_channel(self):
        self.handler.path = "/api/agent-notes"

        routes.handle_get(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "invalid_request",
                "message": "channel_id obrigatorio.",
            },
            status_code=400,
        )

    @patch("bot.dashboard_server_routes.build_channel_context_payload")
    def test_handle_get_channel_context_success(self, mock_build_payload):
        self.handler.path = "/api/channel-context?channel=Canal_A"
        mock_build_payload.return_value = {"ok": True, "channel": {"channel_id": "canal_a"}}

        routes.handle_get(self.handler)

        mock_build_payload.assert_called_with("canal_a")
        self.handler._send_json.assert_called_with(
            {"ok": True, "channel": {"channel_id": "canal_a"}},
            status_code=200,
        )

    @patch("bot.dashboard_server_routes.build_observability_history_payload")
    def test_handle_get_observability_history_success(self, mock_build_payload):
        self.handler.path = "/api/observability/history?channel=Canal_A&limit=10&compare_limit=4"
        mock_build_payload.return_value = {"ok": True, "selected_channel": "canal_a"}

        routes.handle_get(self.handler)

        mock_build_payload.assert_called_with("canal_a", limit=10, compare_limit=4)
        self.handler._send_json.assert_called_with(
            {"ok": True, "selected_channel": "canal_a"},
            status_code=200,
        )

    @patch("bot.dashboard_server_routes.build_semantic_memory_payload")
    def test_handle_get_semantic_memory_success(self, mock_build_payload):
        self.handler.path = (
            "/api/semantic-memory?channel=Canal_A&query=lore&limit=7&search_limit=40"
        )
        mock_build_payload.return_value = {"ok": True, "selected_channel": "canal_a"}

        routes.handle_get(self.handler)

        mock_build_payload.assert_called_with(
            "canal_a",
            query="lore",
            limit=7,
            search_limit=40,
        )
        self.handler._send_json.assert_called_with(
            {"ok": True, "selected_channel": "canal_a"},
            status_code=200,
        )

    def test_handle_put_control_plane_invalid_json(self):
        self.handler.path = "/api/control-plane"
        self.handler._read_json_payload.side_effect = ValueError("Bad JSON")

        routes.handle_put(self.handler)
        self.handler._send_json.assert_called_with(
            {"ok": False, "error": "invalid_request", "message": "Bad JSON"}, status_code=400
        )

    def test_handle_put_not_found(self):
        self.handler.path = "/api/unknown"

        routes.handle_put(self.handler)

        self.handler._send_text.assert_called_with("Not Found", status_code=404)

    def test_handle_put_unauthorized(self):
        self.handler.path = "/api/channel-config"
        self.handler._dashboard_authorized.return_value = False

        routes.handle_put(self.handler)

        self.handler._send_forbidden.assert_called_once()

    @patch("bot.dashboard_server_routes.context_manager")
    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_channel_config_success(self, mock_persistence, mock_context_manager):
        self.handler.path = "/api/channel-config"
        self.handler._read_json_payload.return_value = {
            "channel_id": "canal_a",
            "temperature": 0.41,
            "top_p": 0.77,
            "agent_paused": True,
        }
        mock_persistence.load_channel_config_sync.return_value = {
            "channel_id": "canal_a",
            "temperature": 0.19,
            "top_p": 0.55,
            "agent_paused": False,
        }
        mock_persistence.load_channel_identity_sync.return_value = {
            "channel_id": "canal_a",
            "persona_name": "Byte Coach",
            "tone": "tatico",
            "emote_vocab": ["PogChamp"],
            "lore": "Lore base.",
        }
        mock_persistence.save_channel_config_sync.return_value = {
            "channel_id": "canal_a",
            "temperature": 0.41,
            "top_p": 0.77,
            "agent_paused": True,
            "has_override": True,
            "updated_at": "2026-02-27T13:00:00Z",
            "source": "supabase",
        }
        mock_persistence.save_channel_identity_sync.return_value = {
            "channel_id": "canal_a",
            "persona_name": "Byte Coach",
            "tone": "tatico",
            "emote_vocab": ["PogChamp"],
            "lore": "Lore base.",
            "has_identity": True,
            "updated_at": "2026-02-27T13:00:00Z",
            "source": "supabase",
        }

        routes.handle_put(self.handler)

        mock_persistence.load_channel_config_sync.assert_called_with("canal_a")
        mock_persistence.load_channel_identity_sync.assert_called_with("canal_a")
        mock_persistence.save_channel_config_sync.assert_called_with(
            "canal_a",
            temperature=0.41,
            top_p=0.77,
            agent_paused=True,
        )
        mock_persistence.save_channel_identity_sync.assert_called_with(
            "canal_a",
            persona_name="Byte Coach",
            tone="tatico",
            emote_vocab=["PogChamp"],
            lore="Lore base.",
        )
        mock_context_manager.apply_channel_config.assert_called_with(
            "canal_a",
            temperature=0.41,
            top_p=0.77,
            agent_paused=True,
        )
        mock_context_manager.apply_channel_identity.assert_called_with(
            "canal_a",
            persona_name="Byte Coach",
            tone="tatico",
            emote_vocab=["PogChamp"],
            lore="Lore base.",
        )
        self.handler._send_json.assert_called()

    @patch("bot.dashboard_server_routes.context_manager")
    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_channel_config_preserves_pause_when_payload_omits_flag(
        self, mock_persistence, mock_context_manager
    ):
        self.handler.path = "/api/channel-config"
        self.handler._read_json_payload.return_value = {
            "channel_id": "canal_a",
            "temperature": 0.29,
            "top_p": 0.64,
        }
        mock_persistence.load_channel_config_sync.return_value = {
            "channel_id": "canal_a",
            "agent_paused": True,
        }
        mock_persistence.load_channel_identity_sync.return_value = {
            "channel_id": "canal_a",
            "persona_name": "Byte Coach",
            "tone": "calmo",
            "emote_vocab": ["Kappa", "LUL"],
            "lore": "Contexto legado.",
        }
        mock_persistence.save_channel_config_sync.return_value = {
            "channel_id": "canal_a",
            "temperature": 0.29,
            "top_p": 0.64,
            "agent_paused": True,
            "has_override": True,
            "updated_at": "2026-02-27T13:00:00Z",
            "source": "supabase",
        }
        mock_persistence.save_channel_identity_sync.return_value = {
            "channel_id": "canal_a",
            "persona_name": "Byte Coach",
            "tone": "calmo",
            "emote_vocab": ["Kappa", "LUL"],
            "lore": "Contexto legado.",
            "has_identity": True,
            "updated_at": "2026-02-27T13:00:00Z",
            "source": "supabase",
        }

        routes.handle_put(self.handler)

        mock_persistence.save_channel_config_sync.assert_called_with(
            "canal_a",
            temperature=0.29,
            top_p=0.64,
            agent_paused=True,
        )
        mock_persistence.save_channel_identity_sync.assert_called_with(
            "canal_a",
            persona_name="Byte Coach",
            tone="calmo",
            emote_vocab=["Kappa", "LUL"],
            lore="Contexto legado.",
        )
        mock_context_manager.apply_channel_config.assert_called_with(
            "canal_a",
            temperature=0.29,
            top_p=0.64,
            agent_paused=True,
        )
        mock_context_manager.apply_channel_identity.assert_called_with(
            "canal_a",
            persona_name="Byte Coach",
            tone="calmo",
            emote_vocab=["Kappa", "LUL"],
            lore="Contexto legado.",
        )
        self.handler._send_json.assert_called()

    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_channel_config_invalid_request(self, mock_persistence):
        self.handler.path = "/api/channel-config"
        self.handler._read_json_payload.return_value = {"channel_id": "canal_a", "top_p": 2}
        mock_persistence.save_channel_config_sync.side_effect = ValueError(
            "top_p fora do intervalo permitido."
        )

        routes.handle_put(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "invalid_request",
                "message": "top_p fora do intervalo permitido.",
            },
            status_code=400,
        )

    @patch("bot.dashboard_server_routes.context_manager")
    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_agent_notes_success(self, mock_persistence, mock_context_manager):
        self.handler.path = "/api/agent-notes"
        self.handler._read_json_payload.return_value = {
            "channel_id": "canal_a",
            "notes": "Sem spoiler pesado.",
        }
        mock_persistence.save_agent_notes_sync.return_value = {
            "channel_id": "canal_a",
            "notes": "Sem spoiler pesado.",
            "has_notes": True,
            "updated_at": "2026-02-27T13:10:00Z",
            "source": "supabase",
        }

        routes.handle_put(self.handler)

        mock_persistence.save_agent_notes_sync.assert_called_with(
            "canal_a",
            notes="Sem spoiler pesado.",
        )
        mock_context_manager.apply_agent_notes.assert_called_with(
            "canal_a",
            notes="Sem spoiler pesado.",
        )
        self.handler._send_json.assert_called()

    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_agent_notes_invalid_request(self, mock_persistence):
        self.handler.path = "/api/agent-notes"
        self.handler._read_json_payload.return_value = {"channel_id": "canal_a", "notes": "x"}
        mock_persistence.save_agent_notes_sync.side_effect = ValueError(
            "agent_notes excede o tamanho permitido."
        )

        routes.handle_put(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "invalid_request",
                "message": "agent_notes excede o tamanho permitido.",
            },
            status_code=400,
        )

    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_semantic_memory_success(self, mock_persistence):
        self.handler.path = "/api/semantic-memory"
        self.handler._read_json_payload.return_value = {
            "channel_id": "canal_a",
            "content": "Priorize lore sem spoiler.",
            "memory_type": "instruction",
            "tags": "lore,spoiler",
        }
        mock_persistence.save_semantic_memory_entry_sync.return_value = {
            "entry_id": "mem_1",
            "channel_id": "canal_a",
            "memory_type": "instruction",
            "content": "Priorize lore sem spoiler.",
            "tags": ["lore", "spoiler"],
            "source": "memory",
        }

        routes.handle_put(self.handler)

        mock_persistence.save_semantic_memory_entry_sync.assert_called_with(
            "canal_a",
            content="Priorize lore sem spoiler.",
            memory_type="instruction",
            tags="lore,spoiler",
            context=None,
            entry_id=None,
        )
        self.handler._send_json.assert_called_with(
            {
                "ok": True,
                "mode": routes.TWITCH_CHAT_MODE,
                "entry": {
                    "entry_id": "mem_1",
                    "channel_id": "canal_a",
                    "memory_type": "instruction",
                    "content": "Priorize lore sem spoiler.",
                    "tags": ["lore", "spoiler"],
                    "source": "memory",
                },
            },
            status_code=200,
        )

    @patch("bot.dashboard_server_routes.persistence")
    def test_handle_put_semantic_memory_invalid_request(self, mock_persistence):
        self.handler.path = "/api/semantic-memory"
        self.handler._read_json_payload.return_value = {"channel_id": "canal_a", "content": ""}
        mock_persistence.save_semantic_memory_entry_sync.side_effect = ValueError(
            "semantic_memory_content obrigatorio."
        )

        routes.handle_put(self.handler)

        self.handler._send_json.assert_called_with(
            {
                "ok": False,
                "error": "invalid_request",
                "message": "semantic_memory_content obrigatorio.",
            },
            status_code=400,
        )
