import concurrent.futures
import threading
import unittest

from bot.logic import context_manager


class TestContextIsolationScientific(unittest.TestCase):
    def test_isolation_between_channels(self):
        """Valida que mensagens no Canal A não vazam para o Canal B."""
        ctx_a = context_manager.get("canal_a")
        ctx_b = context_manager.get("canal_b")

        ctx_a.remember_user_message("user_a", "segredo_a")
        ctx_b.remember_user_message("user_b", "segredo_b")

        history_a = ctx_a.format_recent_chat()
        history_b = ctx_b.format_recent_chat()

        self.assertIn("segredo_a", history_a)
        self.assertNotIn("segredo_b", history_a)

        self.assertIn("segredo_b", history_b)
        self.assertNotIn("segredo_a", history_b)

    def test_thread_safety_concurrency(self):
        """Teste de estresse: simula 50 canais sendo acessados simultaneamente."""

        def access_context(i):
            channel_id = f"channel_{i % 5}"
            ctx = context_manager.get(channel_id)
            ctx.remember_user_message(f"user_{i}", f"msg_{i}")
            return channel_id

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 1000 operações concorrentes
            futures = [executor.submit(access_context, i) for i in range(1000)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        active_channels = context_manager.list_active_channels()
        # Deve ter exatamente 5 canais (0 a 4)
        self.assertEqual(len([c for c in active_channels if c.startswith("channel_")]), 5)

        # Cada canal deve ter 12 mensagens (o limite máximo) e não 1000 misturadas
        for i in range(5):
            ctx = context_manager.get(f"channel_{i}")
            self.assertEqual(len(ctx.recent_chat_entries), 12)


if __name__ == "__main__":
    unittest.main()
