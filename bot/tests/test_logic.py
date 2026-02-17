import unittest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
from bot.logic import StreamContext, build_dynamic_prompt, agent_inference

class TestBotLogic(unittest.TestCase):

    def test_uptime_calculation(self):
        ctx = StreamContext()
        ctx.start_time = time.time() - 120
        self.assertEqual(ctx.get_uptime_minutes(), 2)

    def test_build_prompt(self):
        ctx = StreamContext()
        ctx.current_game = "Zelda"
        p = build_dynamic_prompt("Oi", "Juan", ctx)
        self.assertIn("Jogo: Zelda", p)
        self.assertIn("Usuário Juan: Oi", p)

    @patch('asyncio.to_thread')
    def test_agent_inference_success(self, mock_thread):
        loop = asyncio.get_event_loop()
        client = MagicMock()
        context = StreamContext()
        
        mock_resp = MagicMock()
        mock_resp.text = "Olá!"
        mock_thread.return_value = mock_resp
        
        res = loop.run_until_complete(agent_inference("Oi", "Juan", client, context))
        self.assertEqual(res, "Olá!")

    @patch('asyncio.to_thread')
    def test_agent_inference_failure(self, mock_thread):
        loop = asyncio.get_event_loop()
        client = MagicMock()
        context = StreamContext()
        
        mock_thread.side_effect = Exception("Error")
        
        res = loop.run_until_complete(agent_inference("Oi", "Juan", client, context))
        self.assertIn("⚠️ Conexão neural instável", res)

    def test_agent_inference_empty(self):
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(agent_inference("", "Juan", None, None))
        self.assertEqual(res, "")

if __name__ == '__main__':
    unittest.main()
