import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from bot.autonomy_logic import process_autonomy_goal, generate_goal_text
from bot.control_plane import (
    RISK_AUTO_CHAT,
    RISK_CLIP_CANDIDATE,
    RISK_MODERATION_ACTION,
    RISK_SUGGEST_STREAMER,
)

class TestAutonomyLogicV2(unittest.IsolatedAsyncioTestCase):
    @patch("bot.autonomy_logic.agent_inference", return_value="")
    async def test_process_goal_empty_generation(self, mock_inf):
        goal = {"id": "g1", "risk": RISK_AUTO_CHAT, "prompt": "p"}
        res = await process_autonomy_goal(goal, None)
        self.assertEqual(res["outcome"], "generation_empty")

    @patch("bot.autonomy_logic.agent_inference", return_value="Boa live!")
    @patch("bot.autonomy_logic.control_plane.can_send_auto_chat", return_value=(False, "cooldown", {}))
    async def test_process_goal_budget_blocked(self, mock_budget, mock_inf):
        goal = {"id": "g1", "risk": RISK_AUTO_CHAT}
        res = await process_autonomy_goal(goal, None)
        self.assertEqual(res["outcome"], "budget_blocked")

    @patch("bot.autonomy_logic.agent_inference", return_value="Momento épico")
    @patch("bot.autonomy_logic.control_plane.get_config", return_value={"clip_pipeline_enabled": False})
    async def test_process_goal_clip_disabled(self, mock_cfg, mock_inf):
        goal = {"id": "c1", "risk": RISK_CLIP_CANDIDATE}
        res = await process_autonomy_goal(goal, None)
        self.assertEqual(res["outcome"], "disabled")

    @patch("bot.autonomy_logic.agent_inference", return_value="NADA")
    @patch("bot.autonomy_logic.control_plane.get_config", return_value={"clip_pipeline_enabled": True})
    async def test_process_goal_clip_none_returned(self, mock_cfg, mock_inf):
        goal = {"id": "c1", "risk": RISK_CLIP_CANDIDATE}
        res = await process_autonomy_goal(goal, None)
        self.assertEqual(res["outcome"], "no_candidate")

    @patch("bot.autonomy_logic.agent_inference", return_value="Aviso de moderacao")
    async def test_process_goal_moderation(self, mock_inf):
        goal = {"id": "m1", "risk": RISK_MODERATION_ACTION}
        res = await process_autonomy_goal(goal, None)
        self.assertEqual(res["outcome"], "queued")
        self.assertIn("action_id", res)

    @patch("bot.autonomy_logic.agent_inference", return_value="Chat msg")
    @patch("bot.autonomy_logic.control_plane.can_send_auto_chat", return_value=(True, "", {}))
    async def test_process_goal_dispatch_error(self, mock_budget, mock_inf):
        async def fail_dispatcher(t): raise Exception("Network down")
        goal = {"id": "g1", "risk": RISK_AUTO_CHAT}
        res = await process_autonomy_goal(goal, fail_dispatcher)
        self.assertEqual(res["outcome"], "dispatch_error")

    async def test_generate_goal_text_all_risks(self):
        risks = [RISK_AUTO_CHAT, RISK_SUGGEST_STREAMER, RISK_MODERATION_ACTION, RISK_CLIP_CANDIDATE, "UNKNOWN"]
        with patch("bot.autonomy_logic.agent_inference", return_value="result"):
            for r in risks:
                res = await generate_goal_text("p", r)
                self.assertEqual(res, "result")
