import asyncio
import time
import unittest

from bot.logic import context_manager
from bot.sentiment_engine import sentiment_engine


class TestMemoryTTLScientific(unittest.TestCase):
    def test_context_and_sentiment_purging(self):
        """Valida que canais inativos são removidos e ativos permanecem."""
        # Limpa para isolamento
        for ch in context_manager.list_active_channels():
            context_manager.cleanup(ch)

        # 1. Setup: Criamos dois canais
        ctx_ativo = context_manager.get("canal_ativo")
        ctx_inativo = context_manager.get("canal_inativo")

        sentiment_engine.ingest_message("canal_ativo", "muito bom")
        sentiment_engine.ingest_message("canal_inativo", "ruim")

        # 2. Simulamos passagem de tempo para o canal inativo
        ctx_inativo.last_activity = time.time() - 8000  # > 7200s (2h)
        sentiment_engine._last_activity["canal_inativo"] = time.time() - 8000

        # O canal ativo teve atividade agora
        ctx_ativo.last_activity = time.time()
        sentiment_engine._last_activity["canal_ativo"] = time.time()

        # 3. Executamos a purga
        purged_ctx = context_manager.purge_expired(max_age_seconds=7200)
        purged_sent = sentiment_engine.cleanup_inactive(max_age_seconds=7200)

        # 4. Asserções
        active_channels = context_manager.list_active_channels()
        active_sentiments = list(sentiment_engine._channel_events.keys())

        print("\n[SCIENTIFIC] Memory Management Audit")
        print(f"Purged Contexts: {purged_ctx}")
        print(f"Active Channels: {active_channels}")

        self.assertEqual(purged_ctx, 1)
        self.assertEqual(purged_sent, 1)
        self.assertIn("canal_ativo", active_channels)
        self.assertNotIn("canal_inativo", active_channels)

        print("[SCIENTIFIC] Memory Management TTL: OK")


if __name__ == "__main__":
    unittest.main()
