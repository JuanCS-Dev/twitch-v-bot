import asyncio
import threading
import time
from datetime import UTC, datetime
from typing import Any, Optional

from bot.logic_constants import (
    BOT_BRAND,
    DEFAULT_STYLE_PROFILE,
    MAX_RECENT_CHAT_ENTRIES,
    MAX_RECENT_CHAT_PREVIEW_CHARS,
    MAX_RECENT_CHAT_PROMPT_ENTRIES,
    MAX_REPLY_LENGTH,
    MAX_REPLY_LINES,
    OBSERVABILITY_TYPES,
    SYSTEM_INSTRUCTION_TEMPLATE,
)


def normalize_memory_excerpt(text: str, max_length: int = MAX_RECENT_CHAT_PREVIEW_CHARS) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    if len(compact) <= max_length:
        return compact

    head = compact[: max_length - 3].rstrip()
    last_space = head.rfind(" ")
    if last_space >= int(max_length * 0.5):
        head = head[:last_space]
    return head.rstrip(" ,;:") + "..."


class StreamContext:
    def __init__(self):
        self.channel_id = "default"
        self.current_game = "N/A"
        self.stream_vibe = "Conversa"
        self.last_event = "Bot Online"
        self.style_profile = DEFAULT_STYLE_PROFILE
        self.inference_temperature: float | None = None
        self.inference_top_p: float | None = None
        self.channel_paused = False
        self.channel_config_loaded = False
        self.agent_notes = ""
        self.persona_name = ""
        self.persona_tone = ""
        self.persona_emote_vocab: list[str] = []
        self.persona_lore = ""
        self.live_observability: dict[str, str] = {
            "game": "",
            "movie": "",
            "series": "",
            "youtube": "",
            "x": "",
            "topic": "",
        }
        self.recent_chat_entries: list[str] = []
        self.last_byte_reply = ""
        self.start_time = time.time()
        self.last_activity = time.time()

    def get_uptime_minutes(self) -> int:
        return int((time.time() - self.start_time) / 60)

    def _touch(self) -> None:
        self.last_activity = time.time()
        from bot.logic_context import context_manager
        from bot.persistence_layer import persistence

        if not persistence.is_enabled:
            return

        state_snapshot = {
            "current_game": self.current_game,
            "stream_vibe": self.stream_vibe,
            "last_event": self.last_event,
            "style_profile": self.style_profile,
            "live_observability": self.live_observability.copy(),
            "last_byte_reply": self.last_byte_reply,
        }

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(persistence.save_channel_state(self.channel_id, state_snapshot))
        except RuntimeError:
            if context_manager._main_loop and context_manager._main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    persistence.save_channel_state(self.channel_id, state_snapshot),
                    context_manager._main_loop,
                )

    def update_content(self, content_type: str, description: str) -> bool:
        normalized_type = content_type.strip().lower()
        cleaned_description = description.strip()
        if normalized_type not in OBSERVABILITY_TYPES or not cleaned_description:
            return False

        self.live_observability[normalized_type] = cleaned_description
        if normalized_type == "game":
            self.current_game = cleaned_description
        self.last_event = f"Contexto atualizado: {OBSERVABILITY_TYPES[normalized_type]}"
        self._touch()
        return True

    def clear_content(self, content_type: str) -> bool:
        normalized_type = content_type.strip().lower()
        if normalized_type not in OBSERVABILITY_TYPES:
            return False

        self.live_observability[normalized_type] = ""
        if normalized_type == "game":
            self.current_game = "N/A"
        self.last_event = f"Contexto removido: {OBSERVABILITY_TYPES[normalized_type]}"
        self._touch()
        return True

    def list_supported_content_types(self) -> str:
        return ", ".join(OBSERVABILITY_TYPES.keys())

    def format_observability(self) -> str:
        entries = []
        for content_type, label in OBSERVABILITY_TYPES.items():
            value = self.live_observability.get(content_type, "").strip()
            if value:
                entries.append(f"{label}: {value}")
        return " | ".join(entries) if entries else "Sem conteudo registrado."

    def status_snapshot(self) -> str:
        active_count = sum(1 for value in self.live_observability.values() if value)
        return f"Vibe: {self.stream_vibe} | Contextos ativos: {active_count}"

    def remember_user_message(self, author_name: str, message_text: str) -> None:
        safe_author = normalize_memory_excerpt(author_name or "viewer", max_length=32)
        safe_message = normalize_memory_excerpt(message_text)
        if not safe_message:
            return
        self.recent_chat_entries.append(f"{safe_author}: {safe_message}")
        self.recent_chat_entries = self.recent_chat_entries[-MAX_RECENT_CHAT_ENTRIES:]
        self._touch()

    def remember_bot_reply(self, reply_text: str) -> None:
        safe_reply = normalize_memory_excerpt(reply_text, max_length=180)
        if not safe_reply:
            return
        self.last_byte_reply = safe_reply
        self.recent_chat_entries.append(f"{BOT_BRAND}: {safe_reply}")
        self.recent_chat_entries = self.recent_chat_entries[-MAX_RECENT_CHAT_ENTRIES:]
        self._touch()

    def format_recent_chat(self, limit: int = MAX_RECENT_CHAT_PROMPT_ENTRIES) -> str:
        if not self.recent_chat_entries:
            return "Sem historico recente."
        selected = self.recent_chat_entries[-max(1, limit) :]
        return " || ".join(selected)


