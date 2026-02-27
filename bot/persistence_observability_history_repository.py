import logging
from typing import Any

from supabase import Client

from bot.observability_history_contract import normalize_observability_history_point
from bot.persistence_utils import coerce_history_limit, normalize_channel_id, utc_iso_now

logger = logging.getLogger("byte.persistence")


class ObservabilityHistoryRepository:
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

    def _normalize_history_point(
        self,
        channel_id: str,
        payload: dict[str, Any] | None,
        *,
        captured_at: str = "",
    ) -> dict[str, Any]:
        return normalize_observability_history_point(
            payload,
            channel_id=normalize_channel_id(channel_id) or "default",
            captured_at=captured_at,
            fallback_captured_at=utc_iso_now(),
            use_timestamp_fallback=True,
        )

    def save_channel_history_sync(
        self,
        channel_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        point = self._normalize_history_point(normalized, payload)
        cached_points = list(self._cache.get(normalized, []))
        cached_points.append(point)
        self._cache[normalized] = cached_points[-360:]

        if not self._enabled or not self._client:
            return {**point, "source": "memory"}

        try:
            self._client.table("observability_channel_history").insert(
                {
                    "channel_id": normalized,
                    "snapshot": point,
                    "captured_at": "now()",
                }
            ).execute()
            return {**point, "source": "supabase"}
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao salvar histórico de observability para %s: %s",
                normalized,
                error,
            )
            return {**point, "source": "memory"}

    def load_channel_history_sync(
        self,
        channel_id: str,
        *,
        limit: int = 24,
    ) -> list[dict[str, Any]]:
        normalized = normalize_channel_id(channel_id) or "default"
        safe_limit = coerce_history_limit(limit, default=24, maximum=240)
        cached_points = list(self._cache.get(normalized, []))

        if not self._enabled or not self._client:
            return list(reversed(cached_points[-safe_limit:]))

        try:
            result = (
                self._client.table("observability_channel_history")
                .select("channel_id, snapshot, captured_at")
                .eq("channel_id", normalized)
                .order("captured_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
            rows = result.data or []
            points = [
                self._normalize_history_point(
                    str(row.get("channel_id") or normalized),
                    dict(row.get("snapshot") or {}),
                    captured_at=str(row.get("captured_at") or ""),
                )
                for row in rows
            ]
            self._cache[normalized] = list(reversed(points))
            return points
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao carregar histórico de observability para %s: %s",
                normalized,
                error,
            )
            return list(reversed(cached_points[-safe_limit:]))

    def load_latest_snapshots_sync(
        self,
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        safe_limit = coerce_history_limit(limit, default=6, maximum=24)

        if not self._enabled or not self._client:
            latest_points: list[dict[str, Any]] = []
            for channel_id, rows in self._cache.items():
                if not rows:
                    continue
                latest_points.append(
                    self._normalize_history_point(channel_id, dict(rows[-1] or {}))
                )
            latest_points.sort(key=lambda item: str(item.get("captured_at") or ""), reverse=True)
            return latest_points[:safe_limit]

        scan_limit = max(48, safe_limit * 20)
        try:
            result = (
                self._client.table("observability_channel_history")
                .select("channel_id, snapshot, captured_at")
                .order("captured_at", desc=True)
                .limit(scan_limit)
                .execute()
            )
            rows = result.data or []
            by_channel: dict[str, dict[str, Any]] = {}
            for row in rows:
                channel_id = normalize_channel_id(str(row.get("channel_id") or ""))
                if not channel_id or channel_id in by_channel:
                    continue
                by_channel[channel_id] = self._normalize_history_point(
                    channel_id,
                    dict(row.get("snapshot") or {}),
                    captured_at=str(row.get("captured_at") or ""),
                )
                if len(by_channel) >= safe_limit:
                    break
            return list(by_channel.values())
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao carregar comparação multi-canal de observability: %s",
                error,
            )
            latest_points: list[dict[str, Any]] = []
            for channel_id, rows in self._cache.items():
                if not rows:
                    continue
                latest_points.append(
                    self._normalize_history_point(channel_id, dict(rows[-1] or {}))
                )
            latest_points.sort(key=lambda item: str(item.get("captured_at") or ""), reverse=True)
            return latest_points[:safe_limit]
