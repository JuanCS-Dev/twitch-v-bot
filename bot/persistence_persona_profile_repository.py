from typing import Any

from bot.persistence_cached_channel_repository import CachedChannelRepository
from bot.persistence_utils import normalize_optional_text, utc_iso_now

_MAX_NAME_LENGTH = 80
_MAX_PRONOUNS_LENGTH = 40
_MAX_TONE_LENGTH = 160
_MAX_LORE_LENGTH = 1200
_MAX_SENTENCE_STYLE_LENGTH = 20
_MAX_LIST_ITEMS = 10
_MAX_LIST_ITEM_LENGTH = 80
_MAX_MODEL_NAME_LENGTH = 120

_VALID_SENTENCE_STYLES = {"short_punchy", "long_analytical", "balanced", ""}

_VALID_ROUTING_ACTIVITIES = {"chat", "coaching", "search", "reasoning"}


def _normalize_single_line(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _normalize_string_list(
    value: Any,
    *,
    max_items: int = _MAX_LIST_ITEMS,
    max_item_length: int = _MAX_LIST_ITEM_LENGTH,
    strict: bool = False,
) -> list[str]:
    if value in (None, ""):
        return []

    raw_items: list[Any]
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    elif isinstance(value, list | tuple | set):
        raw_items = list(value)
    else:
        if strict:
            raise ValueError("lista invalida.")
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        token = _normalize_single_line(str(item or ""))
        if not token:
            continue
        if len(token) > max_item_length:
            if strict:
                raise ValueError("item da lista excede o tamanho permitido.")
            token = token[:max_item_length].strip()
            if not token:
                continue
        token_key = token.lower()
        if token_key in seen:
            continue
        seen.add(token_key)
        normalized.append(token)

    if strict and len(normalized) > max_items:
        raise ValueError("lista excede o limite permitido.")
    return normalized[:max_items]


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _extract_base_identity(raw: Any) -> dict[str, str]:
    d = _safe_dict(raw)
    return {
        "name": _normalize_single_line(str(d.get("name") or "")),
        "pronouns": _normalize_single_line(str(d.get("pronouns") or "")),
        "lore": str(d.get("lore") or ""),
    }


def _extract_tonality_engine(raw: Any) -> dict[str, Any]:
    d = _safe_dict(raw)
    style_raw = _normalize_single_line(str(d.get("sentence_style") or "")).lower()
    return {
        "tone": _normalize_single_line(str(d.get("tone") or "")),
        "emote_vocab": _normalize_string_list(d.get("emote_vocab"), strict=False),
        "sentence_style": style_raw if style_raw in _VALID_SENTENCE_STYLES else "",
    }


def _extract_behavioral_constraints(raw: Any) -> dict[str, Any]:
    d = _safe_dict(raw)
    return {
        "banned_topics": _normalize_string_list(d.get("banned_topics"), strict=False),
        "cta_triggers": _normalize_string_list(d.get("cta_triggers"), strict=False),
    }


def _extract_model_routing(raw: Any) -> dict[str, str | None]:
    d = _safe_dict(raw)
    routing: dict[str, str | None] = {}
    for activity in _VALID_ROUTING_ACTIVITIES:
        val = _normalize_single_line(str(d.get(activity) or ""))
        routing[activity] = val if val else None
    return routing


def _has_profile(
    base: dict[str, str],
    tonality: dict[str, Any],
    constraints: dict[str, Any],
    routing: dict[str, str | None],
) -> bool:
    if base.get("name") or base.get("pronouns") or (base.get("lore") or "").strip():
        return True
    if tonality.get("tone") or tonality.get("emote_vocab") or tonality.get("sentence_style"):
        return True
    if constraints.get("banned_topics") or constraints.get("cta_triggers"):
        return True
    if any(v for v in routing.values()):
        return True
    return False


class PersonaProfileRepository(CachedChannelRepository):
    @property
    def table_name(self) -> str:
        return "persona_profiles"

    @property
    def select_columns(self) -> str:
        return (
            "channel_id, base_identity, tonality_engine, "
            "behavioral_constraints, model_routing, updated_at"
        )

    @property
    def entity_name(self) -> str:
        return "persona_profile"

    def _default_payload_from_cache(
        self,
        channel_id: str,
        cached: dict[str, Any],
    ) -> dict[str, Any]:
        base = _extract_base_identity(cached.get("base_identity"))
        tonality = _extract_tonality_engine(cached.get("tonality_engine"))
        constraints = _extract_behavioral_constraints(cached.get("behavioral_constraints"))
        routing = _extract_model_routing(cached.get("model_routing"))
        return {
            "channel_id": channel_id,
            "base_identity": base,
            "tonality_engine": tonality,
            "behavioral_constraints": constraints,
            "model_routing": routing,
            "has_profile": _has_profile(base, tonality, constraints, routing),
            "updated_at": str(cached.get("updated_at") or ""),
            "source": str(cached.get("source") or "memory"),
        }

    def _row_to_payload(self, channel_id: str, row: dict[str, Any]) -> dict[str, Any]:
        base = _extract_base_identity(row.get("base_identity"))
        tonality = _extract_tonality_engine(row.get("tonality_engine"))
        constraints = _extract_behavioral_constraints(row.get("behavioral_constraints"))
        routing = _extract_model_routing(row.get("model_routing"))
        return {
            "channel_id": channel_id,
            "base_identity": base,
            "tonality_engine": tonality,
            "behavioral_constraints": constraints,
            "model_routing": routing,
            "has_profile": _has_profile(base, tonality, constraints, routing),
            "updated_at": str(row.get("updated_at") or ""),
            "source": "supabase",
        }

    def _build_memory_payload(self, channel_id: str, **kwargs: Any) -> dict[str, Any]:
        raw_base = _safe_dict(kwargs.get("base_identity"))
        safe_name = _normalize_single_line(
            normalize_optional_text(
                raw_base.get("name"),
                field_name="base_identity.name",
                max_length=_MAX_NAME_LENGTH,
            )
        )
        safe_pronouns = _normalize_single_line(
            normalize_optional_text(
                raw_base.get("pronouns"),
                field_name="base_identity.pronouns",
                max_length=_MAX_PRONOUNS_LENGTH,
            )
        )
        safe_lore = normalize_optional_text(
            raw_base.get("lore"),
            field_name="base_identity.lore",
            max_length=_MAX_LORE_LENGTH,
        )
        base = {"name": safe_name, "pronouns": safe_pronouns, "lore": safe_lore}

        raw_tonality = _safe_dict(kwargs.get("tonality_engine"))
        safe_tone = _normalize_single_line(
            normalize_optional_text(
                raw_tonality.get("tone"),
                field_name="tonality_engine.tone",
                max_length=_MAX_TONE_LENGTH,
            )
        )
        safe_emote_vocab = _normalize_string_list(raw_tonality.get("emote_vocab"), strict=True)
        style_raw = _normalize_single_line(str(raw_tonality.get("sentence_style") or "")).lower()
        if style_raw and style_raw not in _VALID_SENTENCE_STYLES:
            raise ValueError("tonality_engine.sentence_style invalido.")
        tonality = {
            "tone": safe_tone,
            "emote_vocab": safe_emote_vocab,
            "sentence_style": style_raw,
        }

        raw_constraints = _safe_dict(kwargs.get("behavioral_constraints"))
        safe_banned = _normalize_string_list(raw_constraints.get("banned_topics"), strict=True)
        safe_cta = _normalize_string_list(raw_constraints.get("cta_triggers"), strict=True)
        constraints = {"banned_topics": safe_banned, "cta_triggers": safe_cta}

        routing = _extract_model_routing(kwargs.get("model_routing"))
        for activity, model_name in routing.items():
            if model_name and len(model_name) > _MAX_MODEL_NAME_LENGTH:
                raise ValueError(f"model_routing.{activity} excede o tamanho permitido.")

        return {
            "channel_id": channel_id,
            "base_identity": base,
            "tonality_engine": tonality,
            "behavioral_constraints": constraints,
            "model_routing": routing,
            "has_profile": _has_profile(base, tonality, constraints, routing),
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
            "base_identity": payload.get("base_identity", {}),
            "tonality_engine": payload.get("tonality_engine", {}),
            "behavioral_constraints": payload.get("behavioral_constraints", {}),
            "model_routing": payload.get("model_routing", {}),
            "updated_at": "now()",
        }
