import logging
import uuid
from typing import Any

from supabase import Client

from bot.persistence_utils import normalize_channel_id, utc_iso_now

logger = logging.getLogger("byte.persistence.webhooks")


class WebhookRepository:
    def __init__(
        self,
        *,
        enabled: bool,
        client: Client | None,
        cache: dict[str, list[dict[str, Any]]],
    ) -> None:
        self._enabled = enabled
        self._client = client
        self._cache = cache  # channel_id -> list of webhooks

    def save_webhook_sync(
        self,
        channel_id: str,
        webhook: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        webhook_id = str(webhook.get("id") or uuid.uuid4())
        normalized_webhook = {
            "id": webhook_id,
            "channel_id": normalized,
            "url": str(webhook.get("url") or "").strip(),
            "secret": str(webhook.get("secret") or "").strip(),
            "event_types": [str(e) for e in (webhook.get("event_types") or []) if e],
            "is_active": bool(webhook.get("is_active", True)),
            "created_at": str(webhook.get("created_at") or utc_iso_now()),
            "updated_at": utc_iso_now(),
        }

        if normalized not in self._cache:
            self._cache[normalized] = []

        # Update cache
        existing_idx = next(
            (i for i, w in enumerate(self._cache[normalized]) if w["id"] == webhook_id), -1
        )
        if existing_idx >= 0:
            self._cache[normalized][existing_idx] = {**normalized_webhook, "source": "memory"}
        else:
            self._cache[normalized].append({**normalized_webhook, "source": "memory"})

        if not self._enabled or not self._client:
            return {**normalized_webhook, "source": "memory"}

        try:
            self._client.table("outbound_webhooks").upsert(
                {
                    "id": webhook_id,
                    "channel_id": normalized,
                    "url": normalized_webhook["url"],
                    "secret": normalized_webhook["secret"],
                    "event_types": normalized_webhook["event_types"],
                    "is_active": normalized_webhook["is_active"],
                    "updated_at": normalized_webhook["updated_at"],
                }
            ).execute()
            persisted = {**normalized_webhook, "source": "supabase"}
            if existing_idx >= 0:
                self._cache[normalized][existing_idx] = persisted
            else:
                self._cache[normalized][-1] = persisted
            return persisted
        except Exception as error:
            logger.error("PersistenceLayer: Erro ao salvar webhook de %s: %s", normalized, error)
            return {**normalized_webhook, "source": "memory"}

    def load_webhooks_sync(self, channel_id: str) -> list[dict[str, Any]]:
        normalized = normalize_channel_id(channel_id) or "default"

        if normalized not in self._cache:
            self._cache[normalized] = []

        cached = list(self._cache.get(normalized) or [])

        if not self._enabled or not self._client:
            return cached

        try:
            result = (
                self._client.table("outbound_webhooks")
                .select("*")
                .eq("channel_id", normalized)
                .execute()
            )
            rows = list(result.data or [])
            persisted = []
            for row in rows:
                row_dict = dict(row or {})
                persisted.append(
                    {
                        "id": str(row_dict.get("id")),
                        "channel_id": normalized,
                        "url": str(row_dict.get("url")),
                        "secret": str(row_dict.get("secret")),
                        "event_types": row_dict.get("event_types") or [],
                        "is_active": bool(row_dict.get("is_active")),
                        "created_at": str(row_dict.get("created_at") or ""),
                        "updated_at": str(row_dict.get("updated_at") or ""),
                        "source": "supabase",
                    }
                )
            self._cache[normalized] = persisted
            return persisted
        except Exception as error:
            logger.error("PersistenceLayer: Erro ao carregar webhooks de %s: %s", normalized, error)
            return cached

    def save_delivery_sync(
        self,
        webhook_id: str,
        channel_id: str,
        delivery: dict[str, Any],
    ) -> None:
        normalized = normalize_channel_id(channel_id)
        if not self._enabled or not self._client:
            return

        try:
            self._client.table("outbound_webhook_deliveries").insert(
                {
                    "webhook_id": webhook_id,
                    "channel_id": normalized,
                    "event_type": str(delivery.get("event_type") or "unknown"),
                    "status_code": int(delivery.get("status_code") or 0),
                    "success": bool(delivery.get("success")),
                    "latency_ms": int(delivery.get("latency_ms") or 0),
                    "timestamp": str(delivery.get("timestamp") or utc_iso_now()),
                }
            ).execute()
        except Exception as error:
            logger.error("PersistenceLayer: Erro ao salvar log de webhook delivery: %s", error)
