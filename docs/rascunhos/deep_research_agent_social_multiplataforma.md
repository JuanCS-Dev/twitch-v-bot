# Deep Research: Agent Social Multiplataforma Autonomo (Reddit, X, Facebook, Instagram)

Data: 2026-02-21
Status: rascunho para implementacao

## 1) Objetivo e resultado esperado

Construir um novo agent social que:
- opere em Reddit, X, Facebook e Instagram;
- tenha comportamento autonomo (agenda + vies + objetivos programados);
- nao seja apenas reativo a comandos/triggers;
- mantenha compliance de plataforma e controle de risco reputacional.

Resultado esperado deste estudo:
- mapa realista do que cada API permite;
- arquitetura de referencia para autonomia;
- plano de execucao sem ambiguidades para o executor;
- checklist para evitar debito tecnico desde o primeiro commit.

## 2) TL;DR executivo

- E viavel criar um agent autonomo multiplataforma, mas com assimetria forte entre plataformas.
- X e Meta (Facebook/Instagram) sao os mais fortes para near-real-time (stream/webhooks).
- Reddit permite operacao robusta, mas tende a modelo polling/listing (sem webhook oficial equivalente nos docs analisados).
- O maior risco nao e tecnico; e de compliance (spam, automacao abusiva, uso fora de janela de mensagem).
- A arquitetura correta e "policy-first": planejamento autonomo + gates de seguranca + conectores idempotentes por plataforma.

## 3) Evidencias consolidadas por plataforma

## 3.1 Reddit

Capacidades observadas:
- OAuth2 com `authorize` e `access_token`.
- Chamadas autenticadas com bearer em `https://oauth.reddit.com`.
- Escopos granulares (`read`, `submit`, `edit`, `privatemessages`, `mod*`, etc.).
- Endpoints para publicar/comentar/editar/votar/PM/moderar (`/api/submit`, `/api/comment`, `/api/editusertext`, `/api/vote`, `/api/compose`, etc.).
- Limite documentado em wiki legacy: clientes OAuth ate ~60 req/min, com headers de rate limit.

Pontos de implementacao:
- Access token expira em ~1 hora.
- Para refresh token, usar `duration=permanent` no authorize flow.
- User-Agent precisa ser unico e descritivo (recomendacao explicita da documentacao).

Autonomia pratica no Reddit:
- Boa para agenda de publicacao, resposta contextual e moderacao por regras.
- Como nao ha webhook oficial equivalente no material analisado, tratar ingestao como polling inteligente com budget de rate limit.

## 3.2 X (API)

Capacidades observadas:
- OAuth 2.0 Authorization Code + PKCE.
- Endpoint de token: `POST https://api.x.com/2/oauth2/token`.
- Escopos relevantes: `tweet.read`, `tweet.write`, `users.read`, `dm.read`, `dm.write`, `media.write`, `offline.access`.
- Publicacao: `POST /2/tweets` (texto, reply, quote, poll, media).
- Upload de midia chunked: `INIT`, `APPEND`, `FINALIZE`, `STATUS` em `POST /2/media/upload`.
- DM por endpoint dedicado (`/2/dm_conversations/with/{participant_id}/messages`).
- Ingestao near-real-time por filtered stream com conexao persistente; opcao de webhook para entrega.
- Headers de rate limit endpoint-specific: `x-rate-limit-limit`, `x-rate-limit-remaining`, `x-rate-limit-reset`.
- Endpoint OpenAPI disponivel (`/2/openapi.json`).

Pontos de implementacao:
- Access token padrao ~2h; refresh token exige `offline.access`.
- Pricing atual capturado: pay-per-usage com monitoramento de uso e cap mensal indicado na doc capturada.

Autonomia pratica no X:
- Excelente para loop autonomo orientado por eventos (stream/webhook + resposta programada + agenda).
- Requer disciplina forte de rate budget por endpoint e controle de custo por leitura.

## 3.3 Facebook (Pages + Messenger via Graph API)

