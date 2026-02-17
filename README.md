# 🤖 Twitch V-Bot: Gemini 3 Flash Agent

Agente de chat ultra-rápido para Twitch integrado com a Google Cloud Stack.

## 🏗️ Estrutura do Projeto

- **/bot**: Core do agente Python usando `TwitchIO 3.x` e `Google GenAI SDK`.
- **/dashboard**: Painel de controle moderno em React + Vite para monitoramento.
- **/docs**: Documentação técnica e roadmap.

## ⚡ Stack Tecnológica

- **LLM:** Gemini 3 Flash (via Vertex AI `global` location).
- **Runtime:** Python 3.12 + Cloud Run (Serverless).
- **Dashboard:** React + Tailwind CSS.
- **Infra:** Google Cloud Platform (Vertex AI, Secret Manager, Cloud Run).

## 🚀 Como Iniciar

### Bot
1. Configure as variáveis de ambiente (veja `docs/ROADMAP.md`).
2. Instale dependências: `pip install -r bot/requirements.txt`
3. Execute: `python bot/bot.py`

### Dashboard
1. `cd dashboard`
2. `npm install`
3. `npm run dev`

---
*Powered by Google Cloud & Gemini 3*
