import logging
from typing import Any

from supabase import Client

from bot.persistence_utils import normalize_channel_id, utc_iso_now

logger = logging.getLogger("byte.persistence")


class PostStreamReportRepository:
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

    def _normalize_report(
        self,
        channel_id: str,
        report: dict[str, Any] | None,
        *,
        generated_at: str = "",
        trigger: str = "",
    ) -> dict[str, Any]:
        safe_report = dict(report or {})
        safe_generated_at = str(generated_at or safe_report.get("generated_at") or utc_iso_now())
        safe_trigger = (
            str(trigger or safe_report.get("trigger") or "manual_dashboard").strip().lower()
            or "manual_dashboard"
        )
        recommendations = [
            str(item or "").strip()
            for item in list(safe_report.get("recommendations") or [])
            if str(item or "").strip()
        ][:8]
        return {
            **safe_report,
            "channel_id": channel_id,
            "generated_at": safe_generated_at,
            "trigger": safe_trigger,
            "recommendations": recommendations,
        }

    def save_latest_report_sync(
        self,
        channel_id: str,
        report: dict[str, Any],
        *,
        trigger: str = "manual_dashboard",
    ) -> dict[str, Any]:
        normalized = normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        normalized_report = self._normalize_report(normalized, report, trigger=trigger)
        memory_payload = {**normalized_report, "source": "memory"}
        self._cache[normalized] = memory_payload

        if not self._enabled or not self._client:
            return memory_payload

        try:
            self._client.table("post_stream_reports").insert(
                {
                    "channel_id": normalized,
                    "report": normalized_report,
                    "generated_at": normalized_report["generated_at"],
                    "trigger": normalized_report["trigger"],
                }
            ).execute()
            persisted_payload = {**normalized_report, "source": "supabase"}
            self._cache[normalized] = persisted_payload
            return persisted_payload
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao salvar post_stream_report de %s: %s",
                normalized,
                error,
            )
            return memory_payload

    def load_latest_report_sync(self, channel_id: str) -> dict[str, Any] | None:
        normalized = normalize_channel_id(channel_id) or "default"
        cached = self._cache.get(normalized)
        if not self._enabled or not self._client:
            return dict(cached) if cached else None

        try:
            result = (
                self._client.table("post_stream_reports")
                .select("channel_id, report, generated_at, trigger")
                .eq("channel_id", normalized)
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = list(result.data or [])
            if not rows:
                return dict(cached) if cached else None
            row = dict(rows[0] or {})
            report_payload = self._normalize_report(
                normalized,
                dict(row.get("report") or {}),
                generated_at=str(row.get("generated_at") or ""),
                trigger=str(row.get("trigger") or ""),
            )
            persisted_payload = {**report_payload, "source": "supabase"}
            self._cache[normalized] = persisted_payload
            return persisted_payload
        except Exception as error:
            logger.error(
                "PersistenceLayer: Erro ao carregar post_stream_report de %s: %s",
                normalized,
                error,
            )
            return dict(cached) if cached else None
