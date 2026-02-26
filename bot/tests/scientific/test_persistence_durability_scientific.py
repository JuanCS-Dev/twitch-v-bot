import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.persistence_layer import PersistenceLayer


class TestPersistenceDurabilityScientific(unittest.IsolatedAsyncioTestCase):
    async def test_boot_fallback_resilience(self):
        """Valida que o boot usa ENV se o Supabase falhar."""
        with patch.dict(os.environ, {"TWITCH_CHANNEL_LOGIN": "canal_env"}):
            with patch("bot.persistence_layer.create_client", side_effect=Exception("DB Down")):
                p = PersistenceLayer()
                self.assertFalse(p.is_enabled)
                channels = await p.get_active_channels()
                self.assertEqual(channels, [])

    @patch("bot.persistence_layer.create_client")
    async def test_save_load_state_consistency(self, mock_create):
        """Valida integridade do snapshot (Write-Through)."""
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        # Injetamos ENV para que o __init__ habilite o cliente
        with patch.dict(os.environ, {"SUPABASE_URL": "http://test", "SUPABASE_KEY": "test_key"}):
            p = PersistenceLayer()
            self.assertTrue(p.is_enabled)

            state = {
                "current_game": "Valorant",
                "stream_vibe": "Hyped",
                "live_observability": {"game": "Valorant Pro"},
            }

            # Mock encadeado do Supabase SDK
            mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock()

            success = await p.save_channel_state("test_ch", state)
            self.assertTrue(success)

            # Simula Select
            mock_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=state
            )

            loaded = await p.load_channel_state("test_ch")
            self.assertEqual(loaded["current_game"], "Valorant")
            self.assertEqual(loaded["stream_vibe"], "Hyped")


if __name__ == "__main__":
    unittest.main()
