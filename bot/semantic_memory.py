from __future__ import annotations

import hashlib
import math
import re
from typing import Any

EMBEDDING_DIMENSIONS = 48
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _normalize_dimensions(dimensions: Any) -> int:
    try:
        parsed = int(dimensions)
    except (TypeError, ValueError):
        return EMBEDDING_DIMENSIONS
    if parsed < 8:
        return 8
    if parsed > 256:
        return 256
    return parsed


def _tokenize(text: str) -> list[str]:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return []
    return _TOKEN_RE.findall(normalized)


def embed_text(text: str, *, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    safe_dimensions = _normalize_dimensions(dimensions)
    vector = [0.0] * safe_dimensions
    tokens = _tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % safe_dimensions
        sign_bit = int.from_bytes(digest[4:], "big") % 2
        sign = 1.0 if sign_bit == 0 else -1.0
        weight = 1.0 + min(len(token), 16) / 16.0
        vector[bucket] += sign * weight

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 0.0:
        return [0.0] * safe_dimensions
    return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))


def rank_semantic_matches(
    *,
    query_text: str,
    entries: list[dict[str, Any]],
    limit: int = 5,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> list[dict[str, Any]]:
    safe_query = str(query_text or "").strip()
    if not safe_query:
        return []
    safe_limit = max(1, min(int(limit or 5), 20))
    query_embedding = embed_text(safe_query, dimensions=dimensions)
    ranked: list[dict[str, Any]] = []

    for index, entry in enumerate(list(entries or [])):
        item = dict(entry or {})
        embedding = item.get("embedding")
        if (
            not isinstance(embedding, list)
            or len(embedding) != len(query_embedding)
            or not all(isinstance(value, int | float) for value in embedding)
        ):
            embedding = embed_text(str(item.get("content") or ""), dimensions=len(query_embedding))
            item["embedding"] = embedding
        score = cosine_similarity(query_embedding, embedding)
        item["similarity"] = round(float(score), 6)
        item["_index"] = index
        ranked.append(item)

    ranked.sort(
        key=lambda row: (
            -float(row.get("similarity") or 0.0),
            str(row.get("updated_at") or ""),
            -int(row.get("_index", 0)),
        ),
        reverse=False,
    )
    top_entries = ranked[:safe_limit]
    for row in top_entries:
        row.pop("_index", None)
    return top_entries
