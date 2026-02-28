from __future__ import annotations

import logging
import os
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
DEFAULT_PGVECTOR_RPC_FUNCTIONS = (
    "semantic_memory_search_pgvector",
    "semantic_memory_search",
)


def _read_bool_env(var_name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return default
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


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
        self._pgvector_enabled = _read_bool_env(
            "SEMANTIC_MEMORY_PGVECTOR_ENABLED",
            default=True,
        )
        self._pgvector_rpc_functions = self._resolve_pgvector_rpc_functions()
        self._pgvector_warning_emitted = False

    def _normalize_memory_type(self, memory_type: Any) -> str:
        normalized = str(memory_type or "fact").strip().lower() or "fact"
        if normalized not in ALLOWED_MEMORY_TYPES:
            return "fact"
        return normalized

    def _resolve_pgvector_rpc_functions(self) -> tuple[str, ...]:
        configured = str(os.environ.get("SEMANTIC_MEMORY_PGVECTOR_RPC") or "").strip()
        if not configured:
            return DEFAULT_PGVECTOR_RPC_FUNCTIONS
        ordered = [configured]
        ordered.extend(
            function_name
            for function_name in DEFAULT_PGVECTOR_RPC_FUNCTIONS
            if function_name != configured
        )
        return tuple(ordered)

    def _normalize_similarity(self, payload: dict[str, Any]) -> float:
        similarity = payload.get("similarity")
        if isinstance(similarity, int | float):
            return round(max(-1.0, min(1.0, float(similarity))), 6)
        distance = payload.get("distance")
        if isinstance(distance, int | float):
            return round(max(-1.0, min(1.0, 1.0 - float(distance))), 6)
        return 0.0

    def _embedding_literal(self, embedding: list[float]) -> str:
        values = ",".join(f"{float(value):.8f}" for value in embedding)
        return f"[{values}]"

    def _build_pgvector_rpc_payloads(
        self,
        *,
        channel_id: str,
        query_embedding: list[float],
        limit: int,
        search_limit: int,
    ) -> list[dict[str, Any]]:
        query_embedding_literal = self._embedding_literal(query_embedding)
        payload_specs = (
            ("p_channel_id", "p_query_embedding", "p_limit", "p_search_limit"),
            ("channel_id", "query_embedding", "limit", "search_limit"),
        )
        payloads: list[dict[str, Any]] = []
        for (
            channel_key,
            embedding_key,
            limit_key,
            search_limit_key,
        ) in payload_specs:
            payloads.append(
                {
                    channel_key: channel_id,
                    embedding_key: query_embedding,
                    limit_key: limit,
                    search_limit_key: search_limit,
                }
            )
            payloads.append(
                {
                    channel_key: channel_id,
                    embedding_key: query_embedding_literal,
                    limit_key: limit,
                    search_limit_key: search_limit,
                }
            )
        return payloads

    def _normalize_pgvector_row(
        self,
        *,
        channel_id: str,
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            entry = self._normalize_entry(
                channel_id,
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
        except ValueError:
            return None
        return {
            **entry,
            "similarity": self._normalize_similarity(row),
            "source": "supabase_pgvector",
        }

    def _search_entries_pgvector_sync(
        self,
        channel_id: str,
        *,
        query_text: str,
        limit: int,
        search_limit: int,
    ) -> list[dict[str, Any]] | None:
        if not self._pgvector_enabled or not self._enabled or not self._client:
            return None

        query_embedding = embed_text(query_text, dimensions=EMBEDDING_DIMENSIONS)
        rpc_payloads = self._build_pgvector_rpc_payloads(
            channel_id=channel_id,
            query_embedding=query_embedding,
            limit=limit,
            search_limit=search_limit,
        )
        last_error: Exception | None = None
        for function_name in self._pgvector_rpc_functions:
            for payload in rpc_payloads:
                try:
                    result = self._client.rpc(function_name, payload).execute()
                    rows = [dict(row or {}) for row in list(result.data or [])]
                    if not rows:
                        return None
                    normalized_matches = [
                        normalized
                        for normalized in (
                            self._normalize_pgvector_row(channel_id=channel_id, row=row)
                            for row in rows
                        )
                        if normalized
                    ]
                    if not normalized_matches:
                        return None
                    return normalized_matches[:limit]
                except Exception as error:
                    last_error = error
                    continue

        if last_error and not self._pgvector_warning_emitted:
            logger.info(
                "PersistenceLayer: pgvector indisponivel para semantic_memory (%s). "
                "Usando fallback deterministico.",
                last_error,
            )
            self._pgvector_warning_emitted = True
        return None

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
        pgvector_matches = self._search_entries_pgvector_sync(
            normalize_channel_id(channel_id) or "default",
            query_text=safe_query,
            limit=safe_limit,
            search_limit=safe_search_limit,
        )
        if pgvector_matches is not None:
            return pgvector_matches
        candidates = self.load_channel_entries_sync(channel_id, limit=safe_search_limit)
        ranked = rank_semantic_matches(
            query_text=safe_query,
            entries=candidates,
            limit=safe_limit,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return ranked
