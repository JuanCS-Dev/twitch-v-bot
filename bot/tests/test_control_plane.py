import unittest

from bot.control_plane import ControlPlaneState


class TestControlPlaneState(unittest.TestCase):
    def setUp(self):
        self.control_plane = ControlPlaneState()

    def test_suspend_and_resume_agent_wrappers(self):
        suspended = self.control_plane.suspend_agent(reason="panic_button", timestamp=100.0)
        self.assertTrue(suspended["agent_suspended"])

        resumed = self.control_plane.resume_agent(reason="resume_button", timestamp=120.0)
        self.assertFalse(resumed["agent_suspended"])

    def test_build_capabilities_reports_suspend_state(self):
        self.control_plane.suspend_agent(reason="panic_button", timestamp=100.0)
        capabilities = self.control_plane.build_capabilities(bot_mode="eventsub")
        self.assertTrue(capabilities["autonomy"]["suspended"])
        self.assertTrue(capabilities["autonomy"]["suspendable"])

        self.control_plane.resume_agent(reason="resume_button", timestamp=120.0)
        irc_capabilities = self.control_plane.build_capabilities(bot_mode="irc")
        self.assertFalse(irc_capabilities["autonomy"]["suspended"])
        self.assertEqual(
            irc_capabilities["channel_control"]["supported_actions"], ["list", "join", "part"]
        )

    def test_runtime_and_queue_wrappers(self):
        self.control_plane.update_config(
            {
                "autonomy_enabled": True,
                "goals": [{"id": "g1", "interval_seconds": 60, "prompt": "Teste"}],
            }
        )
        self.control_plane.set_loop_running(True)
        self.control_plane.touch_heartbeat(timestamp=100.0)
        self.control_plane.register_tick(reason="manual", timestamp=101.0)
        self.control_plane.register_goal_run(goal_id="g1", risk="suggest_streamer", timestamp=102.0)
        self.control_plane.register_goal_session_result(
            goal_id="g1",
            outcome="queued",
            timestamp=102.5,
        )
        self.control_plane.register_budget_block(reason="cooldown_active", timestamp=103.0)
        self.control_plane.register_dispatch_failure(reason="dispatch_error", timestamp=104.0)

        allowed, reason, _usage = self.control_plane.can_send_auto_chat(timestamp=105.0)
        self.assertTrue(allowed)
        self.assertEqual(reason, "ok")

        self.control_plane.register_auto_chat_sent(timestamp=106.0)
        forced_goals = self.control_plane.consume_due_goals(force=True, timestamp=107.0)
        self.assertEqual(len(forced_goals), 1)

        queued = self.control_plane.enqueue_action(
            kind="suggestion",
            risk="suggest_streamer",
            title="Teste",
            body="Mensagem",
            timestamp=108.0,
        )
        decided = self.control_plane.decide_action(
            action_id=queued["id"],
            decision="approve",
            note="ok",
            timestamp=109.0,
        )
        listed = self.control_plane.list_actions(status="approved", limit=10, timestamp=110.0)
        runtime = self.control_plane.runtime_snapshot(timestamp=111.0)

        self.assertEqual(decided["status"], "approved")
        self.assertEqual(len(listed["items"]), 1)
        self.assertTrue(runtime["loop_running"])
        self.assertEqual(runtime["autonomy_goal_kpi_met_total"], 1)
        self.assertIn("queue", runtime)
        self.assertIn("queue_window_60m", runtime)
