import unittest
import asyncio
import time
import json
import re
from unittest.mock import MagicMock, patch, AsyncMock
from bot.byte_semantics import normalize_current_events_reply_contract
from bot.main import (
    HealthHandler,
    get_secret,
    AgentComponent,
    ByteBot,
    IrcByteBot,
    auto_update_scene_from_message,
    build_status_line,
    extract_movie_title,
    context,
    parse_byte_prompt,
    build_verifiable_prompt,
    build_llm_enhanced_prompt,
    build_direct_answer_instruction,
    extract_multi_reply_parts,
    build_intro_reply,
    handle_byte_prompt_text,
    build_quality_rewrite_prompt,
    is_intro_prompt,
    is_current_events_prompt,
    is_follow_up_prompt,
    is_low_quality_answer,
    is_serious_technical_prompt,
    MAX_CHAT_MESSAGE_LENGTH,
    MULTIPART_SEPARATOR,
    QUALITY_SAFE_FALLBACK,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
    TwitchTokenManager,
    build_irc_token_manager,
    resolve_irc_channel_logins,
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


class DummyIrcWriter:
    def __init__(self):
        self.lines: list[str] = []

    def write(self, payload: bytes):
        self.lines.append(payload.decode("utf-8"))

    async def drain(self):
        return None

    def close(self):
        return None

    async def wait_closed(self):
        return None


class TestBotProduction90Plus(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        context.current_game = "N/A"
        context.stream_vibe = "Conversa"
        context.last_event = "Bot Online"
        context.style_profile = (
            "Tom generalista, claro e natural em PT-BR, sem gíria gamer forçada."
        )
        for content_type in context.live_observability:
            context.live_observability[content_type] = ""
        context.recent_chat_entries = []
        context.last_byte_reply = ""

    def tearDown(self):
        self.loop.close()

    # ── Testes de Infraestrutura (main.py) ────────────────────

    def test_health_server_response(self):
        mock_handler = MagicMock()
        mock_handler.path = "/"
        mock_handler._send_text = MagicMock()

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_text.assert_called_with("AGENT_ONLINE", status_code=200)

    @patch("bot.main.observability.snapshot")
    def test_health_server_observability_endpoint(self, mock_snapshot):
        mock_snapshot.return_value = {"status": "ok"}
        mock_handler = MagicMock()
        mock_handler.path = "/api/observability"
        mock_handler._send_json = MagicMock()

        HealthHandler.do_GET(mock_handler)

        mock_snapshot.assert_called_once()
        mock_handler._send_json.assert_called_with({"status": "ok"}, status_code=200)

    def test_health_server_dashboard_route(self):
        mock_handler = MagicMock()
        mock_handler.path = "/dashboard"
        mock_handler._send_dashboard_asset = MagicMock(return_value=True)

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_dashboard_asset.assert_called_with(
            "index.html", "text/html; charset=utf-8"
        )

    def test_health_server_dashboard_channel_terminal_asset_route(self):
        mock_handler = MagicMock()
        mock_handler.path = "/dashboard/channel-terminal.js"
        mock_handler._send_dashboard_asset = MagicMock(return_value=True)

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_dashboard_asset.assert_called_with(
            "channel-terminal.js",
            "application/javascript; charset=utf-8",
        )

    def test_health_server_not_found_route(self):
        mock_handler = MagicMock()
        mock_handler.path = "/does-not-exist"
        mock_handler._send_text = MagicMock()

        HealthHandler.do_GET(mock_handler)

        mock_handler._send_text.assert_called_with("Not Found", status_code=404)

    def test_health_server_channel_control_post_requires_admin_token(self):
        mock_handler = MagicMock()
        mock_handler.path = "/api/channel-control"
        mock_handler.headers = {}
        mock_handler._send_json = MagicMock()

        with patch("bot.main.BYTE_DASHBOARD_ADMIN_TOKEN", "secret-token"):
            HealthHandler.do_POST(mock_handler)

        mock_handler._send_json.assert_called_with(
            {"ok": False, "error": "forbidden", "message": "Forbidden"},
            status_code=403,
        )

    @patch("bot.main.irc_channel_control.execute")
    def test_health_server_channel_control_post_executes_list_command(
        self, mock_execute
    ):
        mock_execute.return_value = {
            "ok": True,
            "action": "list",
            "channels": ["oisakura", "canal_b"],
            "message": "Connected channels: #oisakura, #canal_b.",
        }
        mock_handler = MagicMock()
        mock_handler.path = "/api/channel-control"
        mock_handler.headers = {"X-Byte-Admin-Token": "secret-token"}
        mock_handler._read_json_payload = MagicMock(return_value={"command": "list"})
        mock_handler._send_json = MagicMock()

        with patch("bot.main.BYTE_DASHBOARD_ADMIN_TOKEN", "secret-token"):
            HealthHandler.do_POST(mock_handler)

        mock_execute.assert_called_with(action="list", channel_login="")
        mock_handler._send_json.assert_called_with(
            mock_execute.return_value, status_code=200
        )

    @patch("google.cloud.secretmanager.SecretManagerServiceClient")
    def test_get_secret_coverage(self, mock_sm):
        """Cobre a função get_secret."""
        with patch("bot.main.PROJECT_ID", "test-proj"):
            mock_client = mock_sm.return_value
            mock_client.access_secret_version.return_value.payload.data.decode.return_value = "top-secret"
            res = get_secret()
            self.assertEqual(res, "top-secret")

    # ── Testes de Componentes (TwitchIO + Logic) ──────────────

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
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
        with patch("bot.main.OWNER_ID", "123"):
            ctx_v = MagicMock()
            ctx_v.message.author.id = "123"
            ctx_v.message.text = "!vibe Chill"
            ctx_v.reply = AsyncMock()
            self.loop.run_until_complete(comp.vibe.callback(comp, ctx_v))
            self.assertEqual(context.stream_vibe, "Chill")
            ctx_v.reply.assert_called()

            # Test !style
            ctx_style = MagicMock()
            ctx_style.message.author.id = "123"
            ctx_style.message.text = "!style Tom geral e analitico"
            ctx_style.reply = AsyncMock()
            self.loop.run_until_complete(comp.style.callback(comp, ctx_style))
            self.assertEqual(context.style_profile, "Tom geral e analitico")
            ctx_style.reply.assert_called()

            # Test !scene update
            ctx_scene = MagicMock()
            ctx_scene.message.author.id = "123"
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
        with (
            patch("bot.main.CLIENT_ID", "c"),
            patch("bot.main.BOT_ID", "b"),
            patch("bot.main.OWNER_ID", "o"),
        ):
            # Mockamos o super().__init__ (commands.Bot)
            with patch("twitchio.ext.commands.Bot.__init__", return_value=None):
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
        self.assertIn("Timestamp de referencia do servidor", enriched)
        self.assertIn("Me manda 1 link/fonte no chat", enriched)

        non_current = "ficha tecnica de Duna Parte 2"
        self.assertFalse(is_current_events_prompt(non_current))
        self.assertEqual(build_verifiable_prompt(non_current), non_current)

    @patch("bot.main.observability.snapshot")
    def test_status_line_exposes_aggregate_metrics_only(self, mock_snapshot):
        mock_snapshot.return_value = {
            "bot": {"uptime_minutes": 14},
            "metrics": {"p95_latency_ms": 420.5},
            "chatters": {"active_10m": 7},
            "chat_analytics": {"messages_10m": 38, "byte_triggers_10m": 9},
        }

        status_line = build_status_line(channel_logins=["oisakura", "canal_teste"])

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
        self.assertIn("[BYTE_SPLIT]", enriched)

    def test_non_technical_current_events_prompt_is_not_serious(self):
        prompt = "como esta a situacao atual do macaquinho push no japao?"
        self.assertFalse(is_serious_technical_prompt(prompt))

    def test_quality_detector_flags_generic_answer(self):
        prompt = "qual o diretor da revolucao dos bichos 2026?"
        generic_answer = "Depende, em geral pode variar conforme a adaptacao."
        low_quality, reason = is_low_quality_answer(prompt, generic_answer)
        self.assertTrue(low_quality)
        self.assertIn("generica", reason)

    def test_quality_detector_flags_current_events_without_verifiable_base(self):
        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        weak_answer = (
            "OpenAI lancou o Sora e o Google anunciou o Gemini 1.5 Pro. "
            "A NVIDIA apresentou novos chips e a Apple publicou pesquisa interna. "
            "Esses foram os maiores anuncios recentes."
        )
        low_quality, reason = is_low_quality_answer(prompt, weak_answer)
        self.assertTrue(low_quality)
        self.assertIn(
            reason,
            {
                "tema_atual_sem_ancora_temporal",
                "tema_atual_sem_base_verificavel",
                "tema_atual_sem_confianca_explicita",
            },
        )

    def test_quality_detector_flags_unstable_model_answer(self):
        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        weak_answer = "Conexao com o modelo instavel. Tente novamente em instantes."
        low_quality, reason = is_low_quality_answer(prompt, weak_answer)
        self.assertTrue(low_quality)
        self.assertEqual(reason, "modelo_indisponivel")

    def test_quality_detector_flags_existence_question_without_direct_position(self):
        prompt = "tem dark romance oficial com o Legolas do Senhor dos Aneis?"
        weak_answer = (
            "Oficialmente nas obras de Tolkien nao existe esse genero com o personagem."
        )
        low_quality, reason = is_low_quality_answer(prompt, weak_answer)
        self.assertTrue(low_quality)
        self.assertEqual(reason, "resposta_existencia_sem_posicao")

    def test_quality_detector_flags_open_question_ending(self):
        prompt = "qual o diretor da revolucao dos bichos 2026?"
        weak_answer = "Andy Serkis e o diretor ligado a adaptacao prevista para 2026. Quer mais detalhes?"
        low_quality, reason = is_low_quality_answer(prompt, weak_answer)
        self.assertTrue(low_quality)
        self.assertEqual(reason, "termina_com_pergunta_aberta")

    def test_quality_rewrite_prompt_contains_safe_fallback(self):
        rewrite_prompt = build_quality_rewrite_prompt(
            "qual a situacao atual do tema?",
            "Resposta vaga.",
            "resposta_generica",
        )
        self.assertIn("Rascunho anterior reprovado", rewrite_prompt)
        self.assertIn(QUALITY_SAFE_FALLBACK, rewrite_prompt)

    def test_quality_rewrite_prompt_reuses_provided_server_timestamp(self):
        server_anchor = (
            "Timestamp de referencia do servidor (UTC): 2026-02-20T12:00:00Z. "
            "Use esse horario para interpretar hoje/agora/nesta semana."
        )
        rewrite_prompt = build_quality_rewrite_prompt(
            "qual a situacao atual do tema?",
            "Resposta vaga.",
            "tema_atual_sem_ancora_temporal",
            server_time_instruction=server_anchor,
        )
        self.assertIn(server_anchor, rewrite_prompt)
        self.assertIn("Correcao alvo:", rewrite_prompt)

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
        enriched = build_llm_enhanced_prompt(
            prompt, server_time_instruction=server_anchor
        )
        markers = re.findall(
            r"Timestamp de referencia do servidor \(UTC\): ([0-9T:\-]+Z)\.", enriched
        )
        self.assertGreaterEqual(len(markers), 1)
        self.assertEqual(len(set(markers)), 1)

    def test_current_events_normalizer_keeps_confidence_and_source_within_limit(self):
        prompt = "quais noticias desta semana sobre layoffs em empresas de tecnologia?"
        server_anchor = (
            "Timestamp de referencia do servidor (UTC): 2026-02-20T12:00:00Z. "
            "Use esse horario para interpretar hoje/agora/nesta semana."
        )
        long_answer = (
            "Nesta semana de fevereiro de 2026, o setor de tecnologia registra cortes focados em "
            "automacao por IA e eficiencia operacional. "
            "A Intel confirmou a reducao de 5% da forca de trabalho global para reestruturar divisoes. "
            "A Salesforce anunciou desligamentos em areas de suporte e vendas, e o mercado observa "
            "possiveis ajustes adicionais em big techs nos proximos dias."
        )
        normalized = normalize_current_events_reply_contract(
            prompt,
            long_answer,
            server_time_instruction=server_anchor,
        )
        low_quality, reason = is_low_quality_answer(prompt, normalized)

        self.assertIn("Confianca:", normalized)
        self.assertIn("Fonte:", normalized)
        self.assertLessEqual(len(normalized), MAX_CHAT_MESSAGE_LENGTH)
        self.assertLessEqual(
            len([line for line in normalized.splitlines() if line.strip()]), 8
        )
        self.assertFalse(low_quality, reason)

    def test_current_events_normalizer_converts_uncertain_hybrid_to_safe_fallback(self):
        prompt = "qual a situacao atual do macaco push no japao hoje?"
        server_anchor = (
            "Timestamp de referencia do servidor (UTC): 2026-02-20T12:00:00Z. "
            "Use esse horario para interpretar hoje/agora/nesta semana."
        )
        hybrid_answer = (
            "Não consegui verificar com confianca agora.\n"
            "Hoje houve suposta atualizacao, mas sem confirmacao robusta."
        )

        normalized = normalize_current_events_reply_contract(
            prompt,
            hybrid_answer,
            server_time_instruction=server_anchor,
        )

        self.assertTrue(normalized.startswith(QUALITY_SAFE_FALLBACK))
        self.assertIn("Confianca: baixa", normalized)
        self.assertIn(
            "Fonte: aguardando 1 link/fonte do chat para confirmar.", normalized
        )
        self.assertNotIn("suposta atualizacao", normalized.lower())

    def test_current_events_normalizer_clamps_confidence_and_source_contract(self):
        prompt = "qual a situacao atual do caso OpenAI vs publishers hoje?"
        answer = (
            "Hoje o caso segue em fase de instrução e análise de provas.\n"
            "Confiança: alta\n"
            "Fonte: Reuters e Bloomberg."
        )

        normalized = normalize_current_events_reply_contract(prompt, answer)

        self.assertIn("Confianca: media", normalized)
        self.assertIn(
            "Fonte: pesquisa web em tempo real (Google Search via Vertex AI).",
            normalized,
        )
        self.assertNotIn("Confianca: alta", normalized)
        self.assertNotIn("Reuters e Bloomberg", normalized)

    def test_current_events_normalizer_uses_grounding_query_in_source_line(self):
        prompt = "qual a situacao atual do macaquinho push no japao hoje?"
        answer = "Hoje o caso segue em monitoramento pelas autoridades locais."
        grounding_metadata = {
            "enabled": True,
            "has_grounding_signal": True,
            "query_count": 1,
            "source_count": 0,
            "chunk_count": 0,
            "web_search_queries": ["macaquinho push japao hoje"],
            "source_urls": [],
        }
        normalized = normalize_current_events_reply_contract(
            prompt,
            answer,
            grounding_metadata=grounding_metadata,
        )

        self.assertIn("Confianca: media", normalized)
        self.assertIn(
            "Fonte: Google Search query: macaquinho push japao hoje.", normalized
        )

    def test_current_events_normalizer_forces_safe_fallback_without_grounding_signal(
        self,
    ):
        prompt = "qual a situacao atual do macaquinho push no japao hoje?"
        answer = "Hoje o caso segue em monitoramento pelas autoridades locais."
        grounding_metadata = {
            "enabled": True,
            "has_grounding_signal": False,
            "query_count": 0,
            "source_count": 0,
            "chunk_count": 0,
            "web_search_queries": [],
            "source_urls": [],
        }
        normalized = normalize_current_events_reply_contract(
            prompt,
            answer,
            grounding_metadata=grounding_metadata,
        )

        self.assertTrue(normalized.startswith(QUALITY_SAFE_FALLBACK))
        self.assertIn("Confianca: baixa", normalized)
        self.assertIn(
            "Fonte: aguardando 1 link/fonte do chat para confirmar.", normalized
        )

    def test_quality_detector_flags_high_risk_uncertainty_outside_canonical_fallback(
        self,
    ):
        prompt = "quais as noticias mais relevantes de IA hoje no mundo?"
        hybrid_answer = (
            "Não consegui verificar com confianca agora.\n"
            "A OpenAI anunciou hoje um recurso novo em rollout global.\n"
            "Confianca: media\n"
            "Fonte: pesquisa web em tempo real (Google Search via Vertex AI)."
        )

        low_quality, reason = is_low_quality_answer(prompt, hybrid_answer)
        self.assertTrue(low_quality)
        self.assertEqual(reason, "incerteza_fora_fallback_canonico")

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

        self.loop.run_until_complete(
            handle_byte_prompt_text("se apresente", "viewer", fake_reply)
        )
        self.assertTrue(replies)
        self.assertTrue(context.last_byte_reply)
        mock_inference.assert_not_called()

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_follow_up_prompt_passes_continuity_instruction_to_llm(
        self, mock_inference
    ):
        mock_inference.return_value = "Segue o contexto da conversa."
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(
            handle_byte_prompt_text("e agora?", "viewer", fake_reply)
        )

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
        self.loop.run_until_complete(
            handle_byte_prompt_text(prompt, "viewer", fake_reply)
        )

        self.assertEqual(len(replies), 2)
        self.assertTrue(all(len(reply) <= 460 for reply in replies))
        self.assertTrue(context.last_byte_reply.startswith("Parte 2"))

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_low_quality_answer_triggers_retry_and_uses_revised_text(
        self, mock_inference
    ):
        mock_inference.side_effect = [
            "Depende, em geral pode variar conforme o contexto.",
            "O diretor ligado a adaptacao de 2026 e Andy Serkis, com lancamento previsto pela Warner.",
        ]
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(
            handle_byte_prompt_text(
                "qual o diretor da revolucao dos bichos 2026?", "viewer", fake_reply
            )
        )

        self.assertEqual(mock_inference.await_count, 2)
        self.assertTrue(replies)
        self.assertIn("Andy Serkis", replies[0])

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_low_quality_answer_uses_safe_fallback_when_retry_fails(
        self, mock_inference
    ):
        mock_inference.side_effect = [
            "Depende, em geral pode variar conforme o contexto.",
            "Depende, em geral isso varia.",
        ]
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(
            handle_byte_prompt_text(
                "qual o diretor da revolucao dos bichos 2026?", "viewer", fake_reply
            )
        )

        self.assertEqual(mock_inference.await_count, 2)
        self.assertTrue(replies)
        self.assertEqual(replies[0], QUALITY_SAFE_FALLBACK)

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_current_events_delivery_keeps_confidence_and_source_labels(
        self, mock_inference
    ):
        mock_inference.return_value = (
            "Nesta semana de fevereiro de 2026, o setor de tecnologia registra cortes focados em "
            "automacao por IA e eficiencia operacional. A Intel confirmou reducao de 5% da forca de "
            "trabalho global para reestruturar divisoes e a Salesforce anunciou desligamentos em "
            "suporte e vendas, com mercado atento a novos ajustes."
        )
        replies = []

        async def fake_reply(text):
            replies.append(text)

        prompt = "quais noticias desta semana sobre layoffs em empresas de tecnologia?"
        self.loop.run_until_complete(
            handle_byte_prompt_text(prompt, "viewer", fake_reply)
        )
        self.assertTrue(replies)
        self.assertIn("Confianca:", replies[0])
        self.assertIn("Fonte:", replies[0])
        low_quality, reason = is_low_quality_answer(prompt, replies[0])
        self.assertFalse(low_quality, reason)

    @patch("bot.main.agent_inference", new_callable=AsyncMock)
    def test_current_events_unstable_model_forces_safe_fallback(self, mock_inference):
        mock_inference.side_effect = [
            "Conexao com o modelo instavel. Tente novamente em instantes.",
            "Conexao com o modelo instavel. Tente novamente em instantes.",
        ]
        replies = []

        async def fake_reply(text):
            replies.append(text)

        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        self.loop.run_until_complete(
            handle_byte_prompt_text(prompt, "viewer", fake_reply)
        )
        self.assertTrue(replies)
        self.assertIn(QUALITY_SAFE_FALLBACK, replies[0])
        self.assertIn("Confianca: baixa", replies[0])
        self.assertIn(
            "Fonte: aguardando 1 link/fonte do chat para confirmar.", replies[0]
        )

    def test_auto_scene_update_for_trusted_link(self):
        with (
            patch("bot.main.OWNER_ID", "123"),
            patch(
                "bot.main.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
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
        with patch("bot.main.OWNER_ID", "123"):
            msg = MagicMock()
            msg.text = "video nude https://youtube.com/watch?v=abc123"
            msg.author.id = "123"
            msg.author.is_mod = False
            msg.author.name = "owner"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertEqual(updates, [])
            self.assertEqual(context.live_observability["youtube"], "")

    def test_auto_scene_update_for_x_link(self):
        with (
            patch("bot.main.OWNER_ID", "123"),
            patch(
                "bot.main.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
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
        with (
            patch("bot.main.OWNER_ID", "123"),
            patch(
                "bot.main.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
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
        with (
            patch("bot.main.OWNER_ID", "123"),
            patch("bot.main.AUTO_SCENE_REQUIRE_METADATA", True),
            patch(
                "bot.main.resolve_scene_metadata", new_callable=AsyncMock
            ) as mock_metadata,
        ):
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
        with patch("bot.main.OWNER_ID", "123"):
            msg = MagicMock()
            msg.text = "Olha https://youtube.com/watch?v=abc123"
            msg.author.id = "999"
            msg.author.is_mod = False
            msg.author.is_moderator = False
            msg.author.name = "viewer"
            updates = self.loop.run_until_complete(auto_update_scene_from_message(msg))

            self.assertEqual(updates, [])
            self.assertEqual(context.live_observability["youtube"], "")

    @patch("bot.main.auto_update_scene_from_message", new_callable=AsyncMock)
    @patch("bot.main.handle_byte_prompt_text", new_callable=AsyncMock)
    def test_irc_replies_to_the_source_channel(
        self, mock_handle_prompt, mock_auto_scene
    ):
        mock_auto_scene.return_value = []

        async def fake_handle(prompt, author_name, reply_fn, status_line_factory=None):
            await reply_fn("ok no canal certo")

        mock_handle_prompt.side_effect = fake_handle
        bot = IrcByteBot(
            host="irc.chat.twitch.tv",
            port=6697,
            use_tls=True,
            bot_login="byte_agent",
            channel_logins=["canal_a", "canal_b"],
            user_token="token",
        )
        writer = DummyIrcWriter()
        bot.writer = writer

        line = "@display-name=Alice;user-id=33;mod=0 :alice!alice@alice PRIVMSG #canal_b :byte status"
        self.loop.run_until_complete(bot._handle_privmsg(line))

        payload = "".join(writer.lines)
        self.assertIn("PRIVMSG #canal_b :ok no canal certo\r\n", payload)
        self.assertNotIn("PRIVMSG #canal_a :ok no canal certo\r\n", payload)

    @patch("bot.main.auto_update_scene_from_message", new_callable=AsyncMock)
    def test_irc_owner_can_manage_channels_without_redeploy(self, mock_auto_scene):
        mock_auto_scene.return_value = []
        with patch("bot.main.OWNER_ID", "42"):
            bot = IrcByteBot(
                host="irc.chat.twitch.tv",
                port=6697,
                use_tls=True,
                bot_login="byte_agent",
                channel_logins=["canal_a"],
                user_token="token",
            )
            writer = DummyIrcWriter()
            bot.writer = writer

            non_owner_join = "@display-name=User;user-id=99;mod=0 :user!user@user PRIVMSG #canal_a :byte join canal_b"
            self.loop.run_until_complete(bot._handle_privmsg(non_owner_join))
            self.assertNotIn("canal_b", bot.channel_logins)

            owner_join = "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan PRIVMSG #canal_a :byte join canal_b"
            self.loop.run_until_complete(bot._handle_privmsg(owner_join))
            self.assertIn("canal_b", bot.channel_logins)

            owner_list = "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan PRIVMSG #canal_a :byte canais"
            self.loop.run_until_complete(bot._handle_privmsg(owner_list))

            owner_part = "@display-name=Juan;user-id=42;mod=0 :juan!juan@juan PRIVMSG #canal_a :byte part canal_b"
            self.loop.run_until_complete(bot._handle_privmsg(owner_part))
            self.assertEqual(bot.channel_logins, ["canal_a"])

            payload = "".join(writer.lines)
            self.assertIn("Somente o owner pode gerenciar canais do Byte.", payload)
            self.assertIn("JOIN #canal_b\r\n", payload)
            self.assertIn("Canais ativos: #canal_a, #canal_b.", payload)
            self.assertIn("PART #canal_b\r\n", payload)

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
        self.assertTrue(
            manager.expires_at_monotonic
            and manager.expires_at_monotonic > time.monotonic()
        )

    def test_irc_auth_failure_detector(self):
        self.assertTrue(
            is_irc_auth_failure_line(
                ":tmi.twitch.tv NOTICE * :Login authentication failed"
            )
        )
        self.assertTrue(
            is_irc_auth_failure_line(
                ":tmi.twitch.tv NOTICE * :Improperly formatted auth"
            )
        )
        self.assertFalse(
            is_irc_auth_failure_line(":tmi.twitch.tv 001 byte_agent :Welcome, GLHF!")
        )

    def test_resolve_irc_channel_logins_prefers_multi_channel_env(self):
        with (
            patch("bot.main.TWITCH_CHANNEL_LOGINS_RAW", "canal_a,canal_b"),
            patch("bot.main.TWITCH_CHANNEL_LOGIN", "canal_c"),
        ):
            channels = resolve_irc_channel_logins()
        self.assertEqual(channels, ["canal_a", "canal_b"])

    @patch("bot.main.get_secret")
    def test_build_irc_token_manager_with_secret_manager(self, mock_get_secret):
        mock_get_secret.return_value = "secret_from_sm"
        with (
            patch("bot.main.TWITCH_USER_TOKEN", "access_token"),
            patch("bot.main.TWITCH_REFRESH_TOKEN", "refresh_token"),
            patch("bot.main.CLIENT_ID", "client_id"),
            patch("bot.main.TWITCH_CLIENT_SECRET_INLINE", ""),
            patch("bot.main.PROJECT_ID", "proj"),
            patch("bot.main.TWITCH_CLIENT_SECRET_NAME", "twitch-client-secret"),
            patch("bot.main.TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", 300),
        ):
            manager = build_irc_token_manager()

        self.assertTrue(manager.can_refresh)
        self.assertEqual(manager.client_secret, "secret_from_sm")
        self.assertEqual(manager.client_id, "client_id")

    @patch("bot.main.get_secret")
    def test_build_irc_token_manager_raises_without_client_secret(
        self, mock_get_secret
    ):
        mock_get_secret.return_value = ""
        with (
            patch("bot.main.TWITCH_USER_TOKEN", "access_token"),
            patch("bot.main.TWITCH_REFRESH_TOKEN", "refresh_token"),
            patch("bot.main.CLIENT_ID", "client_id"),
            patch("bot.main.TWITCH_CLIENT_SECRET_INLINE", ""),
            patch("bot.main.PROJECT_ID", ""),
        ):
            with self.assertRaises(RuntimeError):
                build_irc_token_manager()


if __name__ == "__main__":
    unittest.main()
