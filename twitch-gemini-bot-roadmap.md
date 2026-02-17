# 🤖 Twitch Bot — Gemini 3 Flash + Vertex AI + Cloud Run
> Roadmap executável · Mínimo de código · Zero infraestrutura manual

---

## Visão Geral da Stack

```
Twitch Chat (EventSub WebSocket)
        ↓   TwitchIO 3.x (Python async)
    bot.py  ←→  google-genai SDK >= 1.51.0
                    ↓
            Vertex AI (gemini-3-flash-preview, location=global)
                    ↑
        Application Default Credentials (ADC)
                    ↑
        Cloud Run (min-instances=1, always-on)
```

| Componente | Tecnologia |
|---|---|
| Twitch Chat | TwitchIO 3.2.1 (EventSub WebSocket) |
| LLM SDK | `google-genai >= 1.51.0` |
| Model | `gemini-3-flash-preview` em `global` |
| Hosting | Cloud Run (`min-instances=1`) |
| Auth | ADC via Service Account |
| Segredos | Secret Manager |

---

## FASE 1 — Setup GCloud (15 min)

```bash
# 1. Crie o projeto
gcloud projects create twitch-bot-PROJECT_ID
gcloud config set project twitch-bot-PROJECT_ID

# 2. Ative as APIs
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com

# 3. Crie service account
gcloud iam service-accounts create twitch-bot-sa \
  --display-name="Twitch Bot SA"

# 4. Permissão Vertex AI
gcloud projects add-iam-policy-binding twitch-bot-PROJECT_ID \
  --member="serviceAccount:twitch-bot-sa@twitch-bot-PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# 5. Salve o client_secret da Twitch App no Secret Manager
#    (crie a app em https://dev.twitch.tv/console → "Register Your Application")
echo -n "SEU_CLIENT_SECRET" | \
  gcloud secrets create twitch-client-secret \
  --data-file=- \
  --replication-policy="automatic"

gcloud secrets add-iam-policy-binding twitch-client-secret \
  --member="serviceAccount:twitch-bot-sa@twitch-bot-PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

> **Twitch App:** registre em https://dev.twitch.tv/console.
> Você precisará do `client_id`, `client_secret`, `bot_id` (user ID da conta bot) e `owner_id` (seu user ID).

---

## FASE 2 — Código do Bot (30 min)

### Estrutura (apenas 3 arquivos)

```
twitch-bot/
├── bot.py
├── requirements.txt
└── Dockerfile
```

---

### `requirements.txt`

```
twitchio==3.2.1
google-genai>=1.51.0
google-cloud-secret-manager>=2.20.0
asqlite
```

---

### `bot.py`

```python
import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import twitchio
from twitchio.ext import commands
from google import genai
from google.genai import types
from google.cloud import secretmanager

# ── Config via env vars ───────────────────────────────────────
PROJECT_ID    = os.environ["GOOGLE_CLOUD_PROJECT"]
CLIENT_ID     = os.environ["TWITCH_CLIENT_ID"]
BOT_ID        = os.environ["TWITCH_BOT_ID"]       # user ID numérico da conta bot
OWNER_ID      = os.environ["TWITCH_OWNER_ID"]     # seu user ID numérico
CHANNEL_ID    = os.environ["TWITCH_CHANNEL_ID"]   # user ID numérico do canal alvo

# ── Secret Manager ────────────────────────────────────────────
def load_secret(name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    path   = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    return client.access_secret_version(name=path).payload.data.decode()

# ── Gemini 3 Flash via Vertex AI ──────────────────────────────
gemini = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location="global",   # obrigatório para gemini-3-flash-preview
)

SYSTEM_PROMPT = (
    "Você é um assistente de chat da Twitch. "
    "Responda de forma direta e em no máximo 2 frases. "
    "Nunca use markdown."
)

async def ask_gemini(question: str) -> str:
    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model="gemini-3-flash-preview",
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=120,
            thinking_config=types.ThinkingConfig(
                thinking_level="MINIMAL",  # latência mínima para chat ao vivo
            ),
        ),
    )
    return response.text.strip()

