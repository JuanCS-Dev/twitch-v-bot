import unittest
import asyncio
import time
import json
from unittest.mock import MagicMock, patch, AsyncMock
from bot.main import (
    HealthHandler,
    get_secret,
    AgentComponent,
    ByteBot,
    auto_update_scene_from_message,
    extract_movie_title,
    context,
    parse_byte_prompt,
    build_verifiable_prompt,
    build_llm_enhanced_prompt,
    build_direct_answer_instruction,
    extract_multi_reply_parts,
    build_intro_reply,
    handle_byte_prompt_text,
    is_intro_prompt,
    is_current_events_prompt,
    is_follow_up_prompt,
    is_serious_technical_prompt,
    MAX_CHAT_MESSAGE_LENGTH,
    MULTIPART_SEPARATOR,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
    TwitchTokenManager,
    build_irc_token_manager,
    is_irc_auth_failure_line,
)


class DummyHTTPResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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
        context.recent_chat_entries = []
        context.last_byte_reply = ""

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

    def test_producer_bot_event_logic(self):
        """Cobre event_message com trigger 'byte ...' e comandos com prefixo."""
        # Mock de instância mínima do Bot
        bot_inst = MagicMock(spec=ByteBot)
        bot_inst.handle_commands = AsyncMock()
        bot_inst.handle_byte_prompt = AsyncMock()
        
        # Trigger textual Byte
        msg = MagicMock()
        msg.echo = False
        msg.text = "byte ajuda"
        msg.author.name = "juan"
        msg.author.id = "999"
        msg.reply = AsyncMock()
        
        self.loop.run_until_complete(ByteBot.event_message(bot_inst, msg))
        bot_inst.handle_byte_prompt.assert_called_with(msg, "ajuda")

        # Comando normal
        msg_cmd = MagicMock()
        msg_cmd.echo = False
        msg_cmd.text = "!ask oi"
        self.loop.run_until_complete(ByteBot.event_message(bot_inst, msg_cmd))
        bot_inst.handle_commands.assert_called_with(msg_cmd)

    def test_bot_initialization(self):
        """Cobre o __init__ do ByteBot."""
        with patch('bot.main.CLIENT_ID', 'c'), \
             patch('bot.main.BOT_ID', 'b'), \
             patch('bot.main.OWNER_ID', 'o'):
            # Mockamos o super().__init__ (commands.Bot)
            with patch('twitchio.ext.commands.Bot.__init__', return_value=None):
                b = ByteBot("secret")
                self.assertIsNotNone(b)

    def test_parse_byte_prompt_and_movie_title(self):
        self.assertEqual(parse_byte_prompt("byte ajuda"), "ajuda")
        self.assertEqual(parse_byte_prompt("Byte: status"), "status")
        self.assertEqual(parse_byte_prompt("!byte ajuda"), "ajuda")
        self.assertEqual(parse_byte_prompt("@byte status"), "status")
        self.assertIsNone(parse_byte_prompt("!ask oi"))
        self.assertEqual(
            extract_movie_title('qual a ficha tecnica do filme "Duna Parte 2"?'),
            "Duna Parte 2",
        )
        self.assertEqual(
            extract_movie_title("qual a ficha tecnica do filme que estamos vendo?"),
            "",
        )

    def test_build_verifiable_prompt_for_current_events(self):
        prompt = "como esta a situacao atual do macaquinho Push no Japao?"
        self.assertTrue(is_current_events_prompt(prompt))
        enriched = build_verifiable_prompt(prompt)
        self.assertIn("Instrucoes obrigatorias de confiabilidade", enriched)
        self.assertIn("Me manda 1 link/fonte no chat", enriched)

        non_current = "ficha tecnica de Duna Parte 2"
        self.assertFalse(is_current_events_prompt(non_current))
        self.assertEqual(build_verifiable_prompt(non_current), non_current)

    def test_follow_up_and_adaptive_enrichment(self):
        self.assertTrue(is_follow_up_prompt("e agora?"))
        self.assertFalse(is_follow_up_prompt("ficha tecnica de Interestelar"))

        follow_up_prompt = build_llm_enhanced_prompt("e ele agora?")
        self.assertIn("Instrucoes de continuidade", follow_up_prompt)

        brief_prompt = build_llm_enhanced_prompt("resuma em 1 linha o tema da live")
        self.assertIn("Estilo de resposta: ultra objetivo", brief_prompt)

    def test_question_prompt_enforces_direct_answer_instruction(self):
        prompt = "existe algum dark romance com o legolas do senhor dos aneis?"
        direct_instruction = build_direct_answer_instruction(prompt)
        self.assertIn("Formato de resposta obrigatorio", direct_instruction)
        self.assertIn("Sim,' ou 'Nao,'", direct_instruction)

        enriched = build_llm_enhanced_prompt(prompt)
        self.assertIn("Evite texto generico", enriched)

    def test_serious_prompt_uses_research_enrichment(self):
        prompt = "como funciona a laminina no tratamento de paraplegia e qual a evidencia atual?"
        self.assertTrue(is_serious_technical_prompt(prompt))

        enriched = build_llm_enhanced_prompt(prompt)
        self.assertIn("Instrucoes de pesquisa aprofundada", enriched)
        self.assertIn("[BYTE_SPLIT]", enriched)

    def test_non_technical_current_events_prompt_is_not_serious(self):
        prompt = "como esta a situacao atual do macaquinho push no japao?"
        self.assertFalse(is_serious_technical_prompt(prompt))

    def test_serious_prompt_without_current_events_keeps_reliability_instruction(self):
        prompt = "qual o impacto clinico da laminina na paraplegia?"
        self.assertTrue(is_serious_technical_prompt(prompt))

        enriched = build_llm_enhanced_prompt(prompt)
        self.assertIn("Instrucoes obrigatorias de confiabilidade", enriched)

    def test_serious_limits_support_two_full_chat_comments(self):
        minimum_length = (MAX_CHAT_MESSAGE_LENGTH * 2) + len(MULTIPART_SEPARATOR) + 2
        self.assertGreaterEqual(SERIOUS_REPLY_MAX_LINES, 17)
        self.assertGreaterEqual(SERIOUS_REPLY_MAX_LENGTH, minimum_length)

    def test_extract_multi_reply_parts_with_separator(self):
        response = (
            "Parte 1: contexto cientifico resumido e verificavel.\n"
            "[BYTE_SPLIT]\n"
            "Parte 2: aplicacoes praticas e limites atuais."
        )
        parts = extract_multi_reply_parts(response, max_parts=2)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].startswith("Parte 1"))
        self.assertTrue(parts[1].startswith("Parte 2"))

    def test_intro_prompt_detection_and_rotation(self):
        self.assertTrue(is_intro_prompt("se apresente"))
        self.assertTrue(is_intro_prompt("quem e voce?"))
        self.assertFalse(is_intro_prompt("status da live"))

        with patch("bot.main.intro_template_index", 0):
            first = build_intro_reply()
            second = build_intro_reply()
            self.assertNotEqual(first, second)

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_intro_prompt_uses_template_without_llm(self, mock_inference):
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(handle_byte_prompt_text("se apresente", "viewer", fake_reply))
        self.assertTrue(replies)
        self.assertTrue(context.last_byte_reply)
        mock_inference.assert_not_called()

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_follow_up_prompt_passes_continuity_instruction_to_llm(self, mock_inference):
        mock_inference.return_value = "Segue o contexto da conversa."
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(handle_byte_prompt_text("e agora?", "viewer", fake_reply))

        self.assertTrue(replies)
        self.assertTrue(context.last_byte_reply)
        llm_prompt = mock_inference.await_args.args[0]
        self.assertIn("Instrucoes de continuidade", llm_prompt)

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_serious_prompt_can_reply_in_two_comments(self, mock_inference):
        mock_inference.return_value = (
            "Parte 1: revisao objetiva de mecanismo e evidencias atuais.\n"
            "[BYTE_SPLIT]\n"
            "Parte 2: impacto clinico, limites e proximo passo de validacao."
        )
        replies = []

        async def fake_reply(text):
            replies.append(text)

        prompt = "como funciona a laminina no tratamento de paraplegia e qual a evidencia atual?"
        self.loop.run_until_complete(handle_byte_prompt_text(prompt, "viewer", fake_reply))

        self.assertEqual(len(replies), 2)
        self.assertTrue(all(len(reply) <= 460 for reply in replies))
        self.assertTrue(context.last_byte_reply.startswith("Parte 2"))

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

    @patch("bot.main.urlopen")
    def test_token_manager_force_refresh_rotates_tokens(self, mock_urlopen):
        mock_urlopen.return_value = DummyHTTPResponse(
            {
                "access_token": "novo_access_token",
                "refresh_token": "novo_refresh_token",
                "expires_in": 3600,
            }
        )
        manager = TwitchTokenManager(
            access_token="old",
            refresh_token="old-refresh",
            client_id="cid",
            client_secret="secret",
        )

        new_access_token = self.loop.run_until_complete(manager.force_refresh("teste"))

        self.assertEqual(new_access_token, "novo_access_token")
        self.assertEqual(manager.access_token, "novo_access_token")
        self.assertEqual(manager.refresh_token, "novo_refresh_token")
        self.assertTrue(manager.expires_at_monotonic and manager.expires_at_monotonic > time.monotonic())

    def test_irc_auth_failure_detector(self):
        self.assertTrue(is_irc_auth_failure_line(":tmi.twitch.tv NOTICE * :Login authentication failed"))
        self.assertTrue(is_irc_auth_failure_line(":tmi.twitch.tv NOTICE * :Improperly formatted auth"))
        self.assertFalse(is_irc_auth_failure_line(":tmi.twitch.tv 001 byte_agent :Welcome, GLHF!"))

    @patch("bot.main.get_secret")
    def test_build_irc_token_manager_with_secret_manager(self, mock_get_secret):
        mock_get_secret.return_value = "secret_from_sm"
        with patch("bot.main.TWITCH_USER_TOKEN", "access_token"), \
             patch("bot.main.TWITCH_REFRESH_TOKEN", "refresh_token"), \
             patch("bot.main.CLIENT_ID", "client_id"), \
             patch("bot.main.TWITCH_CLIENT_SECRET_INLINE", ""), \
             patch("bot.main.PROJECT_ID", "proj"), \
             patch("bot.main.TWITCH_CLIENT_SECRET_NAME", "twitch-client-secret"), \
             patch("bot.main.TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", 300):
            manager = build_irc_token_manager()

        self.assertTrue(manager.can_refresh)
        self.assertEqual(manager.client_secret, "secret_from_sm")
        self.assertEqual(manager.client_id, "client_id")

    @patch("bot.main.get_secret")
    def test_build_irc_token_manager_raises_without_client_secret(self, mock_get_secret):
        mock_get_secret.return_value = ""
        with patch("bot.main.TWITCH_USER_TOKEN", "access_token"), \
             patch("bot.main.TWITCH_REFRESH_TOKEN", "refresh_token"), \
             patch("bot.main.CLIENT_ID", "client_id"), \
             patch("bot.main.TWITCH_CLIENT_SECRET_INLINE", ""), \
             patch("bot.main.PROJECT_ID", ""):
            with self.assertRaises(RuntimeError):
                build_irc_token_manager()

if __name__ == '__main__':
    unittest.main()
