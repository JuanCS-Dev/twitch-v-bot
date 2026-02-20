# Byte - Twitch + Cloud Run Validation (2026)

## Escopo

Validacao para o cenario de hoje:

- Bot conectado em canal de terceiro (amigo), como viewer.
- Leitura + resposta a comandos no chat (`byte ...`).
- Deploy em Cloud Run com operacao estavel.
- Duas trilhas: oficial (`eventsub`) e demo sem streamer (`irc`).

## Fontes oficiais consultadas

- Twitch Chat: `https://dev.twitch.tv/docs/chat/`
- Twitch Auth/EventSub: `https://dev.twitch.tv/docs/chat/authenticating/`
- Twitch IRC: `https://dev.twitch.tv/docs/chat/irc/`
- Twitch EventSub types: `https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/`
- Twitch Send Chat Message API: `https://dev.twitch.tv/docs/api/reference/#send-chat-message`
- Cloud Run container contract: `https://cloud.google.com/run/docs/container-contract`
- Cloud Run websockets: `https://cloud.google.com/run/docs/triggering/websockets`
- Cloud Run request timeout: `https://cloud.google.com/run/docs/configuring/request-timeout`

## Twitch - Regras 2026 relevantes

### 1) Caminho oficial cloud chatbot (EventSub + API)

- Twitch reforca EventSub + API como caminho preferido para bots cloud.
- Para canal de terceiro, o fluxo oficial com app token exige autorizacao do broadcaster.

Escopos tipicos:

- Bot account: `user:read:chat`, `user:write:chat`, `user:bot`
- Broadcaster account: `channel:bot`

Observacao:

- Em `channel.chat.message` + envio via `POST /helix/chat/messages` com app token,
  a doc exige `user:bot` + `channel:bot` (ou moderador).

### 2) Trilha de demonstracao sem autorizacao do streamer (IRC)

- Conectar a conta Byte via IRC como usuario normal.
- Ler e responder chat com token de usuario do Byte.
- Escopos recomendados no token de usuario: `chat:read`, `chat:edit`.
- Nessa trilha nao depende de `channel:bot` do streamer para provar funcionamento basico.

Limites/pragmatismo:

- Continua sujeito aos limites de chat da Twitch.
- Deve implementar reconexao e rate control minimo para estabilidade.
- E trilha de demo/POC; para integracao cloud oficial ampla, preferir EventSub.

### 3) Limites de chat

- Existem limites de mensagem por janela e por canal.
- Estourar limite pode silenciar mensagens por periodo.
- Em volume alto, implementar backoff.

## Cloud Run - Regras 2026 relevantes

### 1) Container contract

- Processo HTTP deve escutar em `0.0.0.0`.
- Porta vem de `PORT` (default comum: `8080`).
- Startup deve concluir dentro da janela suportada (doc cita ate 4 minutos).
- Encerramento: `SIGTERM` antes de `SIGKILL`; ideal tratar graceful shutdown.

### 2) Conexoes longas

- WebSocket e request HTTP longa no Cloud Run.
- Continua sujeito ao request timeout do servico.
- Timeout maximo de request: `3600s` (60 min).
- Cliente deve suportar reconnect.

## Status do projeto apos ajustes de hoje

- Branding principal migrado para `Byte`.
- Trigger por chat textual implementado: `byte ...`.
- Comando de ficha tecnica de filme implementado.
- Saida limitada por politica de resposta curta (maximo 8 linhas).
- Modo `irc` implementado para demo sem streamer.
- Health server compativel com Cloud Run (`0.0.0.0:$PORT`).

## Checklist de deploy (hoje)

### Trilha A (sem autorizacao do streamer)

1. Definir `TWITCH_CHAT_MODE=irc`.
2. Configurar `TWITCH_BOT_LOGIN`, `TWITCH_CHANNEL_LOGIN`, `TWITCH_USER_TOKEN`.
3. Habilitar refresh automatico com `TWITCH_REFRESH_TOKEN` + `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` (ou Secret Manager).
4. Confirmar token da conta Byte com `chat:read chat:edit`.
5. Subir no Cloud Run com timeout ate `3600` e min-instances `1`.
6. Validar no chat:
   - `byte ajuda`
   - `byte status`
   - `byte qual a ficha tecnica do filme que estamos vendo?`

### Trilha B (oficial cloud)

1. Definir `TWITCH_CHAT_MODE=eventsub`.
2. Confirmar scopes do bot: `user:read:chat user:write:chat user:bot`.
3. Confirmar autorizacao do broadcaster: `channel:bot`.
4. Garantir `TWITCH_CHANNEL_ID` apontando para o canal alvo.