Capacidades observadas:
- Graph API em versao recente capturada como `v25.0`.
- Publicacao em pagina: `POST /{page_id}/feed`, fotos/videos por endpoints de Page.
- Permissoes de Page citadas nas docs: `pages_manage_posts`, `pages_manage_metadata`, `pages_show_list` e leitura de engajamento (docs variam entre `pages_read_engagement` e `pages_manage_read_engagement`).
- Descoberta de pages/tokens por `/user_id/accounts`.
- Webhooks oficiais com fluxo de verificacao (`hub.challenge`, `hub.verify_token`) e assinatura `X-Hub-Signature-256`.
- Messenger/Instagram messaging: envio por endpoints de messages com `recipient` e `messaging_type`, com restricoes de janela/tag para envio fora da janela padrao.
- Rate/usage headers: `X-App-Usage` e `X-Ad-Account-Usage` com campos `call_count`, `total_time`, `total_cputime`.

Pontos de implementacao:
- Nao confiar em historico de webhook: docs explicitam capturar e persistir payload recebido.
- Validar assinatura de webhook obrigatoriamente.

Autonomia pratica no Facebook:
- Muito forte para automacao orientada por eventos de Page e mensagens.
- Exige camada de policy para evitar envios fora de regra de janela/tag.

## 3.4 Instagram (Graph/Instagram Platform)

Capacidades observadas:
- Publicacao para contas profissionais conectadas a Page.
- Fluxo de publicacao: `/{IG_ID}/media` -> `/{IG_ID}/media_publish`.
- Controle de cota: `/{IG_ID}/content_publishing_limit`.
- Upload resumable em `rupload.facebook.com` (especialmente video/reels).
- Limite documentado: 100 posts publicados por API em janela movel de 24h (carrossel conta como 1).
- Webhooks para comentarios, mentions, messages, live_comments (com requisitos de access/permissions).
- Moderacao de comentarios: hide/unhide, delete, disable/enable comments.
- Private replies com janela temporal especifica (doc indica 7 dias para contexto citado).

Pontos de implementacao:
- Conteudo de midia precisa estar acessivel publicamente no momento da ingestao pela API (quando aplicavel no endpoint).
- Tratar limites de publicacao como primeira classe no scheduler autonomo.

Autonomia pratica no Instagram:
- Boa para agenda de conteudo + moderacao + mensagens controladas por policy.
- Publicacao autonoma precisa ser "quota-aware" para nao estourar limite diario.

## 4) Matriz de capacidade (comparativo direto)

| Capacidade | Reddit | X | Facebook | Instagram |
|---|---|---|---|---|
| Publicar conteudo | Sim | Sim | Sim | Sim (conta profissional) |
| Responder/comentar | Sim | Sim | Sim | Sim |
| DM/Mensagem privada | Sim (PM) | Sim | Sim (Messenger) | Sim (messaging/private replies) |
| Midia rica | Parcial | Forte (upload chunked) | Forte | Forte (inclui resumable) |
| Ingestao em tempo real | Limitada (polling) | Forte (stream/webhook) | Forte (webhooks) | Forte (webhooks) |
| Moderacao | Forte (mod scopes) | Parcial (depende endpoint/scopes) | Forte | Forte |
| Insights/analytics | Parcial | Parcial/Forte (depende plano) | Forte | Forte |
| Risco de custo por leitura | Medio | Alto (pay-per-usage) | Medio | Medio |
| Complexidade de compliance | Media | Alta | Alta | Alta |

## 5) O que significa "autonomo" na pratica (sem virar bot reativo)

Modelo recomendado:
- Loop orientado a objetivos, nao a comandos.
- Agenda ativa (cron + janelas por plataforma + horario por audiencia).
- Motor de decisao com memoria de contexto e vies editorial configuravel.
- Execucao condicionada por policy e rate budget.
- Feedback loop com metricas de impacto para ajustar o plano automaticamente.

Ciclo autonomo padrao:
1. Sense: ler eventos (webhooks/stream/polling) + estado de conta + cotas.
2. Understand: classificar contexto (pergunta, critica, oportunidade, risco).
3. Decide: escolher acao com policy gate (permitir, bloquear, escalar humano).
4. Act: executar via conector com idempotencia.
5. Reflect: medir resultado e ajustar agenda/prompt/pesos.

## 6) Arquitetura de referencia (multi-plataforma)

