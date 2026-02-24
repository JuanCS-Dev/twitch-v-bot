from bot.tests.scientific_shared import (
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_REPLY_LINES,
    QUALITY_SAFE_FALLBACK,
    SERIOUS_REPLY_MAX_LENGTH,
    SERIOUS_REPLY_MAX_LINES,
    ScientificTestCase,
    build_quality_rewrite_prompt,
    extract_multi_reply_parts,
    is_low_quality_answer,
)


class ScientificQualityDetectionTestsMixin(ScientificTestCase):
    def test_quality_detector_flags_generic_answer(self):
        prompt = "qual o diretor da revolucao dos bichos 2026?"
        generic_answer = "Depende, em geral pode variar conforme a adaptacao."
        low_quality, reason = is_low_quality_answer(prompt, generic_answer)
        self.assertTrue(low_quality)
        self.assertIn("generica", reason)

    def test_quality_detector_flags_current_events_without_verifiable_base(self):
        prompt = "quais as noticias mais relevantes de IA nesta semana?"
        weak_answer = (
            "OpenAI lancou o Sora e o Nebius anunciou o Llama 3.1 70B. "
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
        weak_answer = (
            "Andy Serkis e o diretor ligado a adaptacao prevista para 2026. "
            "Quer mais detalhes?"
        )
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

    def test_quality_detector_flags_high_risk_uncertainty_outside_canonical_fallback(self):
        prompt = "quais as noticias mais relevantes de IA hoje no mundo?"
        hybrid_answer = (
            "Nao consegui verificar com confianca agora.\n"
            "A OpenAI anunciou hoje um recurso novo em rollout global.\n"
            "Confianca: media\n"
            "Fonte: pesquisa web em tempo real (DuckDuckGo)."
        )

        low_quality, reason = is_low_quality_answer(prompt, hybrid_answer)
        self.assertTrue(low_quality)
        self.assertEqual(reason, "incerteza_fora_fallback_canonico")

    def test_serious_limits_follow_compact_line_contract(self):
        self.assertEqual(SERIOUS_REPLY_MAX_LINES, MAX_REPLY_LINES)
        self.assertEqual(SERIOUS_REPLY_MAX_LENGTH, MAX_CHAT_MESSAGE_LENGTH)

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
