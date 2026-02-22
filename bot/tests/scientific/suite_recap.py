from unittest.mock import AsyncMock, patch

from bot.tests.scientific_shared import ScientificTestCase


class ScientificRecapTestsMixin:
    """Testes cientificos para RecapEngine (Fase 9)."""

    def test_recap_pattern_o_que_ta_rolando(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertTrue(is_recap_prompt("o que ta rolando?"))
        self.assertTrue(is_recap_prompt("O que está rolando na live?"))

    def test_recap_pattern_cheguei_agora(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertTrue(is_recap_prompt("cheguei agora"))
        self.assertTrue(is_recap_prompt("Cheguei agora, o que eu perdi?"))

    def test_recap_pattern_resumo(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertTrue(is_recap_prompt("resumo"))
        self.assertTrue(is_recap_prompt("me da um resume rapido"))

    def test_recap_pattern_english(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertTrue(is_recap_prompt("what's happening?"))
        self.assertTrue(is_recap_prompt("what did i miss"))

    def test_recap_pattern_me_conta(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertTrue(is_recap_prompt("me conta o que aconteceu"))

    def test_recap_pattern_poe_a_par(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertTrue(is_recap_prompt("poe me a par"))

    def test_recap_pattern_false_positives(self: ScientificTestCase) -> None:
        from bot.recap_engine import is_recap_prompt

        self.assertFalse(is_recap_prompt("boa noite chat"))
        self.assertFalse(is_recap_prompt("joga esse mapa ai"))
        self.assertFalse(is_recap_prompt("!help"))
        self.assertFalse(is_recap_prompt(""))

    @patch("bot.recap_engine.agent_inference")
    def test_recap_generate_success(self: ScientificTestCase, mock_inference: AsyncMock) -> None:
        from bot.recap_engine import generate_recap

        mock_inference.return_value = "O streamer esta jogando Valorant, chat animado com jogadas do ace."
        result = self.loop.run_until_complete(generate_recap())
        self.assertIn("Valorant", result)
        mock_inference.assert_called_once()

    @patch("bot.recap_engine.agent_inference")
    def test_recap_generate_empty_returns_fallback(self: ScientificTestCase, mock_inference: AsyncMock) -> None:
        from bot.recap_engine import generate_recap

        mock_inference.return_value = ""
        result = self.loop.run_until_complete(generate_recap())
        self.assertEqual(result, "Sem contexto suficiente pra recap agora.")

    @patch("bot.recap_engine.agent_inference")
    @patch("bot.recap_engine.observability")
    def test_recap_generate_error_handled(
        self: ScientificTestCase,
        mock_obs: object,
        mock_inference: AsyncMock,
    ) -> None:
        from bot.recap_engine import generate_recap

        mock_inference.side_effect = RuntimeError("LLM down")
        result = self.loop.run_until_complete(generate_recap())
        self.assertEqual(result, "Sem contexto suficiente pra recap agora.")

    @patch("bot.recap_engine.generate_recap")
    def test_recap_prompt_runtime_intercept(self: ScientificTestCase, mock_recap: AsyncMock) -> None:
        from bot.prompt_runtime import handle_byte_prompt_text

        mock_recap.return_value = "Recap: jogando Valorant, chat hyped."
        reply_fn = AsyncMock()
        self.loop.run_until_complete(
            handle_byte_prompt_text("o que ta rolando?", "viewer1", reply_fn)
        )
        reply_fn.assert_called_once()
        self.assertIn("Recap", reply_fn.call_args[0][0])
