import os
import json
import asyncio
import time
import threading
import logging
import re
import ssl
from pathlib import Path
from typing import Any, cast
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import twitchio
from twitchio import eventsub
from twitchio.ext import commands
from google import genai
from google.cloud import secretmanager

from bot import byte_semantics
from bot.channel_control import (
    IrcChannelControlBridge,
    is_dashboard_admin_authorized,
    parse_terminal_command,
)
from bot.channel_status import (
    TWITCH_CHANNEL_LOGIN_PATTERN,
    compose_status_line,
    format_status_channels as format_status_channels_impl,
    normalize_channel_login as normalize_channel_login_impl,
    parse_channel_logins as parse_channel_logins_impl,
)
from bot.logic import (
    BOT_BRAND,
    MAX_REPLY_LINES,
    OBSERVABILITY_TYPES,
    agent_inference,
    context,
    has_grounding_signal,
)
from bot.observability import observability
from bot.prompt_flow import (
    BytePromptRuntime,
    handle_byte_prompt_text as handle_byte_prompt_text_impl,
    handle_movie_fact_sheet_prompt as handle_movie_fact_sheet_prompt_impl,
    unwrap_inference_result as unwrap_inference_result_impl,
)
from bot.scene_metadata import SceneMetadataService

# ── Setup ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ByteBot")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
BOT_ID = os.environ.get("TWITCH_BOT_ID")
OWNER_ID = os.environ.get("TWITCH_OWNER_ID")
CHANNEL_ID = os.environ.get("TWITCH_CHANNEL_ID")
TWITCH_CHAT_MODE = (
    os.environ.get("TWITCH_CHAT_MODE", "eventsub").strip().lower() or "eventsub"
)
ENABLE_LIVE_CONTEXT_LEARNING = os.environ.get(
    "ENABLE_LIVE_CONTEXT_LEARNING", "false"
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TWITCH_CHANNEL_LOGIN = (
    os.environ.get("TWITCH_CHANNEL_LOGIN", "").strip().lstrip("#").lower()
)
TWITCH_CHANNEL_LOGINS_RAW = os.environ.get("TWITCH_CHANNEL_LOGINS", "").strip()
TWITCH_BOT_LOGIN = os.environ.get("TWITCH_BOT_LOGIN", "").strip().lower()
TWITCH_USER_TOKEN = (
    os.environ.get("TWITCH_USER_TOKEN", "").strip().removeprefix("oauth:")
)
TWITCH_REFRESH_TOKEN = os.environ.get("TWITCH_REFRESH_TOKEN", "").strip()
TWITCH_CLIENT_SECRET_INLINE = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
TWITCH_CLIENT_SECRET_NAME = os.environ.get(
    "TWITCH_CLIENT_SECRET_SECRET_NAME", "twitch-client-secret"
).strip()
TWITCH_IRC_HOST = (
    os.environ.get("TWITCH_IRC_HOST", "irc.chat.twitch.tv").strip()
    or "irc.chat.twitch.tv"
)
TWITCH_IRC_PORT = int(os.environ.get("TWITCH_IRC_PORT", "6697"))
TWITCH_IRC_TLS = os.environ.get("TWITCH_IRC_TLS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TWITCH_TOKEN_REFRESH_MARGIN_SECONDS = int(
    os.environ.get("TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", "300")
)
TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS = float(
    os.environ.get("TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS", "5.0")
)
TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS = float(
    os.environ.get("TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS", "8.0")
)
BYTE_DASHBOARD_ADMIN_TOKEN = os.environ.get("BYTE_DASHBOARD_ADMIN_TOKEN", "").strip()

client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

BYTE_VERSION = "1.4"
BYTE_HELP_MESSAGE = byte_semantics.BYTE_HELP_MESSAGE
MAX_CHAT_MESSAGE_LENGTH = byte_semantics.MAX_CHAT_MESSAGE_LENGTH
MULTIPART_SEPARATOR = byte_semantics.MULTIPART_SEPARATOR
SERIOUS_REPLY_MAX_LINES = byte_semantics.SERIOUS_REPLY_MAX_LINES
SERIOUS_REPLY_MAX_LENGTH = byte_semantics.SERIOUS_REPLY_MAX_LENGTH

compact_message = byte_semantics.compact_message
normalize_text_for_scene = byte_semantics.normalize_text_for_scene
format_chat_reply = byte_semantics.format_chat_reply
parse_byte_prompt = byte_semantics.parse_byte_prompt
is_movie_fact_sheet_prompt = byte_semantics.is_movie_fact_sheet_prompt
is_intro_prompt = byte_semantics.is_intro_prompt
is_current_events_prompt = byte_semantics.is_current_events_prompt
is_high_risk_current_events_prompt = byte_semantics.is_high_risk_current_events_prompt
build_verifiable_prompt = byte_semantics.build_verifiable_prompt
is_serious_technical_prompt = byte_semantics.is_serious_technical_prompt
is_follow_up_prompt = byte_semantics.is_follow_up_prompt
build_direct_answer_instruction = byte_semantics.build_direct_answer_instruction
build_llm_enhanced_prompt = byte_semantics.build_llm_enhanced_prompt
is_low_quality_answer = byte_semantics.is_low_quality_answer
build_quality_rewrite_prompt = byte_semantics.build_quality_rewrite_prompt
build_server_time_anchor_instruction = (
    byte_semantics.build_server_time_anchor_instruction
)
normalize_current_events_reply_contract = (
    byte_semantics.normalize_current_events_reply_contract
)
build_current_events_safe_fallback_reply = (
    byte_semantics.build_current_events_safe_fallback_reply
)
extract_multi_reply_parts = byte_semantics.extract_multi_reply_parts
extract_movie_title = byte_semantics.extract_movie_title
build_movie_fact_sheet_query = byte_semantics.build_movie_fact_sheet_query
QUALITY_SAFE_FALLBACK = byte_semantics.QUALITY_SAFE_FALLBACK
BYTE_INTRO_TEMPLATES = byte_semantics.BYTE_INTRO_TEMPLATES
intro_template_index = 0


def build_intro_reply() -> str:
    global intro_template_index
    template = BYTE_INTRO_TEMPLATES[intro_template_index % len(BYTE_INTRO_TEMPLATES)]
    intro_template_index += 1
    return template


IRC_PRIVMSG_PATTERN = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:(?P<author>[^!]+)![^ ]+ PRIVMSG #(?P<channel>[^ ]+) :(?P<message>.*)$"
)
IRC_WELCOME_PATTERN = re.compile(r"^:[^ ]+\s001\s", re.IGNORECASE)
TWITCH_OAUTH_VALIDATE_ENDPOINT = "https://id.twitch.tv/oauth2/validate"
TWITCH_OAUTH_REFRESH_ENDPOINT = "https://id.twitch.tv/oauth2/token"

