import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import bot.eventsub_runtime as es_runtime


class TestEventSubErrorPaths(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.comp = es_runtime.AgentComponent(self.bot)

    @patch("bot.eventsub_runtime.agent_inference", new_callable=AsyncMock)
    async def test_ask_empty_query(self, mock_infer):
        ctx = MagicMock()
        ctx.message.text = "!ask"  # Empty query
        await self.comp.ask._callback(self.comp, ctx)
        mock_infer.assert_not_called()

    @patch("bot.eventsub_runtime.is_owner", return_value=True)
    async def test_scene_clear_invalid_type(self, mock_owner):
        ctx = MagicMock()
        ctx.message.text = "!scene clear invalid_type"
        ctx.reply = AsyncMock()
        with patch("bot.eventsub_runtime.context") as mock_context:
            mock_context.clear_content.return_value = False
            await self.comp.scene._callback(self.comp, ctx)
            ctx.reply.assert_called_with(
                "Tipo invalido. Tipos: " + str(mock_context.list_supported_content_types())
            )
