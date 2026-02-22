# Byte Co-Streamer Roadmap (Upgrade Incremental + Twitch Clips API Oficial)

Documento de execucao para upgrade do agente atual na Twitch (Branch `v2`).
Nao e greenfield, nao e plataforma generica, nao e "novo SO de agentes".
Objetivo: integrar clipping oficial Twitch com o menor delta possivel sobre o que ja funciona.

## 0) Premissas obrigatorias

- O agente ja opera na Twitch hoje (`irc` e `eventsub`), com dashboard e control plane ativos.
- O upgrade deve reaproveitar obrigatoriamente a arquitetura atual:
    - `bot/autonomy_runtime.py`
    - `bot/control_plane.py`
    - `bot/control_plane_actions.py`
    - `bot/dashboard_server_routes.py`
    - `dashboard/features/action-queue/*`
- Clips DEVEM ser operados via API oficial Helix.
- **Google Cloud Run First**: A aplicacao deve permanecer stateless. Logs devem ir para stdout/stderr. Nao depender de disco local para estado critico.
- Nao inventar contrato da Twitch: usar estritamente docs oficiais.
- Regra de engenharia: simplicidade integrada > overengineering.

### 0.1 Guardrails anti-duplicacao (proibicoes globais)

- Proibido criar segunda fila de aprovacao (usar apenas `ControlPlaneActionQueue` existente).
- Proibido criar segundo control plane, segundo servidor HTTP ou segundo fluxo de auth.
- Proibido criar "framework de jobs/workflows" generico para um unico caso de uso (clips).
- Proibido criar camadas abstratas sem uso imediato no clipping atual.
- Proibido duplicar telas/rotas que ja existem no dashboard so para "organizar melhor".
- Proibido tratar este upgrade como reconstrucao completa do agente.

### 0.2 Quando pode criar algo do zero

- Apenas quando houver lacuna real comprovada no codigo existente.
- Arquivo novo deve ter responsabilidade unica e nome especifico de clips.
- Antes de criar arquivo novo, tentar extensao direta nos arquivos base da secao 0.
- Qualquer modulo novo deve entrar integrado no fluxo atual (control plane + observability + dashboard), sem "ramo paralelo".

### 0.3 Estrategia de Branching e Deploy

- **Branch `v2`**: Todo desenvolvimento deste roadmap deve ocorrer obrigatoriamente em uma branch chamada `v2`.
- **Branch `main` (V1)**: A versao atual (V1) deve continuar operante em producao. Nao misturar codigo da V2 na main ate o DoD global.
- **Deploy**: O deploy da V2 deve ser feito em servico paralelo (ex: `byte-costreamer-v2`) ou substituir a V1 somente apos validacao total (Fase 9).

## 1) Baseline ja implementado (nao refazer)

- Contrato de resposta: 1 mensagem, max 4 linhas.
- Runtime com modos `irc` e `eventsub`.
- Fila de risco com `approve|reject` em `/api/action-queue`.
- Dashboard com polling de observabilidade/control plane/action queue.
- Loop de autonomia com goals, budget anti-spam e heartbeat.
- Token manager com validacao e refresh no fluxo IRC (`bot/twitch_tokens.py`).
- Escopos de chat em operacao hoje (docs Twitch):
    - EventSub/chat bot: `user:read:chat`, `user:write:chat`, `user:bot`, `channel:bot`.
    - IRC: `chat:read`, `chat:edit`.

## 2) Contrato oficial Twitch para Clips (fonte normativa)

### 2.1 Endpoints e scopes

- `POST https://api.twitch.tv/helix/clips`
    - Scope: `clips:edit`
    - Token exigido: user access token
- `POST https://api.twitch.tv/helix/videos/clips` (Create Clip From VOD)
    - Scope: `editor:manage:clips` ou `channel:manage:clips`
    - Token aceito: app access token ou user access token (conforme docs)
- `GET https://api.twitch.tv/helix/clips`
    - Token aceito: app access token ou user access token
- `GET https://api.twitch.tv/helix/clips/downloads`
    - Scope: `editor:manage:clips` ou `channel:manage:clips`
    - Token aceito: app access token ou user access token
    - Limite especifico: 100 req/min para `Get Clips Download`

### 2.2 Headers obrigatorios Helix

- `Authorization: Bearer <token>`
- `Client-Id: <client_id>`
- `Client-Id` deve bater com o client do token, senao 401.

### 2.3 Regras oficiais de validacao de token

