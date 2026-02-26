"""Supabase client for persistent storage (chat logs, replies, events).

Falls back silently if SUPABASE_URL is not configured — the bot
continues to work without a database.
"""

import logging
import os
from typing import Any

logger = logging.getLogger("ByteBot")

_client: Any = None
_enabled: bool = False


def _get_client() -> Any:
    """Lazy-init Supabase client singleton."""
    global _client, _enabled
    if _client is not None:
        return _client

    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_KEY") or "").strip()

    if not url or not key:
        logger.info("Supabase not configured (SUPABASE_URL/SUPABASE_KEY missing). DB disabled.")
        _enabled = False
        _client = False  # sentinel: tried but unavailable
        return _client

    try:
        from supabase import create_client

        _client = create_client(url, key)
        _enabled = True
        logger.info("Supabase connected: %s", url.split("//")[-1].split(".")[0])
    except Exception as error:
        logger.warning("Supabase init failed: %s", error)
        _client = False
        _enabled = False

    return _client


from bot.persistence_layer import persistence


def is_enabled() -> bool:
    """Check if Supabase is configured and connected."""
    return persistence.is_enabled


def log_message(author_name: str, message: str, channel: str = "", source: str = "irc") -> None:
    """Log a chat message to Supabase (fire-and-forget)."""
    persistence.log_message_sync(author_name, message, channel, source)


def log_reply(
    prompt: str,
    reply: str,
    author_name: str,
    model: str = "",
    grounded: bool = False,
    latency_ms: int = 0,
) -> None:
    """Log a bot reply to Supabase (fire-and-forget)."""
    persistence.log_reply_sync(prompt, reply, author_name, model, grounded, latency_ms)


def log_event(category: str, details: str = "", metadata: dict[str, Any] | None = None) -> None:
    """Log an observability event to Supabase (fire-and-forget)."""
    # PersistenceLayer ainda não tem log_event_sync, vamos mapear para o client interno
    if not persistence.is_enabled or not persistence._client:
        return
    try:
        persistence._client.table("observability_events").insert(
            {
                "category": category,
                "details": details[:2000],
                "metadata": metadata or {},
            }
        ).execute()
    except Exception:
        pass
