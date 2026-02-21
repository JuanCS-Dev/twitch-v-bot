from bot.tests.scientific_shared import (
    AsyncMock,
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_REPLY_LINES,
    QUALITY_SAFE_FALLBACK,
    ScientificTestCase,
    build_intro_reply,
    context,
    handle_byte_prompt_text,
    is_intro_prompt,
    is_low_quality_answer,
    patch,
)


class ScientificPromptRuntimeFlowTestsMixin(ScientificTestCase):
    def test_intro_prompt_detection_and_rotation(self):
        self.assertTrue(is_intro_prompt("se apresente"))
        self.assertTrue(is_intro_prompt("quem e voce?"))
        self.assertFalse(is_intro_prompt("status da live"))

        with patch("bot.prompt_runtime.intro_template_index", 0):
            first = build_intro_reply()
            second = build_intro_reply()
            self.assertNotEqual(first, second)

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
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

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_follow_up_prompt_passes_continuity_instruction_to_llm(self, mock_inference):
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
        self.assertFalse(mock_inference.await_args.kwargs["enable_grounding"])

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_non_current_prompt_uses_inference_without_grounding(self, mock_inference):
        mock_inference.return_value = "RAG consulta base externa; fine-tuning altera pesos do modelo base."
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(
            handle_byte_prompt_text("qual a diferenca entre RAG e fine-tuning?", "viewer", fake_reply)
        )

        self.assertTrue(replies)
        self.assertTrue(mock_inference.await_args.kwargs["return_metadata"])
        self.assertFalse(mock_inference.await_args.kwargs["enable_grounding"])

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_serious_prompt_forces_single_comment_with_no_split_token(self, mock_inference):
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

        self.assertEqual(len(replies), 1)
        self.assertLessEqual(len(replies[0]), MAX_CHAT_MESSAGE_LENGTH)
        self.assertLessEqual(
            len([line for line in replies[0].splitlines() if line.strip()]),
            MAX_REPLY_LINES,
        )
        self.assertNotIn("[BYTE_SPLIT]", replies[0])
        self.assertEqual(
            " ".join(context.last_byte_reply.split()),
            " ".join(replies[0].split()),
        )
        self.assertTrue(mock_inference.await_args.kwargs["enable_grounding"])

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_low_quality_answer_triggers_retry_and_uses_revised_text(self, mock_inference):
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

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_low_quality_answer_uses_safe_fallback_when_retry_fails(self, mock_inference):
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

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_current_events_delivery_keeps_confidence_and_source_labels(self, mock_inference):
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
        self.loop.run_until_complete(handle_byte_prompt_text(prompt, "viewer", fake_reply))
        self.assertTrue(replies)
        self.assertIn("Confianca:", replies[0])
        self.assertIn("Fonte:", replies[0])
        low_quality, reason = is_low_quality_answer(prompt, replies[0])
        self.assertFalse(low_quality, reason)

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_current_events_unstable_model_forces_safe_fallback(self, mock_inference):
        mock_inference.side_effect = [
            "Conexao com o modelo instavel. Tente novamente em instantes.",
            "Conexao com o modelo instavel. Tente novamente em instantes.",
        ]
        replies = []

        async def fake_reply(text):
            replies.append(text)

        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        self.loop.run_until_complete(handle_byte_prompt_text(prompt, "viewer", fake_reply))
        self.assertTrue(replies)
        self.assertIn(QUALITY_SAFE_FALLBACK, replies[0])
        self.assertIn("Confianca: baixa", replies[0])
        self.assertIn("Fonte: aguardando 1 link/fonte do chat para confirmar.", replies[0])

    @patch("bot.prompt_runtime.agent_inference", new_callable=AsyncMock)
    def test_high_risk_current_events_without_grounding_signal_uses_single_pass_fallback(
        self, mock_inference
    ):
        mock_inference.return_value = (
            "Nao consegui confirmar com seguranca as noticias no recorte pedido.",
            {
                "enabled": True,
                "has_grounding_signal": False,
                "query_count": 0,
                "source_count": 0,
                "chunk_count": 0,
                "web_search_queries": [],
                "source_urls": [],
            },
        )
        replies = []

        async def fake_reply(text):
            replies.append(text)

        self.loop.run_until_complete(
            handle_byte_prompt_text("quais as noticias mais relevantes de IA nesta semana?", "viewer", fake_reply)
        )

        self.assertTrue(replies)
        self.assertEqual(mock_inference.await_count, 1)
        self.assertIn(QUALITY_SAFE_FALLBACK, replies[0])
        self.assertIn("Confianca: baixa", replies[0])
        self.assertIn("Fonte: aguardando 1 link/fonte do chat para confirmar.", replies[0])