- Endpoint oficial: `GET https://id.twitch.tv/oauth2/validate`
- Apps/chatbots que mantem sessao OAuth devem validar no startup e a cada 1h.
- Header aceito: `Authorization: OAuth <token>` (Bearer tambem aceito pela doc).

### 2.4 Comportamento oficial de Create Clip (`POST /helix/clips`)

- Processo assincrono: resposta `202 Accepted`.
- Retorna `id` e `edit_url`.
- A API captura ate 90s ao redor do momento da chamada.
- Por padrao, publica ate os ultimos 30s dessa janela.
- `edit_url` permite ajustar titulo e trecho final (5s a 60s).
- `edit_url` vale por ate 24h ou ate publicacao do clip.
- Confirmacao obrigatoria: chamar `GET /helix/clips?id=<clip_id>`.
- Se apos 15s o clip nao aparecer em `Get Clips`, assumir falha.

### 2.5 Parametros oficiais importantes

- `POST /helix/clips`:
    - Obrigatorio: `broadcaster_id`
    - Opcionais: `has_delay` (boolean, default false), `title`, `duration` (5 a 60, precisao 0.1, default 30)
- `POST /helix/videos/clips`:
    - Obrigatorios: `editor_id`, `broadcaster_id`, `vod_id`, `vod_offset`
    - Opcionais: `title` (recomendado), `duration` (5 a 60, default 30)
    - Regra critica: `vod_offset >= duration`
    - Esse endpoint tambem pode criar clip de trecho anterior da live atual (via VOD em progresso).
- `GET /helix/clips`:
    - `id`, `game_id` e `broadcaster_id` sao mutuamente exclusivos
    - `first` max 100, paginacao por `after`/`before`
    - Em multiplas paginas, resultado pratico total ~= 1000
    - `vod_offset` pode ficar `null` por alguns minutos apos criacao durante live.
- `GET /helix/clips/downloads`:
    - Obrigatorios: `editor_id`, `broadcaster_id`, `clip_id` (max 10)
    - `landscape_download_url` e `portrait_download_url` podem vir `null`.

### 2.6 Erros oficiais que DEVEM ser tratados

- `POST /helix/clips` e `POST /helix/videos/clips`: `202`, `400`, `401`, `403`, `404`.
- `GET /helix/clips`: `200`, `400`, `401`, `404`.
- `GET /helix/clips/downloads`: `200`, `400`, `401`, `403`, `500`.
- `400` (exemplos docs): parametro faltando/invalido, categoria nao clippable, titulo reprovado no AutoMod.
- `401`: token invalido, scope faltando, `Client-Id` mismatch.
- `403`: clips desabilitados ou restritos a followers/subs; usuario banido/timeout; editor nao autorizado.
- `404`: broadcaster nao live no fluxo live; VOD nao encontrado no fluxo VOD.
- `429`: tratar como limite global da API (token bucket), respeitando `Ratelimit-Reset`.

## 3) Objetivo do upgrade (o que entra agora)

- Evoluir o pipeline de clips sobre a fila de risco existente.
- Criar fluxo end-to-end: detectar momento -> aprovar -> criar clip via Helix -> acompanhar status -> entregar links operacionais.
- Incluir caminho live (`/helix/clips`) e caminho VOD (`/helix/videos/clips`) sem quebrar o loop atual.
- Tudo que ja existe deve servir de base; criar do zero apenas onde nao existir capacidade minima.

## 4) Arquitetura alvo incremental (sem reescrever base)

### 4.1 Ordem obrigatoria de extensao (reusar primeiro)

- `bot/control_plane_config.py`
    - Adicionar flags/config de clipping no mesmo contrato atual (`_config`), sem sistema novo de configuracao.
- `bot/control_plane.py`
    - Expor capacidades de clipping em `build_capabilities`, sem novo objeto global.
- `bot/control_plane_actions.py`
    - Reusar a fila atual para `kind=clip_candidate`; nao criar fila paralela.
- `bot/autonomy_runtime.py`
    - Gerar candidatos (`clip_candidate`) sem chamar Twitch API direto no heartbeat.
- `bot/dashboard_server_routes.py`
    - Expor leitura/acao de clip jobs reaproveitando o mesmo padrao de rotas (`/api/...`) e auth existente.
- `dashboard/features/action-queue/*`
    - Reusar approve/reject existente na Fase 1.
- `dashboard/features/clips/*` (novo, apenas quando houver estado real na Fase 3)
    - UI operacional de lifecycle (`queued|creating|polling|ready|failed`).

