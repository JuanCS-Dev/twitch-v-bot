import os
import json
import asyncio
import time
import threading
import logging
import re
import ssl
from typing import Any, cast
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, quote_plus, urlunparse, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import twitchio
from twitchio import eventsub
from twitchio.ext import commands
from google import genai
from google.cloud import secretmanager

from bot import byte_semantics
from bot.logic import (
    BOT_BRAND,
    MAX_REPLY_LINES,
    OBSERVABILITY_TYPES,
    agent_inference,
    context,
)

# ── Setup ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ByteBot")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
CLIENT_ID  = os.environ.get("TWITCH_CLIENT_ID")
BOT_ID     = os.environ.get("TWITCH_BOT_ID")
OWNER_ID   = os.environ.get("TWITCH_OWNER_ID")
CHANNEL_ID = os.environ.get("TWITCH_CHANNEL_ID")
TWITCH_CHAT_MODE = os.environ.get("TWITCH_CHAT_MODE", "eventsub").strip().lower() or "eventsub"
TWITCH_CHANNEL_LOGIN = os.environ.get("TWITCH_CHANNEL_LOGIN", "").strip().lstrip("#").lower()
TWITCH_BOT_LOGIN = os.environ.get("TWITCH_BOT_LOGIN", "").strip().lower()
TWITCH_USER_TOKEN = os.environ.get("TWITCH_USER_TOKEN", "").strip().removeprefix("oauth:")
TWITCH_REFRESH_TOKEN = os.environ.get("TWITCH_REFRESH_TOKEN", "").strip()
TWITCH_CLIENT_SECRET_INLINE = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
TWITCH_CLIENT_SECRET_NAME = os.environ.get("TWITCH_CLIENT_SECRET_SECRET_NAME", "twitch-client-secret").strip()
TWITCH_IRC_HOST = os.environ.get("TWITCH_IRC_HOST", "irc.chat.twitch.tv").strip() or "irc.chat.twitch.tv"
TWITCH_IRC_PORT = int(os.environ.get("TWITCH_IRC_PORT", "6697"))
TWITCH_IRC_TLS = os.environ.get("TWITCH_IRC_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
TWITCH_TOKEN_REFRESH_MARGIN_SECONDS = int(os.environ.get("TWITCH_TOKEN_REFRESH_MARGIN_SECONDS", "300"))
TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS = float(os.environ.get("TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS", "5.0"))
TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS = float(os.environ.get("TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS", "8.0"))

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
build_verifiable_prompt = byte_semantics.build_verifiable_prompt
is_serious_technical_prompt = byte_semantics.is_serious_technical_prompt
is_follow_up_prompt = byte_semantics.is_follow_up_prompt
build_direct_answer_instruction = byte_semantics.build_direct_answer_instruction
build_llm_enhanced_prompt = byte_semantics.build_llm_enhanced_prompt
extract_multi_reply_parts = byte_semantics.extract_multi_reply_parts
extract_movie_title = byte_semantics.extract_movie_title
build_movie_fact_sheet_query = byte_semantics.build_movie_fact_sheet_query
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

URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)
YOUTUBE_HOSTS = {"youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}
X_HOSTS = {"x.com", "twitter.com", "mobile.twitter.com"}
BLOCKED_DOMAINS = {
    "pornhub.com",
    "xvideos.com",
    "xnxx.com",
    "xhamster.com",
    "onlyfans.com",
    "redtube.com",
}
UNSAFE_TERMS = {
    "nude",
    "nud3",
    "nudity",
    "sexo",
    "sex",
    "porn",
    "porno",
    "nsfw",
    "onlyfans",
    "gore",
    "estupro",
    "rape",
    "bestiality",
}
UNSAFE_TERM_PATTERNS = [re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])") for term in UNSAFE_TERMS]
METADATA_CACHE_TTL_SECONDS = int(os.environ.get("AUTO_SCENE_CACHE_TTL_SECONDS", "900"))
METADATA_TIMEOUT_SECONDS = float(os.environ.get("AUTO_SCENE_METADATA_TIMEOUT_SECONDS", "3.0"))
AUTO_SCENE_REQUIRE_METADATA = os.environ.get("AUTO_SCENE_REQUIRE_METADATA", "true").lower() in {"1", "true", "yes"}
metadata_cache: dict[str, tuple[float, dict]] = {}


def is_owner(user_id: str) -> bool:
    return str(user_id) == OWNER_ID


