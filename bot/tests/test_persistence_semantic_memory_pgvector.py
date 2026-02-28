from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from bot.persistence_semantic_memory_repository import SemanticMemoryRepository


def _mock_supabase_memory_rows(mock_client: MagicMock, rows: list[dict[str, object]]) -> None:
    table = mock_client.table.return_value
    select_chain = table.select.return_value.eq.return_value.order.return_value.limit.return_value
    select_chain.execute.return_value = MagicMock(data=rows)


def test_semantic_memory_search_uses_pgvector_rpc_when_available():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value = MagicMock(
        data=[
            {
                "entry_id": "entry_pg_1",
                "channel_id": "canal_a",
                "memory_type": "fact",
                "content": "Canal prioriza lore sem spoiler.",
                "tags": ["lore"],
                "context": {"source": "runtime"},
                "embedding": [0.0] * 48,
                "created_at": "2026-02-28T13:00:00Z",
                "updated_at": "2026-02-28T13:02:00Z",
                "distance": 0.09,
            }
        ]
    )

    with patch.dict(
        os.environ,
        {"SEMANTIC_MEMORY_PGVECTOR_RPC": "semantic_memory_match"},
        clear=False,
    ):
        repository = SemanticMemoryRepository(enabled=True, client=mock_client, cache={})

    matches = repository.search_entries_sync(
        "Canal_A",
        query="lore",
        limit=3,
        search_limit=20,
    )

    assert len(matches) == 1
    assert matches[0]["entry_id"] == "entry_pg_1"
    assert matches[0]["source"] == "supabase_pgvector"
    assert matches[0]["similarity"] == 0.91
    assert mock_client.rpc.call_count == 1
    assert mock_client.rpc.call_args.args[0] == "semantic_memory_match"
    mock_client.table.assert_not_called()


def test_semantic_memory_search_falls_back_to_python_ranking_when_rpc_fails():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = RuntimeError("rpc unavailable")
    _mock_supabase_memory_rows(
        mock_client,
        [
            {
                "entry_id": "entry_legacy_1",
                "channel_id": "canal_a",
                "memory_type": "fact",
                "content": "Canal prioriza lore sem spoiler.",
                "tags": ["lore"],
                "context": {"source": "runtime"},
                "embedding": [0.0] * 48,
                "created_at": "2026-02-28T12:00:00Z",
                "updated_at": "2026-02-28T12:03:00Z",
            }
        ],
    )
    repository = SemanticMemoryRepository(enabled=True, client=mock_client, cache={})

    matches = repository.search_entries_sync(
        "Canal_A",
        query="lore",
        limit=2,
        search_limit=10,
    )

    assert matches
    assert matches[0]["entry_id"] == "entry_legacy_1"
    assert matches[0]["source"] == "supabase"
    assert "similarity" in matches[0]
    assert mock_client.rpc.call_count >= 1
    assert mock_client.table.called


def test_semantic_memory_search_skips_rpc_when_pgvector_is_disabled():
    mock_client = MagicMock()
    _mock_supabase_memory_rows(
        mock_client,
        [
            {
                "entry_id": "entry_plain_1",
                "channel_id": "canal_a",
                "memory_type": "fact",
                "content": "Canal valoriza clips de highlight com contexto.",
                "tags": ["clips"],
                "context": {"source": "manual"},
                "embedding": [0.0] * 48,
                "created_at": "2026-02-28T11:00:00Z",
                "updated_at": "2026-02-28T11:01:00Z",
            }
        ],
    )

    with patch.dict(
        os.environ,
        {"SEMANTIC_MEMORY_PGVECTOR_ENABLED": "0"},
        clear=False,
    ):
        repository = SemanticMemoryRepository(enabled=True, client=mock_client, cache={})

    matches = repository.search_entries_sync(
        "Canal_A",
        query="clips",
        limit=1,
        search_limit=5,
    )

    assert matches
    assert matches[0]["entry_id"] == "entry_plain_1"
    assert matches[0]["source"] == "supabase"
    mock_client.rpc.assert_not_called()


def test_semantic_memory_search_applies_min_similarity_threshold_with_pgvector():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value = MagicMock(
        data=[
            {
                "entry_id": "entry_high",
                "channel_id": "canal_a",
                "memory_type": "fact",
                "content": "Lore sem spoiler e foco narrativo.",
                "tags": ["lore"],
                "context": {"source": "runtime"},
                "embedding": [0.0] * 48,
                "created_at": "2026-02-28T13:00:00Z",
                "updated_at": "2026-02-28T13:02:00Z",
                "similarity": 0.88,
            },
            {
                "entry_id": "entry_low",
                "channel_id": "canal_a",
                "memory_type": "fact",
                "content": "Tema paralelo fora de contexto.",
                "tags": ["offtopic"],
                "context": {"source": "runtime"},
                "embedding": [0.0] * 48,
                "created_at": "2026-02-28T13:00:00Z",
                "updated_at": "2026-02-28T13:02:00Z",
                "similarity": 0.12,
            },
        ]
    )
    repository = SemanticMemoryRepository(enabled=True, client=mock_client, cache={})

    matches = repository.search_entries_sync(
        "canal_a",
        query="lore",
        limit=5,
        search_limit=20,
        min_similarity=0.5,
    )

    assert len(matches) == 1
    assert matches[0]["entry_id"] == "entry_high"
    assert matches[0]["similarity"] == 0.88
    assert mock_client.rpc.call_count == 1


def test_semantic_memory_search_diagnostics_force_fallback_skips_rpc():
    mock_client = MagicMock()
    _mock_supabase_memory_rows(
        mock_client,
        [
            {
                "entry_id": "entry_legacy_1",
                "channel_id": "canal_a",
                "memory_type": "fact",
                "content": "Canal prioriza lore sem spoiler.",
                "tags": ["lore"],
                "context": {"source": "runtime"},
                "embedding": [0.0] * 48,
                "created_at": "2026-02-28T12:00:00Z",
                "updated_at": "2026-02-28T12:03:00Z",
            }
        ],
    )
    repository = SemanticMemoryRepository(enabled=True, client=mock_client, cache={})

    payload = repository.search_entries_with_diagnostics_sync(
        "canal_a",
        query="lore",
        limit=2,
        search_limit=10,
        force_fallback=True,
    )

    assert payload["engine"] == "fallback"
    assert payload["force_fallback"] is True
    assert payload["result_count"] == 1
    assert payload["matches"][0]["entry_id"] == "entry_legacy_1"
    mock_client.rpc.assert_not_called()
