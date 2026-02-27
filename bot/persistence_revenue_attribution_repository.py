import logging
from typing import Any

from supabase import Client

from bot.persistence_utils import normalize_channel_id, utc_iso_now

logger = logging.getLogger("byte.persistence.revenue")


class RevenueAttributionRepository:
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

    def _normalize_conversion(
        self,
        channel_id: str,
        conversion: dict[str, Any],
    ) -> dict[str, Any]:
        safe_conversion = dict(conversion or {})
        return {
            "id": str(safe_conversion.get("id") or ""),
            "channel_id": channel_id,
            "viewer_id": str(safe_conversion.get("viewer_id") or "unknown").strip(),
            "viewer_login": str(safe_conversion.get("viewer_login") or "unknown").strip(),
            "event_type": str(safe_conversion.get("event_type") or "unknown").strip().lower(),
            "revenue_value": float(safe_conversion.get("revenue_value") or 0.0),
            "currency": str(safe_conversion.get("currency") or "USD").strip().upper(),
            "attributed_action_id": str(safe_conversion.get("attributed_action_id") or ""),
            "attributed_action_type": str(safe_conversion.get("attributed_action_type") or ""),
            "attribution_window_seconds": int(
                safe_conversion.get("attribution_window_seconds") or 0
            ),
            "timestamp": str(safe_conversion.get("timestamp") or utc_iso_now()),
        }

    def save_conversion_sync(
        self,
        channel_id: str,
        conversion: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        normalized_conversion = self._normalize_conversion(normalized, conversion)

        # Init cache list if not exists
        if normalized not in self._cache:
            self._cache[normalized] = []

        memory_payload = {**normalized_conversion, "source": "memory"}
        self._cache[normalized].insert(0, memory_payload)
        # Keep recent history manageable
        self._cache[normalized] = self._cache[normalized][:50]

        if not self._enabled or not self._client:
            return memory_payload

        try:
            self._client.table("revenue_conversions").insert(
                {
                    "channel_id": normalized,
                    "conversion": normalized_conversion,
                    "timestamp": normalized_conversion["timestamp"],
                }
            ).execute()
            persisted_payload = {**normalized_conversion, "source": "supabase"}
            # update the cache item we just inserted
            if self._cache[normalized] and self._cache[normalized][0]["id"] == memory_payload["id"]:
                self._cache[normalized][0] = persisted_payload
            return persisted_payload
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao salvar revenue_conversion de %s: %s",
                normalized,
                error,
            )
            return memory_payload

    def load_recent_conversions_sync(
        self, channel_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        normalized = normalize_channel_id(channel_id) or "default"

        if normalized not in self._cache:
            self._cache[normalized] = []

        cached = list(self._cache.get(normalized) or [])

        if not self._enabled or not self._client:
            return cached[:limit]

        try:
            result = (
                self._client.table("revenue_conversions")
                .select("channel_id, conversion, timestamp")
                .eq("channel_id", normalized)
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            rows = list(result.data or [])
            if not rows:
                return cached[:limit]

            persisted = []
            for row in rows:
                row_dict = dict(row or {})
                conv = self._normalize_conversion(
                    normalized, dict(row_dict.get("conversion") or {})
                )
                persisted.append({**conv, "source": "supabase"})

            self._cache[normalized] = persisted
            return persisted
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao carregar revenue_conversions de %s: %s",
                normalized,
                error,
            )
            return cached[:limit]
