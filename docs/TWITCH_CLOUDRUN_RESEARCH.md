# Twitch API + Cloud Run Notes (Co-Streamer)

## Objetivo
Evoluir o bot para atuar como co-streamer generalista, com observabilidade de tudo que aparece na live: jogos, filmes, series, videos do YouTube, posts do X e temas livres.

## Twitch API (Helix/EventSub)

### Autenticacao base
- Helix exige `Authorization: Bearer <token>` e `Client-Id`.
- O `Client-Id` do header deve bater com o token OAuth.

### Rate limit
- Twitch usa token-bucket por minuto.
- Buckets separados para app token e user token.
- Headers de controle:
  - `Ratelimit-Limit`
  - `Ratelimit-Remaining`
  - `Ratelimit-Reset`
- Ao receber `429`, usar `Ratelimit-Reset` para backoff.

### Endpoints mais uteis para observabilidade
- `GET /helix/channels`
  - Traz `title`, `game_name`, `tags`, `content_classification_labels`.
  - Bom para snapshot do "estado editorial" da live.
- `GET /helix/streams`
  - Traz `viewer_count`, `started_at`, `title`, `tags`, `game_name`.
  - Bom para detectar estado live e contexto atual.
- `GET /helix/videos`
  - Base para recuperar VODs e contexto historico.
- `GET /helix/search/channels`
  - Busca por nomes/categorias com `live_only`.
- `GET /helix/chat/chatters`
  - Lista chatters conectados (com escopo de moderacao).

### EventSub
- `POST /helix/eventsub/subscriptions`
  - `transport.method=websocket` exige user access token e `session_id`.
  - `transport.method=webhook` exige app access token.
- `GET /helix/eventsub/subscriptions`
  - Verifica custo, status e total de inscricoes.
- `DELETE /helix/eventsub/subscriptions?id=...`
  - Remove inscricoes antigas/invalidas.

## Cloud Run (servico HTTP + WebSocket)

### Contrato de container
- O container de ingress precisa escutar em `0.0.0.0:$PORT`.
- Default de porta: `8080`.
- Nao escutar em `127.0.0.1`.

### Timeouts e WebSockets
- WebSocket no Cloud Run e tratado como request HTTP longa.
- Continua sujeito ao request timeout do servico.
- Limite atual para timeout de request: ate 60 minutos.
- Cliente deve implementar reconnect automatico.

### Escala e estado
- Session affinity ajuda, mas e best effort (nao garante mesma instancia).
- Se houver multiplas instancias, sincronizar estado externo (ex: Redis/Memorystore Pub/Sub).
- Concurrency suporta muitas conexoes (ate limite de cota do servico).

### Ciclo de vida
- Instancia precisa ficar pronta em ate 4 min no startup.
- Shutdown envia `SIGTERM` e depois `SIGKILL` (~10s).
- Trap de `SIGTERM` e importante para flush/graceful shutdown.

## Implicacoes praticas para este bot
- Manter contexto local para "agora da live" (jogo/filme/serie/youtube/x/topic).
- Priorizar comandos do owner para atualizar contexto em tempo real.
- Tratar respostas do LLM com estilo generalista e sem persona gamer caricata.
- Para ingestao automatica de links:
  - aceitar apenas fontes confiaveis (owner/mod);
  - permitir somente hosts suportados (YouTube e X/Twitter);
  - buscar metadata por oEmbed (titulo/autor/provedor) antes de persistir contexto;
  - bloquear mensagens/URLs com termos sensiveis (NSFW/violencia explicita);
  - manter denylist de dominios adultos.
  - persistir apenas descricao sanitizada no contexto (evitar repetir URL bruta no chat).
- Em deploy no Cloud Run:
  - `--min-instances 1`
  - timeout alinhado ao comportamento esperado do app
  - estrategia de reconnect do cliente/chat
- Para escala horizontal futura:
  - mover contexto para Redis ou outro state store compartilhado.

## Referencias oficiais
- Twitch API Reference: `https://dev.twitch.tv/docs/api/reference`
- Twitch API Guide (rate limits/pagination): `https://dev.twitch.tv/docs/api/guide`
- Cloud Run Container Contract: `https://cloud.google.com/run/docs/container-contract`
- Cloud Run WebSockets: `https://cloud.google.com/run/docs/triggering/websockets`