def is_moderator(author) -> bool:
    return bool(getattr(author, "is_mod", False)) or bool(getattr(author, "is_moderator", False))


def is_trusted_curator(author) -> bool:
    return is_owner(getattr(author, "id", "")) or is_moderator(author)


def normalize_host(host: str) -> str:
    normalized = host.strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    if ":" in normalized:
        normalized = normalized.split(":", maxsplit=1)[0]
    return normalized


def extract_urls(text: str) -> list[str]:
    urls = []
    for raw_url in URL_REGEX.findall(text or ""):
        cleaned_url = raw_url.rstrip(".,!?)]}'\"")
        if cleaned_url:
            urls.append(cleaned_url)
    return urls


def contains_unsafe_terms(text: str) -> bool:
    normalized_text = (text or "").lower()
    return any(pattern.search(normalized_text) for pattern in UNSAFE_TERM_PATTERNS)


def classify_supported_link(url: str) -> str | None:
    parsed = urlparse(url)
    host = normalize_host(parsed.netloc)
    if host in YOUTUBE_HOSTS:
        return "youtube"
    if host in X_HOSTS:
        return "x"
    return None


def is_safe_scene_link(url: str, original_text: str) -> bool:
    parsed = urlparse(url)
    host = normalize_host(parsed.netloc)
    if not host:
        return False
    if host in BLOCKED_DOMAINS:
        return False
    if contains_unsafe_terms(f"{original_text} {parsed.path} {parsed.query}"):
        return False
    return True


def build_status_line() -> str:
    uptime = context.get_uptime_minutes()
    return f"{BOT_BRAND} v{BYTE_VERSION} | Uptime: {uptime}min | {context.status_snapshot()}"


async def handle_movie_fact_sheet_prompt(
    prompt: str,
    author_name: str,
    reply_fn,
) -> None:
    movie_title_from_prompt = extract_movie_title(prompt)
    if movie_title_from_prompt:
        context.update_content("movie", movie_title_from_prompt)

    active_movie = context.live_observability.get("movie", "").strip()
    movie_title = movie_title_from_prompt or active_movie
    if not movie_title:
        await reply_fn("Preciso do nome do filme. Ex.: byte ficha tecnica de Duna Parte 2")
        return

    query = build_movie_fact_sheet_query(movie_title)
    ans = await agent_inference(query, author_name, client, context)
    await reply_fn(format_chat_reply(ans))


async def handle_byte_prompt_text(prompt: str, author_name: str, reply_fn) -> None:
    normalized_prompt = (prompt or "").strip()
    lowered_prompt = normalized_prompt.lower()
    prompt_length = len(normalized_prompt)
    serious_mode = is_serious_technical_prompt(normalized_prompt)
    follow_up_mode = is_follow_up_prompt(normalized_prompt)
    current_events_mode = is_current_events_prompt(normalized_prompt)
    sent_replies: list[str] = []

    async def tracked_reply(text: str) -> None:
        final_text = format_chat_reply(text)
        if not final_text:
            return
        sent_replies.append(final_text)
        context.remember_bot_reply(final_text)
        await reply_fn(final_text)

    def log_interaction(route: str) -> None:
        total_reply_chars = sum(len(reply) for reply in sent_replies)
        logger.info(
            "ByteInteraction route=%s author=%s prompt_chars=%d reply_parts=%d reply_chars=%d serious=%s follow_up=%s current_events=%s",
            route,
            author_name,
            prompt_length,
            len(sent_replies),
            total_reply_chars,
            serious_mode,
            follow_up_mode,
            current_events_mode,
        )

    if not normalized_prompt or lowered_prompt in {"ajuda", "help", "comandos"}:
        await tracked_reply(BYTE_HELP_MESSAGE)
        log_interaction("help")
        return

    if is_intro_prompt(normalized_prompt):
        await tracked_reply(build_intro_reply())
        log_interaction("intro")
        return

    if lowered_prompt.startswith("status"):
        await tracked_reply(build_status_line())
        log_interaction("status")
        return

    if is_movie_fact_sheet_prompt(normalized_prompt):
        await handle_movie_fact_sheet_prompt(normalized_prompt, author_name, tracked_reply)
        log_interaction("movie_fact_sheet")
        return

    inference_prompt = build_llm_enhanced_prompt(normalized_prompt)
    ans = await agent_inference(
        inference_prompt,
        author_name,
        client,
        context,
        max_lines=SERIOUS_REPLY_MAX_LINES if serious_mode else MAX_REPLY_LINES,
        max_length=SERIOUS_REPLY_MAX_LENGTH if serious_mode else MAX_CHAT_MESSAGE_LENGTH,
    )

    if serious_mode:
        parts = extract_multi_reply_parts(ans, max_parts=2)
        if not parts:
            await tracked_reply(ans)
            log_interaction("llm_serious_single")
            return
        for part in parts:
            await tracked_reply(part)
        log_interaction("llm_serious_split")
        return

    await tracked_reply(ans)
    log_interaction("llm_default")


