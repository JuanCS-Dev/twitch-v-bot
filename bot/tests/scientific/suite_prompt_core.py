import re

from bot.tests.scientific_shared import (
    AgentComponent,
    AsyncMock,
    ByteBot,
    MagicMock,
    ScientificTestCase,
    build_direct_answer_instruction,
    build_llm_enhanced_prompt,
    build_status_line,
    build_verifiable_prompt,
    context_manager,
    extract_movie_title,
    is_current_events_prompt,
    is_follow_up_prompt,
    is_serious_technical_prompt,
    parse_byte_prompt,
    patch,
)


class ScientificPromptCoreTestsMixin(ScientificTestCase):
    @patch("bot.eventsub_runtime.agent_inference", new_callable=AsyncMock)
    def test_agent_component_commands(self, mock_inf):
        comp = AgentComponent(bot=MagicMock())

        ctx = MagicMock()
        ctx.message.text = "!ask test"
        ctx.message.author.name = "juan"
        ctx.channel.name = "default"
        ctx.reply = AsyncMock()
        mock_inf.return_value = "bot-ans"

        self.loop.run_until_complete(comp.ask.callback(comp, ctx))
        ctx.reply.assert_called_with("bot-ans")

        ctx_status = MagicMock()
        ctx_status.reply = AsyncMock()
        self.loop.run_until_complete(comp.status.callback(comp, ctx_status))
        ctx_status.reply.assert_called()

        with patch("bot.eventsub_runtime.OWNER_ID", "123"):
            ctx_vibe = MagicMock()
            ctx_vibe.message.author.id = "123"
            ctx_vibe.message.text = "!vibe Chill"
            ctx_vibe.channel.name = "default"
            ctx_vibe.reply = AsyncMock()
            self.loop.run_until_complete(comp.vibe.callback(comp, ctx_vibe))
            self.assertEqual(context_manager.get("default").stream_vibe, "Chill")
            ctx_vibe.reply.assert_called()

            ctx_style = MagicMock()
            ctx_style.message.author.id = "123"
            ctx_style.message.text = "!style Tom geral e analitico"
            ctx_style.channel.name = "default"
            ctx_style.reply = AsyncMock()
            self.loop.run_until_complete(comp.style.callback(comp, ctx_style))
            self.assertEqual(context_manager.get("default").style_profile, "Tom geral e analitico")
            ctx_style.reply.assert_called()

            ctx_scene = MagicMock()
            ctx_scene.message.author.id = "123"
            ctx_scene.message.text = "!scene movie Interestelar"
            ctx_scene.channel.name = "default"
            ctx_scene.reply = AsyncMock()
            self.loop.run_until_complete(comp.scene.callback(comp, ctx_scene))
            self.assertEqual(
                context_manager.get("default").live_observability["movie"], "Interestelar"
            )
            ctx_scene.reply.assert_called()

    def test_producer_bot_event_logic(self):
        bot_inst = MagicMock(spec=ByteBot)
        bot_inst.handle_commands = AsyncMock()
        bot_inst.handle_byte_prompt = AsyncMock()

        msg = MagicMock()
        msg.echo = False
        msg.text = "byte ajuda"
        msg.author.name = "juan"
        msg.author.id = "999"
        msg.channel.name = "default"
        msg.reply = AsyncMock()

        self.loop.run_until_complete(ByteBot.event_message(bot_inst, msg))
        bot_inst.handle_byte_prompt.assert_called_with(msg, "ajuda")

        msg_cmd = MagicMock()
        msg_cmd.echo = False
        msg_cmd.text = "!ask oi"
        msg_cmd.channel.name = "default"
        self.loop.run_until_complete(ByteBot.event_message(bot_inst, msg_cmd))
        bot_inst.handle_commands.assert_called_with(msg_cmd)

    def test_bot_initialization(self):
        with (
            patch("bot.eventsub_runtime.CLIENT_ID", "c"),
            patch("bot.eventsub_runtime.BOT_ID", "b"),
            patch("bot.eventsub_runtime.OWNER_ID", "o"),
        ):
            with patch("twitchio.ext.commands.Bot.__init__", return_value=None):
                bot = ByteBot("secret")
                self.assertIsNotNone(bot)

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
        self.assertIn("Timestamp de referencia do servidor", enriched)
        self.assertIn("Me manda 1 link/fonte no chat", enriched)

        non_current = "ficha tecnica de Duna Parte 2"
        self.assertFalse(is_current_events_prompt(non_current))
        self.assertEqual(build_verifiable_prompt(non_current), non_current)

    @patch("bot.status_runtime.observability.snapshot")
    @patch("bot.status_runtime.context_manager")
    def test_status_line_exposes_aggregate_metrics_only(self, mock_cm, mock_snapshot):
        mock_snapshot.return_value = {
            "bot": {"uptime_minutes": 14},
            "metrics": {"p95_latency_ms": 420.5},
            "chatters": {"active_10m": 7},
            "chat_analytics": {"messages_10m": 38, "byte_triggers_10m": 9},
        }

        import asyncio

        status_line = asyncio.get_event_loop().run_until_complete(
            build_status_line(channel_logins=["oisakura", "canal_teste"])
        )

        self.assertIn("Canais: oisakura, canal_teste", status_line)
        self.assertIn("Chat 10m: 38 msgs/7 ativos", status_line)
        self.assertIn("Triggers 10m: 9", status_line)
        self.assertIn("Privacidade: metricas agregadas", status_line)

    def test_current_events_detection_for_news_prompt(self):
        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        self.assertTrue(is_current_events_prompt(prompt))

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
        self.assertIn("uma unica mensagem", enriched.lower())
        self.assertNotIn("[BYTE_SPLIT]", enriched)

    def test_non_technical_current_events_prompt_is_not_serious(self):
        prompt = "como esta a situacao atual do macaquinho push no japao?"
        self.assertFalse(is_serious_technical_prompt(prompt))

    def test_serious_prompt_without_current_events_keeps_reliability_instruction(self):
        prompt = "qual o impacto clinico da laminina na paraplegia?"
        self.assertTrue(is_serious_technical_prompt(prompt))

        enriched = build_llm_enhanced_prompt(prompt)
        self.assertIn("Instrucoes obrigatorias de confiabilidade", enriched)
        self.assertIn("Contrato anti-generico", enriched)

    def test_current_events_prompt_uses_single_timestamp_reference(self):
        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        server_anchor = (
            "Timestamp de referencia do servidor (UTC): 2026-02-20T12:00:00Z. "
            "Use esse horario para interpretar hoje/agora/nesta semana."
        )
        enriched = build_llm_enhanced_prompt(prompt, server_time_instruction=server_anchor)
        markers = re.findall(
            r"Timestamp de referencia do servidor \(UTC\): ([0-9T:\-]+Z)\.", enriched
        )
        self.assertGreaterEqual(len(markers), 1)
        self.assertEqual(len(set(markers)), 1)
