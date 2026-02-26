import asyncio
import threading
import time
from datetime import UTC, datetime

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
        self.current_game = "N/A"
        self.stream_vibe = "Conversa"
        self.last_event = "Bot Online"
        self.style_profile = DEFAULT_STYLE_PROFILE
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

    def update_content(self, content_type: str, description: str) -> bool:
        self._touch()
        normalized_type = content_type.strip().lower()
        cleaned_description = description.strip()
        if normalized_type not in OBSERVABILITY_TYPES or not cleaned_description:
            return False

        self.live_observability[normalized_type] = cleaned_description
        if normalized_type == "game":
            self.current_game = cleaned_description
        self.last_event = f"Contexto atualizado: {OBSERVABILITY_TYPES[normalized_type]}"
        return True

    def clear_content(self, content_type: str) -> bool:
        self._touch()
        normalized_type = content_type.strip().lower()
        if normalized_type not in OBSERVABILITY_TYPES:
            return False

        self.live_observability[normalized_type] = ""
        if normalized_type == "game":
            self.current_game = "N/A"
        self.last_event = f"Contexto removido: {OBSERVABILITY_TYPES[normalized_type]}"
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
        self._touch()
        safe_author = normalize_memory_excerpt(author_name or "viewer", max_length=32)
        safe_message = normalize_memory_excerpt(message_text)
        if not safe_message:
            return
        self.recent_chat_entries.append(f"{safe_author}: {safe_message}")
        self.recent_chat_entries = self.recent_chat_entries[-MAX_RECENT_CHAT_ENTRIES:]

    def remember_bot_reply(self, reply_text: str) -> None:
        self._touch()
        safe_reply = normalize_memory_excerpt(reply_text, max_length=180)
        if not safe_reply:
            return
        self.last_byte_reply = safe_reply
        self.recent_chat_entries.append(f"{BOT_BRAND}: {safe_reply}")
        self.recent_chat_entries = self.recent_chat_entries[-MAX_RECENT_CHAT_ENTRIES:]

    def format_recent_chat(self, limit: int = MAX_RECENT_CHAT_PROMPT_ENTRIES) -> str:
        if not self.recent_chat_entries:
            return "Sem historico recente."
        selected = self.recent_chat_entries[-max(1, limit) :]
        return " || ".join(selected)


class ContextManager:
    """Gerenciador de contextos isolados por canal com thread-safety e expiração."""

    def __init__(self) -> None:
        self._contexts: dict[str, StreamContext] = {}
        self._lock = threading.Lock()

    def get(self, channel_id: str | None = None) -> StreamContext:
        """Recupera ou cria um contexto para o canal especificado."""
        key = (channel_id or "default").strip().lower()
        with self._lock:
            if key not in self._contexts:
                self._contexts[key] = StreamContext()
            return self._contexts[key]

    def cleanup(self, channel_id: str) -> None:
        """Remove explicitamente um contexto."""
        key = channel_id.strip().lower()
        with self._lock:
            self._contexts.pop(key, None)

    def purge_expired(self, max_age_seconds: float = 7200) -> int:
        """Remove contextos que não tiveram atividade recente."""
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
                purged_ctx = self.purge_expired()
                purged_sent = sentiment_engine.cleanup_inactive()
                if purged_ctx > 0 or purged_sent > 0:
                    from bot.runtime_config import logger

                    logger.info(
                        "Cleanup: Removidos %d contextos e %d motores de sentimento inativos.",
                        purged_ctx,
                        purged_sent,
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                from bot.runtime_config import logger

                logger.error("Falha no loop de cleanup de memoria: %s", e)

    def list_active_channels(self) -> list[str]:
        """Retorna lista de canais com contextos ativos."""
        with self._lock:
            return list(self._contexts.keys())


context_manager = ContextManager()


def build_system_instruction(ctx: StreamContext) -> str:
    return f"{SYSTEM_INSTRUCTION_TEMPLATE} Estilo ativo: {ctx.style_profile}"


def get_server_clock_snapshot() -> tuple[str, int]:
    now_utc = datetime.now(UTC)
    now_utc_iso = now_utc.isoformat(timespec="seconds").replace("+00:00", "Z")
    return now_utc_iso, int(now_utc.timestamp())


def build_dynamic_prompt(
    user_msg: str,
    author_name: str,
    ctx: StreamContext,
    *,
    include_live_context: bool = True,
) -> str:
    server_utc_iso, server_epoch = get_server_clock_snapshot()
    if not include_live_context:
        return (
            "Modo contexto estatico ativo. Ignore historico da live e responda somente ao pedido atual.\n"
            f"Relogio servidor UTC: {server_utc_iso} | Epoch: {server_epoch}\n"
            f"Usuario {author_name}: {user_msg}"
        )

    uptime = ctx.get_uptime_minutes()
    observability = ctx.format_observability()
    recent_chat = ctx.format_recent_chat()
    last_reply = ctx.last_byte_reply or "N/A"
    return (
        "Contexto Atual da Live: "
        f"[Vibe: {ctx.stream_vibe} | Uptime: {uptime}min | "
        f"Observabilidade: {observability} | Ultimo evento: {ctx.last_event} | "
        f"Relogio servidor UTC: {server_utc_iso} | Epoch: {server_epoch}]\n"
        "Use o relogio do servidor como referencia para termos temporais (hoje/agora/nesta semana).\n"
        f"Historico recente: {recent_chat}\n"
        f"Ultima resposta do {BOT_BRAND}: {last_reply}\n"
        f"Usuario {author_name}: {user_msg}"
    )


def enforce_reply_limits(
    text: str, max_lines: int = MAX_REPLY_LINES, max_length: int = MAX_REPLY_LENGTH
) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return ""

    normalized_lines = []
    for raw_line in cleaned.split("\n"):
        line = " ".join(raw_line.split())
        if line:
            normalized_lines.append(line)

    if not normalized_lines:
        normalized_lines = [" ".join(cleaned.split())]

    limited_lines = normalized_lines[:max_lines]
    result = "\n".join(limited_lines).strip()
    if len(result) <= max_length:
        return result

    def close_sentence(fragment: str) -> str:
        cleaned_fragment = fragment.strip().rstrip(" ,;:")
        if not cleaned_fragment:
            return ""
        if cleaned_fragment[-1] in ".!?":
            return cleaned_fragment
        if len(cleaned_fragment) >= max_length:
            cleaned_fragment = cleaned_fragment[: max_length - 1].rstrip(" ,;:")
        if not cleaned_fragment:
            return ""
        return cleaned_fragment + "."

    head = result[:max_length].rstrip()
    punctuation_positions = [head.rfind(symbol) for symbol in (".", "!", "?")]
    best_punctuation = max(punctuation_positions)
    if best_punctuation >= int(max_length * 0.35):
        return head[: best_punctuation + 1].strip()

    last_space = head.rfind(" ")
    if last_space >= int(max_length * 0.55):
        return close_sentence(head[:last_space])
    return close_sentence(head)