class ContextManager:
    """Gerenciador de contextos isolados por canal com thread-safety e persistência."""

    def __init__(self) -> None:
        self._contexts: dict[str, StreamContext] = {}
        self._lock = threading.Lock()
        self._main_loop: asyncio.AbstractEventLoop | None = None

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Injeta o loop principal para suportar chamadas via Dashboard (síncrono)."""
        self._main_loop = loop

    def get(self, channel_id: str | None = None) -> StreamContext:
        """
        Recupera o contexto síncronamente.
        Se não existir na RAM, cria um novo e dispara carregamento do banco em background.
        """
        key = (channel_id or "default").strip().lower()

        with self._lock:
            if key in self._contexts:
                return self._contexts[key]

            ctx = StreamContext()
            ctx.channel_id = key
            self._contexts[key] = ctx

            # Dispara carregamento assíncrono do Supabase (Lazy Load)
            self._trigger_lazy_load(key, ctx)

            return ctx

    def _trigger_lazy_load(self, channel_id: str, ctx: StreamContext) -> None:
        """Inicia a restauração do banco sem bloquear a thread principal."""
        from bot.persistence_layer import persistence

        if not persistence.is_enabled:
            return

        async def _load_task():
            state = await persistence.load_channel_state(channel_id)
            if state:
                ctx.current_game = state.get("current_game", ctx.current_game)
                ctx.stream_vibe = state.get("stream_vibe", ctx.stream_vibe)
                ctx.style_profile = state.get("style_profile", ctx.style_profile)
                ctx.live_observability = state.get("observability", ctx.live_observability)
                ctx.last_byte_reply = state.get("last_reply", ctx.last_byte_reply)

            history = await persistence.load_recent_history(channel_id)
            if history:
                ctx.recent_chat_entries = history

            channel_config = await persistence.load_channel_config(channel_id)
            ctx.inference_temperature = channel_config.get("temperature")
            ctx.inference_top_p = channel_config.get("top_p")
            ctx.channel_paused = bool(channel_config.get("agent_paused", False))

            agent_notes = await persistence.load_agent_notes(channel_id)
            ctx.agent_notes = str(agent_notes.get("notes") or "")

            channel_identity = await persistence.load_channel_identity(channel_id)
            ctx.persona_name = str(channel_identity.get("persona_name") or "")
            ctx.persona_tone = str(channel_identity.get("tone") or "")
            ctx.persona_emote_vocab = list(channel_identity.get("emote_vocab") or [])
            ctx.persona_lore = str(channel_identity.get("lore") or "")
            ctx.channel_config_loaded = True

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_load_task())
        except RuntimeError:
            if self._main_loop and self._main_loop.is_running():
                asyncio.run_coroutine_threadsafe(_load_task(), self._main_loop)

    def get_sync(self, channel_id: str | None = None) -> StreamContext:
        """Alias para get() - mantém compatibilidade."""
        return self.get(channel_id)

    def apply_channel_config(
        self,
        channel_id: str,
        *,
        temperature: float | None,
        top_p: float | None,
        agent_paused: bool = False,
    ) -> None:
        key = (channel_id or "default").strip().lower()
        with self._lock:
            ctx = self._contexts.get(key)
        if ctx is None:
            return
        ctx.inference_temperature = temperature
        ctx.inference_top_p = top_p
        ctx.channel_paused = bool(agent_paused)
        ctx.channel_config_loaded = True

    def ensure_channel_config_loaded(self, channel_id: str | None = None) -> StreamContext:
        key = (channel_id or "default").strip().lower() or "default"
        ctx = self.get(key)
        if bool(getattr(ctx, "channel_config_loaded", False)):
            return ctx

        from bot.persistence_layer import persistence

        if not persistence.is_enabled:
            ctx.channel_config_loaded = True
            return ctx

        channel_config = persistence.load_channel_config_sync(key)
        self.apply_channel_config(
            key,
            temperature=channel_config.get("temperature"),
            top_p=channel_config.get("top_p"),
            agent_paused=bool(channel_config.get("agent_paused", False)),
        )
        channel_identity = persistence.load_channel_identity_sync(key)
        self.apply_channel_identity(
            key,
            persona_name=str(channel_identity.get("persona_name") or ""),
            tone=str(channel_identity.get("tone") or ""),
            emote_vocab=list(channel_identity.get("emote_vocab") or []),
            lore=str(channel_identity.get("lore") or ""),
        )
        return ctx

    def apply_agent_notes(self, channel_id: str, *, notes: str) -> None:
        key = (channel_id or "default").strip().lower()
        with self._lock:
            ctx = self._contexts.get(key)
        if ctx is None:
            return
        ctx.agent_notes = str(notes or "")

    def apply_channel_identity(
        self,
        channel_id: str,
        *,
        persona_name: str,
        tone: str,
        emote_vocab: list[str] | tuple[str, ...],
        lore: str,
    ) -> None:
        key = (channel_id or "default").strip().lower()
        with self._lock:
            ctx = self._contexts.get(key)
        if ctx is None:
            return
        ctx.persona_name = str(persona_name or "")
        ctx.persona_tone = str(tone or "")
        ctx.persona_emote_vocab = [
            str(item).strip() for item in list(emote_vocab or []) if str(item).strip()
        ]
        ctx.persona_lore = str(lore or "")

    async def cleanup(self, channel_id: str) -> None:
        """Remove contexto da RAM (Async para manter assinatura onde esperado)."""
        key = channel_id.strip().lower()
        with self._lock:
            self._contexts.pop(key, None)

    async def purge_expired(self, max_age_seconds: float = 7200) -> int:
        """Remove contextos da RAM que não tiveram atividade recente."""
        now = time.time()
        with self._lock:
            expired_keys = [
                key
                for key, ctx in self._contexts.items()
                if key != "default" and (now - ctx.last_activity) > max_age_seconds
            ]
            for key in expired_keys:
                self._contexts.pop(key, None)
            return len(expired_keys)

    async def start_cleanup_loop(self, interval_seconds: int = 1800) -> None:
        """Loop de background para limpeza periódica de memória."""
        from bot.sentiment_engine import sentiment_engine

        while True:
            try:
                await asyncio.sleep(interval_seconds)
                purged_ctx = await self.purge_expired()
                purged_sent = sentiment_engine.cleanup_inactive()
                if purged_ctx > 0 or purged_sent > 0:
                    from bot.runtime_config import logger

                    logger.info("Cleanup: %d ctx, %d sent", purged_ctx, purged_sent)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def list_active_channels(self) -> list[str]:
        with self._lock:
            return list(self._contexts.keys())


context_manager = ContextManager()


def build_system_instruction(ctx: StreamContext) -> str:
    return f"{SYSTEM_INSTRUCTION_TEMPLATE} Estilo ativo: {ctx.style_profile}"


def enforce_reply_limits(
    text: str, max_lines: int = MAX_REPLY_LINES, max_length: int = MAX_REPLY_LENGTH
) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    limited_lines = lines[:max_lines]
    joined = " ".join(limited_lines)
    if len(joined) <= max_length:
        return joined
    return joined[: max_length - 3].rstrip() + "..."


def get_server_clock_snapshot() -> tuple[str, int]:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ"), int(now.timestamp())


def build_dynamic_prompt(
    user_request: str, author_name: str, ctx: StreamContext | None = None, **kwargs: Any
) -> str:
    """CRÍTICO: Restaura labels que a suite de testes espera."""
    if ctx is None:
        ctx = context_manager.get("default")

    ts, epoch = get_server_clock_snapshot()
    context_line = (
        f"Contexto Atual da Live: [Vibe: {ctx.stream_vibe} | "
        f"Uptime: {ctx.get_uptime_minutes()}min | "
        f"Observabilidade: {ctx.format_observability()} | "
        f"Ultimo evento: {ctx.last_event} | "
        f"Relogio servidor UTC: {ts} | Epoch: {epoch}]"
    )
    history_line = f"Historico recente: {ctx.format_recent_chat()}"
    last_reply_line = f"Ultima resposta do Byte: {ctx.last_byte_reply or 'N/A'}"

    return (
        f"{context_line}\n"
        "Use o relogio do servidor como referencia para termos temporais (hoje/agora/nesta semana).\n"
        f"{history_line}\n"
        f"{last_reply_line}\n"
        f"Usuario {author_name}: {user_request}"
    )
