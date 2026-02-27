from unittest.mock import patch

from bot.coaching_runtime import CoachingRuntime


def _high_risk_snapshot() -> dict:
    return {
        "chat_analytics": {
            "messages_per_minute_10m": 0.05,
            "messages_per_minute_60m": 0.90,
        },
        "chatters": {
            "active_10m": 2,
            "active_60m": 14,
        },
        "agent_outcomes": {
            "ignored_rate_60m": 44.0,
            "llm_interactions_60m": 11,
            "quality_fallback_60m": 5,
        },
        "sentiment": {
            "avg": -0.9,
            "count": 16,
        },
        "stream_health": {
            "score": 41,
        },
    }


def _low_risk_snapshot() -> dict:
    return {
        "chat_analytics": {
            "messages_per_minute_10m": 0.72,
            "messages_per_minute_60m": 0.74,
        },
        "chatters": {
            "active_10m": 12,
            "active_60m": 13,
        },
        "agent_outcomes": {
            "ignored_rate_60m": 10.0,
            "llm_interactions_60m": 13,
            "quality_fallback_60m": 1,
        },
        "sentiment": {
            "avg": 0.8,
            "count": 18,
        },
        "stream_health": {
            "score": 90,
        },
    }


@patch("bot.coaching_runtime.hud_runtime")
def test_evaluate_and_emit_applies_cooldown_antinoise(mock_hud_runtime):
    runtime = CoachingRuntime(cooldown_seconds=120)

    first = runtime.evaluate_and_emit(
        _high_risk_snapshot(),
        channel_id="Canal_A",
        now=1_000.0,
    )
    assert first["channel_id"] == "canal_a"
    assert first["risk_band"] in {"high", "critical"}
    assert first["has_alerts"] is True
    assert first["hud"]["emitted"] is True
    assert first["hud"]["suppressed"] is False
    assert first["hud"]["suppressed_total"] == 0
    assert first["hud"]["last_emitted_at"] == "1970-01-01T00:16:40Z"
    assert first["hud"]["signature"]
    assert mock_hud_runtime.push_message.call_count == 1
    assert mock_hud_runtime.push_message.call_args.kwargs["source"] == "coaching"

    second = runtime.evaluate_and_emit(
        _high_risk_snapshot(),
        channel_id="canal_a",
        now=1_060.0,
    )
    assert second["hud"]["emitted"] is False
    assert second["hud"]["suppressed"] is True
    assert second["hud"]["suppressed_total"] == 1
    assert second["hud"]["last_emitted_at"] == "1970-01-01T00:16:40Z"
    assert mock_hud_runtime.push_message.call_count == 1

    third = runtime.evaluate_and_emit(
        _high_risk_snapshot(),
        channel_id="canal_a",
        now=1_130.0,
    )
    assert third["hud"]["emitted"] is True
    assert third["hud"]["suppressed"] is False
    assert third["hud"]["suppressed_total"] == 1
    assert third["hud"]["last_emitted_at"] == "1970-01-01T00:18:50Z"
    assert mock_hud_runtime.push_message.call_count == 2


@patch("bot.coaching_runtime.hud_runtime")
def test_evaluate_and_emit_isolated_per_channel(mock_hud_runtime):
    runtime = CoachingRuntime(cooldown_seconds=120)

    first = runtime.evaluate_and_emit(
        _high_risk_snapshot(),
        channel_id="Canal_A",
        now=2_000.0,
    )
    second = runtime.evaluate_and_emit(
        _high_risk_snapshot(),
        channel_id="Canal_B",
        now=2_010.0,
    )

    assert first["channel_id"] == "canal_a"
    assert second["channel_id"] == "canal_b"
    assert first["hud"]["emitted"] is True
    assert second["hud"]["emitted"] is True
    assert mock_hud_runtime.push_message.call_count == 2


@patch("bot.coaching_runtime.hud_runtime")
def test_evaluate_and_emit_skips_hud_when_risk_is_low(mock_hud_runtime):
    runtime = CoachingRuntime(cooldown_seconds=120)

    payload = runtime.evaluate_and_emit(
        _low_risk_snapshot(),
        channel_id="Canal_Low",
        now=3_000.0,
    )

    assert payload["channel_id"] == "canal_low"
    assert payload["risk_band"] == "low"
    assert payload["has_alerts"] is False
    assert payload["hud"]["emitted"] is False
    assert payload["hud"]["suppressed"] is False
    assert payload["hud"]["last_emitted_at"] == ""
    assert payload["hud"]["suppressed_total"] == 0
    mock_hud_runtime.push_message.assert_not_called()
