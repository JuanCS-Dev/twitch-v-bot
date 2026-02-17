# 🤖 Twitch V-Bot: Gemini 3 Flash Agent

Agente de chat ultra-rápido e inteligente para Twitch, construído com a **Google Cloud Stack 2026**. Utiliza o Gemini 3 Flash para respostas em tempo real com baixa latência e integração nativa com o ecossistema Google.

## 🏗️ Estrutura do Projeto

- **/bot**: Core do agente Python utilizando `TwitchIO 3.2.1` (EventSub/WebSockets) e `Google GenAI SDK`.
- **/dashboard**: Painel de controle moderno em React + Vite para monitoramento e métricas.
- **/docs**: Documentação detalhada, guias de deploy e roadmap.

## ⚡ Stack Tecnológica

- **LLM:** [Gemini 3 Flash Preview](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash) via Vertex AI.
- **Inference Pattern:** Localização `global`, Grounding com Google Search ativado.
- **Backend:** Python 3.12 em ambiente Serverless.
- **Hosting:** Google Cloud Run (Auto-scaling, Health-checks na porta 8080).
- **Security:** Secrets gerenciados via Google Secret Manager.
- **Integration:** Twitch API via EventSub (WebSockets seguros).

## 🚀 Como Iniciar

### Pré-requisitos
- Conta Google Cloud com faturamento ativo.
- APIs habilitadas: Vertex AI, Secret Manager, Cloud Run.
- Aplicação registrada no [Twitch Dev Console](https://dev.twitch.tv/console).

### Bot
1. Configure os segredos no Secret Manager (`twitch-client-secret`).
2. Defina as variáveis de ambiente baseadas no `.env.example`.
3. Instale as dependências: `pip install -r bot/requirements.txt`.
4. Execute: `python bot/bot.py`.

### Dashboard
1. `cd dashboard`
2. `npm install`
3. `npm run dev`

## 🛠️ Comandos do Agent
- `!ask <pergunta>`: Invocação direta do Gemini com pesquisa web.
- `!wiki <termo>`: Resumo enciclopédico moderno.
- `!ping`: Verificação de latência e status do sistema.

---
*Developed with 🤖 by Gemini CLI - 2026*
