import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.irc_handlers import IrcLineHandlersMixin
from bot.logic import context_manager
from bot.sentiment_engine import sentiment_engine


class IntegratedPhase3Test(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Reset total do estado
        for ch in context_manager.list_active_channels():
            context_manager.cleanup(ch)
        if "canal_a" in sentiment_engine._channel_events:
            sentiment_engine._channel_events["canal_a"].clear()
        if "canal_b" in sentiment_engine._channel_events:
            sentiment_engine._channel_events["canal_b"].clear()

    @patch("bot.scene_runtime.resolve_scene_metadata", new_callable=AsyncMock)
    @patch("bot.irc_handlers.handle_byte_prompt_text", new_callable=AsyncMock)
    @patch("bot.irc_handlers.ENABLE_LIVE_CONTEXT_LEARNING", True)
    @patch("bot.scene_runtime.is_trusted_curator", return_value=True)
    async def test_integrated_scene_and_context_isolation(
        self, mock_curator, mock_handle_prompt, mock_resolve_meta
    ):
        """Valida que um link no Canal A não polui a observabilidade do Canal B."""

        class MockBot(IrcLineHandlersMixin):
            def __init__(self):
                self.bot_login = "bytebot"
                self.joined_channels = {"canal_a", "canal_b"}

            async def send_reply(self, text, channel_login=None):
                pass

            def build_status_line(self):
                return "status"

        bot = MockBot()

        # Simula metadados de um vídeo de Elden Ring
        mock_resolve_meta.return_value = {
            "title": "Elden Ring Boss Fight",
            "provider_name": "YouTube",
        }

        # 1. Canal A recebe um link de YouTube
        line_a = ":user_a!user_a@tmi.twitch.tv PRIVMSG #canal_a :olha esse video https://youtube.com/watch?v=123"
        await bot._handle_privmsg(line_a)

        # 2. Verifica se o Canal A atualizou a observabilidade
        ctx_a = context_manager.get("canal_a")
        self.assertIn("Elden Ring", ctx_a.format_observability())

        # 3. Verifica se o Canal B continua limpo
        ctx_b = context_manager.get("canal_b")
        self.assertEqual(ctx_b.format_observability(), "Sem conteudo registrado.")

        print("\n[SCIENTIFIC] Scene Update Isolation: OK")

    @patch("bot.autonomy_logic.agent_inference", new_callable=AsyncMock)
    async def test_autonomy_sentiment_trigger_isolation(self, mock_inference):
        """Valida que o tédio no Canal A não gera ações autônomas para o Canal B."""
        from bot.autonomy_runtime import autonomy_runtime

        # Canal A: Chat "morto" (Gera tédio)
        for _ in range(10):
            sentiment_engine.ingest_message("canal_a", "mensagem neutra")

        # Canal B: Chat Hyped
        sentiment_engine.ingest_message("canal_b", "PogChamp PogChamp PogChamp")

        # Simulamos o tick de autonomia configurado para o Canal B
        with patch(
            "bot.control_plane.control_plane.get_config",
            return_value={"twitch_channel_login": "canal_b"},
        ):
            # No Canal B, não deve triggerar anti-boredom porque ele está hyped
            self.assertFalse(sentiment_engine.should_trigger_anti_boredom("canal_b"))
            # No Canal A, deve triggerar
            self.assertTrue(sentiment_engine.should_trigger_anti_boredom("canal_a"))

            # O tick do Canal B NÃO deve conter o gatilho do Canal A
            result = await autonomy_runtime._run_tick(force=False, reason="test")

            # Verifica se nenhum goal de tédio foi processado para o Canal B
            goals = [p for p in result.get("processed", []) if "dynamic-anti-boredom" in str(p)]
            self.assertEqual(
                len(goals), 0, "Gatilho de tédio do Canal A vazou para o processamento do Canal B!"
            )

        print("[SCIENTIFIC] Autonomy Sentiment Isolation: OK")


if __name__ == "__main__":
    unittest.main()
