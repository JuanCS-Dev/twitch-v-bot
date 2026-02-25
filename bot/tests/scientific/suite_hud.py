import time
from unittest.mock import MagicMock, patch

from bot.tests.scientific_shared import ScientificTestCase


class ScientificHudTestsMixin(ScientificTestCase):
    """Testes cientificos para HudRuntime (Fase 7)."""

    def test_hud_push_empty_message(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        result = rt.push_message("")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "empty_message")

    def test_hud_push_whitespace_only(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        result = rt.push_message("   \n  ")
        self.assertFalse(result["ok"])

    def test_hud_push_valid_message(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        result = rt.push_message("Sugestao: pause o jogo para interagir com o chat.")
        self.assertTrue(result["ok"])
        entry = result["entry"]
        self.assertIn("ts", entry)
        self.assertEqual(entry["source"], "autonomy")
        self.assertIn("Sugestao", entry["text"])

    def test_hud_push_truncates_long_message(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        long_text = "A" * 500
        result = rt.push_message(long_text)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["entry"]["text"]), 300)

    def test_hud_get_messages_empty(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        messages = rt.get_messages()
        self.assertEqual(messages, [])

    def test_hud_get_messages_since_filter(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        rt.push_message("Msg 1")
        now = time.time()
        rt.push_message("Msg 2")

        # All messages since epoch
        all_msgs = rt.get_messages(since=0.0)
        self.assertEqual(len(all_msgs), 2)

        # Messages since now — should return only message 2
        recent = rt.get_messages(since=now - 0.001)
        self.assertGreaterEqual(len(recent), 1)

    def test_hud_max_buffer(self) -> None:
        from bot.hud_runtime import MAX_HUD_MESSAGES, HudRuntime

        rt = HudRuntime()
        for i in range(MAX_HUD_MESSAGES + 5):
            rt.push_message(f"Message {i}")

        all_msgs = rt.get_messages(since=0.0)
        self.assertLessEqual(len(all_msgs), MAX_HUD_MESSAGES)
        # Oldest messages should have been evicted
        self.assertIn("Message", all_msgs[-1]["text"])

    def test_hud_clear(self) -> None:
        from bot.hud_runtime import HudRuntime

        rt = HudRuntime()
        rt.push_message("Test")
        self.assertEqual(len(rt.get_messages(since=0.0)), 1)
        rt.clear()
        self.assertEqual(len(rt.get_messages(since=0.0)), 0)

    def test_hud_get_status(self) -> None:
        from bot.hud_runtime import MAX_HUD_MESSAGES, HudRuntime

        rt = HudRuntime()
        status = rt.get_status()
        self.assertEqual(status["count"], 0)
        self.assertEqual(status["max"], MAX_HUD_MESSAGES)

        rt.push_message("Test 1")
        rt.push_message("Test 2")
        status = rt.get_status()
        self.assertEqual(status["count"], 2)

    @patch("bot.autonomy_logic.hud_runtime")
    def test_hud_integration_suggest_streamer_pushes(self, mock_hud: MagicMock) -> None:
        from bot.autonomy_logic import _handle_generic_suggestion
        from bot.control_plane_constants import RISK_SUGGEST_STREAMER

        with (
            patch("bot.autonomy_logic.control_plane") as mock_cp,
            patch("bot.autonomy_logic.observability"),
        ):
            mock_cp.enqueue_action.return_value = {"id": "test-action-1"}
            _handle_generic_suggestion(
                goal_id="g1",
                risk=RISK_SUGGEST_STREAMER,
                goal_name="Test",
                prompt="prompt",
                text="Sugestao de teste",
            )
            mock_hud.push_message.assert_called_once_with(  # type: ignore[union-attr]
                "Sugestao de teste", source="autonomy"
            )

    @patch("bot.autonomy_logic.hud_runtime")
    def test_hud_integration_moderation_does_not_push(self, mock_hud: MagicMock) -> None:
        from bot.autonomy_logic import _handle_generic_suggestion
        from bot.control_plane_constants import RISK_MODERATION_ACTION

        with (
            patch("bot.autonomy_logic.control_plane") as mock_cp,
            patch("bot.autonomy_logic.observability"),
        ):
            mock_cp.enqueue_action.return_value = {"id": "test-action-2"}
            _handle_generic_suggestion(
                goal_id="g2",
                risk=RISK_MODERATION_ACTION,
                goal_name="Mod",
                prompt="mod prompt",
                text="Moderacao teste",
            )
            mock_hud.push_message.assert_not_called()  # type: ignore[union-attr]
