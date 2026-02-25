import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import bot.eventsub_runtime as es_runtime
import os

class TestByteBotExtended(unittest.IsolatedAsyncioTestCase):
    @patch("bot.eventsub_runtime.commands.Bot.__init__", return_value=None)
    async def test_event_message_full_dispatch(self, mock_init):
        with patch.dict(os.environ, {"TWITCH_BOT_ID": "123"}):
            bot = es_runtime.ByteBot(client_secret="s")
            bot.handle_commands = AsyncMock()
            
            payload = MagicMock()
            payload.echo = False
            payload.text = "!ask hello"
            payload.author.name = "juan"
            
            # FIXED SYNTAX: Combined patches into a single context manager
            with patch("bot.eventsub_runtime.parse_byte_prompt", return_value=None):
                with patch("bot.eventsub_runtime.auto_update_scene_from_message", new_callable=AsyncMock) as mock_scene:
                    mock_scene.return_value = []
                    await bot.event_message(payload)
                    bot.handle_commands.assert_called_once()
                
    async def test_require_env_fail(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                es_runtime._require_env("MISSING")
