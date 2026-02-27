from unittest.mock import MagicMock

import pytest

from bot.persistence_revenue_attribution_repository import RevenueAttributionRepository


@pytest.fixture
def repo():
    return RevenueAttributionRepository(enabled=False, client=None, cache={})


def test_save_and_load_conversion_sync(repo):
    conv_in = {
        "event_type": "cheer",
        "viewer_login": "cheerer",
        "revenue_value": 1.0,
        "currency": "USD",
    }

    saved = repo.save_conversion_sync("canal_x", conv_in)
    assert saved["event_type"] == "cheer"
    assert saved["source"] == "memory"
    assert saved["channel_id"] == "canal_x"

    loaded = repo.load_recent_conversions_sync("canal_x")
    assert len(loaded) == 1
    assert loaded[0]["viewer_login"] == "cheerer"


def test_load_recent_conversions_empty(repo):
    loaded = repo.load_recent_conversions_sync("empty_channel")
    assert loaded == []
