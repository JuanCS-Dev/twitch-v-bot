from bot.post_stream_report import REPORT_VERSION, build_post_stream_report


def test_build_post_stream_report_uses_history_and_snapshot_outcomes():
    history_points = [
        {
            "channel_id": "canal_a",
            "captured_at": "2026-02-27T20:00:00Z",
            "metrics": {
                "chat_messages_total": 12,
                "byte_triggers_total": 3,
                "replies_total": 4,
                "llm_interactions_total": 4,
                "errors_total": 0,
            },
            "chatters": {"unique_total": 8, "active_60m": 2},
            "sentiment": {"vibe": "Hyped", "avg": 1.1},
            "stream_health": {"score": 71, "band": "stable"},
        },
        {
            "channel_id": "canal_a",
            "captured_at": "2026-02-27T20:30:00Z",
            "metrics": {
                "chat_messages_total": 30,
                "byte_triggers_total": 7,
                "replies_total": 8,
                "llm_interactions_total": 8,
                "errors_total": 2,
            },
            "chatters": {"unique_total": 13, "active_60m": 5},
            "sentiment": {"vibe": "Hyped", "avg": 1.3},
            "stream_health": {"score": 52, "band": "watch"},
        },
    ]
    observability_snapshot = {
        "metrics": {"estimated_cost_usd_total": 0.55},
        "agent_outcomes": {
            "decisions_total_60m": 10,
            "approved_total_60m": 4,
            "rejected_total_60m": 3,
            "ignored_total_60m": 3,
            "ignored_rate_60m": 30.0,
            "useful_engagement_rate_60m": 40.0,
            "token_input_60m": 1200,
            "token_output_60m": 900,
            "estimated_cost_usd_60m": 0.42,
            "estimated_cost_usd_total": 0.55,
        },
    }

    report = build_post_stream_report(
        channel_id="Canal_A",
        history_points=history_points,
        observability_snapshot=observability_snapshot,
        generated_at="2026-02-27T20:40:00Z",
        trigger="manual_dashboard",
    )

    assert report["report_version"] == REPORT_VERSION
    assert report["channel_id"] == "canal_a"
    assert report["history_window"]["points"] == 2
    assert report["history_window"]["first_captured_at"] == "2026-02-27T20:00:00Z"
    assert report["history_window"]["last_captured_at"] == "2026-02-27T20:30:00Z"
    assert report["traffic"]["chat_messages_total"] == 30
    assert report["traffic"]["chat_messages_delta"] == 18
    assert report["traffic"]["errors_delta"] == 2
    assert report["stream_health"]["latest_band"] == "watch"
    assert report["stream_health"]["average_score"] == 61.5
    assert report["decisions_60m"]["total"] == 10
    assert report["decisions_60m"]["approval_rate"] == 40.0
    assert report["cost"]["estimated_cost_usd_60m"] == 0.42
    assert "Canal #canal_a encerrou com stream health 52/100" in report["narrative"]
    assert len(report["recommendations"]) > 0


def test_build_post_stream_report_falls_back_to_snapshot_when_no_history():
    report = build_post_stream_report(
        channel_id="canal_b",
        history_points=[],
        observability_snapshot={
            "metrics": {
                "chat_messages_total": 4,
                "replies_total": 2,
                "errors_total": 0,
                "llm_interactions_total": 2,
                "estimated_cost_usd_total": 0.01,
            },
            "chatters": {"active_60m": 1, "unique_total": 2},
            "sentiment": {"vibe": "Chill", "avg": 0.2},
            "stream_health": {"score": 88, "band": "excellent"},
            "agent_outcomes": {
                "decisions_total_60m": 0,
                "approved_total_60m": 0,
                "rejected_total_60m": 0,
                "ignored_total_60m": 0,
                "ignored_rate_60m": 0.0,
                "useful_engagement_rate_60m": 0.0,
                "token_input_60m": 12,
                "token_output_60m": 18,
                "estimated_cost_usd_60m": 0.01,
            },
        },
        trigger="manual_dashboard",
    )

    assert report["history_window"]["points"] == 0
    assert report["history_window"]["first_captured_at"] == ""
    assert report["traffic"]["chat_messages_total"] == 4
    assert report["stream_health"]["latest_score"] == 88
    assert report["stream_health"]["latest_band"] == "excellent"
    assert report["sentiment"]["dominant_vibe"] == "Chill"
    assert report["decisions_60m"]["total"] == 0
    assert report["cost"]["token_input_60m"] == 12
