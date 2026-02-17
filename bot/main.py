import os
import asyncio
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

import twitchio
from twitchio.ext import commands
from google import genai
from google.cloud import secretmanager

from bot.logic import StreamContext, agent_inference, context

# ── Setup ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InvisibleProducer")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
CLIENT_ID  = os.environ.get("TWITCH_CLIENT_ID")
BOT_ID     = os.environ.get("TWITCH_BOT_ID")
OWNER_ID   = os.environ.get("TWITCH_OWNER_ID")
CHANNEL_ID = os.environ.get("TWITCH_CHANNEL_ID")

client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

# ── Twitch Agent Component ────────────────────────────────────
class AgentComponent(commands.Component):
    def __init__(self, bot: "ProducerBot") -> None:
        self.bot = bot

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context) -> None:
        query = ctx.message.text.removeprefix("!ask").strip()
        if not query: return
        ans = await agent_inference(query, ctx.message.author.name, client, context)
        await ctx.reply(ans)

    @commands.command(name="vibe")
    async def vibe(self, ctx: commands.Context) -> None:
        if str(ctx.message.author.id) == OWNER_ID:
            new_vibe = ctx.message.text.removeprefix("!vibe").strip()
            context.stream_vibe = new_vibe or "Chill"
            await ctx.reply(f"Vibe atualizada para: {context.stream_vibe} ✨")

    @commands.command(name="status")
    async def status(self, ctx: commands.Context) -> None:
        uptime = context.get_uptime_minutes()
        await ctx.reply(f"🤖 Invisible Producer v1.0 | {context.current_game} | Uptime: {uptime}min")

class ProducerBot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        super().__init__(client_id=CLIENT_ID, client_secret=client_secret, bot_id=BOT_ID, owner_id=OWNER_ID, prefix="!")

    async def setup_hook(self) -> None:
        await self.add_component(AgentComponent(self))
        channel = await self.fetch_channel(int(CHANNEL_ID))
        await channel.subscribe_events(twitchio.EventChatMessage)

    async def event_ready(self) -> None:
        logger.info(f"Agent Ready: {self.bot_id}")

    async def event_message(self, message: twitchio.ChatMessage) -> None:
        if message.echo: return
        if "bom dia" in message.text.lower() and not message.text.startswith("!"):
            ans = await agent_inference("Dê um bom dia gamer e rápido", message.author.name, client, context)
            await message.reply(ans)
            return
        await self.handle_commands(message)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AGENT_ONLINE")
    def log_message(self, *_): pass

def run_server():
    HTTPServer(("0.0.0.0", 8080), HealthHandler).serve_forever()

def get_secret():
    sm = secretmanager.SecretManagerServiceClient()
    path = f"projects/{PROJECT_ID}/secrets/twitch-client-secret/versions/latest"
    return sm.access_secret_version(name=path).payload.data.decode("UTF-8")

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    try:
        bot = ProducerBot(client_secret=get_secret())
        bot.run()
    except Exception as e:
        logger.critical(f"Fatal Error: {e}")
