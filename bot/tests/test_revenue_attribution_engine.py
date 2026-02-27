from unittest.mock import MagicMock

import pytest

from bot.revenue_attribution_engine import RevenueAttributionEngine


@pytest.fixture
def mock_persistence():
    return MagicMock()


@pytest.fixture
def engine(mock_persistence):
    return RevenueAttributionEngine(mock_persistence)


def test_process_conversion_with_attribution(engine, mock_persistence):
    mock_persistence.load_observability_channel_history_sync.return_value = [
        {"timestamp": "2026-02-27T18:30:00Z", "state": {"last_action": "clip_generated"}}
    ]
    mock_persistence.save_revenue_conversion_sync.return_value = {"saved": True}

    conversion = engine.process_conversion(
        channel_id="canal_test",
        event_type="sub",
        viewer_id="v1",
        viewer_login="viewer1",
        revenue_value=4.99,
        timestamp="2026-02-27T18:32:00Z",  # 2 minutes later
    )

    assert conversion == {"saved": True}

    # Verify the argument passed to save_revenue_conversion_sync
    saved_arg = mock_persistence.save_revenue_conversion_sync.call_args[0][1]
    assert saved_arg["attributed_action_type"] == "clip_generated"
    assert saved_arg["attribution_window_seconds"] == 120  # 2 minutes
    assert saved_arg["viewer_login"] == "viewer1"


def test_process_conversion_without_attribution(engine, mock_persistence):
    mock_persistence.load_observability_channel_history_sync.return_value = [
        {
            "timestamp": "2026-02-27T18:00:00Z",  # Out of 5 min window
            "state": {"last_action": "clip_generated"},
        }
    ]
    mock_persistence.load_recent_history_sync.return_value = []
    mock_persistence.save_revenue_conversion_sync.return_value = {"saved": True}

    engine.process_conversion(
        channel_id="canal_test",
        event_type="follow",
        viewer_id="v2",
        viewer_login="viewer2",
        revenue_value=0.0,
        timestamp="2026-02-27T18:32:00Z",
    )

    saved_arg = mock_persistence.save_revenue_conversion_sync.call_args[0][1]
    assert saved_arg["attributed_action_type"] == ""
    assert saved_arg["attribution_window_seconds"] == 0