# ── TwitchIO 3 — Component com comandos ──────────────────────
class ChatCommands(commands.Component):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    # !ask <pergunta>
    @commands.command(name="ask")
    async def cmd_ask(self, ctx: commands.Context) -> None:
        question = ctx.message.text.removeprefix("!ask").strip()
        if not question:
            await ctx.reply("Use: !ask <sua pergunta>")
            return
        answer = await ask_gemini(question)
        await ctx.reply(answer)

    # !ping
    @commands.command(name="ping")
    async def cmd_ping(self, ctx: commands.Context) -> None:
        await ctx.reply("pong 🏓")

    # Adicione novos comandos aqui seguindo o mesmo padrão ↑

# ── Bot principal ─────────────────────────────────────────────
class Bot(commands.Bot):
    def __init__(self, client_secret: str) -> None:
        super().__init__(
            client_id=CLIENT_ID,
            client_secret=client_secret,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="!",
        )

    async def setup_hook(self) -> None:
        await self.add_component(ChatCommands(self))
        channel = await self.fetch_channel(int(CHANNEL_ID))
        await channel.subscribe_events(twitchio.EventChatMessage)

    async def event_ready(self) -> None:
        print(f"Bot online: {self.bot_id}")

# ── Healthcheck HTTP (exigido pelo Cloud Run) ─────────────────
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *_): pass

def start_health_server():
    HTTPServer(("0.0.0.0", 8080), Health).serve_forever()

# ── Entrypoint ────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=start_health_server, daemon=True).start()
    client_secret = load_secret("twitch-client-secret")
    bot = Bot(client_secret=client_secret)
    bot.run()
```

---

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

EXPOSE 8080
CMD ["python", "bot.py"]
```

---

## FASE 3 — Deploy no Cloud Run (10 min)

```bash
PROJECT_ID="twitch-bot-PROJECT_ID"
REGION="us-central1"
SA="twitch-bot-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Build
gcloud builds submit \
  --tag "gcr.io/${PROJECT_ID}/twitch-bot:latest"

# Deploy
gcloud run deploy twitch-bot \
  --image "gcr.io/${PROJECT_ID}/twitch-bot:latest" \
  --region "${REGION}" \
  --service-account "${SA}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},TWITCH_CLIENT_ID=xxx,TWITCH_BOT_ID=xxx,TWITCH_OWNER_ID=xxx,TWITCH_CHANNEL_ID=xxx" \
  --min-instances 1 \
  --max-instances 1 \
  --cpu 1 \
  --memory 256Mi \
  --port 8080 \
  --no-allow-unauthenticated
```

> Custo estimado 24/7: **~$5–8/mês** (256Mi, 1 vCPU, us-central1) + tokens Gemini Flash.

---

## FASE 4 — Adicionar Comandos (incremental)

Todo novo comando segue o mesmo padrão dentro de `ChatCommands`:

```python
@commands.command(name="resumo")
async def cmd_resumo(self, ctx: commands.Context) -> None:
    topic = ctx.message.text.removeprefix("!resumo").strip()
    answer = await ask_gemini(f"Resuma em 2 frases: {topic}")
    await ctx.reply(answer)
```

Redeploy após mudança:
```bash
gcloud builds submit --tag "gcr.io/${PROJECT_ID}/twitch-bot:latest"
gcloud run deploy twitch-bot --image "gcr.io/${PROJECT_ID}/twitch-bot:latest" --region us-central1
```

---

## Checklist Completo

- [ ] Projeto GCloud criado com billing ativado
- [ ] APIs habilitadas: `run`, `aiplatform`, `secretmanager`, `artifactregistry`
- [ ] Service account com roles `aiplatform.user` + `secretmanager.secretAccessor`
- [ ] App registrada em https://dev.twitch.tv/console
- [ ] `client_secret` salvo no Secret Manager
- [ ] `bot.py`, `requirements.txt`, `Dockerfile` criados
- [ ] `gcloud builds submit` + `gcloud run deploy`
- [ ] Testar `!ping` e `!ask Olá` no canal

---

## Referências

- Gemini 3 Flash — model ID e thinking_level: https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash
- google-genai SDK >= 1.51.0: https://googleapis.github.io/python-genai/
- TwitchIO 3.x docs: https://twitchio.dev/en/stable/
- Cloud Run min-instances: https://cloud.google.com/run/docs/configuring/min-instances
- Twitch Dev Console: https://dev.twitch.tv/console
