# 🤖 BYTE AI — Agentic Stream Runtime (2026)
## The First "Stream Co-Producer" for Twitch

Byte is not a bot. It is an **Autonomous Agent Runtime** designed to manage, moderate, and grow Twitch channels using high-density intelligence. Powered by **Nebius AI (Kimi K2.5/K2-Thinking)** and **Supabase**, Byte bridges the gap between static commands and true real-time stream management.

---

## ⚡ Elite Performance Stats
- **Inference:** Powered by Nebius Token Factory (TTFT < 300ms).
- **Core:** 89 Python modules, 1,000+ Scientific Tests (100% Pass Rate).
- **Quality:** Structural Health 10.00/10 (Ruff/Pylint/McCabe).
- **Persistence:** Multi-tenant stateful layer via Supabase.
- **UI:** Zero-bloat Vanilla JS Dashboard with real-time telemetry.

---

## 🌟 Key Capabilities (Fases 1-25)

### 1. Persona Studio & Model Routing
Define the "soul" of the agent. Switch between **DeepSeek-R1** for strategic coaching and **Kimi K2.5** for high-speed chat interactions. Customize tone, slang, and behavioral constraints in real-time.

### 2. Tactical Calendar & Autonomy
Schedule strategic events via **Unix Cron** or **Fixed UTC Timestamps**. Byte monitors stream health, sentiment, and engagement goals, taking autonomous actions when necessary.

### 3. High-Density Braille ASCII Art
A proprietary engine that converts images into **2x4 Braille Matrix** art. Deliver ultra-sharp silhouettes (Goku, Batman, Pikachu) directly in the Twitch chat without breaking layout.

### 4. Real-time Clips Pipeline
Autonomous highlight detection + creation. The dashboard provides a visual pipeline with **real thumbnails** and live polling status for every clip job.

### 5. Intelligence & Observability
Live sentiment tracking (Hype vs. Boredom), viewer churn risk assessment, and automated post-stream analytical reports.

---

## 🚀 Quick Start (Operation Guide)

For detailed instructions, see the [**Operations Guide (Antiburro)**](docs/OPERATIONS_GUIDE.md).

### 1. Prerequisites
- Python 3.11+
- Supabase Project (PostgreSQL + pgvector)
- Nebius AI API Key
- Twitch Client ID & Secret

### 2. Installation
```bash
git clone https://github.com/JuanCS-Dev/twitch-byte-bot.git
cd twitch-byte-bot
pip install -r bot/requirements.txt
cp .env.example .env # Fill your keys
```

### 3. Running
```bash
# Start the Agent + Dashboard Server
python -m bot.main
```

---

## 🛠 Tech Stack
- **Backend:** Python (AsyncIO), OpenAI SDK, Croniter, Pillow.
- **Frontend:** HTML5, CSS Variables, Vanilla JS (No Frameworks).
- **Storage:** Supabase (PostgREST, Auth, Realtime).
- **Inference:** Nebius AI Studio (Kimi K2.5, K2-Thinking, Qwen).

---
*Developed by Juan Carlos — VÉRTICE Core Analytics x BYTE AI*
