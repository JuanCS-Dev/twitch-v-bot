import unittest
from unittest.mock import AsyncMock, patch

from bot.autonomy_logic import process_autonomy_goal
from bot.logic import context_manager


class TestAutonomyIsolationScientific(unittest.TestCase):
    @patch("bot.autonomy_logic.agent_inference", new_callable=AsyncMock)
    async def test_autonomy_uses_isolated_context(self, mock_inference):
        """Valida que a autonomia lê o contexto do canal correto."""
        mock_inference.return_value = "Resposta de Autonomia"

        # Setup Canal A
        ctx_a = context_manager.get("canal_a")
        ctx_a.update_content("game", "Elden Ring")

        # Setup Canal B
        ctx_b = context_manager.get("canal_b")
        ctx_b.update_content("game", "Minecraft")

        goal = {"id": "test-goal", "prompt": "fale algo", "risk": "auto_chat"}

        # Executa para Canal A
        await process_autonomy_goal(goal, dispatcher=AsyncMock(), channel_id="canal_a")
        # Verifica se o 4º argumento (ctx) era o do Canal A
        self.assertEqual(mock_inference.call_args[0][3].current_game, "Elden Ring")

        # Executa para Canal B
        await process_autonomy_goal(goal, dispatcher=AsyncMock(), channel_id="canal_b")
        self.assertEqual(mock_inference.call_args[0][3].current_game, "Minecraft")


if __name__ == "__main__":
    unittest.main()
