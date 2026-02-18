import asyncio
import logging
import time
from typing import Dict

from google.genai import types

logger = logging.getLogger("InvisibleProducer")

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
    "Você é o 'Invisible Producer', um co-streamer para lives na Twitch. "
    "Responda com clareza e objetividade para os assuntos ativos da live, incluindo jogos, filmes, séries, vídeos do YouTube, posts do X e temas gerais. "
    "Regras: 1) no máximo 2 frases curtas. 2) use no máximo 1 emoji e só quando fizer sentido. "
    "3) sem markdown. 4) não use persona caricata nem linguagem ofensiva. "
    "5) se faltar contexto, faça uma pergunta objetiva."
)


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


context = StreamContext()


def build_system_instruction(ctx: StreamContext) -> str:
    return f"{SYSTEM_INSTRUCTION_TEMPLATE} Estilo ativo: {ctx.style_profile}"


def build_dynamic_prompt(user_msg: str, author_name: str, ctx: StreamContext) -> str:
    uptime = ctx.get_uptime_minutes()
    observability = ctx.format_observability()
    return (
        "Contexto Atual da Live: "
        f"[Vibe: {ctx.stream_vibe} | Uptime: {uptime}min | "
        f"Observabilidade: {observability} | Ultimo evento: {ctx.last_event}]\n"
        f"Usuario {author_name}: {user_msg}"
    )


async def agent_inference(user_msg: str, author_name: str, client, context, enable_grounding=True):
    if not user_msg:
        return ""
    try:
        dynamic_prompt = build_dynamic_prompt(user_msg, author_name, context)
        tools = [types.Tool(google_search=types.GoogleSearch())] if enable_grounding else []

        config = types.GenerateContentConfig(
            system_instruction=build_system_instruction(context),
            tools=tools,
            temperature=0.6,
            max_output_tokens=150,
            thinking_config=types.ThinkingConfig(include_thoughts=False),
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=dynamic_prompt,
            config=config,
        )
        return response.text.strip() if (response and response.text) else "🤖 Processando..."
    except Exception as e:
        logger.error(f"Inference Error: {e}")
        return "⚠️ Conexao com o modelo instavel. Tente novamente em instantes."
