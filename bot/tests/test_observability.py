import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bot.observability import ObservabilityState


class FakePersistence:
    def __init__(self, loaded=None, *, fail_load=False, fail_save=False):
        self.loaded = loaded
        self.fail_load = fail_load
        self.fail_save = fail_save
        self.saved = []
        self.history_saved = []

    def load_observability_rollup_sync(self):
        if self.fail_load:
            raise RuntimeError("load failed")
        return self.loaded

    def save_observability_rollup_sync(self, state):
        if self.fail_save:
            raise RuntimeError("save failed")
        payload = {
            "rollup_key": "global",
            "state": dict(state or {}),
            "updated_at": "2026-02-27T16:00:00Z",
            "source": "memory",
        }
        self.saved.append(payload)
        return payload

    def save_observability_channel_history_sync(self, channel_id, payload):
        if self.fail_save:
            raise RuntimeError("save failed")
        point = {
            "channel_id": str(channel_id or ""),
            "captured_at": str((payload or {}).get("captured_at") or ""),
            "metrics": dict((payload or {}).get("metrics") or {}),
        }
        self.history_saved.append(point)
        return point


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

    def test_snapshot_supports_per_channel_isolation_and_global_rollup(self):
        state = ObservabilityState()
        base = 1_700_011_000.0
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Bot Online",
            live_observability={},
        )

        state.record_chat_message(
            author_name="alice",
            source="irc",
            text="byte status",
            channel_id="canal_a",
            timestamp=base,
        )
        state.record_byte_trigger(
            prompt="status",
            source="irc",
            author_name="alice",
            channel_id="canal_a",
            timestamp=base + 1,
        )
        state.record_reply(text="online", channel_id="canal_a", timestamp=base + 2)
        state.record_chat_message(
            author_name="bob",
            source="irc",
            text="bom dia",
            channel_id="canal_b",
            timestamp=base + 3,
        )

        global_snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            timestamp=base + 120,
        )
        channel_a_snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            channel_id="canal_a",
            timestamp=base + 120,
        )
        channel_b_snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            channel_id="canal_b",
            timestamp=base + 120,
        )
        unknown_channel_snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            channel_id="canal_x",
            timestamp=base + 120,
        )

        self.assertEqual(global_snapshot["metrics"]["chat_messages_total"], 2)
        self.assertEqual(global_snapshot["metrics"]["byte_triggers_total"], 1)
        self.assertEqual(global_snapshot["metrics"]["replies_total"], 1)
        self.assertEqual(global_snapshot["chatters"]["unique_total"], 2)
        self.assertEqual(global_snapshot["leaderboards"]["top_chatters_60m"][0]["author"], "alice")

        self.assertEqual(channel_a_snapshot["metrics"]["chat_messages_total"], 1)
        self.assertEqual(channel_a_snapshot["metrics"]["byte_triggers_total"], 1)
        self.assertEqual(channel_a_snapshot["metrics"]["replies_total"], 1)
        self.assertEqual(channel_a_snapshot["chatters"]["unique_total"], 1)
        self.assertEqual(
            channel_a_snapshot["leaderboards"]["top_trigger_users_60m"][0],
            {"author": "alice", "triggers": 1},
        )

        self.assertEqual(channel_b_snapshot["metrics"]["chat_messages_total"], 1)
        self.assertEqual(channel_b_snapshot["metrics"]["byte_triggers_total"], 0)
        self.assertEqual(channel_b_snapshot["metrics"]["replies_total"], 0)
        self.assertEqual(channel_b_snapshot["chatters"]["unique_total"], 1)
        self.assertEqual(channel_b_snapshot["leaderboards"]["top_trigger_users_60m"], [])

        self.assertEqual(unknown_channel_snapshot["metrics"]["chat_messages_total"], 0)
        self.assertEqual(unknown_channel_snapshot["metrics"]["byte_triggers_total"], 0)
        self.assertEqual(unknown_channel_snapshot["chatters"]["unique_total"], 0)

    def test_state_restores_and_persists_channel_scopes(self):
        persistence = FakePersistence(
            loaded={
                "rollup_key": "global",
                "updated_at": "2026-02-27T15:55:00Z",
                "source": "supabase",
                "state": {
                    "counters": {"chat_messages_total": 2},
                    "channel_scopes": {
                        "Canal_A": {
                            "counters": {
                                "chat_messages_total": 5,
                                "replies_total": 2,
                            },
                            "route_counts": {"llm_default": 1},
                        },
                        "canal_b": {
                            "counters": {"chat_messages_total": 1},
                        },
                    },
                },
            }
        )
        state = ObservabilityState(
            persistence_layer=persistence,
            persist_interval_seconds=1000.0,
        )
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Boot restored",
            live_observability={},
        )

        channel_a_snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            channel_id="canal_a",
            timestamp=1_700_012_000.0,
        )
        channel_b_snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            channel_id="canal_b",
            timestamp=1_700_012_000.0,
        )

        self.assertEqual(channel_a_snapshot["metrics"]["chat_messages_total"], 5)
        self.assertEqual(channel_a_snapshot["metrics"]["replies_total"], 2)
        self.assertEqual(channel_b_snapshot["metrics"]["chat_messages_total"], 1)

        state.record_chat_message(
            author_name="alice",
            source="irc",
            text="novo evento",
            channel_id="canal_a",
            timestamp=1_700_012_001.0,
        )
        state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            timestamp=1_700_012_010.0,
        )

        self.assertGreater(len(persistence.saved), 0)
        saved_state = persistence.saved[-1]["state"]
        self.assertEqual(saved_state["schema_version"], 2)
        self.assertIn("channel_scopes", saved_state)
        self.assertIn("canal_a", saved_state["channel_scopes"])
        self.assertEqual(
            saved_state["channel_scopes"]["canal_a"]["counters"]["chat_messages_total"],
            6,
        )

    def test_state_flush_persists_history_points_per_active_channel(self):
        persistence = FakePersistence()
        state = ObservabilityState(
            persistence_layer=persistence,
            persist_interval_seconds=1000.0,
        )
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Boot restored",
            live_observability={},
        )

        state.record_chat_message(
            author_name="alice",
            source="irc",
            text="hello",
            channel_id="canal_a",
            timestamp=1_700_050_000.0,
        )
        state.record_byte_trigger(
            prompt="status",
            source="irc",
            author_name="alice",
            channel_id="canal_a",
            timestamp=1_700_050_001.0,
        )
        state.record_chat_message(
            author_name="bob",
            source="irc",
            text="oi",
            channel_id="canal_b",
            timestamp=1_700_050_002.0,
        )
        state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            timestamp=1_700_050_010.0,
        )

        self.assertGreaterEqual(len(persistence.history_saved), 2)
        channels = {entry["channel_id"] for entry in persistence.history_saved}
        self.assertIn("canal_a", channels)
        self.assertIn("canal_b", channels)
        channel_a_point = next(
            entry
            for entry in reversed(persistence.history_saved)
            if entry["channel_id"] == "canal_a"
        )
        self.assertEqual(channel_a_point["metrics"]["chat_messages_total"], 1)
        self.assertEqual(channel_a_point["metrics"]["byte_triggers_total"], 1)

    def test_state_restores_persisted_rollup_and_exposes_metadata(self):
        persistence = FakePersistence(
            loaded={
                "rollup_key": "global",
                "updated_at": "2026-02-27T15:55:00Z",
                "source": "supabase",
                "state": {
                    "counters": {
                        "chat_messages_total": 7,
                        "byte_triggers_total": 2,
                        "replies_total": 1,
                    },
                    "route_counts": {"llm_default": 3},
                    "minute_buckets": {
                        "28333333": {
                            "chat_messages": 4,
                            "byte_triggers": 1,
                            "replies_sent": 1,
                            "llm_requests": 1,
                            "errors": 0,
                        }
                    },
                    "latencies_ms": [90.0, 120.0, 150.0],
                    "recent_events": [
                        {
                            "ts": "2026-02-27T15:54:59Z",
                            "level": "INFO",
                            "event": "byte_interaction",
                            "message": "llm_default by alice",
                        }
                    ],
                    "chatter_last_seen": {"alice": 1_700_010_000.0},
                    "known_chatters": ["alice", "bob"],
                    "chat_events": [
                        {
                            "ts": 1_700_010_000.0,
                            "source": "irc",
                            "author": "alice",
                            "length": 12,
                            "is_command": False,
                            "has_url": False,
                        }
                    ],
                    "byte_trigger_events": [
                        {"ts": 1_700_010_001.0, "author": "alice", "source": "irc"}
                    ],
                    "interaction_events": [
                        {"ts": 1_700_010_002.0, "route": "llm_default", "is_llm": True}
                    ],
                    "quality_events": [],
                    "token_usage_events": [],
                    "autonomy_goal_events": [],
                    "chatter_message_totals": {"alice": 5, "bob": 2},
                    "trigger_user_totals": {"alice": 2},
                    "last_prompt": "status",
                    "last_reply": "online",
                    "estimated_cost_usd_total": 0.1234,
                    "clips_status": {"token_valid": True, "scope_ok": False},
                },
            }
        )
        state = ObservabilityState(
            persistence_layer=persistence,
            persist_interval_seconds=60.0,
        )
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Boot restored",
            live_observability={},
        )

        snapshot = state.snapshot(
            bot_brand="Byte",
            bot_version="1.5",
            bot_mode="irc",
            stream_context=stream_context,
            timestamp=1_700_010_100.0,
        )

        self.assertEqual(snapshot["metrics"]["chat_messages_total"], 7)
        self.assertEqual(snapshot["metrics"]["byte_triggers_total"], 2)
        self.assertEqual(snapshot["routes"][0], {"route": "llm_default", "count": 3})
        self.assertEqual(snapshot["context"]["last_prompt"], "status")
        self.assertEqual(snapshot["context"]["clips_status"]["token_valid"], True)
        self.assertTrue(snapshot["persistence"]["enabled"])
        self.assertTrue(snapshot["persistence"]["restored"])
        self.assertEqual(snapshot["persistence"]["source"], "supabase")
        self.assertEqual(snapshot["persistence"]["updated_at"], "2026-02-27T15:55:00Z")

    def test_snapshot_forces_rollup_flush_when_interval_has_not_elapsed(self):
        persistence = FakePersistence()
        state = ObservabilityState(
            persistence_layer=persistence,
            persist_interval_seconds=1000.0,
        )
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Fresh boot",
            live_observability={},
        )

        with patch("bot.observability_state.time.monotonic", side_effect=[100.0, 101.0]):
            state.record_chat_message(
                author_name="alice",
                source="irc",
                text="hello there",
                timestamp=1_700_020_000.0,
            )
            self.assertEqual(len(persistence.saved), 0)

            snapshot = state.snapshot(
                bot_brand="Byte",
                bot_version="1.5",
                bot_mode="irc",
                stream_context=stream_context,
                timestamp=1_700_020_010.0,
            )

        self.assertEqual(len(persistence.saved), 1)
        self.assertEqual(
            persistence.saved[0]["state"]["counters"]["chat_messages_total"],
            1,
        )
        self.assertEqual(snapshot["metrics"]["chat_messages_total"], 1)
        self.assertFalse(snapshot["persistence"]["dirty"])
        self.assertEqual(snapshot["persistence"]["updated_at"], "2026-02-27T16:00:00Z")

    def test_state_handles_restore_and_flush_failures_without_breaking_snapshot(self):
        state = ObservabilityState(
            persistence_layer=FakePersistence(fail_load=True, fail_save=True),
            persist_interval_seconds=1000.0,
        )
        stream_context = SimpleNamespace(
            stream_vibe="Conversa",
            last_event="Safe mode",
            live_observability={},
        )

        with patch(
            "bot.observability_state.time.monotonic",
            side_effect=[100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
        ):
            state.update_clips_auth_status(
                token_valid=True,
                scope_ok=True,
                timestamp=1_700_030_000.0,
            )
            state.record_token_usage(
                input_tokens=12,
                output_tokens=7,
                estimated_cost_usd=0.03,
                timestamp=1_700_030_001.0,
            )
            state.record_autonomy_goal(
                risk="medium",
                outcome="approved",
                details="scene update",
                timestamp=1_700_030_002.0,
            )
            state.record_auto_scene_update(
                update_types=["game", "vibe"],
                timestamp=1_700_030_003.0,
            )
            state.record_token_refresh(reason="manual", timestamp=1_700_030_004.0)
            state.record_auth_failure(
                details="expired token",
                timestamp=1_700_030_005.0,
            )
            state.record_error(
                category="vision",
                details="frame timeout",
                timestamp=1_700_030_006.0,
            )
            state.record_vision_frame(
                analysis="detected facecam motion",
                timestamp=1_700_030_007.0,
            )
            snapshot = state.snapshot(
                bot_brand="Byte",
                bot_version="1.5",
                bot_mode="irc",
                stream_context=stream_context,
                timestamp=1_700_030_010.0,
            )

        self.assertEqual(snapshot["metrics"]["token_input_total"], 12)
        self.assertEqual(snapshot["metrics"]["token_output_total"], 7)
        self.assertEqual(snapshot["metrics"]["token_refreshes_total"], 1)
        self.assertEqual(snapshot["metrics"]["auth_failures_total"], 1)
        self.assertEqual(snapshot["metrics"]["errors_total"], 2)
        self.assertEqual(snapshot["metrics"]["vision_frames_total"], 1)
        self.assertEqual(snapshot["metrics"]["auto_scene_updates_total"], 2)
        self.assertEqual(snapshot["context"]["clips_status"]["token_valid"], True)
        self.assertTrue(snapshot["persistence"]["enabled"])
        self.assertFalse(snapshot["persistence"]["restored"])
        self.assertTrue(snapshot["persistence"]["dirty"])


if __name__ == "__main__":
    unittest.main()