### 4.2 Novos arquivos permitidos (somente se houver lacuna)

- `bot/twitch_clips_api.py` (permitido na Fase 2)
    - Wrapper especifico de clips (headers Helix, parse de erro, retry 429/5xx).
- `bot/clip_jobs_runtime.py` (permitido na Fase 2+)
    - Maquina de estados minima de jobs de clip (nada de framework generico).
- `bot/clip_jobs_store.py` (permitido apenas na Fase 5)
    - **Cloud Run Alert**: Persistencia deve ser externa (Redis/Firestore) ou aceitar perda. Arquivos locais (`.jsonl`, `.sqlite`) sao efemeros e serao perdidos no restart.
- Proibicao explicita:
    - Nao criar `bot/twitch_helix_client.py` generico agora.
    - Nao criar biblioteca "workflow engine" para um unico fluxo.

### 4.3 Contrato minimo de `clip_candidate` (na fila atual)

- `action.kind`: `clip_candidate`.
- `action.risk`: manter niveis existentes (ex.: `suggest_streamer`) para nao quebrar UX atual.
- `payload.schema`: `clip_candidate.v1`.
- `payload.candidate_id`: id deduplicavel.
- `payload.broadcaster_id`: string numerica obrigatoria.
- `payload.mode`: `live|vod`.
- `payload.suggested_duration`: `5.0` a `60.0`.
- `payload.suggested_title`: opcional.
- `payload.source`: `autonomy_goal|manual|chat_spike|keyword`.
- `payload.source_ts`: timestamp ISO.
- `payload.context_excerpt`: resumo curto do momento.
- `payload.dedupe_key`: hash estavel para evitar duplicado.

### 4.4 Contrato de estado sugerido para `clip_job`

- `job_id`: id interno unico.
- `action_id`: referencia ao item aprovado da action queue (nao perder rastreabilidade).
- `candidate_source`: `chat_spike|keyword|autonomy_goal|manual`.
- `broadcaster_id`: id Twitch alvo.
- `mode`: `live` ou `vod`.
- `requested_duration`: 5-60.
- `requested_title`: texto inicial.
- `status`: `pending_approval|approved|queued|creating|polling|ready|failed|expired`.
- `twitch_clip_id`: id retornado pela Twitch.
- `edit_url`: URL de edicao/publish.
- `clip_url`: URL publica (`Get Clips`).
- `error_code`: `clip_bad_request|clip_unauthorized|clip_forbidden|clip_not_found|clip_rate_limited|clip_unknown`.
- `error_detail`: mensagem curta para operador.
- `attempts`: contador de tentativas.
- `created_at`, `updated_at`, `ready_at`.
- Transicoes validas (obrigatorio):
    - `pending_approval -> approved|expired`
    - `approved -> queued -> creating -> polling -> ready|failed`
    - `failed -> queued` (somente retry manual/limitado)

## 5) Roadmap por fases (execucao)

### Fase 0 - Hardening de auth e pre-condicoes (1 semana)

Objetivo: evitar falhas basicas de OAuth/scope antes de ligar criacao real.

Entregas:
- Adicionar validacao explicita de token para fluxo de clips no startup e scheduler 1h.
- Conferir scopes necessarios no payload de `/validate` antes de habilitar clip pipeline.
- Adicionar flags no control plane:
    - `clip_pipeline_enabled`
    - `clip_api_enabled`
    - `clip_mode_default` (`live|vod`)
- Registrar em observabilidade:
    - `clips_token_valid`
    - `clips_scope_ok`
    - `clips_pipeline_enabled`

Erros comuns previstos:
- Implementador usar app token em `POST /helix/clips` (vai 401).
- Implementador esquecer `Client-Id` no header.
- Implementador ignorar mismatch `Client-Id` vs token.

Criterio de saida:
- Health/observability mostra estado de auth de clips.
- Feature pode ficar ligada/desligada via control plane sem deploy.

Rollback:
- `clip_api_enabled=false` imediatamente.

### Fase 1 - Deteccao de candidatos e aprovacao (1-2 semanas)

Objetivo: gerar candidatos sem chamar API da Twitch ainda.

Entregas:
- Em `autonomy_runtime`, gerar sugestao `clip_candidate` com contexto minimo:
    - timestamp
    - resumo do momento
    - score de confianca
    - duracao sugerida
- Em `control_plane_actions`, padronizar payload de candidato.
- Dashboard reaproveita `/api/action-queue` para approve/reject.

