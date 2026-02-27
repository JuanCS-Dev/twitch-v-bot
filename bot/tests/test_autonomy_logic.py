import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot import autonomy_logic
from bot.control_plane import RISK_AUTO_CHAT, RISK_CLIP_CANDIDATE


class TestAutonomyLogic(unittest.IsolatedAsyncioTestCase):
    @patch("bot.autonomy_logic.agent_inference", new_callable=AsyncMock)
    async def test_process_autonomy_goal_clip_disabled(self, mock_infer):
        # Coverage for clip candidate when disabled
        with patch("bot.autonomy_logic.control_plane") as mock_cp:
            mock_cp.get_config.return_value = {"clip_pipeline_enabled": False}
            goal = {"id": "g1", "risk": RISK_CLIP_CANDIDATE, "prompt": "p"}
            # We don't even need to call inference if it checks config first
            # But the code calls generate_goal_text first. Let's mock it.
            with patch("bot.autonomy_logic.generate_goal_text", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = "Cool clip"
                result = await autonomy_logic.process_autonomy_goal(goal, None)
                self.assertEqual(result["outcome"], "disabled")

    @patch("bot.autonomy_logic.generate_goal_text", new_callable=AsyncMock)
    @patch("bot.autonomy_logic.control_plane")
    async def test_process_autonomy_goal_auto_chat_no_dispatcher(self, mock_cp, mock_gen):
        mock_gen.return_value = "Hello"
        mock_cp.can_send_auto_chat.return_value = (True, "", {})
        mock_cp.enqueue_action.return_value = {"id": "act1"}

        result = await autonomy_logic.process_autonomy_goal({"risk": RISK_AUTO_CHAT}, None)
        self.assertEqual(result["outcome"], "queued_no_dispatcher")

    @patch("bot.autonomy_logic.generate_goal_text", new_callable=AsyncMock)
    @patch("bot.autonomy_logic.context_manager")
    @patch("bot.autonomy_logic.control_plane")
    async def test_process_autonomy_goal_skips_when_channel_is_paused(
        self,
        mock_cp,
        mock_context_manager,
        mock_generate,
    ):
        mock_context_manager.ensure_channel_config_loaded.return_value = MagicMock(
            channel_paused=True
        )

        result = await autonomy_logic.process_autonomy_goal(
            {"id": "g-paused", "risk": RISK_AUTO_CHAT},
            None,
            channel_id="canal_a",
        )

        self.assertEqual(result["outcome"], "channel_paused")
        mock_cp.register_goal_run.assert_not_called()
        mock_generate.assert_not_called()
