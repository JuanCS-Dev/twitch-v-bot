import unittest
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from bot.logic import (
    EMPTY_RESPONSE_FALLBACK,
    MAX_REPLY_LINES,
    StreamContext,
    agent_inference,
    build_dynamic_prompt,
    enforce_reply_limits,
    extract_grounding_metadata,
    extract_response_text,
    has_grounding_signal,
    is_rate_limited_inference_error,
)


def _make_openai_response(text: str | None = None, usage: tuple[int, int] | None = None) -> MagicMock:
    """Build a mock OpenAI-style chat completion response."""
    resp = MagicMock()
    if text is not None:
        choice = MagicMock()
        choice.message.content = text
        resp.choices = [choice]
    else:
        resp.choices = []

    if usage:
        resp.usage.prompt_tokens = usage[0]
        resp.usage.completion_tokens = usage[1]
    else:
        resp.usage = None
    return resp


class TestBotLogic(unittest.TestCase):

    def test_uptime_calculation(self):
        ctx = StreamContext()
        ctx.start_time = time.time() - 120
        self.assertEqual(ctx.get_uptime_minutes(), 2)

    def test_build_prompt(self):
        ctx = StreamContext()
        ctx.update_content("game", "Zelda")
        ctx.update_content("movie", "Duna")
        ctx.remember_user_message("ViewerA", "Que filme e esse?")
        ctx.remember_bot_reply("Parece Duna Parte 2.")
        p = build_dynamic_prompt("Oi", "Juan", ctx)
        self.assertIn("Jogo: Zelda", p)
        self.assertIn("Filme: Duna", p)
        self.assertIn("Historico recente:", p)
        self.assertIn("ViewerA: Que filme e esse?", p)
        self.assertIn("Ultima resposta do Byte:", p)
        self.assertIn("Relogio servidor UTC:", p)
        self.assertIn("Usuario Juan: Oi", p)

    def test_recent_chat_memory_is_bounded(self):
        ctx = StreamContext()
        for index in range(20):
            ctx.remember_user_message("viewer", f"mensagem {index}")
        formatted = ctx.format_recent_chat(limit=20)
        self.assertIn("mensagem 19", formatted)
        self.assertNotIn("viewer: mensagem 0", formatted)
        self.assertLessEqual(len(ctx.recent_chat_entries), 12)

    def test_update_and_clear_content(self):
        ctx = StreamContext()
        self.assertTrue(ctx.update_content("youtube", "Canal Kurzgesagt"))
        self.assertIn("youtube", ctx.live_observability)
        self.assertEqual(ctx.live_observability["youtube"], "Canal Kurzgesagt")
        self.assertTrue(ctx.clear_content("youtube"))
        self.assertEqual(ctx.live_observability["youtube"], "")
        self.assertFalse(ctx.update_content("invalid", "X"))

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch('asyncio.to_thread')
    def test_agent_inference_success(self, mock_thread, mock_search):
        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = []

        mock_resp = _make_openai_response("Olá!")
        mock_thread.return_value = mock_resp

        res = asyncio.run(agent_inference("Oi", "Juan", client, context))
        self.assertEqual(res, "Olá!")

    def test_extract_response_text_from_parts(self):
        response = SimpleNamespace(
            text=None,
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(parts=[SimpleNamespace(text="Resposta vinda de parts")]),
                )
            ],
        )
        self.assertEqual(extract_response_text(response), "Resposta vinda de parts")

    def test_extract_grounding_metadata_from_candidate(self):
        response = SimpleNamespace(
            text="ok",
            candidates=[
                SimpleNamespace(
                    grounding_metadata=SimpleNamespace(
                        web_search_queries=["macaquinho push no japao hoje"],
                        grounding_chunks=[
                            SimpleNamespace(web=SimpleNamespace(uri="https://example.com/noticia"))
                        ],
                    ),
                    citation_metadata=None,
                )
            ],
        )

        metadata = extract_grounding_metadata(response, use_grounding=True)
        self.assertTrue(metadata["enabled"])
        self.assertTrue(metadata["has_grounding_signal"])
        self.assertEqual(metadata["query_count"], 1)
        self.assertEqual(metadata["source_count"], 1)
        self.assertGreaterEqual(metadata["chunk_count"], 1)
        self.assertTrue(has_grounding_signal(metadata))

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch("asyncio.to_thread")
    def test_agent_inference_with_metadata(self, mock_thread, mock_search):
        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = []

        mock_resp = _make_openai_response("Resposta com grounding")
        mock_thread.return_value = mock_resp

        answer, metadata = asyncio.run(
            agent_inference("Oi", "Juan", client, context, return_metadata=True)
        )
        self.assertEqual(answer, "Resposta com grounding")
        self.assertFalse(metadata["enabled"])  # grounding not requested

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch('asyncio.to_thread')
    def test_agent_inference_failure(self, mock_thread, mock_search):
        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = []

        mock_thread.side_effect = Exception("Error")

        res = asyncio.run(agent_inference("Oi", "Juan", client, context))
        self.assertIn("Conexao com o modelo instavel", res)

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch('asyncio.to_thread')
    def test_agent_inference_empty_choices(self, mock_thread, mock_search):
        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = []

        mock_resp = _make_openai_response(text=None)  # no choices
        mock_thread.return_value = mock_resp

        res = asyncio.run(agent_inference("Oi", "Juan", client, context))
        self.assertEqual(res, EMPTY_RESPONSE_FALLBACK)

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("asyncio.to_thread")
    def test_agent_inference_retries_on_429_then_succeeds(self, mock_thread, mock_sleep, mock_search):
        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = []

        recovered_response = _make_openai_response("Resposta apos retry 429")
        mock_thread.side_effect = [Exception("429 RESOURCE_EXHAUSTED"), recovered_response]

        async def fake_sleep(_):
            return None

        mock_sleep.side_effect = fake_sleep

        res = asyncio.run(agent_inference("Oi", "Juan", client, context))
        self.assertEqual(res, "Resposta apos retry 429")
        self.assertEqual(mock_thread.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch("asyncio.to_thread")
    def test_agent_inference_timeout_returns_unstable_fallback(self, mock_thread, mock_search):
        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = []

        mock_thread.side_effect = TimeoutError("timed out")

        res = asyncio.run(agent_inference("Oi", "Juan", client, context, enable_grounding=False))
        self.assertIn("Conexao com o modelo instavel", res)

    def test_enforce_reply_limits(self):
        raw = "\n".join(f"Linha {n}" for n in range(1, 15))
        limited = enforce_reply_limits(raw)
        self.assertEqual(len(limited.splitlines()), MAX_REPLY_LINES)

    def test_enforce_reply_limits_preserves_word_boundary(self):
        raw = " ".join(["palavra"] * 200)
        limited = enforce_reply_limits(raw, max_lines=MAX_REPLY_LINES, max_length=80)
        self.assertLessEqual(len(limited), 80)
        self.assertIn(limited[-1], ".!?")
        self.assertFalse(limited.endswith("..."))
        self.assertNotIn(" ..", limited)

    def test_enforce_reply_limits_chat_contract(self):
        raw = "\n".join(
            [
                "A laminina e uma proteina estrutural importante na matriz extracelular.",
                "Ela atua na adesao celular e na organizacao da lamina basal.",
                "Contribui para migracao e diferenciacao celular em varios tecidos.",
                "Tambem participa de sinalizacao celular em processos de reparo.",
                "Alteracoes de laminina podem impactar integridade de tecidos.",
                "Sua estrutura molecular e alvo de estudo em biologia celular.",
                "Tem relevancia em pesquisa de doencas neuromusculares.",
                "Pode ser citada como ponte entre celulas e matriz extracelular.",
                "Esta nona linha precisa ser cortada pelo limite de 4 linhas.",
            ]
        )
        limited = enforce_reply_limits(raw)
        self.assertLessEqual(len(limited), 460)
        self.assertLessEqual(len(limited.splitlines()), MAX_REPLY_LINES)

    def test_agent_inference_empty(self):
        res = asyncio.run(agent_inference("", "Juan", None, None))
        self.assertEqual(res, "")

    def test_rate_limit_error_detector(self):
        self.assertTrue(is_rate_limited_inference_error(Exception("429 RESOURCE_EXHAUSTED")))
        self.assertTrue(is_rate_limited_inference_error(Exception("rate limit exceeded")))
        self.assertFalse(is_rate_limited_inference_error(Exception("invalid prompt")))

    @patch("bot.logic_inference.search_web", new_callable=AsyncMock)
    @patch("asyncio.to_thread")
    def test_agent_inference_with_grounding_calls_search(self, mock_thread, mock_search):
        """When enable_grounding=True, DDG search is called and results are in metadata."""
        from bot.web_search import WebSearchResult

        client = MagicMock()
        context = StreamContext()
        mock_search.return_value = [
            WebSearchResult(title="News", snippet="Big event.", url="https://news.com/ok"),
        ]
        mock_resp = _make_openai_response("Resposta com busca web.")
        mock_thread.return_value = mock_resp

        answer, metadata = asyncio.run(
            agent_inference("o que aconteceu hoje?", "Juan", client, context,
                           enable_grounding=True, return_metadata=True)
        )
        self.assertEqual(answer, "Resposta com busca web.")
        self.assertTrue(metadata["enabled"])
        self.assertTrue(metadata["has_grounding_signal"])
        self.assertEqual(metadata["source_count"], 1)
        self.assertIn("https://news.com/ok", metadata["source_urls"])
        mock_search.assert_called_once()


if __name__ == '__main__':
    unittest.main()
