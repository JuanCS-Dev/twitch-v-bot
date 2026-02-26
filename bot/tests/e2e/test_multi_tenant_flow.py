import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.irc_handlers import IrcLineHandlersMixin
from bot.logic import context_manager
from bot.sentiment_engine import sentiment_engine


class MockBot(IrcLineHandlersMixin):
    def __init__(self):
        self.bot_login = "bytebot"
        self.joined_channels = {"canal_a", "canal_b"}
        self.replies = {"canal_a": [], "canal_b": []}
        self.token_manager = AsyncMock()

    async def send_reply(self, text, channel_login=None):
        ch = channel_login or "canal_a"
        self.replies[ch].append(text)

    def build_status_line(self) -> str:
        from bot.status_runtime import build_status_line

        # Nota: no código real, build_status_line não recebe canal_id ainda
        # ele usa o context_manager.get() (default)
        # Isso é algo que podemos querer ajustar no futuro, mas para este teste
        # vamos focar no isolamento do StreamContext injetado no IRC Handler.
        return build_status_line()


class TestE2EMultiTenantFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for ch in context_manager.list_active_channels():
            context_manager.cleanup(ch)
        with sentiment_engine._lock:
            sentiment_engine._channel_events.clear()
            sentiment_engine._last_activity.clear()

    @patch("bot.irc_handlers.ENABLE_LIVE_CONTEXT_LEARNING", True)
    @patch("bot.scene_runtime.resolve_scene_metadata", new_callable=AsyncMock)
    @patch("bot.scene_runtime.is_trusted_curator", return_value=True)
    async def test_e2e_crosstalk_prevention(self, mock_curator, mock_resolve_meta):
        bot = MockBot()

        # --- CANAL A ---
        mock_resolve_meta.return_value = {"title": "Elden Ring DLC", "provider_name": "YouTube"}
        await bot._handle_privmsg(":u1!u1@tmi.twitch.tv PRIVMSG #canal_a :PogChamp LETS GO")
        await bot._handle_privmsg(
            ":u1!u1@tmi.twitch.tv PRIVMSG #canal_a :https://youtube.com/watch?v=game123"
        )

        # --- CANAL B ---
        mock_resolve_meta.return_value = {"title": "The Matrix", "provider_name": "YouTube"}
        await bot._handle_privmsg(":u2!u2@tmi.twitch.tv PRIVMSG #canal_b :??? o que rola ???")
        await bot._handle_privmsg(
            ":u2!u2@tmi.twitch.tv PRIVMSG #canal_b :https://youtube.com/watch?v=movie456"
        )

        # Validação de Contexto direto (já que status line pode ser global no momento)
        ctx_a = context_manager.get("canal_a")
        ctx_b = context_manager.get("canal_b")

        self.assertIn("Elden Ring", ctx_a.format_observability())
        self.assertNotIn("The Matrix", ctx_a.format_observability())

        self.assertIn("The Matrix", ctx_b.format_observability())
        self.assertNotIn("Elden Ring", ctx_b.format_observability())

        print("\n[E2E] Context Isolation Verified.")

    @patch("bot.irc_handlers.ENABLE_LIVE_CONTEXT_LEARNING", True)
    async def test_e2e_vibe_isolation(self):
        bot = MockBot()
        for _ in range(5):
            await bot._handle_privmsg(":u!u@tmi.twitch.tv PRIVMSG #canal_a :Pog Pog Pog")
        for _ in range(5):
            await bot._handle_privmsg(":u!u@tmi.twitch.tv PRIVMSG #canal_b :??? ??? ???")

        ctx_a = context_manager.get("canal_a")
        ctx_b = context_manager.get("canal_b")

        self.assertEqual(ctx_a.stream_vibe, "Hyped")
        self.assertEqual(ctx_b.stream_vibe, "Confuso")
        print(f"\n[E2E] Vibe A: {ctx_a.stream_vibe} | Vibe B: {ctx_b.stream_vibe}")


if __name__ == "__main__":
    unittest.main()
