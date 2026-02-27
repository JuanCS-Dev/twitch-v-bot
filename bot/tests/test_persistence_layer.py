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
        self.assertTrue(payload["has_override"])
        self.assertEqual(layer.load_channel_config_sync("canal_a")["temperature"], 0.33)

    async def test_load_channel_config_async_returns_cached_defaults_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = await layer.load_channel_config("default")

        self.assertEqual(payload["channel_id"], "default")
        self.assertIsNone(payload["temperature"])
        self.assertIsNone(payload["top_p"])
        self.assertFalse(payload["has_override"])

    async def test_save_channel_config_async_delegates_to_sync(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        payload = await layer.save_channel_config("Canal_B", temperature=0.21, top_p=0.63)

        self.assertEqual(payload["channel_id"], "canal_b")
        self.assertEqual(payload["temperature"], 0.21)
        self.assertEqual(payload["top_p"], 0.63)

    def test_save_channel_config_sync_rejects_invalid_values(self):
        with patch.dict(os.environ, {}, clear=True):
            layer = PersistenceLayer()

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("", temperature=0.3)

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("canal_a", temperature=2.5)

        with self.assertRaises(ValueError):
            layer.save_channel_config_sync("canal_a", top_p="abc")

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
            "has_override": True,
            "updated_at": "2026-02-27T14:00:00Z",
            "source": "memory",
        }

        payload = layer.load_channel_config_sync("Canal_Fallback")

        self.assertEqual(payload["channel_id"], "canal_fallback")
        self.assertEqual(payload["temperature"], 0.19)
        self.assertEqual(payload["top_p"], 0.52)
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
        saved = layer.save_channel_config_sync("canal_supabase", temperature=0.27, top_p=0.74)

        self.assertEqual(loaded["source"], "supabase")
        self.assertEqual(loaded["temperature"], 0.27)
        self.assertEqual(saved["top_p"], 0.74)
        mock_client.table.return_value.upsert.assert_called_once_with(
            {
                "channel_id": "canal_supabase",
                "temperature": 0.27,
                "top_p": 0.74,
                "updated_at": "now()",
            }
        )