Erros comuns previstos:
- Mandar candidato sem `broadcaster_id`.
- Mandar duracao fora de 5-60.
- Duplicar candidatos iguais em janela curta.

Prevencao:
- Validadores no enqueue.
- Deduplicacao por hash (`source + janela + texto`).

Criterio de saida:
- Cada candidato aprovado vira `clip_job` com estado `queued` (sem chamada API ainda).
- p95 de propagacao candidato -> dashboard <= 10s.

Rollback:
- Desabilitar objetivo de clip no control plane mantendo resto da autonomia.

### Fase 2 - Criacao live via Twitch (`POST /helix/clips`) (2 semanas)

Objetivo: executar clip live via API oficial e fechar ciclo assincrono.

Fluxo obrigatorio:
1. Recebe `clip_job approved`.
2. Chama `POST /helix/clips?broadcaster_id=...&title=...&duration=...`.
3. Espera `202` com `id` e `edit_url`.
4. Poll `GET /helix/clips?id=<id>` ate 15s.
5. Se encontrou clip: status `ready`.
6. Se nao encontrou em 15s: status `failed` com motivo `create_timeout`.

Tratamento de erro por codigo:
- `400`: falha definitiva, sem retry automatico.
- `401`: falha de auth/scope, tentar 1 refresh/validate e parar.
- `403`: falha definitiva (restricao de clips/canal/permissao).
- `404`: canal nao live, falha definitiva para modo live.
- `429`: retry com backoff usando `Ratelimit-Reset`.
- `5xx`: retry com limite curto (ex.: max 3).

Erros comuns previstos:
- Tratar `202` como sucesso final sem polling.
- Salvar so `edit_url` e perder `clip_id`.
- Poll sem timeout e travar worker.

Criterio de saida:
- Job finaliza em `ready` ou `failed` sempre (sem estado zumbi).
- `ready` sempre inclui `twitch_clip_id` + `edit_url`.
- Dashboard mostra motivo legivel de falha.

Rollback:
- `clip_api_enabled=false` e jobs novos voltam para modo sugestao.

### Fase 3 - Dashboard de clips e trilha operacional (1-2 semanas)

Objetivo: operador leigo acompanhar lifecycle completo de clips.

Entregas:
- Nova rota de leitura de jobs de clip em `dashboard_server_routes`.
- Novo modulo `dashboard/features/clips/*`.
- Cards de status:
    - `queued`
    - `creating`
    - `polling`
    - `ready`
    - `failed`
- Acoes:
    - abrir `edit_url`
    - copiar `clip_url`
    - retry manual de job `failed` (com limite)

Erros comuns previstos:
- UI esconder erro tecnico real (dificulta suporte).
- misturar `action_id` com `job_id` e quebrar operacao.

Prevencao:
- Exibir ids separados.
- Exibir erro canonico + detalhe curto.

Criterio de saida:
- Operador resolve 100% dos casos sem olhar logs do servidor.

Rollback:
- manter endpoint backend, desligar apenas render de `clips` na dashboard.

### Fase 4 - Fluxo VOD e download (`/helix/videos/clips` + `/helix/clips/downloads`) (2 semanas)

Objetivo: cobrir momentos perdidos e clipping retroativo.

Entregas:
- Implementar modo `vod` em `twitch_clips_service`.
- Validar antes da chamada:
    - `vod_offset >= duration`
    - `editor_id` presente e consistente com token user quando aplicavel
    - `title` obrigatorio
- Suporte a download URLs via `GET /helix/clips/downloads`.
- Limitar lote de `clip_id` em max 10 por request.

Erros comuns previstos:
- Implementador usar `vod_offset` como inicio (doc define como fim).
- Passar mais de 10 `clip_id` no download.
- Esquecer que `Get Clips Download` tem limite 100 req/min.

Prevencao:
- Helpers de validacao local antes de HTTP.
- batching automatico de `clip_id`.
- throttle por endpoint no cliente Helix.

Criterio de saida:
- Modo VOD gera clip `ready` em casos validos.
- Download URLs retornam e aparecem no dashboard quando disponiveis.

Rollback:
- voltar `clip_mode_default=live`.
- desativar a rota de download mantendo live clipping.

### Fase 5 - Worker desacoplado + persistencia minima (3-4 semanas)

Objetivo: nao bloquear loop de chat/autonomia e sobreviver a restart.

