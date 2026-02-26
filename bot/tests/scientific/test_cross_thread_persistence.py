import asyncio
import threading
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.logic import context_manager
from bot.persistence_layer import persistence


class TestCrossThreadPersistenceScientific(unittest.TestCase):
    def test_dashboard_to_main_loop_persistence(self):
        """Valida que uma thread síncrona (Dashboard) consegue disparar um save no loop principal."""

        loop = asyncio.new_event_loop()
        context_manager.set_main_loop(loop)

        # Mock do PersistenceLayer
        # Nota: is_enabled é uma property, não podemos patchear diretamente com setattr se não tiver setter.
        # Vamos patchear a classe ou apenas o método save_channel_state.
        with patch.object(persistence, "save_channel_state", new_callable=AsyncMock) as mock_save:
            with patch.object(
                type(persistence), "is_enabled", new_callable=PropertyMock
            ) as mock_enabled:
                mock_enabled.return_value = True

                # Simula o loop principal rodando em uma thread
                def run_loop():
                    asyncio.set_event_loop(loop)
                    loop.run_forever()

                t = threading.Thread(target=run_loop, daemon=True)
                t.start()

                try:
                    # 1. Cria contexto (Simulando thread do Dashboard) - síncrono
                    ctx = context_manager.get("dash_ch")

                    # 2. Modifica dado (isso chama _touch() internamente)
                    ctx.update_content("game", "Chess")

                    # 3. Aguarda um momento para a task ser processada no loop principal
                    time.sleep(0.5)

                    # 4. Verifica se o mock_save foi chamado
                    self.assertTrue(
                        mock_save.called, "save_channel_state não foi chamado via cross-thread!"
                    )

                    print("\n[SCIENTIFIC] Cross-Thread Persistence: OK")

                finally:
                    loop.call_soon_threadsafe(loop.stop)
                    t.join(timeout=2)


from unittest.mock import PropertyMock

if __name__ == "__main__":
    unittest.main()
