import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.logic import context_manager
from bot.persistence_layer import persistence


class TestLazyLoadDurabilityScientific(unittest.IsolatedAsyncioTestCase):
    async def test_lazy_load_restores_from_supabase(self):
        """Valida que o bot recupera sua 'consciência' do banco quando a RAM é limpa."""

        # 1. Setup: Habilitar persistência mockada
        with patch.dict(os.environ, {"SUPABASE_URL": "http://test", "SUPABASE_KEY": "test"}):
            with patch.object(persistence, "_enabled", True):
                with patch.object(persistence, "_client", MagicMock()):
                    # 2. Dados que 'já estariam' no banco
                    saved_state = {
                        "current_game": "Hades II",
                        "stream_vibe": "Hyped",
                        "last_reply": "Bom jogo a todos!",
                        "style_profile": "Tom gamer",
                        "observability": {"game": "Hades II"},
                    }
                    saved_history = ["user1: msg antiga", "user2: msg antiga 2"]

                    # 3. Mock das funções de carregamento
                    with patch.object(
                        persistence, "load_channel_state", new_callable=AsyncMock
                    ) as mock_load_state:
                        with patch.object(
                            persistence, "load_recent_history", new_callable=AsyncMock
                        ) as mock_load_hist:
                            mock_load_state.return_value = saved_state
                            mock_load_hist.return_value = saved_history

                            # 4. AÇÃO: Limpar RAM e chamar o GET
                            await context_manager.cleanup("ghost_ch")

                            # O get() deve dispara o Lazy Load
                            ctx = context_manager.get("ghost_ch")

                            # 5. Aguarda o lazy load completar (background task)
                            await asyncio.sleep(0.1)

                            # ASSERÇÃO: O bot 'lembrou' do estado?
                            self.assertEqual(ctx.current_game, "Hades II")
                            self.assertEqual(ctx.stream_vibe, "Hyped")
                            self.assertEqual(len(ctx.recent_chat_entries), 2)
                            self.assertIn("msg antiga", ctx.recent_chat_entries[0])
                            self.assertEqual(ctx.channel_id, "ghost_ch")

                            print("\n[SCIENTIFIC] Lazy Load Durability: OK")


if __name__ == "__main__":
    unittest.main()
