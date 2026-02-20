# Byte - Twitch AI Chat Bot

`Byte` e um bot de chat da Twitch com Gemini 3 Flash (Vertex AI) e deploy em Cloud Run.

## O que ele faz hoje

- Conecta no canal como viewer (`irc`) ou modo oficial cloud (`eventsub`).
- Responde ao trigger `byte ...` com resposta curta e direta.
- Suporta comando de ficha tecnica e perguntas abertas.
- Mantem resposta curta para chat (limite de linhas por resposta).

## Comandos de chat

- `byte ajuda`
- `byte status`
- `byte ficha tecnica <filme>`
- `byte qual a ficha tecnica do filme que estamos vendo?`
- `byte <pergunta livre>`

## Modos de operacao

### `TWITCH_CHAT_MODE=irc` (demo sem autorizacao do streamer)

- Usa IRC com token de usuario da conta Byte.
- Scopes: `chat:read` e `chat:edit`.
- Variaveis principais:
  - `TWITCH_BOT_LOGIN`
  - `TWITCH_CHANNEL_LOGIN`
  - `TWITCH_USER_TOKEN`
  - `TWITCH_REFRESH_TOKEN` (opcional, recomendado)

### `TWITCH_CHAT_MODE=eventsub` (oficial cloud chatbot)

- Fluxo recomendado para producao cloud 2026.
- Em canal de terceiro, requer autorizacao do broadcaster.
- Scopes:
  - Bot: `user:read:chat`, `user:write:chat`, `user:bot`
  - Broadcaster: `channel:bot`
- Variaveis principais:
  - `TWITCH_CLIENT_ID`
  - `TWITCH_BOT_ID`
  - `TWITCH_CHANNEL_ID`

## Setup rapido

1. Copie `.env.example` para `.env` e preencha sem commitar secrets.
2. Instale dependencias: `pip install -r bot/requirements.txt`.
3. Rode local: `python bot/main.py`.
4. Deploy Cloud Run: `./deploy.sh`.

## Deploy Cloud Run

- Container escuta em `0.0.0.0:$PORT`.
- Timeout recomendado para conexao longa: `3600s`.
- Health endpoint em `GET /`.

## Visual Assets (placeholders prontos)

Use esta estrutura para os assets visuais do GitHub:

```text
assets/
  hero-banner-byte.png
  demo-chat-loop.gif
  architecture-byte-flow.png
  command-cards.png
  cloudrun-proof.png
```

Tabela de placeholders:

| Asset | Path sugerido | Uso no README |
|---|---|---|
| Hero banner | `assets/hero-banner-byte.png` | Topo do README |
| Demo GIF | `assets/demo-chat-loop.gif` | Secao "Como funciona" |
| Arquitetura | `assets/architecture-byte-flow.png` | Secao tecnica |
| Cards de comando | `assets/command-cards.png` | Secao comandos |
| Deploy proof | `assets/cloudrun-proof.png` | Secao producao |

Guia de criacao visual: `docs/GITHUB_VISUAL_ASSETS_2026.md`

## Documentacao

- Setup anti-erro: `docs/SETUP_2026_ANTI_BURRO.md`
- Validacao Twitch + Cloud Run: `docs/TWITCH_CLOUDRUN_RESEARCH.md`
- Guia visual GitHub 2026: `docs/GITHUB_VISUAL_ASSETS_2026.md`

## Seguranca

- Nao commite `.env`, tokens ou client secrets.
- Use Secret Manager para `TWITCH_CLIENT_SECRET`.
- Revise staging com `git status --short` antes de push.

## Licenca

Este projeto e open-source sob a licenca MIT. Veja `LICENSE`.

## Self-host

Qualquer pessoa pode fazer deploy do Byte na propria conta GCP usando `deploy.sh`.
