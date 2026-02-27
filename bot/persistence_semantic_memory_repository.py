from __future__ import annotations

import logging
import uuid
from typing import Any

from supabase import Client

from bot.persistence_utils import (
    coerce_history_limit,
    normalize_channel_id,
    normalize_optional_text,
    utc_iso_now,
)
from bot.semantic_memory import EMBEDDING_DIMENSIONS, embed_text, rank_semantic_matches

logger = logging.getLogger("byte.persistence")

ALLOWED_MEMORY_TYPES = {"fact", "preference", "event", "instruction", "context"}


class SemanticMemoryRepository:
    def __init__(
        self,
        *,
        enabled: bool,
        client: Client | None,
        cache: dict[str, list[dict[str, Any]]],
    ) -> None:
        self._enabled = enabled
        self._client = client
        self._cache = cache

    def _normalize_memory_type(self, memory_type: Any) -> str:
        normalized = str(memory_type or "fact").strip().lower() or "fact"
        if normalized not in ALLOWED_MEMORY_TYPES:
            return "fact"
        return normalized

    def _normalize_tags(self, tags: Any) -> list[str]:
        if tags in (None, ""):
            return []
        values: list[Any]
        if isinstance(tags, str):
            values = tags.split(",")
        elif isinstance(tags, list | tuple | set):
            values = list(tags)
        else:
            values = [tags]

        normalized_tags: list[str] = []
        for value in values:
            normalized = str(value or "").strip().lower()
            if not normalized:
                continue
            cleaned = normalize_optional_text(
                normalized,
                field_name="semantic_memory_tag",
                max_length=32,
            )
            if not cleaned:
                continue
            normalized_tags.append(cleaned.replace(" ", "_"))
        unique_tags = list(dict.fromkeys(normalized_tags))
        return unique_tags[:12]

    def _normalize_context(self, context: Any) -> dict[str, Any]:
        if context in (None, ""):
            return {}
        if not isinstance(context, dict):
            raise ValueError("semantic_memory_context invalido.")
        payload: dict[str, Any] = {}
        for raw_key, raw_value in list(context.items())[:20]:
            key = str(raw_key or "").strip().lower()
            if not key:
                continue
            key = key.replace(" ", "_")[:40]
            if isinstance(raw_value, bool | int | float):
                payload[key] = raw_value
                continue
            if raw_value is None:
                payload[key] = None
                continue
            payload[key] = normalize_optional_text(
                raw_value,
                field_name="semantic_memory_context_value",
                max_length=180,
            )
        return payload

    def _normalize_embedding(self, embedding: Any, content: str) -> list[float]:
        if (
            isinstance(embedding, list)
            and len(embedding) == EMBEDDING_DIMENSIONS
            and all(isinstance(value, int | float) for value in embedding)
        ):
            return [float(value) for value in embedding]
        return embed_text(content, dimensions=EMBEDDING_DIMENSIONS)

    def _normalize_entry(self, channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        content = normalize_optional_text(
            payload.get("content"),
            field_name="semantic_memory_content",
            max_length=1200,
        )
        if not content:
            raise ValueError("semantic_memory_content obrigatorio.")

        created_at = str(payload.get("created_at") or utc_iso_now())
        updated_at = str(payload.get("updated_at") or created_at or utc_iso_now())
        entry_id = str(payload.get("entry_id") or "").strip().lower() or uuid.uuid4().hex
        return {
            "entry_id": entry_id,
            "channel_id": channel_id,
            "memory_type": self._normalize_memory_type(payload.get("memory_type")),
            "content": content,
            "tags": self._normalize_tags(payload.get("tags")),
            "context": self._normalize_context(payload.get("context")),
            "embedding": self._normalize_embedding(payload.get("embedding"), content),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def _sorted_entries(
        self,
        channel_id: str,
        *,
        source: str,
    ) -> list[dict[str, Any]]:
        rows = list(self._cache.get(channel_id, []))
        normalized = [{**dict(row or {}), "source": source} for row in rows]
        normalized.sort(
            key=lambda row: (
                str(row.get("updated_at") or ""),
                str(row.get("entry_id") or ""),
            ),
            reverse=True,
        )
        return normalized

    def save_entry_sync(
        self,
        channel_id: str,
        *,
        content: Any,
        memory_type: Any = "fact",
        tags: Any = None,
        context: Any = None,
        entry_id: Any = None,
    ) -> dict[str, Any]:
        normalized_channel = normalize_channel_id(channel_id)
        if not normalized_channel:
            raise ValueError("channel_id obrigatorio.")

        current_entries = [dict(item or {}) for item in self._cache.get(normalized_channel, [])]
        now_iso = utc_iso_now()
        normalized_payload = self._normalize_entry(
            normalized_channel,
            {
                "entry_id": entry_id,
                "memory_type": memory_type,
                "content": content,
                "tags": tags,
                "context": context,
                "updated_at": now_iso,
                "created_at": now_iso,
            },
        )

        replacement_index = next(
            (
                index
                for index, existing in enumerate(current_entries)
                if str(existing.get("entry_id") or "") == normalized_payload["entry_id"]
            ),
            -1,
        )
        if replacement_index >= 0:
            normalized_payload["created_at"] = str(
                current_entries[replacement_index].get("created_at") or now_iso
            )
            current_entries[replacement_index] = normalized_payload
        else:
            current_entries.append(normalized_payload)
        self._cache[normalized_channel] = current_entries[-360:]
        memory_payload = {**normalized_payload, "source": "memory"}

        if not self._enabled or not self._client:
            return memory_payload

        try:
            self._client.table("semantic_memory_entries").upsert(
                {
                    "channel_id": normalized_channel,
                    "entry_id": normalized_payload["entry_id"],
                    "memory_type": normalized_payload["memory_type"],
                    "content": normalized_payload["content"],
                    "tags": normalized_payload["tags"],
                    "context": normalized_payload["context"],
                    "embedding": normalized_payload["embedding"],
                    "created_at": normalized_payload["created_at"],
                    "updated_at": "now()",
                }
            ).execute()
            return {**normalized_payload, "source": "supabase"}
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao salvar semantic_memory de %s: %s",
                normalized_channel,
                error,
            )
            return memory_payload

    def load_channel_entries_sync(
        self,
        channel_id: str,
        *,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        normalized_channel = normalize_channel_id(channel_id) or "default"
        safe_limit = coerce_history_limit(limit, default=12, maximum=120)
        if not self._enabled or not self._client:
            return self._sorted_entries(normalized_channel, source="memory")[:safe_limit]

        try:
            result = (
                self._client.table("semantic_memory_entries")
                .select(
                    "entry_id, channel_id, memory_type, content, tags, context, embedding, created_at, updated_at"
                )
                .eq("channel_id", normalized_channel)
                .order("updated_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
            rows = list(result.data or [])
            normalized_entries: list[dict[str, Any]] = []
            for row in rows:
                try:
                    entry = self._normalize_entry(
                        normalized_channel,
                        {
                            "entry_id": row.get("entry_id"),
                            "memory_type": row.get("memory_type"),
                            "content": row.get("content"),
                            "tags": row.get("tags"),
                            "context": row.get("context"),
                            "embedding": row.get("embedding"),
                            "created_at": row.get("created_at"),
                            "updated_at": row.get("updated_at"),
                        },
                    )
                    normalized_entries.append(entry)
                except ValueError:
                    continue
            self._cache[normalized_channel] = normalized_entries
            return [{**entry, "source": "supabase"} for entry in normalized_entries[:safe_limit]]
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao carregar semantic_memory de %s: %s",
                normalized_channel,
                error,
            )
            return self._sorted_entries(normalized_channel, source="memory")[:safe_limit]

    def search_entries_sync(
        self,
        channel_id: str,
        *,
        query: Any,
        limit: int = 5,
        search_limit: int = 60,
    ) -> list[dict[str, Any]]:
        safe_query = normalize_optional_text(
            query,
            field_name="semantic_memory_query",
            max_length=220,
        )
        if not safe_query:
            return []
        safe_limit = coerce_history_limit(limit, default=5, maximum=20)
        safe_search_limit = coerce_history_limit(search_limit, default=60, maximum=360)
        candidates = self.load_channel_entries_sync(channel_id, limit=safe_search_limit)
        ranked = rank_semantic_matches(
            query_text=safe_query,
            entries=candidates,
            limit=safe_limit,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return ranked
