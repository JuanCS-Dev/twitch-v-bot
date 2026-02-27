from bot.semantic_memory import (
    EMBEDDING_DIMENSIONS,
    cosine_similarity,
    embed_text,
    rank_semantic_matches,
)


def test_embed_text_is_deterministic_and_normalized():
    first = embed_text("Lore spoiler control")
    second = embed_text("Lore spoiler control")

    assert len(first) == EMBEDDING_DIMENSIONS
    assert first == second
    magnitude = sum(value * value for value in first) ** 0.5
    assert abs(magnitude - 1.0) < 1e-6


def test_cosine_similarity_handles_empty_or_mismatched_vectors():
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0], []) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


def test_rank_semantic_matches_orders_by_similarity_and_limits_result():
    entries = [
        {
            "entry_id": "a",
            "content": "Streamer prefere lore sem spoiler",
            "updated_at": "2026-02-27T21:00:00Z",
        },
        {
            "entry_id": "b",
            "content": "Canal foca em speedrun competitivo",
            "updated_at": "2026-02-27T21:01:00Z",
        },
    ]

    matches = rank_semantic_matches(
        query_text="lore",
        entries=entries,
        limit=1,
    )

    assert len(matches) == 1
    assert matches[0]["entry_id"] == "a"
    assert "similarity" in matches[0]
