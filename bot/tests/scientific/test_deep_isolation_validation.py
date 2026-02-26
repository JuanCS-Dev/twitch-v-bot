import asyncio
import concurrent.futures
import threading
import time
import unittest

from bot.logic import build_dynamic_prompt, context_manager
from bot.sentiment_engine import sentiment_engine


class TestDeepIsolationValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Limpar estados para garantir isolamento puro nos testes
        for ch in context_manager.list_active_channels():
            await context_manager.cleanup(ch)

    async def test_full_state_isolation_scientific(self):
        """Valida isolamento atômico de todo o estado (Contexto + Vibe + Observabilidade)."""
        channels = {
            "gaming_hub": {"game": "Elden Ring", "msg": "Pog Pog Pog", "expected_vibe": "Hyped"},
            "news_room": {
                "topic": "Economia",
                "msg": "??? ??? ??? ??? ???",
                "expected_vibe": "Confuso",
            },
            "chill_zone": {"topic": "Musica", "msg": "haha nice", "expected_vibe": "Divertido"},
        }

        for ch, data in channels.items():
            ctx = context_manager.get(ch)
            if "game" in data:
                ctx.update_content("game", data["game"])
            if "topic" in data:
                ctx.update_content("topic", data["topic"])

            ctx.remember_user_message("viewer", data["msg"])

            # Reset explicitamente o histórico de sentimentos para o canal
            if ch.lower() in sentiment_engine._channel_events:
                sentiment_engine._channel_events[ch.lower()].clear()

            sentiment_engine.ingest_message(ch, data["msg"])
            ctx.stream_vibe = sentiment_engine.get_vibe(ch)

        # Verificação Cruzada
        for ch, data in channels.items():
            ctx = context_manager.get(ch)
            vibe = sentiment_engine.get_vibe(ch)
            prompt = build_dynamic_prompt("o que rola?", "admin", ctx)

            print(f"\n--- Validation Audit [{ch}] ---")
            self.assertEqual(vibe, data["expected_vibe"], f"Vibe incorreta para {ch}")

            # Garante que dados de outros canais não vazaram no prompt
            for other_ch, other_data in channels.items():
                if other_ch != ch:
                    self.assertNotIn(
                        other_data["msg"],
                        prompt,
                        f"Leak detectado: msg de {other_ch} no prompt de {ch}",
                    )

    async def test_high_concurrency_race_conditions(self):
        """Teste de estresse concorrente para detectar race conditions no ContextManager."""
        num_channels = 5
        ops_per_thread = 20
        num_threads = 5

        async def worker(tid):
            for i in range(ops_per_thread):
                ch_id = f"stress_ch_{i % num_channels}"
                ctx = context_manager.get(ch_id)
                ctx.remember_user_message(f"thread_{tid}", f"msg_{i}")
                sentiment_engine.ingest_message(ch_id, "top gg")
                _ = sentiment_engine.get_vibe(ch_id)

        tasks = [worker(i) for i in range(num_threads)]
        await asyncio.gather(*tasks)

        # Validação final de integridade
        active_channels = context_manager.list_active_channels()
        for i in range(num_channels):
            ch_id = f"stress_ch_{i}"
            ctx = context_manager.get(ch_id)
            self.assertEqual(len(ctx.recent_chat_entries), 12)
            self.assertTrue(ch_id in active_channels)


if __name__ == "__main__":
    unittest.main()
