import asyncio
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from bot.logic_context import context_manager, StreamContext

class TestConcurrencyScientific(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        context_manager.set_main_loop(self.loop)
        
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()
        time.sleep(0.1)

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def tearDown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop_thread.join(timeout=1)

    def test_scientific_touch_concurrency_stability(self):
        """CIENTÍFICO: Validar que múltiplas chamadas ao _touch em threads paralelas não crasham o sistema."""
        ctx = StreamContext()
        ctx.channel_id = "test_channel"
        
        # Mocking a read-only property requires PropertyMock on the class
        with patch("bot.persistence_layer.PersistenceLayer.is_enabled", new_callable=PropertyMock) as mock_enabled:
            mock_enabled.return_value = True
            with patch("bot.persistence_layer.persistence.save_channel_state", return_value=asyncio.Future()) as mock_save:
                mock_save.return_value.set_result(True)
                
                def call_touch_repeatedly():
                    for _ in range(50):
                        ctx._touch()
                        time.sleep(0.001)

                threads = [threading.Thread(target=call_touch_repeatedly) for _ in range(10)]
                for t in threads:
                    t.start()
                
                for t in threads:
                    t.join(timeout=5)

                self.assertTrue(mock_save.called)
                print(f"Sucesso Científico: {mock_save.call_count} chamadas de persistência agendadas com segurança via threads externas.")

if __name__ == "__main__":
    unittest.main()
