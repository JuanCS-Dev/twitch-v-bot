from typing import Any

from bot.persistence_cached_channel_repository import CachedChannelRepository
from bot.persistence_utils import normalize_optional_text, utc_iso_now

_MAX_EMOTE_VOCAB_ITEMS = 20
_MAX_EMOTE_TOKEN_LENGTH = 32


def _normalize_single_line(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _normalize_emote_vocab(value: Any, *, strict: bool) -> list[str]:
    if value in (None, ""):
        return []

    raw_items: list[Any]
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    elif isinstance(value, list | tuple | set):
        raw_items = list(value)
    else:
        if strict:
            raise ValueError("emote_vocab invalido.")
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        token = _normalize_single_line(str(item or ""))
        if not token:
            continue

        if len(token) > _MAX_EMOTE_TOKEN_LENGTH:
            if strict:
                raise ValueError("emote_vocab contem item invalido.")
            token = token[:_MAX_EMOTE_TOKEN_LENGTH].strip()
            if not token:
                continue

        token_key = token.lower()
        if token_key in seen:
            continue
        seen.add(token_key)
        normalized.append(token)

    if strict and len(normalized) > _MAX_EMOTE_VOCAB_ITEMS:
        raise ValueError("emote_vocab excede o limite permitido.")

    return normalized[:_MAX_EMOTE_VOCAB_ITEMS]


class ChannelIdentityRepository(CachedChannelRepository):
    @property
    def table_name(self) -> str:
        return "channel_identity"

    @property
    def select_columns(self) -> str:
        return "channel_id, persona_name, tone, emote_vocab, lore, updated_at"

    @property
    def entity_name(self) -> str:
        return "channel_identity"

    def _default_payload_from_cache(
        self,
        channel_id: str,
        cached: dict[str, Any],
    ) -> dict[str, Any]:
        persona_name = _normalize_single_line(str(cached.get("persona_name") or ""))
        tone = _normalize_single_line(str(cached.get("tone") or ""))
        emote_vocab = _normalize_emote_vocab(cached.get("emote_vocab"), strict=False)
        lore = str(cached.get("lore") or "")
        return {
            "channel_id": channel_id,
            "persona_name": persona_name,
            "tone": tone,
            "emote_vocab": emote_vocab,
            "lore": lore,
            "has_identity": bool(persona_name or tone or emote_vocab or lore.strip()),
            "updated_at": str(cached.get("updated_at") or ""),
            "source": str(cached.get("source") or "memory"),
        }

    def _row_to_payload(self, channel_id: str, row: dict[str, Any]) -> dict[str, Any]:
        persona_name = _normalize_single_line(str(row.get("persona_name") or ""))
        tone = _normalize_single_line(str(row.get("tone") or ""))
        emote_vocab = _normalize_emote_vocab(row.get("emote_vocab"), strict=False)
        lore = str(row.get("lore") or "")
        return {
            "channel_id": channel_id,
            "persona_name": persona_name,
            "tone": tone,
            "emote_vocab": emote_vocab,
            "lore": lore,
            "has_identity": bool(persona_name or tone or emote_vocab or lore.strip()),
            "updated_at": str(row.get("updated_at") or ""),
            "source": "supabase",
        }

    def _build_memory_payload(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        safe_persona_name = _normalize_single_line(
            normalize_optional_text(
                kwargs.get("persona_name"),
                field_name="persona_name",
                max_length=80,
            )
        )
        safe_tone = _normalize_single_line(
            normalize_optional_text(
                kwargs.get("tone"),
                field_name="tone",
                max_length=160,
            )
        )
        safe_emote_vocab = _normalize_emote_vocab(kwargs.get("emote_vocab"), strict=True)
        safe_lore = normalize_optional_text(
            kwargs.get("lore"),
            field_name="lore",
            max_length=1200,
        )
        return {
            "channel_id": channel_id,
            "persona_name": safe_persona_name,
            "tone": safe_tone,
            "emote_vocab": safe_emote_vocab,
            "lore": safe_lore,
            "has_identity": bool(
                safe_persona_name or safe_tone or safe_emote_vocab or safe_lore.strip()
            ),
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
            "persona_name": payload.get("persona_name", ""),
            "tone": payload.get("tone", ""),
            "emote_vocab": list(payload.get("emote_vocab") or []),
            "lore": payload.get("lore", ""),
            "updated_at": "now()",
        }