METADATA_CACHE_TTL_SECONDS = int(os.environ.get("AUTO_SCENE_CACHE_TTL_SECONDS", "900"))
METADATA_TIMEOUT_SECONDS = float(
    os.environ.get("AUTO_SCENE_METADATA_TIMEOUT_SECONDS", "3.0")
)
AUTO_SCENE_REQUIRE_METADATA = os.environ.get(
    "AUTO_SCENE_REQUIRE_METADATA", "true"
).lower() in {"1", "true", "yes"}
scene_metadata_service = SceneMetadataService(
    metadata_cache_ttl_seconds=METADATA_CACHE_TTL_SECONDS,
    metadata_timeout_seconds=METADATA_TIMEOUT_SECONDS,
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
irc_channel_control = IrcChannelControlBridge()


def is_owner(user_id: str) -> bool:
    return str(user_id) == OWNER_ID


def is_moderator(author) -> bool:
    return bool(getattr(author, "is_mod", False)) or bool(
        getattr(author, "is_moderator", False)
    )


def is_trusted_curator(author) -> bool:
    return is_owner(getattr(author, "id", "")) or is_moderator(author)


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


def normalize_channel_login(channel_login: str) -> str:
    return normalize_channel_login_impl(
        channel_login, pattern=TWITCH_CHANNEL_LOGIN_PATTERN
    )


def parse_channel_logins(raw_value: str) -> list[str]:
    return parse_channel_logins_impl(raw_value, pattern=TWITCH_CHANNEL_LOGIN_PATTERN)


def format_status_channels(
    channel_logins: list[str] | None = None, max_items: int = 3
) -> str:
    fallback = parse_channel_logins(TWITCH_CHANNEL_LOGINS_RAW) or parse_channel_logins(
        TWITCH_CHANNEL_LOGIN
    )
    return format_status_channels_impl(
        channel_logins,
        fallback_channels=fallback,
        fallback_mode=TWITCH_CHAT_MODE,
        max_items=max_items,
        pattern=TWITCH_CHANNEL_LOGIN_PATTERN,
    )


def build_status_line(channel_logins: list[str] | None = None) -> str:
    snapshot = observability.snapshot(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        bot_mode=TWITCH_CHAT_MODE,
        stream_context=context,
    )
    metrics = snapshot.get("metrics", {})
    chatters = snapshot.get("chatters", {})
    chat_analytics = snapshot.get("chat_analytics", {})
    uptime = int(
        snapshot.get("bot", {}).get("uptime_minutes", context.get_uptime_minutes())
    )
    chat_10m = int(chat_analytics.get("messages_10m", 0))
    active_10m = int(chatters.get("active_10m", 0))
    triggers_10m = int(chat_analytics.get("byte_triggers_10m", 0))
    p95_latency_ms = float(metrics.get("p95_latency_ms", 0.0))
    channels_label = format_status_channels(channel_logins=channel_logins)
    return compose_status_line(
        bot_brand=BOT_BRAND,
        bot_version=BYTE_VERSION,
        uptime_minutes=uptime,
        channels_label=channels_label,
        chat_messages_10m=chat_10m,
        active_chatters_10m=active_10m,
        triggers_10m=triggers_10m,
        p95_latency_ms=p95_latency_ms,
    )


def unwrap_inference_result(result: Any) -> tuple[str, dict | None]:
    return unwrap_inference_result_impl(result)


def build_prompt_runtime() -> BytePromptRuntime:
    return BytePromptRuntime(
        agent_inference=agent_inference,
        client=client,
        context=context,
        observability=observability,
        logger=logger,
        byte_help_message=BYTE_HELP_MESSAGE,
        max_reply_lines=MAX_REPLY_LINES,
        max_chat_message_length=MAX_CHAT_MESSAGE_LENGTH,
        serious_reply_max_lines=SERIOUS_REPLY_MAX_LINES,
        serious_reply_max_length=SERIOUS_REPLY_MAX_LENGTH,
        quality_safe_fallback=QUALITY_SAFE_FALLBACK,
        format_chat_reply=format_chat_reply,
        is_serious_technical_prompt=is_serious_technical_prompt,
        is_follow_up_prompt=is_follow_up_prompt,
        is_current_events_prompt=is_current_events_prompt,
        is_high_risk_current_events_prompt=is_high_risk_current_events_prompt,
        build_server_time_anchor_instruction=build_server_time_anchor_instruction,
        is_intro_prompt=is_intro_prompt,
        build_intro_reply=build_intro_reply,
        is_movie_fact_sheet_prompt=is_movie_fact_sheet_prompt,
        extract_movie_title=extract_movie_title,
        build_movie_fact_sheet_query=build_movie_fact_sheet_query,
        build_llm_enhanced_prompt=build_llm_enhanced_prompt,
        has_grounding_signal=has_grounding_signal,
        normalize_current_events_reply_contract=normalize_current_events_reply_contract,
        is_low_quality_answer=is_low_quality_answer,
        build_quality_rewrite_prompt=build_quality_rewrite_prompt,
        build_current_events_safe_fallback_reply=build_current_events_safe_fallback_reply,
        extract_multi_reply_parts=extract_multi_reply_parts,
        enable_live_context_learning=ENABLE_LIVE_CONTEXT_LEARNING,
    )


async def handle_movie_fact_sheet_prompt(
    prompt: str,
    author_name: str,
    reply_fn,
) -> None:
    await handle_movie_fact_sheet_prompt_impl(
        prompt,
        author_name,
        reply_fn,
        runtime=build_prompt_runtime(),
    )


async def handle_byte_prompt_text(
    prompt: str,
    author_name: str,
    reply_fn,
    status_line_factory=None,
) -> None:
    if callable(status_line_factory):

        def effective_status_factory() -> str:
            try:
                return str(status_line_factory())
            except Exception as error:
                logger.warning("Falha ao montar status customizado: %s", error)
                return build_status_line()
    else:
        effective_status_factory = build_status_line
    await handle_byte_prompt_text_impl(
        prompt,
        author_name,
        reply_fn,
        runtime=build_prompt_runtime(),
        status_line_factory=effective_status_factory,
    )


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


async def auto_update_scene_from_message(message: Any) -> list[str]:
    author = getattr(message, "author", None)
    if not is_trusted_curator(author):
        return []

    message_text = str(getattr(message, "text", "") or "")
    if not message_text or message_text.startswith("!"):
        return []

    if contains_unsafe_terms(message_text):
        logger.warning("Auto-observabilidade bloqueada por termos sensiveis no texto.")
        return []

    updated_types = []
    seen_types = set()
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
            logger.warning(
                "Auto-observabilidade bloqueada apos classificacao de metadata: %s", url
            )
            continue

        author_name = str(getattr(author, "name", "autor") or "autor")
        description = compact_message(
            build_sanitized_scene_description(content_type, author_name, metadata),
            max_len=220,
        )
        if context.update_content(content_type, description):
            updated_types.append(content_type)
            seen_types.add(content_type)
    return updated_types


def get_ctx_message_text(ctx: commands.Context) -> str:
    message = getattr(ctx, "message", None)
    return str(getattr(message, "text", "") or "")


def get_ctx_author(ctx: commands.Context) -> Any:
    message = getattr(ctx, "message", None)
    return getattr(message, "author", None)


# ── Twitch Agent Component ────────────────────────────────────
class AgentComponent(commands.Component):
    def __init__(self, bot: "ByteBot") -> None:
        self.bot = bot

    async def component_check(self, ctx: commands.Context) -> bool:
        """Permite comandos com prefixo para qualquer usuario do chat."""
        return True

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context) -> None:
        query = get_ctx_message_text(ctx).removeprefix("!ask").strip()
        if not query:
            return
        author_name = str(getattr(get_ctx_author(ctx), "name", "viewer") or "viewer")
        ans = await agent_inference(
            query,
            author_name,
            client,
            context,
            enable_live_context=ENABLE_LIVE_CONTEXT_LEARNING,
        )
        await ctx.reply(format_chat_reply(ans))

    @commands.command(name="vibe")
    async def vibe(self, ctx: commands.Context) -> None:
        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if is_owner(author_id):
            new_vibe = get_ctx_message_text(ctx).removeprefix("!vibe").strip()
            context.stream_vibe = new_vibe or "Conversa"
            context.last_event = "Vibe atualizada"
            await ctx.reply(f"Vibe atualizada para: {context.stream_vibe}")

    @commands.command(name="style")
    async def style(self, ctx: commands.Context) -> None:
        style_text = get_ctx_message_text(ctx).removeprefix("!style").strip()
        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if not is_owner(author_id):
            await ctx.reply("Somente o dono do canal pode ajustar o estilo.")
            return
        if not style_text:
            await ctx.reply(format_chat_reply(f"Estilo atual: {context.style_profile}"))
            return

        context.style_profile = style_text
        context.last_event = "Estilo de conversa atualizado"
        await ctx.reply("Estilo de conversa atualizado.")

    @commands.command(name="scene")
    async def scene(self, ctx: commands.Context) -> None:
        payload = get_ctx_message_text(ctx).removeprefix("!scene").strip()
        if not payload:
            observability = context.format_observability()
            await ctx.reply(
                format_chat_reply(f"Observabilidade da live: {observability}")
            )
            return

        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if not is_owner(author_id):
            await ctx.reply("Somente o dono do canal pode atualizar a observabilidade.")
            return

        tokens = payload.split(maxsplit=1)
        action_or_type = tokens[0].lower()

        if action_or_type == "clear":
            if len(tokens) < 2:
                await ctx.reply(
                    f"Uso: !scene clear <tipo>. Tipos: {context.list_supported_content_types()}"
                )
                return

            content_type = tokens[1].strip().lower()
            if not context.clear_content(content_type):
                await ctx.reply(
                    f"Tipo invalido. Tipos: {context.list_supported_content_types()}"
                )
                return

            label = OBSERVABILITY_TYPES.get(content_type, content_type)
            await ctx.reply(f"Contexto removido: {label}.")
            return

        if len(tokens) < 2:
            await ctx.reply(
                f"Uso: !scene <tipo> <descricao>. Tipos: {context.list_supported_content_types()}"
            )
            return

        content_type = action_or_type
        description = tokens[1].strip()
        if not context.update_content(content_type, description):
            await ctx.reply(
                f"Tipo invalido ou descricao vazia. Tipos: {context.list_supported_content_types()}"
            )
            return

        label = OBSERVABILITY_TYPES.get(content_type, content_type)
        await ctx.reply(
            format_chat_reply(f"Contexto atualizado: {label} -> {description}")
        )

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        await ctx.reply(format_chat_reply(self.bot.build_status_line()))


