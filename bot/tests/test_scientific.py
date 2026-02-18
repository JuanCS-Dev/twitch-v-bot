import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import bot.main
from bot.main import (
    HealthHandler,
    get_secret,
    AgentComponent,
    ProducerBot,
    auto_update_scene_from_message,
    context,
)

class TestBotProduction90Plus(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        context.current_game = "N/A"
        context.stream_vibe = "Conversa"
        context.last_event = "Bot Online"
        context.style_profile = "Tom generalista, claro e natural em PT-BR, sem gíria gamer forçada."
        for content_type in context.live_observability:
            context.live_observability[content_type] = ""

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
        """Cobre os comandos !ask, !vibe, !style, !scene e !status em AgentComponent."""
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

            # Test !style
            ctx_style = MagicMock()
            ctx_style.message.author.id = '123'
            ctx_style.message.text = "!style Tom geral e analitico"
            ctx_style.reply = AsyncMock()
            self.loop.run_until_complete(comp.style.callback(comp, ctx_style))
            self.assertEqual(context.style_profile, "Tom geral e analitico")
            ctx_style.reply.assert_called()

            # Test !scene update
            ctx_scene = MagicMock()
            ctx_scene.message.author.id = '123'
            ctx_scene.message.text = "!scene movie Interestelar"
            ctx_scene.reply = AsyncMock()
            self.loop.run_until_complete(comp.scene.callback(comp, ctx_scene))
            self.assertEqual(context.live_observability["movie"], "Interestelar")
            ctx_scene.reply.assert_called()

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
        msg.author.id = "999"
        msg.author.is_subscriber = True
        msg.reply = AsyncMock()
        mock_inf.return_value = "dia!"
        
        self.loop.run_until_complete(ProducerBot.event_message(bot_inst, msg))
        msg.reply.assert_called_with("dia!")

        # Comando normal
        msg_cmd = MagicMock()
        msg_cmd.echo = False
        msg_cmd.text = "!ask oi"
        msg_cmd.author.id = "999"
        msg_cmd.author.is_subscriber = True
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

    def test_auto_scene_update_for_trusted_link(self):
        with patch('bot.main.OWNER_ID', '123'), \
             patch('bot.main.resolve_scene_metadata', new_callable=AsyncMock) as mock_metadata:
            mock_metadata.return_value = {"title": "Review sem spoiler"}
            msg = MagicMock()
            msg.text = "Olha esse video https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertIn("youtube", updates)
            self.assertEqual(
                context.live_observability["youtube"],
                'Video do YouTube: "Review sem spoiler" (compartilhado por owner)',
            )

    def test_auto_scene_blocks_sensitive_content(self):
        with patch('bot.main.OWNER_ID', '123'):
            msg = MagicMock()
            msg.text = "video nude https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertEqual(updates, [])
            self.assertEqual(context.live_observability["youtube"], "")

    def test_auto_scene_update_for_x_link(self):
        with patch('bot.main.OWNER_ID', '123'), \
             patch('bot.main.resolve_scene_metadata', new_callable=AsyncMock) as mock_metadata:
            mock_metadata.return_value = {"author_name": "CinemaCentral"}
            msg = MagicMock()
            msg.text = "Olha esse post https://x.com/user/status/12345"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertIn("x", updates)
            self.assertEqual(
                context.live_observability["x"],
                "Post do X de CinemaCentral (compartilhado por owner)",
            )

    def test_auto_scene_blocks_sensitive_metadata(self):
        with patch('bot.main.OWNER_ID', '123'), \
             patch('bot.main.resolve_scene_metadata', new_callable=AsyncMock) as mock_metadata:
            mock_metadata.return_value = {"title": "analise nsfw de trailer"}
            msg = MagicMock()
            msg.text = "Olha esse video https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertEqual(updates, [])
            self.assertEqual(context.live_observability["youtube"], "")

    def test_auto_scene_requires_metadata(self):
        with patch('bot.main.OWNER_ID', '123'), \
             patch('bot.main.AUTO_SCENE_REQUIRE_METADATA', True), \
             patch('bot.main.resolve_scene_metadata', new_callable=AsyncMock) as mock_metadata:
            mock_metadata.return_value = None
            msg = MagicMock()
            msg.text = "Olha esse video https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertEqual(updates, [])
            self.assertEqual(context.live_observability["youtube"], "")

    def test_auto_scene_ignores_untrusted_user(self):
        with patch('bot.main.OWNER_ID', '123'):
            msg = MagicMock()
            msg.text = "Olha https://youtube.com/watch?v=abc123"
            msg.author.id = "999"
            msg.author.is_mod = False
            msg.author.is_moderator = False
            msg.author.name = "viewer"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertEqual(updates, [])
            self.assertEqual(context.live_observability["youtube"], "")

if __name__ == '__main__':
    unittest.main()
