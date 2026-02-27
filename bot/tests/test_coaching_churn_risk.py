from bot.coaching_churn_risk import build_coaching_signature, build_viewer_churn_payload


def test_build_viewer_churn_payload_high_risk_with_alerts():
    payload = build_viewer_churn_payload(
        {
            "chat_analytics": {
                "messages_per_minute_10m": 0.06,
                "messages_per_minute_60m": 0.82,
            },
            "chatters": {
                "active_10m": 2,
                "active_60m": 13,
            },
            "agent_outcomes": {
                "ignored_rate_60m": 47.0,
                "llm_interactions_60m": 10,
                "quality_fallback_60m": 5,
            },
            "sentiment": {
                "avg": -1.1,
                "count": 14,
            },
            "stream_health": {
                "score": 39,
            },
        }
    )

    assert payload["version"] == "viewer_churn_risk_v1"
    assert payload["risk_score"] >= 60
    assert payload["risk_band"] in {"high", "critical"}
    assert payload["has_alerts"] is True
    assert payload["primary_alert"] is not None
    assert any(alert["id"] == "chat_velocity_drop" for alert in payload["alerts"])


def test_build_viewer_churn_payload_low_risk_without_alerts():
    payload = build_viewer_churn_payload(
        {
            "chat_analytics": {
                "messages_per_minute_10m": 0.71,
                "messages_per_minute_60m": 0.75,
            },
            "chatters": {
                "active_10m": 11,
                "active_60m": 13,
            },
            "agent_outcomes": {
                "ignored_rate_60m": 9.0,
                "llm_interactions_60m": 12,
                "quality_fallback_60m": 1,
            },
            "sentiment": {
                "avg": 0.7,
                "count": 25,
            },
            "stream_health": {
                "score": 89,
            },
        }
    )

    assert payload["risk_band"] == "low"
    assert payload["risk_score"] < 35
    assert payload["has_alerts"] is False
    assert payload["alerts"] == []
    assert payload["primary_alert"] is None


def test_build_coaching_signature_is_stable_for_same_payload():
    payload = build_viewer_churn_payload(
        {
            "chat_analytics": {
                "messages_per_minute_10m": 0.19,
                "messages_per_minute_60m": 0.77,
            },
            "chatters": {
                "active_10m": 3,
                "active_60m": 9,
            },
            "agent_outcomes": {
                "ignored_rate_60m": 40.0,
                "llm_interactions_60m": 8,
                "quality_fallback_60m": 2,
            },
        }
    )
    signature_a = build_coaching_signature(payload)
    signature_b = build_coaching_signature(payload)

    assert signature_a == signature_b
    assert signature_a
