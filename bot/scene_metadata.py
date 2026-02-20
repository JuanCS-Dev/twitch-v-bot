import asyncio
import json
import re
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse, urlunparse
from urllib.request import Request, urlopen


class SceneMetadataService:
    def __init__(
        self,
        *,
        metadata_cache_ttl_seconds: int = 900,
        metadata_timeout_seconds: float = 3.0,
        blocked_domains: set[str] | None = None,
        youtube_hosts: set[str] | None = None,
        x_hosts: set[str] | None = None,
        unsafe_terms: set[str] | None = None,
    ) -> None:
        self.metadata_cache_ttl_seconds = metadata_cache_ttl_seconds
        self.metadata_timeout_seconds = metadata_timeout_seconds
        self.blocked_domains = blocked_domains or {
            "pornhub.com",
            "xvideos.com",
            "xnxx.com",
            "xhamster.com",
            "onlyfans.com",
            "redtube.com",
        }
        self.youtube_hosts = youtube_hosts or {"youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}
        self.x_hosts = x_hosts or {"x.com", "twitter.com", "mobile.twitter.com"}
        self.unsafe_terms = unsafe_terms or {
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
        self.url_regex = re.compile(r"https?://[^\s]+", re.IGNORECASE)
        self.unsafe_term_patterns = [
            re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")
            for term in self.unsafe_terms
        ]
        self.metadata_cache: dict[str, tuple[float, dict]] = {}

    @staticmethod
    def normalize_host(host: str) -> str:
        normalized = host.strip().lower()
        if normalized.startswith("www."):
            normalized = normalized[4:]
        if ":" in normalized:
            normalized = normalized.split(":", maxsplit=1)[0]
        return normalized

    def extract_urls(self, text: str) -> list[str]:
        urls = []
        for raw_url in self.url_regex.findall(text or ""):
            cleaned_url = raw_url.rstrip(".,!?)]}'\"")
            if cleaned_url:
                urls.append(cleaned_url)
        return urls

    def contains_unsafe_terms(self, text: str) -> bool:
        normalized_text = (text or "").lower()
        return any(pattern.search(normalized_text) for pattern in self.unsafe_term_patterns)

    def classify_supported_link(self, url: str) -> str | None:
        parsed = urlparse(url)
        host = self.normalize_host(parsed.netloc)
        if host in self.youtube_hosts:
            return "youtube"
        if host in self.x_hosts:
            return "x"
        return None

    def is_safe_scene_link(self, url: str, original_text: str) -> bool:
        parsed = urlparse(url)
        host = self.normalize_host(parsed.netloc)
        if not host:
            return False
        if host in self.blocked_domains:
            return False
        if self.contains_unsafe_terms(f"{original_text} {parsed.path} {parsed.query}"):
            return False
        return True

    @staticmethod
    def build_oembed_endpoint(url: str, content_type: str) -> str | None:
        encoded_url = quote_plus(url)
        if content_type == "youtube":
            return f"https://www.youtube.com/oembed?url={encoded_url}&format=json"
        if content_type == "x":
            return f"https://publish.twitter.com/oembed?url={encoded_url}&omit_script=true"
        return None

    def build_metadata_source_url(self, url: str, content_type: str) -> str:
        if content_type != "x":
            return url

        parsed = urlparse(url)
        host = self.normalize_host(parsed.netloc)
        if host == "x.com":
            return urlunparse(parsed._replace(netloc="twitter.com"))
        return url

    def fetch_oembed_metadata(self, url: str, content_type: str) -> dict | None:
        source_url = self.build_metadata_source_url(url, content_type)
        endpoint = self.build_oembed_endpoint(source_url, content_type)
        if not endpoint:
            return None

        request = Request(endpoint, headers={"User-Agent": "ByteBot/1.0"})
        try:
            with urlopen(request, timeout=self.metadata_timeout_seconds) as response:
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

    def get_cached_metadata(self, url: str) -> dict | None:
        now = time.monotonic()
        cached = self.metadata_cache.get(url)
        if not cached:
            return None

        expires_at, metadata = cached
        if now > expires_at:
            self.metadata_cache.pop(url, None)
            return None
        return metadata

    def set_cached_metadata(self, url: str, metadata: dict) -> None:
        expires_at = time.monotonic() + self.metadata_cache_ttl_seconds
        self.metadata_cache[url] = (expires_at, metadata)

    async def resolve_scene_metadata(self, url: str, content_type: str) -> dict | None:
        cached = self.get_cached_metadata(url)
        if cached:
            return cached

        metadata = await asyncio.to_thread(self.fetch_oembed_metadata, url, content_type)
        if metadata:
            self.set_cached_metadata(url, metadata)
        return metadata

    @staticmethod
    def metadata_to_safety_text(metadata: dict | None) -> str:
        if not metadata:
            return ""
        inspected_keys = ("title", "author_name", "provider_name", "description")
        values = [str(metadata.get(key, "")) for key in inspected_keys if metadata.get(key)]
        return " ".join(values)

    def is_safe_scene_metadata(
        self,
        metadata: dict | None,
        message_text: str,
        url: str,
        *,
        require_metadata: bool,
    ) -> bool:
        if metadata is None and require_metadata:
            return False

        inspection_text = f"{message_text} {url} {self.metadata_to_safety_text(metadata)}"
        return not self.contains_unsafe_terms(inspection_text)

    @staticmethod
    def build_sanitized_scene_description(
        content_type: str,
        author_name: str,
        metadata: dict | None,
        *,
        normalize_text_for_scene: Callable[..., str],
    ) -> str:
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
