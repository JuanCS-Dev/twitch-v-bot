import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import bot.main
from bot.main import HealthHandler, get_secret, AgentComponent, ProducerBot, context

class TestBotProduction90Plus(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    # ── Testes de Infraestrutura (main.py) ────────────────────
    
    def test_health_server_response(self):
        """Cobre a classe HealthHandler."""
        mock_handler = MagicMock()
        mock_handler.wfile = MagicMock()
        HealthHandler.do_GET(mock_handler)
        mock_handler.send_response.assert_called_with(200)
        mock_handler.end_headers.assert_called()

    @patch('google.cloud.secretmanager.SecretManagerServiceClient')
    def test_get_secret_coverage(self, mock_sm):
        """Cobre a função get_secret."""
        with patch('bot.main.PROJECT_ID', 'test-proj'):
            mock_client = mock_sm.return_value
            mock_client.access_secret_version.return_value.payload.data.decode.return_value = "top-secret"
            res = get_secret()
            self.assertEqual(res, "top-secret")

    # ── Testes de Componentes (TwitchIO + Logic) ──────────────

    @patch('bot.main.agent_inference', new_callable=AsyncMock)
    def test_agent_component_commands(self, mock_inf):
        """Cobre os comandos !ask, !vibe e !status em AgentComponent."""
        comp = AgentComponent(bot=MagicMock())
        
        # Test !ask
        ctx = MagicMock()
        ctx.message.text = "!ask test"
        ctx.message.author.name = "juan"
        ctx.reply = AsyncMock()
        mock_inf.return_value = "bot-ans"
        
        # Chamamos o callback original para bypassar o wrapper do TwitchIO que injeta o self
        self.loop.run_until_complete(comp.ask.callback(comp, ctx))
        ctx.reply.assert_called_with("bot-ans")

        # Test !status
        ctx_s = MagicMock()
        ctx_s.reply = AsyncMock()
        self.loop.run_until_complete(comp.status.callback(comp, ctx_s))
        ctx_s.reply.assert_called()

        # Test !vibe (Owner check)
        with patch('bot.main.OWNER_ID', '123'):
            ctx_v = MagicMock()
            ctx_v.message.author.id = '123'
            ctx_v.message.text = "!vibe Chill"
            ctx_v.reply = AsyncMock()
            self.loop.run_until_complete(comp.vibe.callback(comp, ctx_v))
            self.assertEqual(context.stream_vibe, "Chill")
            ctx_v.reply.assert_called()

    @patch('bot.main.agent_inference', new_callable=AsyncMock)
    def test_producer_bot_event_logic(self, mock_inf):
        """Cobre event_message e lógica proativa."""
        # Mock de instância mínima do Bot
        bot_inst = MagicMock(spec=ProducerBot)
        bot_inst.handle_commands = AsyncMock()
        
        # Proativo: Bom dia
        msg = MagicMock()
        msg.echo = False
        msg.text = "bom dia pessoal"
        msg.author.name = "juan"
        msg.reply = AsyncMock()
        mock_inf.return_value = "dia!"
        
        self.loop.run_until_complete(ProducerBot.event_message(bot_inst, msg))
        msg.reply.assert_called_with("dia!")

        # Comando normal
        msg_cmd = MagicMock()
        msg_cmd.echo = False
        msg_cmd.text = "!ask oi"
        self.loop.run_until_complete(ProducerBot.event_message(bot_inst, msg_cmd))
        bot_inst.handle_commands.assert_called_with(msg_cmd)

    def test_bot_initialization(self):
        """Cobre o __init__ do ProducerBot."""
        with patch('bot.main.CLIENT_ID', 'c'), \
             patch('bot.main.BOT_ID', 'b'), \
             patch('bot.main.OWNER_ID', 'o'):
            # Mockamos o super().__init__ (commands.Bot)
            with patch('twitchio.ext.commands.Bot.__init__', return_value=None):
                b = ProducerBot("secret")
                self.assertIsNotNone(b)

if __name__ == '__main__':
    unittest.main()
