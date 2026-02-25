from bot.tests.scientific_shared import (
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_REPLY_LINES,
    QUALITY_SAFE_FALLBACK,
    ScientificTestCase,
    is_low_quality_answer,
    normalize_current_events_reply_contract,
)


class ScientificCurrentEventsNormalizerTestsMixin(ScientificTestCase):
    def test_current_events_normalizer_keeps_confidence_and_source_within_limit(self):
        prompt = "quais noticias desta semana sobre layoffs em empresas de tecnologia?"
        server_anchor = (
            "Timestamp de referencia do servidor (UTC): 2026-02-20T12:00:00Z. "
            "Use esse horario para interpretar hoje/agora/nesta semana."
        )
        long_answer = (
            "Nesta semana de fevereiro de 2026, o setor de tecnologia registra cortes "
            "focados em automacao por IA e eficiencia operacional. "
            "A Intel confirmou a reducao de 5% da forca de trabalho global para "
            "reestruturar divisoes. "
            "A Salesforce anunciou desligamentos em areas de suporte e vendas, e o "
            "mercado observa possiveis ajustes adicionais em big techs nos proximos dias."
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
            len([line for line in normalized.splitlines() if line.strip()]),
            MAX_REPLY_LINES,
        )
        self.assertFalse(low_quality, reason)

    def test_current_events_normalizer_converts_uncertain_hybrid_to_safe_fallback(self):
        prompt = "qual a situacao atual do macaco push no japao hoje?"
        server_anchor = (
            "Timestamp de referencia do servidor (UTC): 2026-02-20T12:00:00Z. "
            "Use esse horario para interpretar hoje/agora/nesta semana."
        )
        hybrid_answer = (
            "Nao consegui verificar com confianca agora.\n"
            "Hoje houve suposta atualizacao, mas sem confirmacao robusta."
        )

        normalized = normalize_current_events_reply_contract(
            prompt,
            hybrid_answer,
            server_time_instruction=server_anchor,
        )

        self.assertTrue(normalized.startswith(QUALITY_SAFE_FALLBACK))
        self.assertIn("Confianca: baixa", normalized)
        self.assertIn("Fonte: aguardando 1 link/fonte do chat para confirmar.", normalized)
        self.assertNotIn("suposta atualizacao", normalized.lower())

    def test_current_events_normalizer_clamps_confidence_and_source_contract(self):
        prompt = "qual a situacao atual do caso OpenAI vs publishers hoje?"
        answer = (
            "Hoje o caso segue em fase de instrucao e analise de provas.\n"
            "Confianca: alta\n"
            "Fonte: Reuters e Bloomberg."
        )

        normalized = normalize_current_events_reply_contract(prompt, answer)

        self.assertIn("Confianca: media", normalized)
        self.assertIn(
            "Fonte: pesquisa web em tempo real (DuckDuckGo).",
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
        self.assertIn("Fonte: DuckDuckGo query: macaquinho push japao hoje.", normalized)

    def test_current_events_normalizer_forces_safe_fallback_without_grounding_signal(self):
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
        self.assertIn("Fonte: aguardando 1 link/fonte do chat para confirmar.", normalized)
