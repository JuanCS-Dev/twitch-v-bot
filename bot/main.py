import os
import json
import asyncio
import time
import threading
import logging
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, quote_plus, urlunparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import twitchio
from twitchio.ext import commands
from google import genai
from google.cloud import secretmanager

from bot.logic import OBSERVABILITY_TYPES, agent_inference, context

# ── Setup ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InvisibleProducer")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
CLIENT_ID  = os.environ.get("TWITCH_CLIENT_ID")
BOT_ID     = os.environ.get("TWITCH_BOT_ID")
OWNER_ID   = os.environ.get("TWITCH_OWNER_ID")
CHANNEL_ID = os.environ.get("TWITCH_CHANNEL_ID")

client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

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


def is_authorized_user(author) -> bool:
    return is_owner(getattr(author, "id", "")) or bool(getattr(author, "is_subscriber", False))


def is_moderator(author) -> bool:
    return bool(getattr(author, "is_mod", False)) or bool(getattr(author, "is_moderator", False))


def is_trusted_curator(author) -> bool:
    return is_owner(getattr(author, "id", "")) or is_moderator(author)


def compact_message(text: str, max_len: int = 450) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


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


def normalize_text_for_scene(text: str, max_len: int = 120) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


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

    request = Request(endpoint, headers={"User-Agent": "InvisibleProducer/1.0"})
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


async def auto_update_scene_from_message(message: twitchio.ChatMessage) -> list[str]:
    if not is_trusted_curator(message.author):
        return []

    message_text = message.text or ""
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

        author_name = getattr(message.author, "name", "autor")
        description = compact_message(build_sanitized_scene_description(content_type, author_name, metadata), max_len=220)
        if context.update_content(content_type, description):
            updated_types.append(content_type)
            seen_types.add(content_type)
    return updated_types


# ── Twitch Agent Component ────────────────────────────────────
class AgentComponent(commands.Component):
    def __init__(self, bot: "ProducerBot") -> None:
        self.bot = bot

    async def component_check(self, ctx: commands.Context) -> bool:
        """Restringe o uso do bot apenas ao Dono do canal e Inscritos (Subs)."""
        if not is_authorized_user(ctx.author):
            # Opcional: Logar tentativa de acesso não autorizado
            return False
        return True

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!ask").strip()
        if not query: return
        ans = await agent_inference(query, ctx.message.author.name, client, context)
        await ctx.reply(ans)

    @commands.command(name="vibe")
    async def vibe(self, ctx: commands.Context) -> None:
        if is_owner(ctx.message.author.id):
            new_vibe = ctx.message.text.removeprefix("!vibe").strip()
            context.stream_vibe = new_vibe or "Conversa"
            context.last_event = "Vibe atualizada"
            await ctx.reply(f"Vibe atualizada para: {context.stream_vibe}")

    @commands.command(name="style")
    async def style(self, ctx: commands.Context) -> None:
        style_text = ctx.message.text.removeprefix("!style").strip()
        if not is_owner(ctx.message.author.id):
            await ctx.reply("Somente o dono do canal pode ajustar o estilo.")
            return
        if not style_text:
            await ctx.reply(compact_message(f"Estilo atual: {context.style_profile}"))
            return

        context.style_profile = style_text
        context.last_event = "Estilo de conversa atualizado"
        await ctx.reply("Estilo de conversa atualizado.")

    @commands.command(name="scene")
    async def scene(self, ctx: commands.Context) -> None:
        payload = ctx.message.text.removeprefix("!scene").strip()
        if not payload:
            observability = context.format_observability()
            await ctx.reply(compact_message(f"Observabilidade da live: {observability}"))
            return

        if not is_owner(ctx.message.author.id):
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
        await ctx.reply(compact_message(f"Contexto atualizado: {label} -> {description}"))

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        uptime = context.get_uptime_minutes()
        status_line = f"Invisible Producer v1.1 | Uptime: {uptime}min | {context.status_snapshot()}"
        await ctx.reply(compact_message(status_line))

class ProducerBot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        super().__init__(client_id=CLIENT_ID, client_secret=client_secret, bot_id=BOT_ID, owner_id=OWNER_ID, prefix="!")

    async def setup_hook(self) -> None:
        await self.add_component(AgentComponent(self))
        channel = await self.fetch_channel(int(CHANNEL_ID))
        await channel.subscribe_events(twitchio.EventChatMessage)

    async def event_ready(self) -> None:
        logger.info(f"Agent Ready: {self.bot_id}")

    async def event_message(self, message: twitchio.ChatMessage) -> None:
        if message.echo:
            return

        updates = await auto_update_scene_from_message(message)
        if updates:
            labels = ", ".join(OBSERVABILITY_TYPES.get(content_type, content_type) for content_type in updates)
            logger.info("Observabilidade automatica atualizada: %s", labels)

        # Inteligência proativa apenas para usuario autorizado.
        is_authorized = is_authorized_user(message.author)
        if is_authorized and "bom dia" in message.text.lower() and not message.text.startswith("!"):
            ans = await agent_inference(
                "Cumprimente o chat com um bom dia breve, acolhedor e natural.",
                message.author.name,
                client,
                context,
            )
            await message.reply(ans)
            return
        await self.handle_commands(message)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AGENT_ONLINE")
    def log_message(self, *_): pass

def run_server():
    port = int(os.environ.get("PORT", "8080"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

def get_secret():
    sm = secretmanager.SecretManagerServiceClient()
    path = f"projects/{PROJECT_ID}/secrets/twitch-client-secret/versions/latest"
    return sm.access_secret_version(name=path).payload.data.decode("UTF-8")

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    try:
        bot = ProducerBot(client_secret=get_secret())
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal Error: {e}")
