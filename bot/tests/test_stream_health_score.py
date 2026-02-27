from bot.stream_health_score import STREAM_HEALTH_VERSION, build_stream_health_score


def test_build_stream_health_score_returns_excellent_band_for_healthy_channel():
    payload = build_stream_health_score(
        sentiment={
            "avg": 2.0,
            "count": 20,
            "positive": 18,
            "negative": 1,
        },
        chat_analytics={
            "messages_60m": 100,
            "byte_triggers_60m": 6,
            "messages_per_minute_60m": 1.2,
        },
        agent_outcomes={
            "llm_interactions_60m": 20,
            "quality_retry_60m": 0,
            "quality_fallback_60m": 0,
        },
        timeline=[{"errors": 0}, {"errors": 0}],
    )

    assert payload["version"] == STREAM_HEALTH_VERSION
    assert payload["score"] == 100
    assert payload["band"] == "excellent"
    assert payload["components"]["trigger_hit_rate"]["ratio"] == 0.06
    assert payload["components"]["anomalies"]["events"] == 0


def test_build_stream_health_score_returns_stable_band_for_mid_high_signal():
    payload = build_stream_health_score(
        sentiment={
            "avg": 1.0,
            "count": 12,
            "positive": 9,
            "negative": 2,
        },
        chat_analytics={
            "messages_60m": 100,
            "byte_triggers_60m": 9,
            "messages_per_minute_60m": 0.74,
        },
        agent_outcomes={
            "llm_interactions_60m": 20,
            "quality_retry_60m": 10,
            "quality_fallback_60m": 3,
        },
        timeline=[],
    )

    assert payload["score"] == 75
    assert payload["band"] == "stable"


def test_build_stream_health_score_returns_watch_band_for_declining_signal():
    payload = build_stream_health_score(
        sentiment={
            "avg": 0.2,
            "count": 8,
            "positive": 4,
            "negative": 3,
        },
        chat_analytics={
            "messages_60m": 100,
            "byte_triggers_60m": 12,
            "messages_per_minute_60m": 0.37,
        },
        agent_outcomes={
            "llm_interactions_60m": 0,
            "quality_retry_60m": 12,
            "quality_fallback_60m": 8,
        },
        timeline=[],
    )

    assert payload["score"] == 54
    assert payload["band"] == "watch"


def test_build_stream_health_score_is_defensive_with_invalid_input():
    payload = build_stream_health_score(
        sentiment={"avg": "invalid"},
        chat_analytics={
            "messages_60m": "0",
            "byte_triggers_60m": 5,
            "messages_per_minute_60m": -5,
        },
        agent_outcomes={
            "llm_interactions_60m": None,
            "quality_retry_60m": "4",
            "quality_fallback_60m": "3",
        },
        timeline=[{"errors": "8"}],
    )

    assert payload["score"] == 15
    assert payload["band"] == "critical"
    assert payload["components"]["sentiment"]["score"] == 50.0
    assert payload["components"]["trigger_hit_rate"]["ratio"] == 0.0
    assert payload["components"]["anomalies"]["events"] == 15
