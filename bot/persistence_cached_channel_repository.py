import logging
from abc import ABC, abstractmethod
from typing import Any

from supabase import Client

from bot.persistence_utils import normalize_channel_id

logger = logging.getLogger("byte.persistence")


class CachedChannelRepository(ABC):
    def __init__(
        self,
        *,
        enabled: bool,
        client: Client | None,
        cache: dict[str, dict[str, Any]],
    ) -> None:
        self._enabled = enabled
        self._client = client
        self._cache = cache

    @property
    @abstractmethod
    def table_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def select_columns(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def entity_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _default_payload_from_cache(
        self,
        channel_id: str,
        cached: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def _row_to_payload(self, channel_id: str, row: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def _build_memory_payload(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def _build_upsert_payload(
        self,
        channel_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _default_payload(self, channel_id: str) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id) or "default"
        cached = self._cache.get(normalized, {})
        return self._default_payload_from_cache(normalized, cached)

    def load_sync(self, channel_id: str) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id) or "default"
        if not self._enabled or not self._client:
            return self._default_payload(normalized)

        try:
            result = (
                self._client.table(self.table_name)
                .select(self.select_columns)
                .eq("channel_id", normalized)
                .maybe_single()
                .execute()
            )
            payload = self._row_to_payload(normalized, result.data or {})
            self._cache[normalized] = payload
            return payload
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao carregar %s de %s: %s",
                self.entity_name,
                normalized,
                error,
            )
            return self._default_payload(normalized)

    def save_sync(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        payload = self._build_memory_payload(normalized, **kwargs)
        self._cache[normalized] = payload

        if not self._enabled or not self._client:
            return payload

        try:
            self._client.table(self.table_name).upsert(
                self._build_upsert_payload(normalized, payload)
            ).execute()
            persisted = self.load_sync(normalized)
            persisted["source"] = "supabase"
            self._cache[normalized] = persisted
            return persisted
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao salvar %s de %s: %s",
                self.entity_name,
                normalized,
                error,
            )
            return payload
