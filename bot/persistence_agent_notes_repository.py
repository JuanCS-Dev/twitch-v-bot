from typing import Any

from bot.persistence_cached_channel_repository import CachedChannelRepository
from bot.persistence_utils import normalize_optional_text, utc_iso_now


class AgentNotesRepository(CachedChannelRepository):
    @property
    def table_name(self) -> str:
        return "agent_notes"

    @property
    def select_columns(self) -> str:
        return "channel_id, notes, updated_at"

    @property
    def entity_name(self) -> str:
        return "agent_notes"

    def _default_payload_from_cache(
        self,
        channel_id: str,
        cached: dict[str, Any],
    ) -> dict[str, Any]:
        notes = str(cached.get("notes", "") or "")
        return {
            "channel_id": channel_id,
            "notes": notes,
            "has_notes": bool(notes.strip()),
            "updated_at": cached.get("updated_at", ""),
            "source": cached.get("source", "memory"),
        }

    def _row_to_payload(self, channel_id: str, row: dict[str, Any]) -> dict[str, Any]:
        notes = str(row.get("notes") or "")
        return {
            "channel_id": channel_id,
            "notes": notes,
            "has_notes": bool(notes.strip()),
            "updated_at": str(row.get("updated_at") or ""),
            "source": "supabase",
        }

    def _build_memory_payload(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        safe_notes = normalize_optional_text(
            kwargs.get("notes"),
            field_name="agent_notes",
            max_length=2000,
        )
        return {
            "channel_id": channel_id,
            "notes": safe_notes,
            "has_notes": bool(safe_notes.strip()),
            "updated_at": utc_iso_now(),
            "source": "memory",
        }

    def _build_upsert_payload(
        self,
        channel_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "channel_id": channel_id,
            "notes": payload.get("notes", ""),
            "updated_at": "now()",
        }

    def save_sync(self, channel_id: str, *, notes: Any = None) -> dict[str, Any]:
        return super().save_sync(channel_id, notes=notes)
