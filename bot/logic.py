import time
import asyncio
import logging
from google.genai import types

logger = logging.getLogger("InvisibleProducer")

class StreamContext:
    def __init__(self):
        self.current_game = "Iniciando..."
        self.stream_vibe = "Hype"
        self.last_event = "Bot Online"
        self.start_time = time.time()

    def get_uptime_minutes(self) -> int:
        return int((time.time() - self.start_time) / 60)

context = StreamContext()

SYSTEM_INSTRUCTION = (
    "Você é o 'Invisible Producer', um agente autônomo de elite para streams da Twitch. "
    "Sua missão é gerenciar o chat, manter o hype e ser o co-piloto do streamer. "
    "1. Responda em no máximo 2 frases curtas. 2. Use emojis semânticos. 3. Sem markdown."
)

def build_dynamic_prompt(user_msg: str, author_name: str, ctx: StreamContext) -> str:
    uptime = ctx.get_uptime_minutes()
    return f"Contexto Atual: [Jogo: {ctx.current_game} | Vibe: {ctx.stream_vibe} | Uptime: {uptime}min]\nUsuário {author_name}: {user_msg}"

async def agent_inference(user_msg: str, author_name: str, client, context, enable_grounding=True):
    if not user_msg:
        return ""
    try:
        dynamic_prompt = build_dynamic_prompt(user_msg, author_name, context)
        tools = [types.Tool(google_search=types.GoogleSearch())] if enable_grounding else []
        
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools,
            temperature=0.8,
            max_output_tokens=150,
            thinking_config=types.ThinkingConfig(include_thoughts=False)
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=dynamic_prompt,
            config=config
        )
        return response.text.strip() if (response and response.text) else "🤖 Processando..."
    except Exception as e:
        logger.error(f"Inference Error: {e}")
        return "⚠️ Conexão neural instável. Voltando em breve!"
