import os
import unittest
from unittest.mock import MagicMock, patch

from bot.persistence_layer import PersistenceLayer


class TestPersistenceLayer(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        patch.stopall()

    def test_save_channel_config_sync_uses_memory_fallback_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = layer.save_channel_config_sync("Canal_A", temperature=0.33, top_p=0.91)

        self.assertEqual(payload["channel_id"], "canal_a")
        self.assertEqual(payload["temperature"], 0.33)
        self.assertEqual(payload["top_p"], 0.91)
        self.assertFalse(payload["agent_paused"])
        self.assertTrue(payload["has_override"])
        self.assertEqual(layer.load_channel_config_sync("canal_a")["temperature"], 0.33)

    async def test_load_channel_config_async_returns_cached_defaults_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = await layer.load_channel_config("default")

        self.assertEqual(payload["channel_id"], "default")
        self.assertIsNone(payload["temperature"])
        self.assertIsNone(payload["top_p"])
        self.assertFalse(payload["agent_paused"])
        self.assertFalse(payload["has_override"])

    async def test_save_channel_config_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = await layer.save_channel_config("Canal_B", temperature=0.21, top_p=0.63)

        self.assertEqual(payload["channel_id"], "canal_b")
        self.assertEqual(payload["temperature"], 0.21)
        self.assertEqual(payload["top_p"], 0.63)
        self.assertFalse(payload["agent_paused"])

    def test_save_channel_config_sync_uses_agent_paused_override(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = layer.save_channel_config_sync("Canal_Pause", agent_paused=True)

        self.assertEqual(payload["channel_id"], "canal_pause")
        self.assertIsNone(payload["temperature"])
        self.assertIsNone(payload["top_p"])
        self.assertTrue(payload["agent_paused"])
        self.assertTrue(payload["has_override"])

    def test_save_agent_notes_sync_uses_memory_fallback_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = layer.save_agent_notes_sync("Canal_A", notes="Priorize lore.\nSem backseat.")

        self.assertEqual(payload["channel_id"], "canal_a")
        self.assertEqual(payload["notes"], "Priorize lore.\nSem backseat.")
        self.assertTrue(payload["has_notes"])
        self.assertEqual(layer.load_agent_notes_sync("canal_a")["notes"], payload["notes"])

    def test_save_agent_notes_sync_clears_empty_notes(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = layer.save_agent_notes_sync("Canal_A", notes=None)

        self.assertEqual(payload["channel_id"], "canal_a")
        self.assertEqual(payload["notes"], "")
        self.assertFalse(payload["has_notes"])

    async def test_load_agent_notes_async_returns_cached_defaults_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = await layer.load_agent_notes("default")

        self.assertEqual(payload["channel_id"], "default")
        self.assertEqual(payload["notes"], "")
        self.assertFalse(payload["has_notes"])

    async def test_save_agent_notes_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = await layer.save_agent_notes("Canal_B", notes="Foque no host.")

        self.assertEqual(payload["channel_id"], "canal_b")
        self.assertEqual(payload["notes"], "Foque no host.")

    def test_save_channel_config_sync_rejects_invalid_values(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("", temperature=0.3)

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("canal_a", temperature=2.5)

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("canal_a", top_p="abc")

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("canal_a", agent_paused="talvez")

    def test_save_agent_notes_sync_rejects_invalid_values(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with self.assertRaises(ValueError):
            layer.save_agent_notes_sync("", notes="x")

        with self.assertRaises(ValueError):
            layer.save_agent_notes_sync("canal_a", notes="x" * 2001)

    def test_load_channel_config_sync_returns_memory_fallback_on_supabase_error(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.side_effect = RuntimeError("supabase down")

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        layer._channel_config_cache["canal_fallback"] = {
            "channel_id": "canal_fallback",
            "temperature": 0.19,
            "top_p": 0.52,
            "agent_paused": True,
            "has_override": True,
            "updated_at": "2026-02-27T14:00:00Z",
            "source": "memory",
        }

        payload = layer.load_channel_config_sync("Canal_Fallback")

        self.assertEqual(payload["channel_id"], "canal_fallback")
        self.assertEqual(payload["temperature"], 0.19)
        self.assertEqual(payload["top_p"], 0.52)
        self.assertTrue(payload["agent_paused"])
        self.assertEqual(payload["source"], "memory")

    def test_save_channel_config_sync_returns_memory_payload_on_supabase_error(self):
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError(
            "write failed"
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        payload = layer.save_channel_config_sync("Canal_C", temperature=0.44, top_p=0.66)

        self.assertEqual(payload["channel_id"], "canal_c")
        self.assertEqual(payload["temperature"], 0.44)
        self.assertEqual(payload["top_p"], 0.66)
        self.assertFalse(payload["agent_paused"])
        self.assertEqual(payload["source"], "memory")

    def test_load_agent_notes_sync_returns_memory_fallback_on_supabase_error(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.side_effect = RuntimeError("supabase down")

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        layer._agent_notes_cache["canal_fallback"] = {
            "channel_id": "canal_fallback",
            "notes": "Segura a ironia.",
            "has_notes": True,
            "updated_at": "2026-02-27T14:05:00Z",
            "source": "memory",
        }

        payload = layer.load_agent_notes_sync("Canal_Fallback")

        self.assertEqual(payload["channel_id"], "canal_fallback")
        self.assertEqual(payload["notes"], "Segura a ironia.")
        self.assertEqual(payload["source"], "memory")

    def test_save_agent_notes_sync_returns_memory_payload_on_supabase_error(self):
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError(
            "write failed"
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        payload = layer.save_agent_notes_sync("Canal_C", notes="Nao force meme.")

        self.assertEqual(payload["channel_id"], "canal_c")
        self.assertEqual(payload["notes"], "Nao force meme.")
        self.assertEqual(payload["source"], "memory")

    def test_load_and_save_channel_config_sync_with_supabase(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.return_value = MagicMock(
            data={
                "channel_id": "canal_supabase",
                "temperature": 0.27,
                "top_p": 0.74,
                "agent_paused": True,
                "updated_at": "2026-02-27T12:00:00Z",
            }
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        loaded = layer.load_channel_config_sync("canal_supabase")
        saved = layer.save_channel_config_sync(
            "canal_supabase",
            temperature=0.27,
            top_p=0.74,
            agent_paused=True,
        )

        self.assertEqual(loaded["source"], "supabase")
        self.assertEqual(loaded["temperature"], 0.27)
        self.assertTrue(loaded["agent_paused"])
        self.assertEqual(saved["top_p"], 0.74)
        mock_client.table.return_value.upsert.assert_called_once_with(
            {
                "channel_id": "canal_supabase",
                "temperature": 0.27,
                "top_p": 0.74,
                "agent_paused": True,
                "updated_at": "now()",
            }
        )

    def test_load_and_save_agent_notes_sync_with_supabase(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.return_value = MagicMock(
            data={
                "channel_id": "canal_supabase",
                "notes": "Leia o chat antes de responder.",
                "updated_at": "2026-02-27T12:10:00Z",
            }
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        loaded = layer.load_agent_notes_sync("canal_supabase")
        saved = layer.save_agent_notes_sync(
            "canal_supabase",
            notes="Leia o chat antes de responder.",
        )

        self.assertEqual(loaded["source"], "supabase")
        self.assertEqual(loaded["notes"], "Leia o chat antes de responder.")
        self.assertEqual(saved["source"], "supabase")
        mock_client.table.return_value.upsert.assert_called_once_with(
            {
                "channel_id": "canal_supabase",
                "notes": "Leia o chat antes de responder.",
                "updated_at": "now()",
            }
        )

    def test_load_channel_state_sync_returns_none_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        self.assertIsNone(layer.load_channel_state_sync("Canal_A"))

    def test_load_channel_state_sync_reads_supabase_row(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.return_value = MagicMock(
            data={"channel_id": "canal_a", "current_game": "Balatro"}
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        payload = layer.load_channel_state_sync("Canal_A")

        self.assertEqual(payload["current_game"], "Balatro")
        table.select.return_value.eq.assert_called_with("channel_id", "canal_a")

    def test_load_recent_history_sync_reads_supabase_rows(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        order_chain = (
            table.select.return_value.eq.return_value.order.return_value.limit.return_value
        )
        order_chain.execute.return_value = MagicMock(
            data=[
                {"author": "byte", "message": "reply"},
                {"author": "viewer", "message": "hello"},
            ]
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        payload = layer.load_recent_history_sync("Canal_A", limit=2)

        self.assertEqual(payload, ["viewer: hello", "byte: reply"])
        table.select.return_value.eq.assert_called_with("channel_id", "canal_a")

    async def test_async_state_and_history_loaders_delegate_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with patch.object(
            layer, "load_channel_state_sync", return_value={"channel_id": "canal_a"}
        ) as mock_state:
            state = await layer.load_channel_state("Canal_A")
        with patch.object(
            layer, "load_recent_history_sync", return_value=["viewer: hello"]
        ) as mock_history:
            history = await layer.load_recent_history("Canal_A", limit=3)

        self.assertEqual(state, {"channel_id": "canal_a"})
        self.assertEqual(history, ["viewer: hello"])
        mock_state.assert_called_once_with("Canal_A")
        mock_history.assert_called_once_with("Canal_A", limit=3)

    def test_observability_channel_history_memory_fallback_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        saved = layer.save_observability_channel_history_sync(
            "Canal_A",
            {
                "captured_at": "2026-02-27T17:00:00Z",
                "metrics": {
                    "chat_messages_total": 11,
                    "byte_triggers_total": 3,
                    "replies_total": 2,
                    "llm_interactions_total": 2,
                    "errors_total": 0,
                },
                "chatters": {"unique_total": 4, "active_60m": 2},
                "chat_analytics": {"messages_60m": 8, "byte_triggers_60m": 3},
                "agent_outcomes": {"ignored_rate_60m": 10.0},
            },
        )
        loaded = layer.load_observability_channel_history_sync("canal_a", limit=5)
        latest = layer.load_latest_observability_channel_snapshots_sync(limit=3)

        self.assertEqual(saved["source"], "memory")
        self.assertEqual(loaded[0]["channel_id"], "canal_a")
        self.assertEqual(loaded[0]["metrics"]["chat_messages_total"], 11)
        self.assertEqual(latest[0]["channel_id"], "canal_a")

    def test_observability_channel_history_uses_timestamp_fallback_when_captured_at_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        saved = layer.save_observability_channel_history_sync(
            "Canal_A",
            {
                "timestamp": "2026-02-27T17:05:00Z",
                "metrics": {"chat_messages_total": 3},
            },
        )

        self.assertEqual(saved["captured_at"], "2026-02-27T17:05:00Z")
        self.assertEqual(saved["channel_id"], "canal_a")

    def test_observability_channel_history_supabase_roundtrip(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = (
            table.select.return_value.eq.return_value.order.return_value.limit.return_value
        )
        select_chain.execute.return_value = MagicMock(
            data=[
                {
                    "channel_id": "canal_supabase",
                    "captured_at": "2026-02-27T17:10:00Z",
                    "snapshot": {
                        "metrics": {
                            "chat_messages_total": 14,
                            "byte_triggers_total": 4,
                            "replies_total": 3,
                            "llm_interactions_total": 3,
                            "errors_total": 1,
                        },
                        "chatters": {"unique_total": 5, "active_60m": 3},
                    },
                }
            ]
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        loaded = layer.load_observability_channel_history_sync("canal_supabase", limit=6)
        saved = layer.save_observability_channel_history_sync(
            "canal_supabase",
            {
                "metrics": {
                    "chat_messages_total": 14,
                    "byte_triggers_total": 4,
                    "replies_total": 3,
                    "llm_interactions_total": 3,
                    "errors_total": 1,
                }
            },
        )

        self.assertEqual(loaded[0]["channel_id"], "canal_supabase")
        self.assertEqual(loaded[0]["metrics"]["chat_messages_total"], 14)
        self.assertEqual(saved["source"], "supabase")
        insert_payload = mock_client.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_payload["channel_id"], "canal_supabase")
        self.assertEqual(insert_payload["captured_at"], "now()")
        self.assertIn("snapshot", insert_payload)

    def test_observability_latest_snapshots_supabase_uses_distinct_channels(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.order.return_value.limit.return_value
        select_chain.execute.return_value = MagicMock(
            data=[
                {
                    "channel_id": "canal_a",
                    "captured_at": "2026-02-27T17:20:00Z",
                    "snapshot": {"metrics": {"chat_messages_total": 30}},
                },
                {
                    "channel_id": "canal_a",
                    "captured_at": "2026-02-27T17:19:00Z",
                    "snapshot": {"metrics": {"chat_messages_total": 29}},
                },
                {
                    "channel_id": "canal_b",
                    "captured_at": "2026-02-27T17:18:00Z",
                    "snapshot": {"metrics": {"chat_messages_total": 18}},
                },
            ]
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        latest = layer.load_latest_observability_channel_snapshots_sync(limit=2)

        self.assertEqual(len(latest), 2)
        self.assertEqual(latest[0]["channel_id"], "canal_a")
        self.assertEqual(latest[1]["channel_id"], "canal_b")
        self.assertEqual(latest[0]["metrics"]["chat_messages_total"], 30)

    async def test_observability_channel_history_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with patch.object(
            layer,
            "save_observability_channel_history_sync",
            return_value={"channel_id": "canal_a", "source": "memory"},
        ) as mock_save:
            saved = await layer.save_observability_channel_history(
                "Canal_A",
                {"metrics": {"chat_messages_total": 1}},
            )
        with patch.object(
            layer,
            "load_observability_channel_history_sync",
            return_value=[{"channel_id": "canal_a"}],
        ) as mock_load:
            loaded = await layer.load_observability_channel_history("Canal_A", limit=7)
        with patch.object(
            layer,
            "load_latest_observability_channel_snapshots_sync",
            return_value=[{"channel_id": "canal_a"}],
        ) as mock_latest:
            latest = await layer.load_latest_observability_channel_snapshots(limit=4)

        self.assertEqual(saved["channel_id"], "canal_a")
        self.assertEqual(loaded[0]["channel_id"], "canal_a")
        self.assertEqual(latest[0]["channel_id"], "canal_a")
        mock_save.assert_called_once_with("Canal_A", {"metrics": {"chat_messages_total": 1}})
        mock_load.assert_called_once_with("Canal_A", limit=7)
        mock_latest.assert_called_once_with(limit=4)

    def test_post_stream_report_memory_fallback_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        saved = layer.save_post_stream_report_sync(
            "Canal_A",
            {
                "generated_at": "2026-02-27T20:05:00Z",
                "trigger": "manual_dashboard",
                "narrative": "Resumo final da live.",
                "recommendations": ["Priorizar backlog no inicio."],
            },
            trigger="manual_dashboard",
        )
        loaded = layer.load_latest_post_stream_report_sync("canal_a")

        self.assertEqual(saved["channel_id"], "canal_a")
        self.assertEqual(saved["source"], "memory")
        self.assertEqual(loaded["generated_at"], "2026-02-27T20:05:00Z")
        self.assertEqual(loaded["recommendations"], ["Priorizar backlog no inicio."])

    def test_post_stream_report_supabase_roundtrip(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = (
            table.select.return_value.eq.return_value.order.return_value.limit.return_value
        )
        select_chain.execute.return_value = MagicMock(
            data=[
                {
                    "channel_id": "canal_supabase",
                    "generated_at": "2026-02-27T20:10:00Z",
                    "trigger": "manual_dashboard",
                    "report": {
                        "narrative": "Resumo supabase",
                        "recommendations": ["Reforcar CTA inicial."],
                    },
                }
            ]
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        loaded = layer.load_latest_post_stream_report_sync("canal_supabase")
        saved = layer.save_post_stream_report_sync(
            "canal_supabase",
            {
                "generated_at": "2026-02-27T20:11:00Z",
                "trigger": "manual_dashboard",
                "narrative": "Resumo salvo",
                "recommendations": ["Seguir baseline."],
            },
            trigger="manual_dashboard",
        )

        self.assertEqual(loaded["source"], "supabase")
        self.assertEqual(loaded["generated_at"], "2026-02-27T20:10:00Z")
        self.assertEqual(saved["source"], "supabase")
        self.assertEqual(saved["channel_id"], "canal_supabase")
        insert_payload = mock_client.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_payload["channel_id"], "canal_supabase")
        self.assertEqual(insert_payload["trigger"], "manual_dashboard")
        self.assertEqual(insert_payload["generated_at"], "2026-02-27T20:11:00Z")

    async def test_post_stream_report_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with patch.object(
            layer,
            "save_post_stream_report_sync",
            return_value={"channel_id": "canal_a", "source": "memory"},
        ) as mock_save:
            saved = await layer.save_post_stream_report(
                "Canal_A",
                {"narrative": "Resumo"},
                trigger="manual_dashboard",
            )
        with patch.object(
            layer,
            "load_latest_post_stream_report_sync",
            return_value={"channel_id": "canal_a", "source": "memory"},
        ) as mock_load:
            loaded = await layer.load_latest_post_stream_report("Canal_A")

        self.assertEqual(saved["channel_id"], "canal_a")
        self.assertEqual(loaded["channel_id"], "canal_a")
        mock_save.assert_called_once_with(
            "Canal_A",
            {"narrative": "Resumo"},
            trigger="manual_dashboard",
        )
        mock_load.assert_called_once_with("Canal_A")

    def test_semantic_memory_memory_fallback_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        saved = layer.save_semantic_memory_entry_sync(
            "Canal_A",
            content="Viewer prefere lore sem spoiler.",
            memory_type="preference",
            tags="lore,spoiler",
        )
        loaded = layer.load_semantic_memory_entries_sync("canal_a", limit=5)
        matches = layer.search_semantic_memory_entries_sync(
            "canal_a",
            query="lore",
            limit=3,
            search_limit=15,
        )

        self.assertEqual(saved["channel_id"], "canal_a")
        self.assertEqual(saved["memory_type"], "preference")
        self.assertEqual(saved["source"], "memory")
        self.assertEqual(loaded[0]["entry_id"], saved["entry_id"])
        self.assertGreaterEqual(matches[0]["similarity"], 0.0)

    def test_semantic_memory_supabase_roundtrip(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = (
            table.select.return_value.eq.return_value.order.return_value.limit.return_value
        )
        select_chain.execute.return_value = MagicMock(
            data=[
                {
                    "entry_id": "entry_1",
                    "channel_id": "canal_supabase",
                    "memory_type": "fact",
                    "content": "Canal prioriza gameplay limpo.",
                    "tags": ["gameplay"],
                    "context": {"source": "runtime"},
                    "embedding": [0.0] * 48,
                    "created_at": "2026-02-27T20:20:00Z",
                    "updated_at": "2026-02-27T20:20:00Z",
                }
            ]
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        loaded = layer.load_semantic_memory_entries_sync("canal_supabase", limit=4)
        saved = layer.save_semantic_memory_entry_sync(
            "canal_supabase",
            content="Atualizar lore da season.",
            memory_type="instruction",
            tags="lore,season",
        )

        self.assertEqual(loaded[0]["source"], "supabase")
        self.assertEqual(loaded[0]["entry_id"], "entry_1")
        self.assertEqual(saved["channel_id"], "canal_supabase")
        self.assertEqual(saved["source"], "supabase")
        upsert_payload = mock_client.table.return_value.upsert.call_args[0][0]
        self.assertEqual(upsert_payload["channel_id"], "canal_supabase")
        self.assertEqual(upsert_payload["memory_type"], "instruction")
        self.assertEqual(upsert_payload["updated_at"], "now()")

    async def test_semantic_memory_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with patch.object(
            layer,
            "save_semantic_memory_entry_sync",
            return_value={"channel_id": "canal_a", "source": "memory"},
        ) as mock_save:
            saved = await layer.save_semantic_memory_entry(
                "Canal_A",
                content="memo",
                memory_type="fact",
                tags="meta",
                context={"scene": "boss"},
                entry_id="entry_1",
            )
        with patch.object(
            layer,
            "load_semantic_memory_entries_sync",
            return_value=[{"channel_id": "canal_a"}],
        ) as mock_load:
            loaded = await layer.load_semantic_memory_entries("Canal_A", limit=6)
        with patch.object(
            layer,
            "search_semantic_memory_entries_sync",
            return_value=[{"channel_id": "canal_a", "similarity": 0.7}],
        ) as mock_search:
            matches = await layer.search_semantic_memory_entries(
                "Canal_A",
                query="lore",
                limit=2,
                search_limit=20,
            )

        self.assertEqual(saved["channel_id"], "canal_a")
        self.assertEqual(loaded[0]["channel_id"], "canal_a")
        self.assertEqual(matches[0]["channel_id"], "canal_a")
        mock_save.assert_called_once_with(
            "Canal_A",
            content="memo",
            memory_type="fact",
            tags="meta",
            context={"scene": "boss"},
            entry_id="entry_1",
        )
        mock_load.assert_called_once_with("Canal_A", limit=6)
        mock_search.assert_called_once_with(
            "Canal_A",
            query="lore",
            limit=2,
            search_limit=20,
        )

    def test_observability_rollup_memory_fallback_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        saved = layer.save_observability_rollup_sync({"counters": {"chat_messages_total": 2}})
        loaded = layer.load_observability_rollup_sync()

        self.assertEqual(saved["rollup_key"], "global")
        self.assertEqual(saved["source"], "memory")
        self.assertEqual(loaded["state"]["counters"]["chat_messages_total"], 2)

    def test_observability_rollup_supabase_roundtrip(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.return_value = MagicMock(
            data={
                "rollup_key": "global",
                "state": {"counters": {"chat_messages_total": 9}},
                "updated_at": "2026-02-27T17:00:00Z",
            }
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        loaded = layer.load_observability_rollup_sync()
        saved = layer.save_observability_rollup_sync({"counters": {"chat_messages_total": 9}})

        self.assertEqual(loaded["source"], "supabase")
        self.assertEqual(loaded["state"]["counters"]["chat_messages_total"], 9)
        self.assertEqual(saved["source"], "supabase")
        mock_client.table.return_value.upsert.assert_called_once_with(
            {
                "rollup_key": "global",
                "state": {"counters": {"chat_messages_total": 9}},
                "updated_at": "now()",
            }
        )

    def test_observability_rollup_load_returns_cached_payload_on_supabase_error(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.side_effect = RuntimeError("boom")

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        layer._observability_rollup_cache = {
            "rollup_key": "global",
            "state": {"counters": {"errors_total": 3}},
            "updated_at": "2026-02-27T18:00:00Z",
            "source": "memory",
        }

        loaded = layer.load_observability_rollup_sync()

        self.assertEqual(loaded["state"]["counters"]["errors_total"], 3)
        self.assertEqual(loaded["source"], "memory")

    def test_observability_rollup_load_returns_cached_payload_when_row_missing(self):
        mock_client = MagicMock()
        table = mock_client.table.return_value
        select_chain = table.select.return_value.eq.return_value.maybe_single.return_value
        select_chain.execute.return_value = MagicMock(data=None)

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        layer._observability_rollup_cache = {
            "rollup_key": "global",
            "state": {"counters": {"replies_total": 4}},
            "updated_at": "2026-02-27T18:10:00Z",
            "source": "memory",
        }

        loaded = layer.load_observability_rollup_sync()

        self.assertEqual(loaded["state"]["counters"]["replies_total"], 4)
        self.assertEqual(loaded["source"], "memory")

    def test_observability_rollup_save_returns_memory_payload_on_supabase_error(self):
        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError(
            "write failed"
        )

        with patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test_key"},
            clear=True,
        ):
            with patch("bot.persistence_layer.create_client", return_value=mock_client):
                layer = PersistenceLayer()

        saved = layer.save_observability_rollup_sync({"counters": {"errors_total": 5}})

        self.assertEqual(saved["source"], "memory")
        self.assertEqual(saved["state"]["counters"]["errors_total"], 5)

    async def test_observability_rollup_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with patch.object(
            layer,
            "load_observability_rollup_sync",
            return_value={"rollup_key": "global"},
        ) as mock_load:
            loaded = await layer.load_observability_rollup()
        with patch.object(
            layer,
            "save_observability_rollup_sync",
            return_value={"rollup_key": "global", "source": "memory"},
        ) as mock_save:
            saved = await layer.save_observability_rollup({"counters": {"chat_messages_total": 1}})

        self.assertEqual(loaded["rollup_key"], "global")
        self.assertEqual(saved["source"], "memory")
        mock_load.assert_called_once_with()
        mock_save.assert_called_once_with({"counters": {"chat_messages_total": 1}})