class ByteBot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        resolved_client_id = CLIENT_ID or require_env("TWITCH_CLIENT_ID")
        resolved_bot_id = BOT_ID or require_env("TWITCH_BOT_ID")
        super().__init__(
            client_id=resolved_client_id,
            client_secret=client_secret,
            bot_id=resolved_bot_id,
            owner_id=OWNER_ID or "",
            prefix="!",
        )

    async def setup_hook(self) -> None:
        await self.add_component(AgentComponent(self))
        if not CHANNEL_ID:
            raise RuntimeError("TWITCH_CHANNEL_ID e obrigatorio no modo eventsub.")
        payload = eventsub.ChatMessageSubscription(
            broadcaster_user_id=str(CHANNEL_ID),
            user_id=str(self.bot_id),
        )
        await self.subscribe_websocket(payload=payload, as_bot=True)

    async def event_ready(self) -> None:
        logger.info("%s pronto no chat. Bot ID: %s", BOT_BRAND, self.bot_id)

    def build_status_line(self) -> str:
        return build_status_line()

    async def handle_movie_fact_sheet(
        self, message: Any, prompt: str, author_name: str
    ) -> None:
        reply_fn = getattr(message, "reply", None)
        if callable(reply_fn):
            await handle_movie_fact_sheet_prompt(prompt, author_name, reply_fn)

    async def handle_byte_prompt(self, message: Any, prompt: str) -> None:
        author = getattr(message, "author", None)
        author_name = str(getattr(author, "name", "viewer") or "viewer")
        reply_fn = getattr(message, "reply", None)
        if callable(reply_fn):
            await handle_byte_prompt_text(
                prompt,
                author_name,
                reply_fn,
                status_line_factory=self.build_status_line,
            )

    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        message = cast(Any, payload)
        if message.echo:
            return

        raw_text = message.text or ""
        author = getattr(message, "author", None)
        author_name = str(getattr(author, "name", "viewer") or "viewer")
        byte_prompt = parse_byte_prompt(raw_text)
        if raw_text and (not raw_text.startswith("!") or byte_prompt is not None):
            if ENABLE_LIVE_CONTEXT_LEARNING:
                context.remember_user_message(author_name, raw_text)
            observability.record_chat_message(
                author_name=author_name, source="eventsub", text=raw_text
            )

        updates: list[str] = []
        if ENABLE_LIVE_CONTEXT_LEARNING:
            updates = await auto_update_scene_from_message(message)
        if updates:
            labels = ", ".join(
                OBSERVABILITY_TYPES.get(content_type, content_type)
                for content_type in updates
            )
            logger.info("Observabilidade automatica atualizada: %s", labels)
            observability.record_auto_scene_update(update_types=updates)

        if byte_prompt is not None:
            observability.record_byte_trigger(
                prompt=byte_prompt, source="eventsub", author_name=author_name
            )
            await self.handle_byte_prompt(message, byte_prompt)
            return

        await cast(Any, self).handle_commands(message)