Entregas:
- Worker de clips separado do heartbeat da autonomia.
- Fila interna de jobs com reprocessamento seguro.
- **Persistencia**: Implementar persistencia de jobs compativel com Cloud Run (ex: Firestore, Redis) ou tolerar perda de estado em restart se usar memoria/arquivo efemero.
- Rehidratacao de jobs `queued|creating|polling` no startup.

Erros comuns previstos:
- Fazer HTTP de clips dentro do loop de autonomia.
- perder job em restart por estado somente in-memory/arquivo local no Cloud Run.
- retry infinito em erro permanente.

Prevencao:
- worker dedicado com timeout por etapa.
- politica de retries por classe de erro.
- TTL para job morto.

Criterio de saida:
- restart do processo nao perde jobs ativos (se persistencia externa configurada).
- latencia do chat nao degrada quando clips estao sendo criados.

Rollback:
- desligar worker e voltar para modo `approval-only`.

## 6) Dependencias entre fases

- Fase 0 bloqueia Fase 2 e Fase 4.
- Fase 1 bloqueia Fase 2 (nao ha job confiavel sem candidato).
- Fase 2 bloqueia Fase 3 (nao ha status real para dashboard sem criacao real).
- Fase 5 depende de Fase 2 estavel.
- Fase 4 pode andar em paralelo com Fase 3 apos Fase 2.

## 7) Checklist de erros que o implementador mais vai cometer

- Usar login do canal em vez de `broadcaster_id` numerico.
- Usar token errado para endpoint errado (`clips:edit` vs `editor:manage:clips`/`channel:manage:clips`).
- Nao validar token no startup e de hora em hora.
- Ignorar limite de 15s no polling de `Create Clip`.
- Nao mapear 403 como restricao de canal/permissao.
- Nao tratar `429` com `Ratelimit-Reset`.
- Deixar job sem estado final (`ready|failed`).
- Repetir mesma tentativa em loop para erro definitivo (`400/403/404`).
- Nao separar claramente `edit_url` (edicao) de `clip_url` (consumo publico).
- Nao registrar `attempts`, `error_code`, `error_detail` para suporte.

## 8) Validacao tecnica minima por fase

- Unitarios backend:
    - `python -m unittest bot.tests.test_scientific`
    - `python -m unittest discover -s bot/tests`
- Smoke auth:
    - validar que `/api/observability` exibe status de clips auth e feature flags.
- Smoke API Twitch (ambiente dev):
    - criar 1 clip live em canal de teste e confirmar `Get Clips` em <= 15s.
    - validar falhas esperadas:
        - `broadcaster_id` invalido -> 400
        - token sem scope -> 401
        - canal offline no live create -> 404

## 9) Criterio de pronto global (DoD)

- Pipeline de clip live funcional ponta a ponta em producao.
- Falhas mapeadas para codigos de negocio legiveis.
- Dashboard operacional mostra status e links sem abrir logs.
- Flags permitem desligar clipping sem redeploy.
- Token validation para sessao OAuth conforme requisito Twitch (startup + hourly).

## 10) Referencias oficiais Twitch (usar estas, nao blog/post de terceiros)

- API Reference (Create Clip, Create Clip From VOD, Get Clips, Get Clips Download):
    - `https://dev.twitch.tv/docs/api/reference#create-clip`
    - `https://dev.twitch.tv/docs/api/reference#create-clip-from-vod`
    - `https://dev.twitch.tv/docs/api/reference#get-clips`
    - `https://dev.twitch.tv/docs/api/reference#get-clips-download`
- Scopes:
    - `https://dev.twitch.tv/docs/authentication/scopes/`
- Validating tokens:
    - `https://dev.twitch.tv/docs/authentication/validate-tokens/`
- API rate limits:
    - `https://dev.twitch.tv/docs/api/guide#twitch-rate-limits`

## 11) Relatorio de Progresso (Branch v2)

**Status Geral**: Fases 0, 1 e 2 completas. Fase 3 (Backend) completa.
**Ultima Atualizacao**: 22/02/2026

### Entregas Realizadas
- **Infraestrutura (Fase 0)**:
    - [x] Flags de configuracao implementadas (`clip_pipeline_enabled`).
    - [x] Validacao de escopo `clips:edit` no startup e loop horario.
    - [x] Observabilidade de auth status via `/api/observability`.
- **Logica de Autonomia (Fase 1)**:
    - [x] Novo risco `RISK_CLIP_CANDIDATE`.
    - [x] Geracao de candidatos via LLM (`AutonomyLogic`).
    - [x] Integracao com fila de aprovacao existente.
