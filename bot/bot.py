import os
import asyncio
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

import twitchio
from twitchio.ext import commands
from google import genai
from google.genai import types
from google.cloud import secretmanager

# ── Logging Configuration ─────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TwitchVBot")

# ── Environment Configuration ─────────────────────────────────
PROJECT_ID    = os.environ.get("GOOGLE_CLOUD_PROJECT")
CLIENT_ID     = os.environ.get("TWITCH_CLIENT_ID")
BOT_ID        = os.environ.get("TWITCH_BOT_ID")
OWNER_ID      = os.environ.get("TWITCH_OWNER_ID")
CHANNEL_ID    = os.environ.get("TWITCH_CHANNEL_ID")
REGION        = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

# ── Vertex AI Client Initialization (2026 Production Pattern) ─
# Using the modern google-genai SDK for high-level inference
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location="global",  # Gemini 3 Flash Preview currently requires 'global'
)

# ── System Behavior ───────────────────────────────────────────
DEFAULT_SYSTEM_INSTRUCTION = (
    "Você é o assistente oficial do canal. Responda de forma curta (máx 2 frases). "
    "Mantenha um tom descontraído e gamer. Use no máximo um emoji. "
    "Nunca utilize markdown ou formatação complexa."
)

async def generate_response(
    prompt: str, 
    enable_grounding: bool = True, 
    instruction: str = DEFAULT_SYSTEM_INSTRUCTION
) -> str:
    """
    Inference via Vertex AI with Google Search Grounding.
    """
    try:
        # Define Tools: Google Search for real-time data
        tools = [types.Tool(google_search=types.GoogleSearch())] if enable_grounding else []
        
        # Generation Configuration (Optimized for 2026 Latency)
        config = types.GenerateContentConfig(
            system_instruction=instruction,
            tools=tools,
            temperature=0.7,
            max_output_tokens=150,
            thinking_config=types.ThinkingConfig(include_thoughts=False), # Minimal latency for Twitch
        )

        # Async execution using thread-pool for the synchronous SDK calls
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=prompt,
            config=config
        )
        
        if not response.text:
            return "🤖 Sistema processando... mande outra pergunta!"
            
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Vertex AI Error: {e}")
        return "⚠️ Erro na conexão neural com o Gemini. Tente novamente."

# ── Twitch Bot Logic ──────────────────────────────────────────
class CoreBot(commands.Component):
    def __init__(self, bot: "TwitchVBot") -> None:
        self.bot = bot

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!ask").strip()
        if not query:
            await ctx.reply("Diga algo! Ex: !ask quem é o maior streamer do mundo?")
            return
        answer = await generate_response(query)
        await ctx.reply(answer)

    @commands.command(name="wiki")
    async def wiki(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!wiki").strip()
        instruction = "Gere um resumo informativo e estruturado, mas com linguagem descontraída."
        answer = await generate_response(query or "o universo", enable_grounding=True, instruction=instruction)
        await ctx.reply(answer)

    @commands.command(name="pesquisa")
    async def pesquisa(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!pesquisa").strip()
        instruction = "Pesquise na web e responda detalhadamente usando as informações mais recentes."
        answer = await generate_response(query or "últimas notícias tech", enable_grounding=True, instruction=instruction)
        await ctx.reply(answer)

    @commands.command(name="clima")
    async def clima(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!clima").strip()
        instruction = "Forneça a previsão do tempo atual, temperatura e condições para a cidade mencionada."
        answer = await generate_response(query or "São Paulo", enable_grounding=True, instruction=instruction)
        await ctx.reply(answer)

    @commands.command(name="historia")
    async def historia(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!historia").strip()
        instruction = "Crie uma história curta, criativa e envolvente (pode usar humor ou lore gamer)."
        answer = await generate_response(query or "um bot que queria ser humano", enable_grounding=False, instruction=instruction)
        await ctx.reply(answer)

    @commands.command(name="traduzir")
    async def traduzir(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!traduzir").strip()
        instruction = "Traduza o texto para Português do Brasil (PT-BR), mantendo o tom original."
        answer = await generate_response(query or "Hello world", enable_grounding=False, instruction=instruction)
        await ctx.reply(answer)

    @commands.command(name="imaginar")
    async def imaginar(self, ctx: commands.Context) -> None:
        await ctx.reply("🎨 O módulo de geração de imagens (Imagen 3) requer permissões adicionais no Vertex AI. Em breve!")

    @commands.command(name="falar")
    async def falar(self, ctx: commands.Context) -> None:
        await ctx.reply("🎙️ O módulo de síntese de voz está sendo calibrado. Em breve no chat!")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.reply("Pong! ⚡ Sistema operacional.")

# ── Main Application ──────────────────────────────────────────
class TwitchVBot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        super().__init__(
            client_id=CLIENT_ID,
            client_secret=client_secret,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="!",
        )

    async def setup_hook(self) -> None:
        await self.add_component(CoreBot(self))
        channel = await self.fetch_channel(int(CHANNEL_ID))
        await channel.subscribe_events(twitchio.EventChatMessage)

    async def event_ready(self) -> None:
        logger.info(f"V-Bot Online | Logged as ID: {self.bot_id}")

# ── Infrastructure (Cloud Run Health & Secrets) ───────────────
class HealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *_): pass

def start_health_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthServer)
    server.serve_forever()

def load_twitch_secret() -> str:
    """Fetches secret from GCP Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/twitch-client-secret/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode("UTF-8")

if __name__ == "__main__":
    # Start internal server for Cloud Run health checks
    threading.Thread(target=start_health_server, daemon=True).start()
    
    try:
        # Load credentials and start bot
        secret = load_twitch_secret()
        bot = TwitchVBot(client_secret=secret)
        bot.run()
    except Exception as e:
        logger.critical(f"Startup failed: {e}")