class IrcAuthor:
    def __init__(self, login: str, tags: dict[str, str]) -> None:
        self.login = login
        self.name = tags.get("display-name") or login
        self.id = tags.get("user-id", "")
        is_mod = tags.get("mod") == "1" or "moderator/" in tags.get("badges", "")
        self.is_mod = is_mod
        self.is_moderator = is_mod


class IrcMessageAdapter:
    def __init__(self, text: str, author: IrcAuthor) -> None:
        self.text = text
        self.author = author
        self.echo = False


def parse_irc_tags(raw_tags: str) -> dict[str, str]:
    if not raw_tags:
        return {}

    parsed: dict[str, str] = {}
    for item in raw_tags.split(";"):
        if "=" in item:
            key, value = item.split("=", maxsplit=1)
        else:
            key, value = item, ""
        parsed[key] = value.replace(r"\s", " ").replace(r"\:", ";").replace(r"\\", "\\")
    return parsed


def flatten_chat_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return " | ".join(lines)


def is_irc_auth_failure_line(line: str) -> bool:
    lowered_line = (line or "").lower()
    return (
        "login authentication failed" in lowered_line
        or "improperly formatted auth" in lowered_line
    )


class TwitchAuthError(RuntimeError):
    pass


class TwitchTokenManager:
    def __init__(
        self,
        *,
        access_token: str,
        refresh_token: str = "",
        client_id: str = "",
        client_secret: str = "",
        refresh_margin_seconds: int = 300,
    ) -> None:
        self.access_token = access_token.strip().removeprefix("oauth:")
        self.refresh_token = refresh_token.strip()
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.refresh_margin_seconds = max(30, int(refresh_margin_seconds))
        self.expires_at_monotonic: float | None = None
        self.validated_once = False

    @property
    def can_refresh(self) -> bool:
        return bool(self.refresh_token and self.client_id and self.client_secret)

    def _set_expiration(self, expires_in: int | float | str | None) -> None:
        if expires_in is None:
            self.expires_at_monotonic = None
            return
        try:
            expiry_seconds = float(expires_in)
        except (TypeError, ValueError):
            self.expires_at_monotonic = None
            return
        self.expires_at_monotonic = time.monotonic() + max(expiry_seconds, 0.0)

    def _is_expiring_soon(self) -> bool:
        if self.expires_at_monotonic is None:
            return False
        return time.monotonic() >= (
            self.expires_at_monotonic - self.refresh_margin_seconds
        )

    def _validate_token_sync(self) -> dict | None:
        request = Request(
            TWITCH_OAUTH_VALIDATE_ENDPOINT,
            headers={"Authorization": f"OAuth {self.access_token}"},
        )
        try:
            with urlopen(
                request, timeout=TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS
            ) as response:
                if response.status != 200:
                    return None
                payload = response.read()
        except HTTPError as error:
            if error.code in {400, 401}:
                return None
            raise TwitchAuthError(
                f"Falha ao validar token Twitch (HTTP {error.code})."
            ) from error
        except (URLError, TimeoutError, ValueError) as error:
            raise TwitchAuthError(
                f"Falha de rede ao validar token Twitch: {error}"
            ) from error

        try:
            parsed_payload = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TwitchAuthError(
                "Resposta invalida ao validar token Twitch."
            ) from error
        return parsed_payload if isinstance(parsed_payload, dict) else None

    def _refresh_token_sync(self) -> dict:
        payload = urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode("utf-8")
        request = Request(
            TWITCH_OAUTH_REFRESH_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urlopen(
                request, timeout=TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS
            ) as response:
                raw_payload = response.read()
                status_code = response.status
        except HTTPError as error:
            response_text = ""
            try:
                response_text = error.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                response_text = ""
            details = response_text or f"HTTP {error.code}"
            raise TwitchAuthError(
                f"Falha ao renovar token Twitch: {details}"
            ) from error
        except (URLError, TimeoutError, ValueError) as error:
            raise TwitchAuthError(
                f"Falha de rede ao renovar token Twitch: {error}"
            ) from error

        if status_code != 200:
            raise TwitchAuthError(f"Falha ao renovar token Twitch: HTTP {status_code}")

        try:
            parsed_payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TwitchAuthError(
                "Resposta invalida no refresh de token Twitch."
            ) from error

        if not isinstance(parsed_payload, dict) or not parsed_payload.get(
            "access_token"
        ):
            raise TwitchAuthError("Resposta de refresh da Twitch sem access_token.")
        return parsed_payload

    async def force_refresh(self, reason: str) -> str:
        if not self.can_refresh:
            raise TwitchAuthError(
                "Refresh automatico requer TWITCH_REFRESH_TOKEN, TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET."
            )
        refreshed_payload = await asyncio.to_thread(self._refresh_token_sync)
        self.access_token = (
            str(refreshed_payload.get("access_token", ""))
            .strip()
            .removeprefix("oauth:")
        )
        previous_refresh_token = self.refresh_token
        rotated_refresh_token = str(refreshed_payload.get("refresh_token", "")).strip()
        if rotated_refresh_token:
            self.refresh_token = rotated_refresh_token
            if rotated_refresh_token != previous_refresh_token:
                logger.info(
                    "Refresh token Twitch rotacionado em memoria para esta instancia."
                )
        self._set_expiration(refreshed_payload.get("expires_in"))
        self.validated_once = True
        logger.info("Token Twitch renovado automaticamente (%s).", reason)
        observability.record_token_refresh(reason=reason)
        return self.access_token

    async def ensure_token_for_connection(self) -> str:
        if not self.access_token:
            raise TwitchAuthError("TWITCH_USER_TOKEN ausente.")

        if self.can_refresh:
            if self.expires_at_monotonic is None:
                validation = await asyncio.to_thread(self._validate_token_sync)
                self.validated_once = True
                if validation is None:
                    logger.warning(
                        "Token Twitch invalido. Tentando renovar automaticamente..."
                    )
                    await self.force_refresh("token invalido antes da conexao IRC")
                else:
                    self._set_expiration(validation.get("expires_in"))
            if self._is_expiring_soon():
                await self.force_refresh("token proximo da expiracao")
            return self.access_token

        if not self.validated_once:
            validation = await asyncio.to_thread(self._validate_token_sync)
            self.validated_once = True
            if validation is None:
                raise TwitchAuthError(
                    "TWITCH_USER_TOKEN invalido e refresh automatico nao configurado."
                )
            self._set_expiration(validation.get("expires_in"))

        return self.access_token


class IrcByteBot:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        use_tls: bool,
        bot_login: str,
        channel_login: str | None = None,
        channel_logins: list[str] | None = None,
        user_token: str = "",
        token_manager: TwitchTokenManager | None = None,
    ) -> None:
        provided_channels = list(channel_logins or [])
        if channel_login:
            provided_channels.append(channel_login)
        resolved_channels: list[str] = []
        seen_channels: set[str] = set()
        for candidate in provided_channels:
            normalized = normalize_channel_login(candidate)
            if not normalized or normalized in seen_channels:
                continue
            seen_channels.add(normalized)
            resolved_channels.append(normalized)
        if not resolved_channels:
            raise RuntimeError("Defina ao menos 1 canal valido para o modo IRC.")

        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.bot_login = bot_login.lower()
        self.channel_logins = resolved_channels
        self.joined_channels = set(resolved_channels)
        self.primary_channel_login = resolved_channels[0]
        self.token_manager = token_manager or TwitchTokenManager(
            access_token=user_token
        )
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    def build_status_line(self) -> str:
        return build_status_line(channel_logins=self.channel_logins)

    def _prepare_reply_text(self, text: str) -> str:
        return flatten_chat_text(format_chat_reply(text))

    async def send_reply(self, text: str, channel_login: str | None = None) -> None:
        target_channel = normalize_channel_login(
            channel_login or self.primary_channel_login
        )
        if not target_channel:
            target_channel = self.primary_channel_login
        if target_channel not in self.joined_channels:
            target_channel = self.primary_channel_login

        safe_text = self._prepare_reply_text(text)
        if not safe_text:
            return
        await self._send_raw(f"PRIVMSG #{target_channel} :{safe_text}")

    async def _send_tracked_channel_reply(self, channel_login: str, text: str) -> None:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel or target_channel not in self.joined_channels:
            return
        safe_text = self._prepare_reply_text(text)
        if not safe_text:
            return
        context.remember_bot_reply(safe_text)
        observability.record_reply(text=safe_text)
        await self._send_raw(f"PRIVMSG #{target_channel} :{safe_text}")

    async def _join_channel(self, channel_login: str) -> bool:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return False
        if target_channel in self.joined_channels:
            return False

        await self._send_raw(f"JOIN #{target_channel}")
        self.channel_logins.append(target_channel)
        self.joined_channels.add(target_channel)
        if not self.primary_channel_login:
            self.primary_channel_login = target_channel
        logger.info("Byte entrou no canal IRC #%s", target_channel)
        return True

    async def _part_channel(self, channel_login: str) -> bool:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return False
        if target_channel not in self.joined_channels:
            return False
        if len(self.channel_logins) <= 1:
            return False

        await self._send_raw(f"PART #{target_channel}")
        self.joined_channels.remove(target_channel)
        self.channel_logins = [
            channel for channel in self.channel_logins if channel != target_channel
        ]
        self.primary_channel_login = self.channel_logins[0]
        logger.info("Byte saiu do canal IRC #%s", target_channel)
        return True

    async def admin_list_channels(self) -> list[str]:
        return list(self.channel_logins)

    async def admin_join_channel(
        self, channel_login: str
    ) -> tuple[bool, str, list[str]]:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return (
                False,
                "Invalid channel login. Use Twitch login format (no #).",
                list(self.channel_logins),
            )

        if target_channel in self.joined_channels:
            return (
                True,
                f"Already connected to #{target_channel}.",
                list(self.channel_logins),
            )

        joined = await self._join_channel(target_channel)
        if not joined:
            return (
                False,
                f"Failed to join #{target_channel}.",
                list(self.channel_logins),
            )
        return (True, f"Joined #{target_channel}.", list(self.channel_logins))

    async def admin_part_channel(
        self, channel_login: str
    ) -> tuple[bool, str, list[str]]:
        target_channel = normalize_channel_login(channel_login)
        if not target_channel:
            return (
                False,
                "Invalid channel login. Use Twitch login format (no #).",
                list(self.channel_logins),
            )

        if target_channel not in self.joined_channels:
            return (
                False,
                f"Channel not connected: #{target_channel}.",
                list(self.channel_logins),
            )

        if len(self.channel_logins) <= 1:
            return (
                False,
                "Cannot leave the last active channel. Join another one first.",
                list(self.channel_logins),
            )

        parted = await self._part_channel(target_channel)
        if not parted:
            return (
                False,
                f"Failed to leave #{target_channel}.",
                list(self.channel_logins),
            )
        return (True, f"Left #{target_channel}.", list(self.channel_logins))

    def _parse_channel_management_prompt(self, prompt: str) -> tuple[str, str] | None:
        normalized_prompt = " ".join((prompt or "").strip().split())
        if not normalized_prompt:
            return None

        lowered_prompt = normalized_prompt.lower()
        if lowered_prompt in {
            "canais",
            "canal",
            "channels",
            "channel",
            "list channels",
            "listar canais",
        }:
            return ("list", "")

        for prefix in ("join ", "entrar ", "add "):
            if lowered_prompt.startswith(prefix):
                return ("join", normalized_prompt[len(prefix) :].strip())

        for prefix in ("part ", "leave ", "sair ", "remove "):
            if lowered_prompt.startswith(prefix):
                return ("part", normalized_prompt[len(prefix) :].strip())

        return None

    async def _handle_channel_management_prompt(
        self, prompt: str, author: IrcAuthor, source_channel: str
    ) -> bool:
        command = self._parse_channel_management_prompt(prompt)
        if command is None:
            return False

        if not is_owner(author.id):
            await self._send_tracked_channel_reply(
                source_channel,
                "Somente o owner pode gerenciar canais do Byte.",
            )
            return True

        action, raw_target = command
        if action == "list":
            channels = ", ".join(f"#{channel}" for channel in self.channel_logins)
            await self._send_tracked_channel_reply(
                source_channel,
                f"Canais ativos: {channels}.",
            )
            return True

        if action == "join":
            target_channel = normalize_channel_login(raw_target)
            if not target_channel:
                await self._send_tracked_channel_reply(
                    source_channel,
                    "Uso: byte join <canal>.",
                )
                return True
            if target_channel in self.joined_channels:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Ja estou no canal #{target_channel}.",
                )
                return True

            joined = await self._join_channel(target_channel)
            if joined:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Canal adicionado: #{target_channel}. Byte responde onde for acionado.",
                )
            else:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Nao consegui entrar em #{target_channel}.",
                )
            return True

        if action == "part":
            target_channel = normalize_channel_login(raw_target or source_channel)
            if not target_channel:
                await self._send_tracked_channel_reply(
                    source_channel,
                    "Uso: byte part <canal>.",
                )
                return True
            if target_channel not in self.joined_channels:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Nao estou no canal #{target_channel}.",
                )
                return True
            if len(self.channel_logins) <= 1:
                await self._send_tracked_channel_reply(
                    source_channel,
                    "Nao posso sair do ultimo canal ativo. Entre em outro canal primeiro com 'byte join <canal>'.",
                )
                return True

            if target_channel == source_channel:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Saindo de #{target_channel}.",
                )
                await self._part_channel(target_channel)
                return True

            parted = await self._part_channel(target_channel)
            if parted:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Canal removido: #{target_channel}.",
                )
            else:
                await self._send_tracked_channel_reply(
                    source_channel,
                    f"Nao consegui sair de #{target_channel}.",
                )
            return True

        return False

    async def _send_raw(self, line: str) -> None:
        if self.writer is None:
            raise RuntimeError("Conexao IRC nao inicializada.")
        self.writer.write(f"{line}\r\n".encode("utf-8"))
        await self.writer.drain()

    async def _await_login_confirmation(self, timeout_seconds: float = 15.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timeout aguardando confirmacao de login IRC.")
            if self.reader is None:
                raise RuntimeError("Leitor IRC indisponivel durante login.")

            payload = await asyncio.wait_for(self.reader.readline(), timeout=remaining)
            if not payload:
                raise ConnectionError("Conexao IRC encerrada durante autenticacao.")

            line = payload.decode("utf-8", errors="ignore").rstrip("\r\n")
            if not line:
                continue
            if line.startswith("PING"):
                await self._send_raw(line.replace("PING", "PONG", 1))
                continue
            if is_irc_auth_failure_line(line):
                raise TwitchAuthError(f"Falha de autenticacao IRC: {line}")
            if IRC_WELCOME_PATTERN.search(line):
                return

    async def _connect(self) -> None:
        access_token = await self.token_manager.ensure_token_for_connection()
        ssl_context = ssl.create_default_context() if self.use_tls else None
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port, ssl=ssl_context
        )
        await self._send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands")
        await self._send_raw(f"PASS oauth:{access_token}")
        await self._send_raw(f"NICK {self.bot_login}")
        await self._await_login_confirmation()
        for channel_login in self.channel_logins:
            await self._send_raw(f"JOIN #{channel_login}")
        channels_summary = ", ".join(f"#{channel}" for channel in self.channel_logins)
        logger.info("%s conectado via IRC em %s", BOT_BRAND, channels_summary)

    async def _close(self) -> None:
        if self.writer is None:
            return
        try:
            self.writer.close()
            await self.writer.wait_closed()
        finally:
            self.reader = None
            self.writer = None

    async def _handle_privmsg(self, line: str) -> None:
        match = IRC_PRIVMSG_PATTERN.match(line)
        if not match:
            return

        channel = match.group("channel").lstrip("#").lower()
        if channel not in self.joined_channels:
            return

        author_login = (match.group("author") or "").strip().lower()
        if not author_login or author_login == self.bot_login:
            return

        text = (match.group("message") or "").strip()
        if not text:
            return

        tags = parse_irc_tags(match.group("tags") or "")
        author = IrcAuthor(author_login, tags)
        message = IrcMessageAdapter(text, author)
        byte_prompt = parse_byte_prompt(text)
        if not text.startswith("!") or byte_prompt is not None:
            if ENABLE_LIVE_CONTEXT_LEARNING:
                context.remember_user_message(author.name, text)
            observability.record_chat_message(
                author_name=author.name, source="irc", text=text
            )

        updates: list[str] = []
        if ENABLE_LIVE_CONTEXT_LEARNING:
            updates = await auto_update_scene_from_message(message)
        if updates:
            labels = ", ".join(
                OBSERVABILITY_TYPES.get(content_type, content_type)
                for content_type in updates
            )
            logger.info("Observabilidade automatica atualizada: %s", labels)
            observability.record_auto_scene_update(update_types=updates)

        if byte_prompt is None:
            return
        observability.record_byte_trigger(
            prompt=byte_prompt, source="irc", author_name=author.name
        )
        management_handled = await self._handle_channel_management_prompt(
            byte_prompt, author, channel
        )
        if management_handled:
            return

        async def reply_in_source_channel(text: str) -> None:
            await self.send_reply(text, channel_login=channel)

        await handle_byte_prompt_text(
            byte_prompt,
            author.name,
            reply_in_source_channel,
            status_line_factory=self.build_status_line,
        )

    async def _recover_authentication(self, auth_error: Exception) -> bool:
        logger.warning("Falha de autenticacao IRC: %s", auth_error)
        observability.record_auth_failure(details=str(auth_error))
        try:
            await self.token_manager.force_refresh("falha de autenticacao IRC")
            logger.info("Reconectando com token renovado automaticamente.")
            return True
        except Exception as refresh_error:
            logger.error("Refresh automatico falhou: %s", refresh_error)
            observability.record_error(
                category="irc_refresh", details=str(refresh_error)
            )
            return False

    async def run_forever(self) -> None:
        while True:
            reconnect_delay_seconds = 5
            try:
                await self._connect()
                while True:
                    if self.reader is None:
                        raise RuntimeError("Leitor IRC indisponivel.")
                    payload = await self.reader.readline()
                    if not payload:
                        raise ConnectionError("Conexao IRC encerrada.")
                    line = payload.decode("utf-8", errors="ignore").rstrip("\r\n")
                    if not line:
                        continue
                    if line.startswith("PING"):
                        await self._send_raw(line.replace("PING", "PONG", 1))
                        continue
                    if is_irc_auth_failure_line(line):
                        raise TwitchAuthError(line)
                    if line.startswith("RECONNECT"):
                        raise ConnectionError("Servidor IRC solicitou reconexao.")
                    await self._handle_privmsg(line)
            except asyncio.CancelledError:
                raise
            except TwitchAuthError as auth_error:
                recovered = await self._recover_authentication(auth_error)
                reconnect_delay_seconds = 2 if recovered else 20
            except Exception as error:
                logger.warning("Conexao IRC instavel: %s", error)
                observability.record_error(
                    category="irc_connection", details=str(error)
                )
                reconnect_delay_seconds = 5
            finally:
                await self._close()
            await asyncio.sleep(reconnect_delay_seconds)


