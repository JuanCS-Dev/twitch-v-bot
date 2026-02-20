import asyncio
import logging
import time
from typing import Dict

from google.genai import types

logger = logging.getLogger("ByteBot")

BOT_BRAND = "Byte"
MAX_REPLY_LINES = 8
MAX_REPLY_LENGTH = 460
MAX_RECENT_CHAT_ENTRIES = 12
MAX_RECENT_CHAT_PREVIEW_CHARS = 140
MAX_RECENT_CHAT_PROMPT_ENTRIES = 5

OBSERVABILITY_TYPES = {
    "game": "Jogo",
    "movie": "Filme",
    "series": "Serie",
    "youtube": "Video YouTube",
    "x": "Post X",
    "topic": "Tema",
}

DEFAULT_STYLE_PROFILE = (
    "Tom generalista, claro e natural em PT-BR, sem gíria gamer forçada."
)

SYSTEM_INSTRUCTION_TEMPLATE = (
    "Você é Byte, chatbot de uma live na Twitch. "
    "Responda de forma objetiva para os assuntos ativos da live, incluindo jogos, filmes, series, videos do YouTube, posts do X e temas gerais. "
    "Regras: 1) no maximo 8 linhas. 2) frases curtas e informativas. "
    "3) sem markdown. 4) nao use linguagem ofensiva nem invente fatos sem sinalizar incerteza. "
    "5) se faltar contexto essencial, faca uma pergunta curta. "
    "6) para assunto atual, priorize informacao recente e verificavel. "
    "7) responda primeiro a pergunta principal, sem rodeio."
)
MODEL_NAME = "gemini-3-flash-preview"
MODEL_MAX_OUTPUT_TOKENS = 320
MODEL_TEMPERATURE = 0.15
EMPTY_RESPONSE_FALLBACK = "Nao consegui consolidar a resposta agora. Tente reformular em uma frase."
UNSTABLE_CONNECTION_FALLBACK = "Conexao com o modelo instavel. Tente novamente em instantes."


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
        self.live_observability: Dict[str, str] = {
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

    def get_uptime_minutes(self) -> int:
        return int((time.time() - self.start_time) / 60)

    def update_content(self, content_type: str, description: str) -> bool:
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
        safe_author = normalize_memory_excerpt(author_name or "viewer", max_length=32)
        safe_message = normalize_memory_excerpt(message_text)
        if not safe_message:
            return
        self.recent_chat_entries.append(f"{safe_author}: {safe_message}")
        self.recent_chat_entries = self.recent_chat_entries[-MAX_RECENT_CHAT_ENTRIES:]

    def remember_bot_reply(self, reply_text: str) -> None:
        safe_reply = normalize_memory_excerpt(reply_text, max_length=180)
        if not safe_reply:
            return
        self.last_byte_reply = safe_reply
        self.recent_chat_entries.append(f"{BOT_BRAND}: {safe_reply}")
        self.recent_chat_entries = self.recent_chat_entries[-MAX_RECENT_CHAT_ENTRIES:]

    def format_recent_chat(self, limit: int = MAX_RECENT_CHAT_PROMPT_ENTRIES) -> str:
        if not self.recent_chat_entries:
            return "Sem historico recente."
        selected = self.recent_chat_entries[-max(1, limit):]
        return " || ".join(selected)


context = StreamContext()


def build_system_instruction(ctx: StreamContext) -> str:
    return f"{SYSTEM_INSTRUCTION_TEMPLATE} Estilo ativo: {ctx.style_profile}"


def build_dynamic_prompt(user_msg: str, author_name: str, ctx: StreamContext) -> str:
    uptime = ctx.get_uptime_minutes()
    observability = ctx.format_observability()
    recent_chat = ctx.format_recent_chat()
    last_reply = ctx.last_byte_reply or "N/A"
    return (
        "Contexto Atual da Live: "
        f"[Vibe: {ctx.stream_vibe} | Uptime: {uptime}min | "
        f"Observabilidade: {observability} | Ultimo evento: {ctx.last_event}]\n"
        f"Historico recente: {recent_chat}\n"
        f"Ultima resposta do {BOT_BRAND}: {last_reply}\n"
        f"Usuario {author_name}: {user_msg}"
    )


def enforce_reply_limits(text: str, max_lines: int = MAX_REPLY_LINES, max_length: int = MAX_REPLY_LENGTH) -> str:
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


def extract_response_text(response) -> str:
    direct_text = getattr(response, "text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        text_parts = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                text_parts.append(part_text.strip())
        if text_parts:
            return "\n".join(text_parts).strip()
    return ""


async def agent_inference(
    user_msg: str,
    author_name: str,
    client,
    context,
    enable_grounding: bool = True,
    max_lines: int = MAX_REPLY_LINES,
    max_length: int = MAX_REPLY_LENGTH,
):
    if not user_msg:
        return ""

    dynamic_prompt = build_dynamic_prompt(user_msg, author_name, context)
    grounding_modes = [enable_grounding]
    if enable_grounding:
        grounding_modes.append(False)

    for use_grounding in grounding_modes:
        try:
            tools: types.ToolListUnion = [types.Tool(google_search=types.GoogleSearch())] if use_grounding else []
            config = types.GenerateContentConfig(
                system_instruction=build_system_instruction(context),
                tools=tools,
                temperature=MODEL_TEMPERATURE,
                max_output_tokens=MODEL_MAX_OUTPUT_TOKENS,
                thinking_config=types.ThinkingConfig(
                    include_thoughts=False,
                    thinking_level=types.ThinkingLevel.MINIMAL,
                ),
            )

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=MODEL_NAME,
                contents=dynamic_prompt,
                config=config,
            )
            reply_text = extract_response_text(response)
            if reply_text:
                return enforce_reply_limits(reply_text, max_lines=max_lines, max_length=max_length)

            logger.warning("Gemini retornou resposta sem texto (grounding=%s).", use_grounding)
        except Exception as e:
            logger.error("Inference Error (grounding=%s): %s", use_grounding, e)
            if not use_grounding:
                return UNSTABLE_CONNECTION_FALLBACK

    return EMPTY_RESPONSE_FALLBACK
