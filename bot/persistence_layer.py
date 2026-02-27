import asyncio
import logging
import os
import time
from typing import Any, Optional

from supabase import Client, create_client

logger = logging.getLogger("byte.persistence")


def _normalize_channel_id(channel_id: str) -> str:
    return str(channel_id or "").strip().lower()


def _utc_iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _normalize_optional_float(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    field_name: str,
) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} invalido.") from error
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} fora do intervalo permitido.")
    return round(parsed, 4)


def _normalize_optional_text(
    value: Any,
    *,
    field_name: str,
    max_length: int,
) -> str:
    if value in (None, ""):
        return ""
    normalized = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    trimmed_lines = [line.rstrip() for line in normalized.split("\n")]
    cleaned = "\n".join(trimmed_lines).strip()
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} excede o tamanho permitido.")
    return cleaned


def _normalize_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in (0, 0.0):
            return False
        if value in (1, 1.0):
            return True
    if value in (None, ""):
        return False
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"{field_name} invalido.")


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

    def _default_channel_config(self, channel_id: str) -> dict[str, Any]:
        normalized = _normalize_channel_id(channel_id) or "default"
        cached = self._channel_config_cache.get(normalized, {})
        temperature = cached.get("temperature")
        top_p = cached.get("top_p")
        agent_paused = bool(cached.get("agent_paused", False))
        return {
            "channel_id": normalized,
            "temperature": temperature,
            "top_p": top_p,
            "agent_paused": agent_paused,
            "has_override": temperature is not None or top_p is not None or agent_paused,
            "updated_at": cached.get("updated_at", ""),
            "source": cached.get("source", "memory"),
        }

    def _default_agent_notes(self, channel_id: str) -> dict[str, Any]:
        normalized = _normalize_channel_id(channel_id) or "default"
        cached = self._agent_notes_cache.get(normalized, {})
        notes = str(cached.get("notes", "") or "")
        return {
            "channel_id": normalized,
            "notes": notes,
            "has_notes": bool(notes.strip()),
            "updated_at": cached.get("updated_at", ""),
            "source": cached.get("source", "memory"),
        }

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
        normalized = _normalize_channel_id(channel_id) or "default"
        if not self._enabled or not self._client:
            return self._default_channel_config(normalized)

        try:
            result = (
                self._client.table("channels_config")
                .select("channel_id, temperature, top_p, agent_paused, updated_at")
                .eq("channel_id", normalized)
                .maybe_single()
                .execute()
            )
            row = result.data or {}
            safe_agent_paused = bool(row.get("agent_paused", False))
            payload = {
                "channel_id": normalized,
                "temperature": row.get("temperature"),
                "top_p": row.get("top_p"),
                "agent_paused": safe_agent_paused,
                "has_override": (
                    row.get("temperature") is not None
                    or row.get("top_p") is not None
                    or safe_agent_paused
                ),
                "updated_at": str(row.get("updated_at") or ""),
                "source": "supabase",
            }
            self._channel_config_cache[normalized] = payload
            return payload
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao carregar config de %s: %s", normalized, e)
            return self._default_channel_config(normalized)

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
        normalized = _normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        safe_temperature = _normalize_optional_float(
            temperature,
            minimum=0.0,
            maximum=2.0,
            field_name="temperature",
        )
        safe_top_p = _normalize_optional_float(
            top_p,
            minimum=0.0,
            maximum=1.0,
            field_name="top_p",
        )
        safe_agent_paused = _normalize_bool(agent_paused, field_name="agent_paused")

        payload = {
            "channel_id": normalized,
            "temperature": safe_temperature,
            "top_p": safe_top_p,
            "agent_paused": safe_agent_paused,
            "has_override": safe_temperature is not None
            or safe_top_p is not None
            or safe_agent_paused,
            "updated_at": _utc_iso_now(),
            "source": "memory",
        }
        self._channel_config_cache[normalized] = payload

        if not self._enabled or not self._client:
            return payload

        try:
            self._client.table("channels_config").upsert(
                {
                    "channel_id": normalized,
                    "temperature": safe_temperature,
                    "top_p": safe_top_p,
                    "agent_paused": safe_agent_paused,
                    "updated_at": "now()",
                }
            ).execute()
            persisted = self.load_channel_config_sync(normalized)
            persisted["source"] = "supabase"
            self._channel_config_cache[normalized] = persisted
            return persisted
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao salvar config de %s: %s", normalized, e)
            return payload

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
        normalized = _normalize_channel_id(channel_id) or "default"
        if not self._enabled or not self._client:
            return self._default_agent_notes(normalized)

        try:
            result = (
                self._client.table("agent_notes")
                .select("channel_id, notes, updated_at")
                .eq("channel_id", normalized)
                .maybe_single()
                .execute()
            )
            row = result.data or {}
            notes = str(row.get("notes") or "")
            payload = {
                "channel_id": normalized,
                "notes": notes,
                "has_notes": bool(notes.strip()),
                "updated_at": str(row.get("updated_at") or ""),
                "source": "supabase",
            }
            self._agent_notes_cache[normalized] = payload
            return payload
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao carregar agent_notes de %s: %s", normalized, e)
            return self._default_agent_notes(normalized)

    async def load_agent_notes(self, channel_id: str) -> dict[str, Any]:
        return self.load_agent_notes_sync(channel_id)

    def save_agent_notes_sync(self, channel_id: str, *, notes: Any = None) -> dict[str, Any]:
        normalized = _normalize_channel_id(channel_id)
        if not normalized:
            raise ValueError("channel_id obrigatorio.")

        safe_notes = _normalize_optional_text(
            notes,
            field_name="agent_notes",
            max_length=2000,
        )
        payload = {
            "channel_id": normalized,
            "notes": safe_notes,
            "has_notes": bool(safe_notes.strip()),
            "updated_at": _utc_iso_now(),
            "source": "memory",
        }
        self._agent_notes_cache[normalized] = payload

        if not self._enabled or not self._client:
            return payload

        try:
            self._client.table("agent_notes").upsert(
                {
                    "channel_id": normalized,
                    "notes": safe_notes,
                    "updated_at": "now()",
                }
            ).execute()
            persisted = self.load_agent_notes_sync(normalized)
            persisted["source"] = "supabase"
            self._agent_notes_cache[normalized] = persisted
            return persisted
        except Exception as e:
            logger.error("PersistenceLayer: Erro ao salvar agent_notes de %s: %s", normalized, e)
            return payload

    async def save_agent_notes(self, channel_id: str, *, notes: Any = None) -> dict[str, Any]:
        return self.save_agent_notes_sync(channel_id, notes=notes)

    # --- Persistência de Estado (Channel State) ---

    def load_channel_state_sync(self, channel_id: str) -> dict[str, Any] | None:
        """Busca o snapshot do StreamContext do Supabase."""
        if not self._enabled or not self._client:
            return None
        normalized = _normalize_channel_id(channel_id) or channel_id
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
        normalized = _normalize_channel_id(channel_id) or channel_id
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
            "updated_at": _utc_iso_now(),
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
