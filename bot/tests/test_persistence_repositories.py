import os
from unittest.mock import patch

from bot.persistence_agent_notes_repository import AgentNotesRepository
from bot.persistence_channel_config_repository import ChannelConfigRepository
from bot.persistence_layer import PersistenceLayer
from bot.persistence_observability_history_repository import ObservabilityHistoryRepository


def test_channel_config_repository_memory_roundtrip_when_disabled():
    cache: dict[str, dict[str, object]] = {}
    repository = ChannelConfigRepository(enabled=False, client=None, cache=cache)

    saved = repository.save_sync("Canal_A", temperature=0.37, top_p=0.83, agent_paused=False)
    loaded = repository.load_sync("canal_a")

    assert saved["channel_id"] == "canal_a"
    assert saved["source"] == "memory"
    assert loaded["temperature"] == 0.37
    assert loaded["top_p"] == 0.83
    assert loaded["has_override"] is True


def test_agent_notes_repository_sanitizes_text_and_marks_has_notes():
    cache: dict[str, dict[str, object]] = {}
    repository = AgentNotesRepository(enabled=False, client=None, cache=cache)

    saved = repository.save_sync("Canal_A", notes="  Priorize lore.  \r\nSem backseat.  ")
    loaded = repository.load_sync("canal_a")

    assert saved["channel_id"] == "canal_a"
    assert saved["notes"] == "Priorize lore.\nSem backseat."
    assert saved["has_notes"] is True
    assert loaded["notes"] == "Priorize lore.\nSem backseat."


def test_observability_history_repository_memory_timeline_and_latest_snapshots():
    cache: dict[str, list[dict[str, object]]] = {}
    repository = ObservabilityHistoryRepository(enabled=False, client=None, cache=cache)

    repository.save_channel_history_sync(
        "Canal_A",
        {"captured_at": "2026-02-27T17:00:00Z", "metrics": {"chat_messages_total": 10}},
    )
    repository.save_channel_history_sync(
        "Canal_A",
        {"captured_at": "2026-02-27T17:10:00Z", "metrics": {"chat_messages_total": 11}},
    )
    repository.save_channel_history_sync(
        "Canal_B",
        {"captured_at": "2026-02-27T17:12:00Z", "metrics": {"chat_messages_total": 3}},
    )

    channel_timeline = repository.load_channel_history_sync("canal_a", limit=2)
    latest = repository.load_latest_snapshots_sync(limit=2)

    assert channel_timeline[0]["metrics"]["chat_messages_total"] == 11
    assert channel_timeline[1]["metrics"]["chat_messages_total"] == 10
    assert latest[0]["channel_id"] == "canal_b"
    assert latest[1]["channel_id"] == "canal_a"


def test_persistence_layer_facade_shares_repository_caches():
    with patch.dict(os.environ, {}, clear=True):
        layer = PersistenceLayer()

    assert layer._channel_config_repo._cache is layer._channel_config_cache
    assert layer._agent_notes_repo._cache is layer._agent_notes_cache
    assert layer._observability_history_repo._cache is layer._observability_channel_history_cache