class HealthHandler(BaseHTTPRequestHandler):
    MAX_CONTROL_BODY_BYTES = 4096

    def _send_bytes(
        self, payload: bytes, content_type: str, status_code: int = 200
    ) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
        serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(
            serialized, "application/json; charset=utf-8", status_code=status_code
        )

    def _send_text(self, text: str, status_code: int = 200) -> None:
        self._send_bytes(
            text.encode("utf-8"), "text/plain; charset=utf-8", status_code=status_code
        )

    def _dashboard_authorized(self) -> bool:
        if not BYTE_DASHBOARD_ADMIN_TOKEN:
            return True
        return is_dashboard_admin_authorized(
            self.headers, BYTE_DASHBOARD_ADMIN_TOKEN
        )

    def _send_dashboard_auth_challenge(self) -> None:
        payload = b"Unauthorized"
        self.send_response(401)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("WWW-Authenticate", 'Basic realm="Byte Dashboard"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_payload(self) -> dict[str, Any]:
        raw_length = str(self.headers.get("Content-Length", "0") or "0")
        try:
            content_length = int(raw_length)
        except ValueError as error:
            raise ValueError("Invalid Content-Length header.") from error

        if content_length <= 0:
            raise ValueError("Request body is required.")
        if content_length > self.MAX_CONTROL_BODY_BYTES:
            raise ValueError("Request body is too large.")

        payload_bytes = self.rfile.read(content_length)
        if not payload_bytes:
            raise ValueError("Request body is empty.")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid JSON payload.") from error

        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object.")
        return payload

    def _send_dashboard_asset(self, relative_path: str, content_type: str) -> bool:
        target_path = (DASHBOARD_DIR / relative_path).resolve()
        if DASHBOARD_DIR not in target_path.parents:
            self._send_text("Not Found", status_code=404)
            return True
        if not target_path.is_file():
            self._send_text("Not Found", status_code=404)
            return True

        self._send_bytes(
            target_path.read_bytes(), content_type=content_type, status_code=200
        )
        return True

    def do_GET(self):
        parsed_path = urlparse(self.path or "/")
        route = parsed_path.path or "/"
        if route in {"/", "/healthz"}:
            self._send_text("AGENT_ONLINE", status_code=200)
            return

        protected_dashboard_routes = {
            "/api/observability",
            "/dashboard",
            "/dashboard/",
            "/dashboard/app.js",
            "/dashboard/styles.css",
            "/dashboard/channel-terminal.js",
        }
        if route in protected_dashboard_routes and not self._dashboard_authorized():
            if route.startswith("/dashboard"):
                self._send_dashboard_auth_challenge()
            else:
                self._send_json(
                    {"ok": False, "error": "forbidden", "message": "Forbidden"},
                    status_code=403,
                )
            return

        if route == "/api/observability":
            snapshot = observability.snapshot(
                bot_brand=BOT_BRAND,
                bot_version=BYTE_VERSION,
                bot_mode=TWITCH_CHAT_MODE,
                stream_context=context,
            )
            self._send_json(snapshot, status_code=200)
            return

        if route in {"/dashboard", "/dashboard/"}:
            self._send_dashboard_asset("index.html", "text/html; charset=utf-8")
            return

        if route == "/dashboard/app.js":
            self._send_dashboard_asset(
                "app.js", "application/javascript; charset=utf-8"
            )
            return

        if route == "/dashboard/styles.css":
            self._send_dashboard_asset("styles.css", "text/css; charset=utf-8")
            return

        if route == "/dashboard/channel-terminal.js":
            self._send_dashboard_asset(
                "channel-terminal.js", "application/javascript; charset=utf-8"
            )
            return

        self._send_text("Not Found", status_code=404)

    def do_POST(self):
        parsed_path = urlparse(self.path or "/")
        route = parsed_path.path or "/"

        if route != "/api/channel-control":
            self._send_text("Not Found", status_code=404)
            return

        if not is_dashboard_admin_authorized(self.headers, BYTE_DASHBOARD_ADMIN_TOKEN):
            self._send_json(
                {"ok": False, "error": "forbidden", "message": "Forbidden"},
                status_code=403,
            )
            return

        try:
            payload = self._read_json_payload()
        except ValueError as error:
            self._send_json(
                {"ok": False, "error": "invalid_request", "message": str(error)},
                status_code=400,
            )
            return

        action = str(payload.get("action", "") or "").strip().lower()
        channel_login = str(payload.get("channel", "") or "").strip()
        command_text = str(payload.get("command", "") or "").strip()
        if command_text:
            try:
                action, channel_login = parse_terminal_command(command_text)
            except ValueError as error:
                self._send_json(
                    {"ok": False, "error": "invalid_command", "message": str(error)},
                    status_code=400,
                )
                return

        result = irc_channel_control.execute(action=action, channel_login=channel_login)
        if result.get("ok"):
            self._send_json(result, status_code=200)
            return

        error_code = str(result.get("error", "") or "")
        if error_code in {"runtime_unavailable", "timeout"}:
            status_code = 503
        elif error_code in {"runtime_error"}:
            status_code = 500
        else:
            status_code = 400
        self._send_json(result, status_code=status_code)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server():
    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


def get_secret(secret_name: str = "twitch-client-secret") -> str:
    sm = secretmanager.SecretManagerServiceClient()
    path = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    return sm.access_secret_version(name=path).payload.data.decode("UTF-8")


def require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


def resolve_irc_channel_logins() -> list[str]:
    explicit_channels = parse_channel_logins(TWITCH_CHANNEL_LOGINS_RAW)
    if explicit_channels:
        return explicit_channels

    fallback_channels = parse_channel_logins(TWITCH_CHANNEL_LOGIN)
    if fallback_channels:
        return fallback_channels

    required_single_channel = require_env("TWITCH_CHANNEL_LOGIN")
    required_channels = parse_channel_logins(required_single_channel)
    if not required_channels:
        raise RuntimeError(
            "TWITCH_CHANNEL_LOGIN invalido. Use login Twitch sem # e com 3-25 caracteres."
        )
    return required_channels


def resolve_client_secret_for_irc_refresh() -> str:
    if TWITCH_CLIENT_SECRET_INLINE:
        return TWITCH_CLIENT_SECRET_INLINE
    if not PROJECT_ID:
        return ""
    secret_name = TWITCH_CLIENT_SECRET_NAME or "twitch-client-secret"
    try:
        return get_secret(secret_name=secret_name)
    except Exception as error:
        logger.warning(
            "Nao foi possivel ler segredo '%s' para refresh automatico: %s",
            secret_name,
            error,
        )
        return ""


def build_irc_token_manager() -> TwitchTokenManager:
    user_token = TWITCH_USER_TOKEN or require_env("TWITCH_USER_TOKEN")
    refresh_token = TWITCH_REFRESH_TOKEN.strip()
    if not refresh_token:
        return TwitchTokenManager(access_token=user_token)

    client_id = CLIENT_ID or require_env("TWITCH_CLIENT_ID")
    client_secret = resolve_client_secret_for_irc_refresh()
    if not client_secret:
        raise RuntimeError(
            "TWITCH_REFRESH_TOKEN definido, mas TWITCH_CLIENT_SECRET nao encontrado. "
            "Defina TWITCH_CLIENT_SECRET ou configure o segredo no Secret Manager."
        )

    return TwitchTokenManager(
        access_token=user_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        refresh_margin_seconds=TWITCH_TOKEN_REFRESH_MARGIN_SECONDS,
    )


def run_irc_mode() -> None:
    token_manager = build_irc_token_manager()
    channel_logins = resolve_irc_channel_logins()
    bot = IrcByteBot(
        host=TWITCH_IRC_HOST,
        port=TWITCH_IRC_PORT,
        use_tls=TWITCH_IRC_TLS,
        bot_login=TWITCH_BOT_LOGIN or require_env("TWITCH_BOT_LOGIN"),
        channel_logins=channel_logins,
        token_manager=token_manager,
    )

    async def run_with_channel_control() -> None:
        irc_channel_control.bind(loop=asyncio.get_running_loop(), bot=bot)
        try:
            await bot.run_forever()
        finally:
            irc_channel_control.unbind()

    asyncio.run(run_with_channel_control())


def run_eventsub_mode() -> None:
    require_env("TWITCH_CLIENT_ID")
    require_env("TWITCH_BOT_ID")
    require_env("TWITCH_CHANNEL_ID")
    bot = ByteBot(client_secret=get_secret())
    bot.run()


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    try:
        if TWITCH_CHAT_MODE == "irc":
            run_irc_mode()
        else:
            run_eventsub_mode()
    except Exception as e:
        logger.critical("Fatal Byte Error: %s", e)
        observability.record_error(category="fatal", details=str(e))
