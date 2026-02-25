import unittest
from types import SimpleNamespace

from bot.observability import ObservabilityState


class TestObservabilityState(unittest.TestCase):
    def test_snapshot_tracks_core_metrics_and_routes(self):
        state = ObservabilityState()
        base = 1_700_000_000.0
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Bot Online",
            live_observability={"movie": "Duna Parte 2"},
            get_uptime_minutes=lambda: 9,
        )

        state.record_chat_message(
            author_name="alice", source="irc", text="byte status", timestamp=base
        )
        state.record_chat_message(
            author_name="bob", source="irc", text="!scene movie matrix", timestamp=base + 20
        )
        state.record_chat_message(
            author_name="bob", source="irc", text="watch https://example.com", timestamp=base + 40
        )
        state.record_byte_trigger(
            prompt="status", source="irc", author_name="alice", timestamp=base + 1
        )
        state.record_reply(text="Byte v1.4 | Uptime: 9min", timestamp=base + 2)
        state.record_byte_interaction(
            route="llm_default",
            author_name="alice",
            prompt_chars=11,
            reply_parts=1,
            reply_chars=24,
            serious=False,
            follow_up=False,
            current_events=True,
            latency_ms=120.5,
            timestamp=base + 2,
        )
        state.record_quality_gate(outcome="pass", reason="ok", timestamp=base + 3)
        snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.4",
            bot_mode="irc",
            stream_context=stream_context,
            timestamp=base + 180,
        )
        analytics = snapshot["chat_analytics"]
        leaderboards = snapshot["leaderboards"]

        self.assertEqual(snapshot["bot"]["brand"], "Byte")
        self.assertEqual(snapshot["bot"]["uptime_minutes"], 9)
        self.assertEqual(snapshot["metrics"]["chat_messages_total"], 3)
        self.assertEqual(snapshot["metrics"]["chat_messages_irc_total"], 3)
        self.assertEqual(snapshot["metrics"]["chat_prefixed_messages_total"], 1)
        self.assertEqual(snapshot["metrics"]["chat_messages_with_url_total"], 1)
        self.assertEqual(snapshot["metrics"]["byte_triggers_total"], 1)
        self.assertEqual(snapshot["metrics"]["interactions_total"], 1)
        self.assertEqual(snapshot["metrics"]["replies_total"], 1)
        self.assertEqual(snapshot["metrics"]["llm_interactions_total"], 1)
        self.assertEqual(snapshot["metrics"]["current_events_interactions_total"], 1)
        self.assertEqual(snapshot["metrics"]["quality_checks_total"], 1)
        self.assertEqual(snapshot["metrics"]["quality_retry_total"], 0)
        self.assertEqual(snapshot["metrics"]["quality_retry_success_total"], 0)
        self.assertEqual(snapshot["metrics"]["quality_fallback_total"], 0)
        self.assertGreater(snapshot["metrics"]["avg_latency_ms"], 0)
        self.assertEqual(snapshot["chatters"]["unique_total"], 2)
        self.assertEqual(snapshot["chatters"]["active_10m"], 2)
        self.assertEqual(analytics["messages_10m"], 3)
        self.assertEqual(analytics["messages_60m"], 3)
        self.assertEqual(analytics["messages_per_minute_10m"], 0.3)
        self.assertEqual(analytics["prefixed_commands_60m"], 1)
        self.assertEqual(analytics["url_messages_60m"], 1)
        self.assertEqual(analytics["source_counts_60m"]["irc"], 3)
        self.assertEqual(analytics["byte_triggers_10m"], 1)
        self.assertEqual(leaderboards["top_chatters_60m"][0], {"author": "bob", "messages": 2})
        self.assertEqual(
            leaderboards["top_trigger_users_60m"][0], {"author": "alice", "triggers": 1}
        )
        self.assertEqual(snapshot["context"]["active_contexts"], 1)
        self.assertEqual(snapshot["context"]["items"]["movie"], "Duna Parte 2")
        self.assertEqual(snapshot["routes"][0]["route"], "llm_default")
        self.assertEqual(snapshot["routes"][0]["count"], 1)
        self.assertEqual(len(snapshot["timeline"]), 30)

    def test_snapshot_tracks_errors_refresh_and_event_order(self):
        state = ObservabilityState()
        base = 1_700_010_000.0
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Bot Online",
            live_observability={},
        )

        state.record_token_refresh(reason="manual", timestamp=base)
        state.record_auth_failure(details="invalid token", timestamp=base + 1)
        state.record_error(category="irc_connection", details="socket reset", timestamp=base + 2)
        state.record_byte_interaction(
            route="llm_default",
            author_name="bob",
            prompt_chars=10,
            reply_parts=1,
            reply_chars=20,
            serious=True,
            follow_up=True,
            current_events=False,
            latency_ms=300,
            timestamp=base + 3,
        )
        state.record_byte_interaction(
            route="llm_default",
            author_name="bob",
            prompt_chars=10,
            reply_parts=1,
            reply_chars=20,
            serious=False,
            follow_up=False,
            current_events=False,
            latency_ms=100,
            timestamp=base + 4,
        )
        state.record_byte_interaction(
            route="llm_default",
            author_name="bob",
            prompt_chars=10,
            reply_parts=1,
            reply_chars=20,
            serious=False,
            follow_up=False,
            current_events=False,
            latency_ms=200,
            timestamp=base + 5,
        )
        state.record_quality_gate(outcome="retry", reason="resposta_generica", timestamp=base + 6)
        state.record_quality_gate(
            outcome="fallback", reason="tema_atual_sem_ancora_temporal", timestamp=base + 7
        )

        snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.4",
            bot_mode="eventsub",
            stream_context=stream_context,
            timestamp=base + 300,
        )

        self.assertEqual(snapshot["metrics"]["token_refreshes_total"], 1)
        self.assertEqual(snapshot["metrics"]["auth_failures_total"], 1)
        self.assertEqual(snapshot["metrics"]["errors_total"], 2)
        self.assertEqual(snapshot["metrics"]["serious_interactions_total"], 1)
        self.assertEqual(snapshot["metrics"]["follow_up_interactions_total"], 1)
        self.assertEqual(snapshot["metrics"]["quality_checks_total"], 2)
        self.assertEqual(snapshot["metrics"]["quality_retry_total"], 1)
        self.assertEqual(snapshot["metrics"]["quality_fallback_total"], 1)
        self.assertEqual(snapshot["metrics"]["avg_latency_ms"], 200.0)
        self.assertEqual(snapshot["metrics"]["p95_latency_ms"], 200.0)
        self.assertTrue(snapshot["recent_events"])
        self.assertEqual(snapshot["recent_events"][0]["event"], "quality_gate")


if __name__ == "__main__":
    unittest.main()