Componentes minimos:
- `Autonomy Planner`: gera plano diario/semanal por objetivo.
- `Policy Engine`: valida compliance, risco e regras de marca.
- `Platform Connectors`: Reddit/X/Meta com contrato unico.
- `Event Ingestion`: webhook receiver + stream consumers + pollers.
- `Scheduler`: fila com prioridade, janelas e controle de quota.
- `Memory`: curto prazo (estado operacional) + longo prazo (aprendizados).
- `Observability`: logs estruturados, metricas, tracing e auditoria por acao.
- `Human Escalation`: inbox de revisao para casos ambigous/high-risk.

Contrato comum do conector (anti-acoplamento):
- `publish(content, target, options) -> action_result`
- `reply(thread_ref, content, options) -> action_result`
- `moderate(object_ref, action, reason) -> action_result`
- `sync_state(scope) -> platform_state`
- `get_limits() -> rate_budget_state`
- `ack_event(event_id) -> void`

Campos obrigatorios de `action_result`:
- `ok`
- `platform`
- `action_type`
- `external_id`
- `idempotency_key`
- `rate_cost`
- `policy_decision_id`
- `timestamp`
- `error` (quando aplicavel)

## 7) Seguranca, compliance e governanca

Guardrails obrigatorios:
- Nao publicar fora de permissao/escopo/token valido.
- Nao enviar mensagens fora da janela/tag permitida pela plataforma.
- Nao executar acoes repetidas (idempotencia por `idempotency_key`).
- Nao ultrapassar orcamento de rate/custo diario por plataforma.
- Nao permitir acao sensivel sem `policy_decision_id` auditavel.

Regras de risco:
- `low`: executa autonomamente.
- `medium`: executa com template seguro + monitoramento.
- `high`: bloqueia e envia para revisao humana.

Persistencia auditavel:
- guardar payload de webhook recebido (Meta/X), decisao de policy e resposta da API.
- manter trilha "input -> decisao -> output" para debugging e compliance.

## 8) Plano de implementacao por fases (executor-ready)

Fase 0 - Fundacao (1 semana)
- Definir contrato comum dos conectores e `action_result`.
- Implementar `Policy Engine` minimo com regras bloqueadoras.
- Implementar cofre de segredos + rotacao de tokens + refresh workers.
- Entregar observabilidade base (logs estruturados + metricas por plataforma).

Criterio de aceite:
- sem acao em producao sem `policy_decision_id`;
- sem secrets hardcoded;
- connector testado com mocks de erro, rate limit e token expirado.

Fase 1 - Reddit + X MVP (1-2 semanas)
- Reddit connector (publish/comment/pm/listing + polling scheduler).
- X connector (publish/reply/media + stream consumer opcional inicial).
- Scheduler com quota budget e janelas por plataforma.
- Persistir eventos e resultados em storage unico.

Criterio de aceite:
- cada acao com idempotencia;
- retries com exponential backoff + jitter;
- dashboard operacional mostrando rate budget e fila pendente.

Fase 2 - Facebook + Instagram MVP (1-2 semanas)
- Webhook receiver assinado (`X-Hub-Signature-256`) + verificacao inicial.
- Facebook Page posting + Messenger send.
- Instagram publishing (`media`/`media_publish`) + quota de 100/24h + moderacao de comentarios.
- Regras de janela/tag para mensagens fora da janela padrao.

Criterio de aceite:
- nenhum webhook perdido sem log de erro;
- fila de replay para eventos falhos;
- bloqueio automatico quando limite diario de IG aproximar do teto configurado.

Fase 3 - Autonomia avancada (2+ semanas)
- Planner orientado a objetivo (campanhas, temas, sazonalidade).
- Loop de aprendizado por performance (engagement, resposta, conversao).
- Human-in-the-loop para topicos sensiveis.
- Simulacao/offline replay para testar novas politicas antes de producao.

Criterio de aceite:
- meta de SLO operacional atingida;
- regressao < limite definido em testes de replay;
- custo mensal dentro do budget por plataforma.

## 9) Checklist anti-debito tecnico (obrigatorio para executor)

