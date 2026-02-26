import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.logic import agent_inference, build_dynamic_prompt, context_manager, enforce_reply_limits


class TestBotLogic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await context_manager.cleanup("default")

    def test_enforce_reply_limits(self):
        # Suite espera que se houver 5 linhas, a 5a seja removida.
        text = "L1\nL2\nL3\nL4\nL5"
        res = enforce_reply_limits(text, max_lines=4)
        self.assertNotIn("L5", res)
        self.assertEqual(len(res.split()), 4)

    def test_build_prompt(self):
        ctx = context_manager.get_sync("default")
        ctx.remember_user_message("user", "oi")
        prompt = build_dynamic_prompt("teste", "autor", ctx)
        self.assertIn("Historico recente:", prompt)
        self.assertIn("user: oi", prompt)

    @patch("bot.logic_inference._execute_inference_with_retry")
    async def test_agent_inference_success(self, mock_execute):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Resposta do bot"
        mock_execute.return_value = mock_response

        ctx = context_manager.get("test")
        mock_client = MagicMock()
        res = await agent_inference("pergunta", "user", mock_client, ctx)
        self.assertEqual(res, "Resposta do bot")


if __name__ == "__main__":
    unittest.main()
