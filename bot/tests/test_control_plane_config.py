import time
import unittest
from unittest.mock import patch

from bot.control_plane_config import ControlPlaneConfigRuntime


class TestControlPlaneConfig(unittest.TestCase):
    def setUp(self):
        self.cpc = ControlPlaneConfigRuntime()

    def test_get_config(self):
        cfg = self.cpc.get_config()
        self.assertIn("autonomy_enabled", cfg)
        self.assertFalse(cfg["autonomy_enabled"])

    def test_update_config_bools(self):
        self.cpc.update_config({"autonomy_enabled": True, "clip_pipeline_enabled": True})
        cfg = self.cpc.get_config()
        self.assertTrue(cfg["autonomy_enabled"])
        self.assertTrue(cfg["clip_pipeline_enabled"])

    def test_update_config_numeric(self):
        self.cpc.update_config({"heartbeat_interval_seconds": 120, "budget_messages_10m": 5})
        cfg = self.cpc.get_config()
        self.assertEqual(cfg["heartbeat_interval_seconds"], 120)
        self.assertEqual(cfg["budget_messages_10m"], 5)

    def test_can_send_auto_chat_cooldown(self):
        now = time.time()
        self.cpc.update_config({"min_cooldown_seconds": 60})
        # Record a send 30s ago
        self.cpc.register_auto_chat_sent(timestamp=now - 30)

        allowed, reason, usage = self.cpc.can_send_auto_chat(timestamp=now)
        self.assertFalse(allowed)
        self.assertEqual(reason, "cooldown_active")

    def test_can_send_auto_chat_budget(self):
        now = time.time()
        # Set cooldown to minimum to avoid interference
        self.cpc.update_config({"budget_messages_10m": 1, "min_cooldown_seconds": 15})
        # Record a send 100s ago (passes cooldown but uses budget)
        self.cpc.register_auto_chat_sent(timestamp=now - 100)

        allowed, reason, usage = self.cpc.can_send_auto_chat(timestamp=now)
        self.assertFalse(allowed)
        self.assertEqual(reason, "budget_10m_exceeded")

    def test_suspend_agent_blocks_auto_chat_and_updates_snapshot(self):
        now = time.time()
        self.cpc.suspend_agent(reason="panic_button", timestamp=now)

        allowed, reason, usage = self.cpc.can_send_auto_chat(timestamp=now + 1)
        self.assertFalse(allowed)
        self.assertEqual(reason, "agent_suspended")
        self.assertEqual(usage["messages_daily"], 0)

        snap = self.cpc.runtime_base_snapshot(timestamp=now + 1)
        self.assertTrue(snap["suspended"])
        self.assertEqual(snap["suspend_reason"], "panic_button")
        self.assertEqual(snap["suspended_epoch"], now)
        self.assertTrue(snap["suspended_at"])

    def test_resume_agent_restores_runtime_snapshot(self):
        now = time.time()
        self.cpc.suspend_agent(reason="panic_button", timestamp=now)
        self.cpc.resume_agent(reason="dashboard_resume", timestamp=now + 5)

        allowed, reason, _usage = self.cpc.can_send_auto_chat(timestamp=now + 6)
        self.assertTrue(allowed)
        self.assertEqual(reason, "ok")

        snap = self.cpc.runtime_base_snapshot(timestamp=now + 6)
        self.assertFalse(snap["suspended"])
        self.assertEqual(snap["suspended_epoch"], 0.0)
        self.assertEqual(snap["suspend_reason"], "")
        self.assertEqual(snap["last_resume_reason"], "dashboard_resume")
        self.assertEqual(snap["last_resumed_epoch"], now + 5)
        self.assertTrue(snap["last_resumed_at"])

    def test_consume_due_goals_force(self):
        self.cpc.update_config(
            {"autonomy_enabled": False, "goals": [{"id": "g1", "interval_seconds": 60}]}
        )
        # Even if disabled, force works
        goals = self.cpc.consume_due_goals(force=True)
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["id"], "g1")

    def test_consume_due_goals_intervals(self):
        now = time.time()
        self.cpc.update_config(
            {"autonomy_enabled": True, "goals": [{"id": "g1", "interval_seconds": 60}]}
        )

        # First call initializes due_at (sets it to now + 60)
        self.cpc.consume_due_goals(timestamp=now)
        self.assertEqual(len(self.cpc.consume_due_goals(timestamp=now)), 0)

        # After interval
        goals = self.cpc.consume_due_goals(timestamp=now + 61)
        self.assertEqual(len(goals), 1)

    def test_consume_due_goals_skips_when_suspended_without_force(self):
        self.cpc.update_config(
            {"autonomy_enabled": True, "goals": [{"id": "g1", "interval_seconds": 60}]}
        )
        self.cpc.suspend_agent(timestamp=time.time())
        goals = self.cpc.consume_due_goals(timestamp=time.time() + 61)
        self.assertEqual(goals, [])

    def test_update_config_agent_suspended_updates_runtime_state(self):
        with patch("bot.control_plane_config.time.time", return_value=123.0):
            self.cpc.update_config({"agent_suspended": True})

        suspended_snap = self.cpc.runtime_base_snapshot(timestamp=123.0)
        self.assertTrue(suspended_snap["suspended"])
        self.assertEqual(suspended_snap["suspend_reason"], "config_update")
        self.assertEqual(suspended_snap["suspended_epoch"], 123.0)

        with patch("bot.control_plane_config.time.time", return_value=456.0):
            self.cpc.update_config({"agent_suspended": False})

        resumed_snap = self.cpc.runtime_base_snapshot(timestamp=456.0)
        self.assertFalse(resumed_snap["suspended"])
        self.assertEqual(resumed_snap["last_resume_reason"], "config_update")
        self.assertEqual(resumed_snap["last_resumed_epoch"], 456.0)

    def test_runtime_registration(self):
        self.cpc.register_tick(reason="test")
        self.cpc.register_goal_run(goal_id="g", risk="r")
        self.cpc.register_budget_block(reason="b")
        self.cpc.register_dispatch_failure(reason="f")

        snap = self.cpc.runtime_base_snapshot()
        # Snapshot structure: autonomy_ticks_total is top-level or in autonomy key
        # Looking at control_plane_config_helpers.py might be needed but let's check snap
        self.assertEqual(snap["autonomy_ticks_total"], 1)
        self.assertEqual(snap["autonomy_goal_runs_total"], 1)
