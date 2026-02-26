from typing import Any

from bot.access_control import is_trusted_curator
from bot.byte_semantics import compact_message, normalize_text_for_scene
from bot.logic import context_manager
from bot.runtime_config import (
    AUTO_SCENE_REQUIRE_METADATA,
    METADATA_CACHE_TTL_SECONDS,
    METADATA_TIMEOUT_SECONDS,
    OWNER_ID,
    logger,
)
from bot.scene_metadata import SceneMetadataService

scene_metadata_service = SceneMetadataService(
    metadata_cache_ttl_seconds=METADATA_CACHE_TTL_SECONDS,
    metadata_timeout_seconds=METADATA_TIMEOUT_SECONDS,
)


def normalize_host(host: str) -> str:
    return scene_metadata_service.normalize_host(host)


def extract_urls(text: str) -> list[str]:
    return scene_metadata_service.extract_urls(text)


def contains_unsafe_terms(text: str) -> bool:
    return scene_metadata_service.contains_unsafe_terms(text)


def classify_supported_link(url: str) -> str | None:
    return scene_metadata_service.classify_supported_link(url)


def is_safe_scene_link(url: str, original_text: str) -> bool:
    return scene_metadata_service.is_safe_scene_link(url, original_text)


def build_oembed_endpoint(url: str, content_type: str) -> str | None:
    return scene_metadata_service.build_oembed_endpoint(url, content_type)


def build_metadata_source_url(url: str, content_type: str) -> str:
    return scene_metadata_service.build_metadata_source_url(url, content_type)


def fetch_oembed_metadata(url: str, content_type: str) -> dict | None:
    return scene_metadata_service.fetch_oembed_metadata(url, content_type)


def get_cached_metadata(url: str) -> dict | None:
    return scene_metadata_service.get_cached_metadata(url)


def set_cached_metadata(url: str, metadata: dict) -> None:
    scene_metadata_service.set_cached_metadata(url, metadata)


async def resolve_scene_metadata(url: str, content_type: str) -> dict | None:
    return await scene_metadata_service.resolve_scene_metadata(url, content_type)


def metadata_to_safety_text(metadata: dict | None) -> str:
    return scene_metadata_service.metadata_to_safety_text(metadata)


def is_safe_scene_metadata(metadata: dict | None, message_text: str, url: str) -> bool:
    return scene_metadata_service.is_safe_scene_metadata(
        metadata,
        message_text,
        url,
        require_metadata=AUTO_SCENE_REQUIRE_METADATA,
    )


def build_sanitized_scene_description(
    content_type: str, author_name: str, metadata: dict | None
) -> str:
    return scene_metadata_service.build_sanitized_scene_description(
        content_type,
        author_name,
        metadata,
        normalize_text_for_scene=normalize_text_for_scene,
    )


async def auto_update_scene_from_message(message: Any, channel_id: str | None = None) -> list[str]:
    author = getattr(message, "author", None)
    if not is_trusted_curator(author, OWNER_ID):
        return []

    message_text = str(getattr(message, "text", "") or "")
    if not message_text or message_text.startswith("!"):
        return []

    if contains_unsafe_terms(message_text):
        logger.warning("Auto-observabilidade bloqueada por termos sensiveis no texto.")
        return []

    updated_types: list[str] = []
    seen_types: set[str] = set()
    for url in extract_urls(message_text):
        content_type = classify_supported_link(url)
        if not content_type or content_type in seen_types:
            continue
        if not is_safe_scene_link(url, message_text):
            logger.warning(
                "Auto-observabilidade bloqueada para URL potencialmente insegura: %s",
                url,
            )
            continue

        metadata = await resolve_scene_metadata(url, content_type)
        if not is_safe_scene_metadata(metadata, message_text, url):
            logger.warning("Auto-observabilidade bloqueada apos classificacao de metadata: %s", url)
            continue

        author_name = str(getattr(author, "name", "autor") or "autor")
        description = compact_message(
            build_sanitized_scene_description(content_type, author_name, metadata),
            max_len=220,
        )
        ctx = context_manager.get(channel_id)
        if ctx.update_content(content_type, description):
            updated_types.append(content_type)
            seen_types.add(content_type)
    return updated_types