- **Execucao Live (Fase 2)**:
    - [x] Wrapper `TwitchClipsAPI` robusto (com tratamento de 202/429).
    - [x] `ClipJobsRuntime` implementado (Queued -> Polling -> Ready).
    - [x] Polling assincrono com timeout.
- **Backend Dashboard (Fase 3 - Parcial)**:
    - [x] Rota `GET /api/clip-jobs` exposta.
- **Qualidade & Refatoracao**:
    - [x] Separacao de `AutonomyLogic` e `ObservabilityAnalytics` (arquivos < 300 linhas).
    - [x] Suite de testes cientificos (`bot/tests/scientific/suite_clips.py`) com 100% de aprovacao.

### Proximos Passos Imediatos
1. **Frontend Dashboard (Fase 3 UI)**: Implementar cards de clips e acoes na interface HTML/JS.
2. **Modo VOD (Fase 4)**: Implementar logica retroativa.
3. **Persistencia (Fase 5)**: Salvar estado dos jobs.

## 12) Relatorio de Progresso - Fase 4 (Branch v2)

**Status**: Fase 4 (VOD & Downloads) completa e validada.
**Ultima Atualizacao**: 22/02/2026

### Entregas Realizadas
- **Backend API (Fase 4)**:
    - [x] Implementado `create_clip_from_vod` (POST /helix/videos/clips).
    - [x] Implementado `get_clip_download_url` (GET /helix/clips/downloads) com tratamento de rate limit 429.
- **Runtime (Fase 4)**:
    - [x] Suporte a `mode="vod"` no processamento de jobs.
    - [x] Validacao de parametros VOD (`vod_offset >= duration`).
    - [x] Ciclo de vida estendido: Jobs `ready` buscam `download_url` automaticamente.
- **Frontend Dashboard (Fase 4)**:
    - [x] Botao "Download" exibido condicionalmente nos cards.
- **Qualidade**:
    - [x] Nova suite de testes `bot/tests/scientific/suite_clips_vod.py` cobrindo cenarios de sucesso e falha.
    - [x] Cobertura de rate limits especificos de download.

### Proximos Passos
1. **Persistencia (Fase 5)**: Salvar estado dos jobs para sobreviver a restarts do Cloud Run.

## 13) Relatorio de Progresso - Fase 5 (Branch v2)

**Status**: Fase 5 (Persistencia) completa e validada.
**Ultima Atualizacao**: 22/02/2026

### Entregas Realizadas
- **Infraestrutura**:
    - [x] API Firestore ativada no projeto GCP.
- **Backend Persistencia**:
    - [x] Implementado `FirestoreJobStore` em `bot/clip_jobs_store.py`.
    - [x] Suporte a `load_active_jobs` para reidratacao no startup.
    - [x] Suporte a `save_job` (upsert) para persistencia incremental.
- **Runtime Integration**:
    - [x] `ClipJobsRuntime` agora carrega estado do Firestore na inicializacao.
    - [x] Novos jobs sao salvos imediatamente.
    - [x] Atualizacoes de estado (`polling`, `ready`, `failed`) sao persistidas.
- **Resiliencia**:
    - [x] Sistema sobrevive a restarts do container sem perder jobs em andamento.
    - [x] Fallback gracioso (no-op) se PROJECT_ID nao estiver definido (dev local sem GCP).

### Proximos Passos
- **Validacao Final**: Teste E2E completo em ambiente de staging.
- **Merge**: Criar PR para `main` e planejar rollout.

### Fase 6 - Byte Vision & Visual Triggering (Bonus)

Objetivo: Dar "olhos" ao agente para reagir ao jogo e detectar clips visualmente, nao so por chat.

**Arquitetura Dual-Source**:
1. **OBS Source (Alta fidelidade)**: Script local envia screenshots via HTTP.
2. **Viewer Source (Cloud)**: Worker captura frames do stream Twitch publico (com delay natural).

**Fluxo de Dados**:
Input (Frame) -> Vision Runtime -> Gemini 1.5 Flash -> Context Update -> Autonomy Trigger.

**Entregas**:
- Rota `POST /api/vision/ingest` para receber frames.
- `VisionRuntime` para chamar Gemini Multimodal.
- Integracao com `SceneContext` (atualizar estado do jogo automaticamente).
- **Visual Clip Trigger**: Se Gemini detectar "Victory", "Death", "Pentakill" -> Gerar `clip_candidate`.

**Riscos**:
- Custo de inferencia de imagem (controlar sampling rate).
- Latencia do modo Viewer (reagir ao passado).
