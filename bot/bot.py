import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import twitchio
from twitchio.ext import commands
from google import genai
from google.genai import types
from google.cloud import secretmanager

# ── Configuration ─────────────────────────────────────────────
PROJECT_ID    = os.environ.get("GOOGLE_CLOUD_PROJECT")
CLIENT_ID     = os.environ.get("TWITCH_CLIENT_ID")
BOT_ID        = os.environ.get("TWITCH_BOT_ID")
OWNER_ID      = os.environ.get("TWITCH_OWNER_ID")
CHANNEL_ID    = os.environ.get("TWITCH_CHANNEL_ID")

# ── Vertex AI Client (Gemini 3 Flash) ─────────────────────────
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location="global", # Required for gemini-3-flash-preview
)

SYSTEM_PROMPT = (
    "Você é um assistente de chat da Twitch moderno e minimalista. "
    "Responda de forma direta, sem markdown, no máximo 2 frases. "
    "Seja útil, mas mantenha a vibe de stream."
)

async def ask_gemini(prompt: str) -> str:
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=150,
                thinking_config=types.ThinkingConfig(include_thoughts=False),
            ),
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return "Desculpe, tive um erro ao processar sua resposta. 🤖"

# ── Twitch Bot Components ─────────────────────────────────────
class CoreCommands(commands.Component):
    def __init__(self, bot: "TwitchBot") -> None:
        self.bot = bot

    @commands.command(name="ask")
    async def ask_command(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!ask").strip()
        if not query:
            await ctx.reply("O que você quer saber? Digite !ask <pergunta>")
            return
        
        answer = await ask_gemini(query)
        await ctx.reply(answer)

    @commands.command(name="ping")
    async def ping_command(self, ctx: commands.Context) -> None:
        await ctx.reply("Bot online e operante! ⚡")

# ── Main Bot Class ────────────────────────────────────────────
class TwitchBot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        super().__init__(
            client_id=CLIENT_ID,
            client_secret=client_secret,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="!",
        )

    async def setup_hook(self) -> None:
        await self.add_component(CoreCommands(self))
        channel = await self.fetch_channel(int(CHANNEL_ID))
        await channel.subscribe_events(twitchio.EventChatMessage)

    async def event_ready(self) -> None:
        print(f"Logged in as | {self.bot_id}")

# ── Healthcheck (Cloud Run) ───────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *_): pass

def run_health_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthHandler)
    server.serve_forever()

# ── Secrets and Entrypoint ────────────────────────────────────
def get_secret(secret_id: str) -> str:
    sm = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    return sm.access_secret_version(name=name).payload.data.decode("UTF-8")

if __name__ == "__main__":
    # Start health server for Cloud Run
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Load Twitch Client Secret from Secret Manager
    twitch_secret = get_secret("twitch-client-secret")
    
    bot = TwitchBot(client_secret=twitch_secret)
    bot.run()
