import asyncio
import logging
import os
import time
from typing import Any, Optional

from supabase import Client, create_client

logger = logging.getLogger("byte.persistence")


class PersistenceLayer:
    """
    Camada unificada de persistência para o Byte Bot.
    Gerencia estado, histórico e configurações via Supabase com mecanismos de fallback.
    """

    def __init__(self) -> None:
        self._url = (os.environ.get("SUPABASE_URL") or "").strip()
        self._key = (os.environ.get("SUPABASE_KEY") or "").strip()
        self._client: Client | None = None
        self._enabled = False

        if self._url and self._key:
            try:
                self._client = create_client(self._url, self._key)
                self._enabled = True
                logger.info("PersistenceLayer: Supabase conectado com sucesso.")
            except Exception as e:
                logger.warning("PersistenceLayer: Falha na inicialização do Supabase: %s", e)
        else:
            logger.info("PersistenceLayer: Supabase não configurado. Operando em modo volátil.")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    # --- Lógica de Boot e Canais ---

    async def get_active_channels(self) -> list[str]:
        """
        Tenta carregar a lista de canais do banco.
        Se falhar ou estiver desabilitado, retorna lista vazia para gatilhar o fallback de ENV.
        """
        if not self._enabled or not self._client:
            return []

        try:
            # Timeout implícito via tempo de execução da query
            result = (
                self._client.table("channels_config")
                .select("channel_id")
                .eq("is_active", True)
                .execute()
            )
            channels = [row["channel_id"] for row in (result.data or [])]
            if channels:
                logger.info("PersistenceLayer: Carregados %d canais do Supabase.", len(channels))
            return channels
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao carregar channels_config: %s", e)
            return []

    # --- Persistência de Estado (Channel State) ---

    async def load_channel_state(self, channel_id: str) -> dict[str, Any] | None:
        """Busca o snapshot do StreamContext do Supabase."""
        if not self._enabled or not self._client:
            return None
        try:
            result = (
                self._client.table("channel_state")
                .select("*")
                .eq("channel_id", channel_id)
                .maybe_single()
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error("PersistenceLayer: Falha ao carregar estado de %s: %s", channel_id, e)
            return None

    async def save_channel_state(self, channel_id: str, state: dict[str, Any]) -> bool:
        """Upsert do snapshot do canal."""
        if not self._enabled or not self._client:
            return False
        try:
            payload = {
                "channel_id": channel_id,
                "current_game": state.get("current_game", "N/A"),
                "stream_vibe": state.get("stream_vibe", "Chill"),
                "last_event": state.get("last_event"),
                "style_profile": state.get("style_profile"),
                "observability": state.get("live_observability", {}),
                "last_reply": state.get("last_byte_reply"),
                "updated_at": "now()",
                "last_activity": "now()",
            }
            self._client.table("channel_state").upsert(payload).execute()
            return True
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao salvar estado de %s: %s", channel_id, e)
            return False

    # --- Persistência de Histórico (Channel History) ---

    async def append_history(self, channel_id: str, author: str, message: str) -> None:
        """Adiciona mensagem ao histórico persistente."""
        if not self._enabled or not self._client:
            return
        try:
            self._client.table("channel_history").insert(
                {"channel_id": channel_id, "author": author, "message": message[:2000]}
            ).execute()
        except Exception as e:
            logger.debug("PersistenceLayer: Falha ao persistir histórico: %s", e)

    async def load_recent_history(self, channel_id: str, limit: int = 12) -> list[str]:
        """Recupera histórico para reconstruir o StreamContext."""
        if not self._enabled or not self._client:
            return []
        try:
            result = (
                self._client.table("channel_history")
                .select("author, message")
                .eq("channel_id", channel_id)
                .order("ts", desc=True)
                .limit(limit)
                .execute()
            )
            data = result.data or []
            return [f"{row['author']}: {row['message']}" for row in reversed(data)]
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao carregar histórico de %s: %s", channel_id, e)
            return []

    # --- Telemetria (Absorvendo supabase_client.py) ---

    def log_message_sync(
        self, author_name: str, message: str, channel: str = "", source: str = "irc"
    ) -> None:
        if not self._enabled or not self._client:
            return
        try:
            self._client.table("chat_messages").insert(
                {
                    "author_name": author_name,
                    "message": message[:2000],
                    "channel": channel,
                    "source": source,
                }
            ).execute()
        except Exception:
            pass

    def log_reply_sync(
        self,
        prompt: str,
        reply: str,
        author_name: str,
        model: str = "",
        grounded: bool = False,
        latency_ms: int = 0,
    ) -> None:
        if not self._enabled or not self._client:
            return
        try:
            self._client.table("bot_replies").insert(
                {
                    "prompt": prompt[:2000],
                    "reply": reply[:2000],
                    "author_name": author_name,
                    "model": model,
                    "grounded": grounded,
                    "latency_ms": latency_ms,
                }
            ).execute()
        except Exception:
            pass


persistence = PersistenceLayer()