Arquitetura e codigo:
- Nao acoplar regras de negocio dentro dos conectores HTTP.
- Nao criar if/else por plataforma no core; usar strategy/adapters.
- Nao misturar payload nativo no dominio interno sem mapeamento tipado.

Confiabilidade:
- Implementar idempotencia em toda acao mutavel.
- Implementar retries apenas para erros transientes.
- Implementar dead-letter queue para eventos falhos.
- Implementar clock-safe scheduling (timezone + DST).

Qualidade:
- Contract tests por conector (request/response/erro/rate/token).
- Testes de policy engine com casos proibidos e permitidos.
- Testes de carga focados no webhook receiver e fila.

Operacao:
- Telemetria por acao: latencia, erro, custo, consumo de quota.
- Alertas para token perto de expirar, fila acumulada e erro 4xx/5xx acima do baseline.
- Feature flags para ativar/desativar automacoes por plataforma.

Governanca:
- Versionar politicas de autonomia (policy-as-code).
- Registrar quem alterou vies/agenda/regras e quando.
- Ter kill-switch global e kill-switch por plataforma.

## 10) Riscos principais e mitigacoes

Risco: bloqueio/suspensao por comportamento interpretado como spam.
Mitigacao: throttling forte, diversidade de conteudo, limites por topico/tempo, human review em risco medio/alto.

Risco: divergencia entre docs e comportamento real da API.
Mitigacao: smoke tests diarios por endpoint critico + canary account por plataforma.

Risco: custo inesperado (especialmente leitura/eventos no X).
Mitigacao: budget guard diario/mensal + desligamento automatico de features custosas.

Risco: perda de eventos webhook.
Mitigacao: ack rapido + persistencia imediata + replay queue + monitoramento de lag.

## 11) Decisoes de produto recomendadas agora

1. Comecar com um "autonomy profile" conservador por plataforma (baixo risco).
2. Definir 3 objetivos mensuraveis iniciais (ex.: resposta util, frequencia saudavel, cobertura de comunidade).
3. Ligar publicacao 100% autonoma apenas apos 2 semanas de shadow mode.
4. Reservar via policy uma classe de topicos que sempre exige aprovacao humana.

## 12) Fontes oficiais consultadas (captura deste estudo)

Reddit:
- OAuth2 wiki: `https://github.com/reddit-archive/reddit/wiki/oauth2`
- API wiki: `https://github.com/reddit-archive/reddit/wiki/api`
- API reference/scopes (live): `https://www.reddit.com/dev/api/` e `/api/v1/scopes`

X:
- Auth OAuth2/PKCE docs em `docs.x.com`
- Rate limits docs em `docs.x.com`
- Posts create: `POST /2/tweets`
- Media upload chunked: `POST /2/media/upload`
- DM endpoint: `/2/dm_conversations/with/{participant_id}/messages`
- Filtered stream e Activity APIs em `docs.x.com`
- OpenAPI spec: `/2/openapi.json`

Meta (Facebook/Instagram):
- Graph API overview
- Facebook Pages API (getting started + posts)
- Graph Webhooks (overview + getting started)
- Messenger send messages docs
- Meta rate limiting docs
- Instagram content publishing/webhooks/comment moderation/private replies/insights docs

---

Nota final:
- Este documento separa capacidades confirmadas por documentacao de decisoes arquiteturais recomendadas.
- Antes de go-live, validar novamente versoes de API e termos de uso, porque limites/escopos podem mudar.

## 13) Fatos confirmados vs pontos para PoC

Fatos confirmados nas fontes consultadas:
- endpoints de auth, publicacao e mensageria listados neste documento;
- existencia de escopos granulares por plataforma;
- existencia de mecanismos de rate/usage headers;
- existencia de webhooks/stream para X e Meta;
- limite de publicacao de IG de 100 posts/24h na documentacao capturada.

Pontos que exigem PoC antes de producao:
- latencia e estabilidade real de stream/webhook em carga do seu caso de uso;
- quotas efetivas no plano contratado (especialmente X pay-per-usage);
- permissoes aprovadas no app review da Meta para todos os campos necessarios;
- regras de entrega de mensagens fora da janela padrao em casos especificos do produto;
- comportamento de moderacao automatica em comunidades com regras locais restritivas.
