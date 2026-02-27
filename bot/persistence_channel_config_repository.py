from typing import Any

from bot.persistence_cached_channel_repository import CachedChannelRepository
from bot.persistence_utils import normalize_bool, normalize_optional_float, utc_iso_now


class ChannelConfigRepository(CachedChannelRepository):
    @property
    def table_name(self) -> str:
        return "channels_config"

    @property
    def select_columns(self) -> str:
        return "channel_id, temperature, top_p, agent_paused, updated_at"

    @property
    def entity_name(self) -> str:
        return "config"

    def _default_payload_from_cache(
        self,
        channel_id: str,
        cached: dict[str, Any],
    ) -> dict[str, Any]:
        temperature = cached.get("temperature")
        top_p = cached.get("top_p")
        agent_paused = bool(cached.get("agent_paused", False))
        return {
            "channel_id": channel_id,
            "temperature": temperature,
            "top_p": top_p,
            "agent_paused": agent_paused,
            "has_override": temperature is not None or top_p is not None or agent_paused,
            "updated_at": cached.get("updated_at", ""),
            "source": cached.get("source", "memory"),
        }

    def _row_to_payload(self, channel_id: str, row: dict[str, Any]) -> dict[str, Any]:
        safe_agent_paused = bool(row.get("agent_paused", False))
        return {
            "channel_id": channel_id,
            "temperature": row.get("temperature"),
            "top_p": row.get("top_p"),
            "agent_paused": safe_agent_paused,
            "has_override": (
                row.get("temperature") is not None
                or row.get("top_p") is not None
                or safe_agent_paused
            ),
            "updated_at": str(row.get("updated_at") or ""),
            "source": "supabase",
        }

    def _build_memory_payload(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        safe_temperature = normalize_optional_float(
            kwargs.get("temperature"),
            minimum=0.0,
            maximum=2.0,
            field_name="temperature",
        )
        safe_top_p = normalize_optional_float(
            kwargs.get("top_p"),
            minimum=0.0,
            maximum=1.0,
            field_name="top_p",
        )
        safe_agent_paused = normalize_bool(kwargs.get("agent_paused"), field_name="agent_paused")
        return {
            "channel_id": channel_id,
            "temperature": safe_temperature,
            "top_p": safe_top_p,
            "agent_paused": safe_agent_paused,
            "has_override": safe_temperature is not None
            or safe_top_p is not None
            or safe_agent_paused,
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
            "temperature": payload.get("temperature"),
            "top_p": payload.get("top_p"),
            "agent_paused": payload.get("agent_paused"),
            "updated_at": "now()",
        }

    def save_sync(
        self,
        channel_id: str,
        *,
        temperature: Any = None,
        top_p: Any = None,
        agent_paused: Any = False,
    ) -> dict[str, Any]:
        return super().save_sync(
            channel_id,
            temperature=temperature,
            top_p=top_p,
            agent_paused=agent_paused,
        )
