import logging
import os
from typing import Any

from supabase import Client, create_client

from bot.persistence_agent_notes_repository import AgentNotesRepository
from bot.persistence_channel_config_repository import ChannelConfigRepository
from bot.persistence_observability_history_repository import ObservabilityHistoryRepository
from bot.persistence_post_stream_report_repository import PostStreamReportRepository
from bot.persistence_utils import normalize_channel_id, utc_iso_now

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
        self._channel_config_cache: dict[str, dict[str, Any]] = {}
        self._agent_notes_cache: dict[str, dict[str, Any]] = {}
        self._observability_rollup_cache: dict[str, Any] | None = None
        self._observability_channel_history_cache: dict[str, list[dict[str, Any]]] = {}
        self._post_stream_report_cache: dict[str, dict[str, Any]] = {}

        if self._url and self._key:
            try:
                self._client = create_client(self._url, self._key)
                self._enabled = True
                logger.info("PersistenceLayer: Supabase conectado com sucesso.")
            except Exception as e:
                logger.warning("PersistenceLayer: Falha na inicialização do Supabase: %s", e)
        else:
            logger.info("PersistenceLayer: Supabase não configurado. Operando em modo volátil.")

        self._channel_config_repo = ChannelConfigRepository(
            enabled=self._enabled,
            client=self._client,
            cache=self._channel_config_cache,
        )
        self._agent_notes_repo = AgentNotesRepository(
            enabled=self._enabled,
            client=self._client,
            cache=self._agent_notes_cache,
        )
        self._observability_history_repo = ObservabilityHistoryRepository(
            enabled=self._enabled,
            client=self._client,
            cache=self._observability_channel_history_cache,
        )
        self._post_stream_report_repo = PostStreamReportRepository(
            enabled=self._enabled,
            client=self._client,
            cache=self._post_stream_report_cache,
        )

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

    def load_channel_config_sync(self, channel_id: str) -> dict[str, Any]:
        return self._channel_config_repo.load_sync(channel_id)

    async def load_channel_config(self, channel_id: str) -> dict[str, Any]:
        return self.load_channel_config_sync(channel_id)

    def save_channel_config_sync(
        self,
        channel_id: str,
        *,
        temperature: Any = None,
        top_p: Any = None,
        agent_paused: Any = False,
    ) -> dict[str, Any]:
        return self._channel_config_repo.save_sync(
            channel_id,
            temperature=temperature,
            top_p=top_p,
            agent_paused=agent_paused,
        )

    async def save_channel_config(
        self,
        channel_id: str,
        *,
        temperature: Any = None,
        top_p: Any = None,
        agent_paused: Any = False,
    ) -> dict[str, Any]:
        return self.save_channel_config_sync(
            channel_id,
            temperature=temperature,
            top_p=top_p,
            agent_paused=agent_paused,
        )

    def load_agent_notes_sync(self, channel_id: str) -> dict[str, Any]:
        return self._agent_notes_repo.load_sync(channel_id)

    async def load_agent_notes(self, channel_id: str) -> dict[str, Any]:
        return self.load_agent_notes_sync(channel_id)

    def save_agent_notes_sync(self, channel_id: str, *, notes: Any = None) -> dict[str, Any]:
        return self._agent_notes_repo.save_sync(channel_id, notes=notes)

    async def save_agent_notes(self, channel_id: str, *, notes: Any = None) -> dict[str, Any]:
        return self.save_agent_notes_sync(channel_id, notes=notes)

    # --- Persistência de Estado (Channel State) ---

    def load_channel_state_sync(self, channel_id: str) -> dict[str, Any] | None:
        """Busca o snapshot do StreamContext do Supabase."""
        if not self._enabled or not self._client:
            return None
        normalized = normalize_channel_id(channel_id) or channel_id
        try:
            result = (
                self._client.table("channel_state")
                .select("*")
                .eq("channel_id", normalized)
                .maybe_single()
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error("PersistenceLayer: Falha ao carregar estado de %s: %s", normalized, e)
            return None

    async def load_channel_state(self, channel_id: str) -> dict[str, Any] | None:
        return self.load_channel_state_sync(channel_id)

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

    def load_recent_history_sync(self, channel_id: str, limit: int = 12) -> list[str]:
        """Recupera histórico para reconstruir o StreamContext."""
        if not self._enabled or not self._client:
            return []
        normalized = normalize_channel_id(channel_id) or channel_id
        try:
            result = (
                self._client.table("channel_history")
                .select("author, message")
                .eq("channel_id", normalized)
                .order("ts", desc=True)
                .limit(limit)
                .execute()
            )
            data = result.data or []
            return [f"{row['author']}: {row['message']}" for row in reversed(data)]
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao carregar histórico de %s: %s", normalized, e)
            return []

    async def load_recent_history(self, channel_id: str, limit: int = 12) -> list[str]:
        return self.load_recent_history_sync(channel_id, limit=limit)

    # --- Telemetria (Absorvendo supabase_client.py) ---

    def save_observability_channel_history_sync(
        self,
        channel_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self._observability_history_repo.save_channel_history_sync(channel_id, payload)

    async def save_observability_channel_history(
        self,
        channel_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.save_observability_channel_history_sync(channel_id, payload)

    def load_observability_channel_history_sync(
        self,
        channel_id: str,
        *,
        limit: int = 24,
    ) -> list[dict[str, Any]]:
        return self._observability_history_repo.load_channel_history_sync(channel_id, limit=limit)

    async def load_observability_channel_history(
        self,
        channel_id: str,
        *,
        limit: int = 24,
    ) -> list[dict[str, Any]]:
        return self.load_observability_channel_history_sync(channel_id, limit=limit)

    def load_latest_observability_channel_snapshots_sync(
        self,
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        return self._observability_history_repo.load_latest_snapshots_sync(limit=limit)

    async def load_latest_observability_channel_snapshots(
        self,
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        return self.load_latest_observability_channel_snapshots_sync(limit=limit)

    def save_post_stream_report_sync(
        self,
        channel_id: str,
        report: dict[str, Any],
        *,
        trigger: str = "manual_dashboard",
    ) -> dict[str, Any]:
        return self._post_stream_report_repo.save_latest_report_sync(
            channel_id,
            report,
            trigger=trigger,
        )

    async def save_post_stream_report(
        self,
        channel_id: str,
        report: dict[str, Any],
        *,
        trigger: str = "manual_dashboard",
    ) -> dict[str, Any]:
        return self.save_post_stream_report_sync(
            channel_id,
            report,
            trigger=trigger,
        )

    def load_latest_post_stream_report_sync(
        self,
        channel_id: str,
    ) -> dict[str, Any] | None:
        return self._post_stream_report_repo.load_latest_report_sync(channel_id)

    async def load_latest_post_stream_report(
        self,
        channel_id: str,
    ) -> dict[str, Any] | None:
        return self.load_latest_post_stream_report_sync(channel_id)

    def load_observability_rollup_sync(self) -> dict[str, Any] | None:
        cached = self._observability_rollup_cache
        if not self._enabled or not self._client:
            return dict(cached) if cached else None
        try:
            result = (
                self._client.table("observability_rollups")
                .select("rollup_key, state, updated_at")
                .eq("rollup_key", "global")
                .maybe_single()
                .execute()
            )
            row = result.data or None
            if not row:
                return dict(cached) if cached else None
            payload = {
                "rollup_key": "global",
                "state": dict(row.get("state") or {}),
                "updated_at": str(row.get("updated_at") or ""),
                "source": "supabase",
            }
            self._observability_rollup_cache = payload
            return dict(payload)
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao carregar observability rollup: %s", e)
            return dict(cached) if cached else None

    def save_observability_rollup_sync(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "rollup_key": "global",
            "state": dict(state or {}),
            "updated_at": utc_iso_now(),
            "source": "memory",
        }
        self._observability_rollup_cache = payload
        if not self._enabled or not self._client:
            return dict(payload)
        try:
            self._client.table("observability_rollups").upsert(
                {
                    "rollup_key": "global",
                    "state": dict(state or {}),
                    "updated_at": "now()",
                }
            ).execute()
            payload["source"] = "supabase"
            self._observability_rollup_cache = payload
            return dict(payload)
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao salvar observability rollup: %s", e)
            return dict(payload)

    async def load_observability_rollup(self) -> dict[str, Any] | None:
        return self.load_observability_rollup_sync()

    async def save_observability_rollup(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.save_observability_rollup_sync(state)

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
