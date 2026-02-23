---
title: Twitch Byte Bot
emoji: 🤖
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# ByteBot Twitch (HF Space)

Este é o deploy automático do ByteBot para a Twitch rodando no Hugging Face Spaces via Docker.

## Configuração

O bot precisa das seguintes variáveis de ambiente (configuradas no painel do Space em **Settings -> Repository Secrets**):

- `NEBIUS_API_KEY`
- `TWITCH_OWNER_ID`
- `TWITCH_CLIENT_ID`
- `TWITCH_BOT_ID`
- `TWITCH_CHANNEL_ID`
- `TWITCH_BOT_LOGIN`
- `TWITCH_CHANNEL_LOGIN`
- `TWITCH_USER_TOKEN`
- `TWITCH_REFRESH_TOKEN`
- `BYTE_DASHBOARD_ADMIN_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_KEY`

O bot usa o `duckduckgo-search` para current events e mantém a sessão ativa via self-heartbeat de 3 em 3 minutos.