def build_oembed_endpoint(url: str, content_type: str) -> str | None:
    encoded_url = quote_plus(url)
    if content_type == "youtube":
        return f"https://www.youtube.com/oembed?url={encoded_url}&format=json"
    if content_type == "x":
        return f"https://publish.twitter.com/oembed?url={encoded_url}&omit_script=true"
    return None


def build_metadata_source_url(url: str, content_type: str) -> str:
    if content_type != "x":
        return url

    parsed = urlparse(url)
    host = normalize_host(parsed.netloc)
    if host == "x.com":
        return urlunparse(parsed._replace(netloc="twitter.com"))
    return url


def fetch_oembed_metadata(url: str, content_type: str) -> dict | None:
    source_url = build_metadata_source_url(url, content_type)
    endpoint = build_oembed_endpoint(source_url, content_type)
    if not endpoint:
        return None

    request = Request(endpoint, headers={"User-Agent": "ByteBot/1.0"})
    try:
        with urlopen(request, timeout=METADATA_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return None
            payload = response.read()
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None

    try:
        parsed_payload = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    return parsed_payload if isinstance(parsed_payload, dict) else None


def get_cached_metadata(url: str) -> dict | None:
    now = time.monotonic()
    cached = metadata_cache.get(url)
    if not cached:
        return None

    expires_at, metadata = cached
    if now > expires_at:
        metadata_cache.pop(url, None)
        return None
    return metadata


def set_cached_metadata(url: str, metadata: dict) -> None:
    expires_at = time.monotonic() + METADATA_CACHE_TTL_SECONDS
    metadata_cache[url] = (expires_at, metadata)


async def resolve_scene_metadata(url: str, content_type: str) -> dict | None:
    cached = get_cached_metadata(url)
    if cached:
        return cached

    metadata = await asyncio.to_thread(fetch_oembed_metadata, url, content_type)
    if metadata:
        set_cached_metadata(url, metadata)
    return metadata


def metadata_to_safety_text(metadata: dict | None) -> str:
    if not metadata:
        return ""
    inspected_keys = ("title", "author_name", "provider_name", "description")
    values = [str(metadata.get(key, "")) for key in inspected_keys if metadata.get(key)]
    return " ".join(values)


def is_safe_scene_metadata(metadata: dict | None, message_text: str, url: str) -> bool:
    if metadata is None and AUTO_SCENE_REQUIRE_METADATA:
        return False

    inspection_text = f"{message_text} {url} {metadata_to_safety_text(metadata)}"
    return not contains_unsafe_terms(inspection_text)


def build_sanitized_scene_description(content_type: str, author_name: str, metadata: dict | None) -> str:
    safe_author = normalize_text_for_scene(author_name, max_len=60) or "autor"
    safe_title = normalize_text_for_scene(str((metadata or {}).get("title", "")))
    safe_post_author = normalize_text_for_scene(str((metadata or {}).get("author_name", "")), max_len=60)

    if content_type == "youtube":
        if safe_title:
            return f'Video do YouTube: "{safe_title}" (compartilhado por {safe_author})'
        return f"Video do YouTube compartilhado por {safe_author}"
    if content_type == "x":
        if safe_post_author:
            return f"Post do X de {safe_post_author} (compartilhado por {safe_author})"
        return f"Post do X compartilhado por {safe_author}"
    return f"Contexto compartilhado por {safe_author}"


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
            logger.warning("Auto-observabilidade bloqueada para URL potencialmente insegura: %s", url)
            continue

        metadata = await resolve_scene_metadata(url, content_type)
        if not is_safe_scene_metadata(metadata, message_text, url):
            logger.warning("Auto-observabilidade bloqueada apos classificacao de metadata: %s", url)
            continue

        author_name = str(getattr(author, "name", "autor") or "autor")
        description = compact_message(build_sanitized_scene_description(content_type, author_name, metadata), max_len=220)
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
        ans = await agent_inference(query, author_name, client, context)
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
            await ctx.reply(format_chat_reply(f"Observabilidade da live: {observability}"))
            return

        author_id = str(getattr(get_ctx_author(ctx), "id", "") or "")
        if not is_owner(author_id):
            await ctx.reply("Somente o dono do canal pode atualizar a observabilidade.")
            return

        tokens = payload.split(maxsplit=1)
        action_or_type = tokens[0].lower()

        if action_or_type == "clear":
            if len(tokens) < 2:
                await ctx.reply(f"Uso: !scene clear <tipo>. Tipos: {context.list_supported_content_types()}")
                return

            content_type = tokens[1].strip().lower()
            if not context.clear_content(content_type):
                await ctx.reply(f"Tipo invalido. Tipos: {context.list_supported_content_types()}")
                return

            label = OBSERVABILITY_TYPES.get(content_type, content_type)
            await ctx.reply(f"Contexto removido: {label}.")
            return

        if len(tokens) < 2:
            await ctx.reply(f"Uso: !scene <tipo> <descricao>. Tipos: {context.list_supported_content_types()}")
            return

        content_type = action_or_type
        description = tokens[1].strip()
        if not context.update_content(content_type, description):
            await ctx.reply(f"Tipo invalido ou descricao vazia. Tipos: {context.list_supported_content_types()}")
            return

        label = OBSERVABILITY_TYPES.get(content_type, content_type)
        await ctx.reply(format_chat_reply(f"Contexto atualizado: {label} -> {description}"))

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

    async def handle_movie_fact_sheet(self, message: Any, prompt: str, author_name: str) -> None:
        reply_fn = getattr(message, "reply", None)
        if callable(reply_fn):
            await handle_movie_fact_sheet_prompt(prompt, author_name, reply_fn)

    async def handle_byte_prompt(self, message: Any, prompt: str) -> None:
        author = getattr(message, "author", None)
        author_name = str(getattr(author, "name", "viewer") or "viewer")
        reply_fn = getattr(message, "reply", None)
        if callable(reply_fn):
            await handle_byte_prompt_text(prompt, author_name, reply_fn)

    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        message = cast(Any, payload)
        if message.echo:
            return

        raw_text = message.text or ""
        byte_prompt = parse_byte_prompt(raw_text)
        if raw_text and (not raw_text.startswith("!") or byte_prompt is not None):
            author = getattr(message, "author", None)
            context.remember_user_message(str(getattr(author, "name", "viewer") or "viewer"), raw_text)

        updates = await auto_update_scene_from_message(message)
        if updates:
            labels = ", ".join(OBSERVABILITY_TYPES.get(content_type, content_type) for content_type in updates)
            logger.info("Observabilidade automatica atualizada: %s", labels)

        if byte_prompt is not None:
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
    return "login authentication failed" in lowered_line or "improperly formatted auth" in lowered_line


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
        return time.monotonic() >= (self.expires_at_monotonic - self.refresh_margin_seconds)

    def _validate_token_sync(self) -> dict | None:
        request = Request(
            TWITCH_OAUTH_VALIDATE_ENDPOINT,
            headers={"Authorization": f"OAuth {self.access_token}"},
        )
        try:
            with urlopen(request, timeout=TWITCH_TOKEN_VALIDATE_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    return None
                payload = response.read()
        except HTTPError as error:
            if error.code in {400, 401}:
                return None
            raise TwitchAuthError(f"Falha ao validar token Twitch (HTTP {error.code}).") from error
        except (URLError, TimeoutError, ValueError) as error:
            raise TwitchAuthError(f"Falha de rede ao validar token Twitch: {error}") from error

        try:
            parsed_payload = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TwitchAuthError("Resposta invalida ao validar token Twitch.") from error
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
            with urlopen(request, timeout=TWITCH_TOKEN_REFRESH_TIMEOUT_SECONDS) as response:
                raw_payload = response.read()
                status_code = response.status
        except HTTPError as error:
            response_text = ""
            try:
                response_text = error.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                response_text = ""
            details = response_text or f"HTTP {error.code}"
            raise TwitchAuthError(f"Falha ao renovar token Twitch: {details}") from error
        except (URLError, TimeoutError, ValueError) as error:
            raise TwitchAuthError(f"Falha de rede ao renovar token Twitch: {error}") from error

        if status_code != 200:
            raise TwitchAuthError(f"Falha ao renovar token Twitch: HTTP {status_code}")

        try:
            parsed_payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TwitchAuthError("Resposta invalida no refresh de token Twitch.") from error

        if not isinstance(parsed_payload, dict) or not parsed_payload.get("access_token"):
            raise TwitchAuthError("Resposta de refresh da Twitch sem access_token.")
        return parsed_payload

    async def force_refresh(self, reason: str) -> str:
        if not self.can_refresh:
            raise TwitchAuthError(
                "Refresh automatico requer TWITCH_REFRESH_TOKEN, TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET."
            )
        refreshed_payload = await asyncio.to_thread(self._refresh_token_sync)
        self.access_token = str(refreshed_payload.get("access_token", "")).strip().removeprefix("oauth:")
        previous_refresh_token = self.refresh_token
        rotated_refresh_token = str(refreshed_payload.get("refresh_token", "")).strip()
        if rotated_refresh_token:
            self.refresh_token = rotated_refresh_token
            if rotated_refresh_token != previous_refresh_token:
                logger.info("Refresh token Twitch rotacionado em memoria para esta instancia.")
        self._set_expiration(refreshed_payload.get("expires_in"))
        self.validated_once = True
        logger.info("Token Twitch renovado automaticamente (%s).", reason)
        return self.access_token

    async def ensure_token_for_connection(self) -> str:
        if not self.access_token:
            raise TwitchAuthError("TWITCH_USER_TOKEN ausente.")

        if self.can_refresh:
            if self.expires_at_monotonic is None:
                validation = await asyncio.to_thread(self._validate_token_sync)
                self.validated_once = True
                if validation is None:
                    logger.warning("Token Twitch invalido. Tentando renovar automaticamente...")
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
                raise TwitchAuthError("TWITCH_USER_TOKEN invalido e refresh automatico nao configurado.")
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
        channel_login: str,
        user_token: str = "",
        token_manager: TwitchTokenManager | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.bot_login = bot_login.lower()
        self.channel_login = channel_login.lower()
        self.token_manager = token_manager or TwitchTokenManager(access_token=user_token)
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def send_reply(self, text: str) -> None:
        safe_text = flatten_chat_text(format_chat_reply(text))
        if not safe_text:
            return
        await self._send_raw(f"PRIVMSG #{self.channel_login} :{safe_text}")

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
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port, ssl=ssl_context)
        await self._send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands")
        await self._send_raw(f"PASS oauth:{access_token}")
        await self._send_raw(f"NICK {self.bot_login}")
        await self._send_raw(f"JOIN #{self.channel_login}")
        await self._await_login_confirmation()
        logger.info("%s conectado via IRC em #%s", BOT_BRAND, self.channel_login)

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
        if channel != self.channel_login:
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
            context.remember_user_message(author.name, text)

        updates = await auto_update_scene_from_message(message)
        if updates:
            labels = ", ".join(OBSERVABILITY_TYPES.get(content_type, content_type) for content_type in updates)
            logger.info("Observabilidade automatica atualizada: %s", labels)

        if byte_prompt is None:
            return
        await handle_byte_prompt_text(byte_prompt, author.name, self.send_reply)

    async def _recover_authentication(self, auth_error: Exception) -> bool:
        logger.warning("Falha de autenticacao IRC: %s", auth_error)
        try:
            await self.token_manager.force_refresh("falha de autenticacao IRC")
            logger.info("Reconectando com token renovado automaticamente.")
            return True
        except Exception as refresh_error:
            logger.error("Refresh automatico falhou: %s", refresh_error)
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
                reconnect_delay_seconds = 5
            finally:
                await self._close()
            await asyncio.sleep(reconnect_delay_seconds)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AGENT_ONLINE")

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


def resolve_client_secret_for_irc_refresh() -> str:
    if TWITCH_CLIENT_SECRET_INLINE:
        return TWITCH_CLIENT_SECRET_INLINE
    if not PROJECT_ID:
        return ""
    secret_name = TWITCH_CLIENT_SECRET_NAME or "twitch-client-secret"
    try:
        return get_secret(secret_name=secret_name)
    except Exception as error:
        logger.warning("Nao foi possivel ler segredo '%s' para refresh automatico: %s", secret_name, error)
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
    bot = IrcByteBot(
        host=TWITCH_IRC_HOST,
        port=TWITCH_IRC_PORT,
        use_tls=TWITCH_IRC_TLS,
        bot_login=TWITCH_BOT_LOGIN or require_env("TWITCH_BOT_LOGIN"),
        channel_login=TWITCH_CHANNEL_LOGIN or require_env("TWITCH_CHANNEL_LOGIN"),
        token_manager=token_manager,
    )
    asyncio.run(bot.run_forever())


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
