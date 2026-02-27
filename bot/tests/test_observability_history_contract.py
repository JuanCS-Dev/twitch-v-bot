from bot.observability_history_contract import normalize_observability_history_point


def test_normalize_observability_history_point_defaults_when_payload_missing():
    normalized = normalize_observability_history_point(None)

    assert normalized["channel_id"] == "default"
    assert normalized["captured_at"] == ""
    assert normalized["metrics"]["chat_messages_total"] == 0
    assert normalized["metrics"]["byte_triggers_total"] == 0
    assert normalized["metrics"]["replies_total"] == 0
    assert normalized["metrics"]["llm_interactions_total"] == 0
    assert normalized["metrics"]["errors_total"] == 0
    assert normalized["chatters"]["unique_total"] == 0
    assert normalized["chatters"]["active_60m"] == 0
    assert normalized["chat_analytics"]["messages_60m"] == 0
    assert normalized["chat_analytics"]["byte_triggers_60m"] == 0
    assert normalized["chat_analytics"]["messages_per_minute_60m"] == 0.0
    assert normalized["agent_outcomes"]["useful_engagement_rate_60m"] == 0.0
    assert normalized["agent_outcomes"]["ignored_rate_60m"] == 0.0
    assert normalized["sentiment"]["vibe"] == "Chill"
    assert normalized["sentiment"]["avg"] == 0.0
    assert normalized["sentiment"]["count"] == 0
    assert normalized["stream_health"]["version"] == "v1"
    assert normalized["stream_health"]["score"] == 0
    assert normalized["stream_health"]["band"] == "critical"
    assert normalized["context"]["last_prompt"] == ""
    assert normalized["context"]["last_reply"] == ""


def test_normalize_observability_history_point_applies_channel_and_captured_overrides():
    normalized = normalize_observability_history_point(
        {
            "channel_id": "payload_channel",
            "captured_at": "2026-02-27T17:00:00Z",
            "metrics": {"chat_messages_total": "9"},
        },
        channel_id="canal_a",
        captured_at="2026-02-27T18:00:00Z",
    )

    assert normalized["channel_id"] == "canal_a"
    assert normalized["captured_at"] == "2026-02-27T18:00:00Z"
    assert normalized["metrics"]["chat_messages_total"] == 9


def test_normalize_observability_history_point_uses_timestamp_and_default_fallbacks():
    with_timestamp = normalize_observability_history_point(
        {"timestamp": "2026-02-27T19:00:00Z"},
        channel_id="canal_a",
        use_timestamp_fallback=True,
    )
    with_default = normalize_observability_history_point(
        {},
        channel_id="canal_a",
        fallback_captured_at="2026-02-27T20:00:00Z",
        use_timestamp_fallback=True,
    )

    assert with_timestamp["captured_at"] == "2026-02-27T19:00:00Z"
    assert with_default["captured_at"] == "2026-02-27T20:00:00Z"


def test_normalize_observability_history_point_clamps_stream_health_and_coerces_sentiment():
    normalized = normalize_observability_history_point(
        {
            "channel_id": "canal_z",
            "sentiment": {
                "vibe": "Hyped",
                "avg": "1.25",
                "count": "9",
                "positive": "7",
                "negative": "2",
            },
            "stream_health": {
                "version": "",
                "score": "140",
                "band": "unknown-band",
            },
        }
    )

    assert normalized["sentiment"] == {
        "vibe": "Hyped",
        "avg": 1.25,
        "count": 9,
        "positive": 7,
        "negative": 2,
    }
    assert normalized["stream_health"] == {
        "version": "v1",
        "score": 100,
        "band": "critical",
    }
