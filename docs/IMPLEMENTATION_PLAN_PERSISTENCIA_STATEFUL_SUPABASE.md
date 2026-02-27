# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.22
**Data:** 27 de Fevereiro de 2026
**Status:** FASES 1-7 CONCLUÍDAS ✅ (INCLUINDO HISTÓRICO PERSISTIDO + COMPARAÇÃO MULTI-CANAL NA DASHBOARD OPERACIONAL) | FASE 8 PLANEJADA | FASE 9 CONCLUÍDA ✅ (GATE FORMAL BACKEND -> DASHBOARD + CHECKLIST DE RELEASE ATIVO NA CI) | FASE 10 CONCLUÍDA ✅ (10.1-10.4) | FASE 11 CONCLUÍDA ✅ (STREAM HEALTH SCORE MULTI-CANAL + INTEGRAÇÃO VISUAL NO LAYOUT ATUAL) | FASE 12 NO TOPO DO BACKLOG
**Objetivo:** consolidar o Byte Bot como runtime stateful, com persistência operacional real, dashboard utilizável e controles de soberania por canal.

---

## 1. Estado Validado da Arquitetura

1. **RAM / Runtime local:** continua sendo a camada quente para loop, fila de ações, HUD e snapshots de observabilidade.
2. **Supabase / Postgres:** já é usado como fonte persistente para `channel_state`, `channel_history`, `channels_config` e jobs de clips.
3. **Dashboard -> API -> Runtime:** o fluxo command-driven já existe via `/api/control-plane`, `/api/channel-control`, `/api/action-queue`, `/api/autonomy/tick`, `/api/hud/messages`.

### Achados relevantes da validação

- `resolve_irc_channel_logins()` já lê canais ativos do Supabase antes do fallback de ENV.
- O HUD standalone já existe em `/dashboard/hud`; nesta validação ele foi exposto na dashboard principal e ajustado para funcionar com admin token.
- `POST /api/autonomy/tick` já implementa o "manual tick".
- Os gatilhos dinâmicos de sentimento já estão ativos no loop de autonomia.
- O pipeline de clips com persistência de jobs já existe e precisa ser tratado como capacidade implementada, não futura.

---

## 2. Status por Fase

### Fases 1-3: Persistência Base e Lazy Restore ✅

- Persistência de histórico e estado por canal implementada em `persistence_layer.py`.
- Lazy restore de contexto já suportado pelo runtime.
- Telemetria básica já consegue gravar eventos/mensagens/respostas quando Supabase está ativo.

### Fase 4: Canais Dinâmicos e Boot Sequence ✅

- Implementada em `bootstrap_runtime.py` + `persistence_layer.py`.
- `channels_config` já alimenta o boot sequence no modo IRC.
- Fallback para `TWITCH_CHANNEL_LOGINS` e `TWITCH_CHANNEL_LOGIN` continua preservado.

### Fase 5: Observabilidade Stateful (Métricas Operacionais) ✅ Concluída

**Já existe**

- Snapshot operacional robusto via `/api/observability`.
- Registro de mensagens, replies e eventos em persistência.
- Runtime de observabilidade consolidado para health, outcomes e fila.
- Rollup global persistente em `observability_rollups` com save throttled e restore automático no bootstrap do `ObservabilityState`.
- Reidratação pós-restart de counters, routes, timeline, recent events, janelas analíticas, leaderboards e status de clips a partir do rollup persistido.
- Snapshot agora expõe metadados de persistência (`enabled/restored/source/updated_at`) e a dashboard mostra o estado do rollup no topo sem criar layout paralelo.
- Snapshot passou a suportar escopo real por canal com `channel_scopes` (schema v2), mantendo compatibilidade de restore com estado legado.

### Fase 6: Dashboard Integrada (Multi-Channel UI) ✅ Concluída

**Já existe**

- Dashboard modular com control plane, fila de risco, clips, observabilidade e HUD.
- Channel manager operacional para `list`, `join`, `part`.
- HUD embutida no painel principal e overlay standalone em `/dashboard/hud`.
- Exposição explícita do overlay OBS na UI principal concluída nesta validação.
- Dashboard agora mantém um `focused channel` persistido em `localStorage` e usa esse canal como contexto primário.
- `/api/observability` passou a aceitar `?channel=` para renderizar o `StreamContext` do canal selecionado.
- `/api/observability?channel=` agora consulta snapshot per-channel real (counters/leaderboards/routes/timeline segregados por canal).
- Novo `GET /api/channel-context` expõe `runtime context + channel_state + channel_history` para inspeção operacional.
- Painel `Agent Context & Internals` agora mostra snapshot persistido e histórico recente por canal sem inventar uma UI paralela.
- Novo `GET /api/observability/history` com timeline persistida por canal selecionado e comparação dos snapshots mais recentes por canal.
- Persistência dedicada de histórico em `observability_channel_history`, com fallback em memória quando Supabase indisponível.
- Painel `Agent Context & Internals` foi estendido com:
  - tabela `Persisted Channel Timeline` (histórico do canal focado);
  - tabela `Multi-Channel Comparison (Persisted)` (comparativo lado a lado).

**Discovery de layout aplicado nesta entrega**

- Estudo da dashboard atual executado antes da implementação para mapear encaixe visual no painel já existente.
- A integração ficou no fluxo e hierarquia atuais de observabilidade/contexto, sem criação de tela paralela ou padrão genérico.

### Fase 7: Soberania e Comando ✅ Concluída

**Já existe**

- Control plane com config runtime, budgets, action queue e capabilities.
- `POST /api/autonomy/tick` para disparo manual do loop.
- `POST /api/agent/suspend` e `POST /api/agent/resume` implementados com estado explícito no runtime.
- Bloqueio operacional de auto-chat e agenda automática quando o agente está suspenso.
- Dashboard expõe o `panic suspend` / `resume agent` no mesmo padrão visual do control plane atual.
- HUD streamer como trilha paralela de resposta tática.
- Override por canal de `temperature` e `top_p` persistido em `channels_config`.
- Inferência aplica override por canal restaurado do estado persistido.
- Dashboard expõe directives operacionais por canal no painel operacional existente.
- Pause/silence por canal persistido em `channels_config.agent_paused`, aplicado no runtime e respeitado no prompt handler + autonomia.
- Persistência de notas operacionais em `agent_notes` com restore no `StreamContext`.
- `agent_notes` agora é injetado de forma segura no system prompt antes da inferência.
- Dashboard expõe leitura/escrita de `agent_notes` e o painel de contexto mostra o snapshot persistido dessas notas.

### Fase 8: Gestão de Memória Semântica (Vector Memory) ❌ Não implementada

- Não há integração `pgvector` no código atual.
- Não existe interface de dashboard para inspeção/edição de memória semântica.
- Deve permanecer como fase futura, separada do escopo operacional imediato.

### Fase 9: Paridade Backend -> Dashboard (Contrato de Integração Visual) ✅ Concluída

**Objetivo da fase**

- Garantir que toda capacidade operacional implementada no backend tenha previsão e trilha explícita de integração visual na dashboard.
- Evitar backlog invisível de features backend sem superfície de operação para streamer/admin.
- Preservar o layout, hierarquia visual, padrões de interação e linguagem de componentes já existentes na dashboard operacional (sem UI genérica/paralela).

**Etapa obrigatória de discovery (antes de implementar UI nova)**

- Estudar a dashboard atual (`/dashboard`) e mapear: estrutura de painéis, componentes reutilizáveis, padrões de estado/seleção de canal e contratos visuais já consolidados.
- Registrar no plano, para cada capability nova, onde ela entra no layout atual (painel existente, card existente ou extensão incremental) antes de codar.

**Definição de pronto (DoD da paridade)**

- Toda entrega backend que altera operação (`/api/*`, state runtime, governança por canal, observabilidade, autonomia) deve mapear pelo menos um ponto de visualização/controle na dashboard.
- Se não houver UI no mesmo ciclo, o item só pode ser aceito com justificativa explícita de endpoint interno e plano de exposição visual com prioridade definida.
- O plano deve ser atualizado na mesma PR com a linha de paridade (backend -> painel UI -> teste).
- Toda UI nova deve ser extensão do layout atual (componentes/painéis existentes), sem criar "dashboard paralela" nem padrão visual genérico desconectado.

**Entregáveis da fase**

- Matriz de paridade backend/dashboard por domínio: Observability, Control Plane, Channel Governance, Clips, Prompt/Inference Runtime.
- Gate de revisão: mudança backend operacional exige teste de rota/API e teste da dashboard correspondente.
- Checklist de release para impedir merge de capacidade operacional "headless" sem decisão explícita.
- Checklist de consistência visual: aderência ao layout atual, reaproveitamento de componentes e ausência de blocos genéricos fora do padrão do projeto.

**Critérios de aceite**

- 100% dos endpoints operacionais críticos mapeados para painel existente ou card planejado com prioridade.
- Testes de backend e dashboard verdes para os fluxos alterados no ciclo.
- Documento de implementação atualizado com o status de paridade por capability.
- Evidência de discovery do layout atual anexada ao ciclo (mapa de encaixe visual por capability).

**Fechamento da Fase 9 (ciclo atual)**

- Gate formal executável implementado em `bot/dashboard_parity_gate.py` com validação automática de:
  - inventário de rotas operacionais (`GET/PUT/POST`) via parsing dos dispatch tables reais;
  - matriz de paridade por capability/domínio com decisão obrigatória por endpoint (`integrated` ou `headless_approved`);
  - presença de evidência de testes backend e dashboard por endpoint integrado.
- Dashboard test de contrato de API criado em `dashboard/tests/api_contract_parity.test.js`, cobrindo os fluxos operacionais reais:
  - control plane/config/notes/suspend/resume;
  - channel control, action queue (incluindo `decision`), autonomy tick;
  - clips, HUD, observability, channel context e history.
- CI atualizada em `.github/workflows/ci.yml`:
  - execução de testes da dashboard (`node --test ...`);
  - execução do gate formal de paridade (`python -m bot.dashboard_parity_gate`) no job de lint.
- Exceções headless agora são explícitas e versionadas no gate:
  - `/api/vision/status` e `/api/vision/ingest` com exposição planejada na **Fase 19** (Clip Suggestion Intelligence).
- `/api/sentiment/scores` saiu do status headless e foi integrado ao layout atual na Fase 11 (`metrics_health`, `intelligence_panel`, `agent_context_internals`), com cobertura de testes backend + dashboard.
- Preservação de layout: o contrato mantém o encaixe das capacidades no layout existente (`control_plane`, `risk_queue`, `agent context`, `clips`, `hud`) sem dashboard paralela.

### Fase 10: Saneamento Estrutural (Anti-Espaguete + Anti-Duplicação) ✅ Concluída

**Diagnóstico atual (evidência objetiva)**

- `ruff check bot --select C901` apontou funções com complexidade acima do orçamento, incluindo:
  - `bot/dashboard_server_routes.py:292` (`handle_get`, complexidade 20);
  - `bot/control_plane_config.py:66` (`update_config`, complexidade 17);
  - `bot/irc_management.py:42` (`_handle_channel_management_prompt`, complexidade 17);
  - `bot/byte_semantics_quality.py:170` (`is_low_quality_answer`, complexidade 16).
- `pylint --enable=R0801` apontou duplicação relevante:
  - serialização de histórico de observabilidade duplicada entre
    `bot/dashboard_server_routes.py:118` e `bot/persistence_layer.py:434`;
  - padrão repetido de autorização + leitura de payload + erro `invalid_request`
    entre `bot/dashboard_server_routes.py` e `bot/dashboard_server_routes_post.py`;
  - montagem repetida do payload de control plane entre rotas GET e POST.

**Fases de correção propostas**

1. **Fase 10.1 - Normalização de contratos de payload** ✅ Concluída
   - Contrato compartilhado extraído para `bot/observability_history_contract.py`.
   - Duplicação de shape JSON removida entre camada de persistência e camada HTTP para histórico de observabilidade.
2. **Fase 10.2 - Refactor do roteamento HTTP** ✅ Concluída
   - Introduzir helpers comuns para guardas (`auth required`), parse de payload e respostas de erro padrão.
   - Reorganizar `handle_get` para dispatch table por rota (reduzir branching encadeado).
3. **Fase 10.3 - Fatiamento da camada de persistência** ✅ Concluída
   - Separar responsabilidades em sub-repositórios (`channel_config`, `agent_notes`, `observability`), mantendo `PersistenceLayer` como facade.
   - Reduzir acoplamento e tamanho de arquivo em `bot/persistence_layer.py`.
4. **Fase 10.4 - Gate automatizado de saúde estrutural** ✅ Concluída
   - Adicionar checagem de complexidade e duplicação no pipeline (alvos mínimos para `ruff C901` e `pylint R0801` nos módulos críticos).
   - Bloquear merge de nova capacidade operacional que reintroduza duplicações já removidas.

**Critérios de aceite da fase**

- `bot/dashboard_server_routes.py:292` deixa de ser hotspot de complexidade (quebra por handlers menores).
- Duplicação entre `bot/dashboard_server_routes.py:118` e `bot/persistence_layer.py:434` removida por contrato único.
- Fluxos de erro/autorização deixam de repetir blocos idênticos entre GET/PUT/POST.
- Testes de backend/dashboard mantêm cobertura dos fluxos refatorados sem regressão comportamental.

**Fechamento da Fase 10.1 (ciclo atual)**

- `bot/dashboard_server_routes.py` e `bot/persistence_layer.py` agora usam o mesmo contrato de normalização de histórico (`normalize_observability_history_point`).
- Testes novos adicionados para o contrato compartilhado em `bot/tests/test_observability_history_contract.py`.
- Testes de integração funcional da etapa reforçados em:
  - `bot/tests/test_persistence_layer.py` (fallback via `timestamp` no fluxo real de persistência);
  - `bot/tests/test_dashboard_routes_v3.py` (serialização HTTP preservada sem fallback implícito de `timestamp`).
- Validação executada: `pytest -q --no-cov bot/tests/test_observability_history_contract.py bot/tests/test_persistence_layer.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py` (`92 passed`).

**Fechamento da Fase 10.2 (ciclo atual)**

- Helpers HTTP compartilhados extraídos para `bot/dashboard_http_helpers.py`:
  - parse de rota/query (`parse_dashboard_request_path`);
  - guarda de autorização (`require_dashboard_auth`);
  - leitura/validação de payload JSON (`read_json_payload_or_error`, `require_auth_and_read_payload`);
  - resposta padrão `invalid_request` (`send_invalid_request`);
  - payload único de control plane (`build_control_plane_state_payload`).
- `bot/dashboard_server_routes.py` foi reorganizado para dispatch table em GET/PUT (`_GET_ROUTE_HANDLERS`, `_PUT_ROUTE_HANDLERS`) com handlers menores por rota.
- `bot/dashboard_server_routes_post.py` foi reorganizado para dispatch table em POST (`_POST_ROUTE_HANDLERS`) e removeu repetição de blocos de auth/payload/erro.
- Testes novos da etapa em `bot/tests/test_dashboard_http_helpers.py` cobrindo parsing, auth, payload JSON, fluxo combinado auth+payload e payload de control plane.
- Validação executada:
  - `pytest -q --no-cov bot/tests/test_dashboard_http_helpers.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py` (`67 passed`);
  - `ruff check bot/dashboard_http_helpers.py bot/dashboard_server_routes.py bot/dashboard_server_routes_post.py bot/tests/test_dashboard_http_helpers.py` (verde);
  - `ruff format --check bot/dashboard_http_helpers.py bot/dashboard_server_routes.py bot/dashboard_server_routes_post.py bot/tests/test_dashboard_http_helpers.py` (verde);
  - `PYLINTHOME=/tmp/pylint-cache pylint --disable=all --enable=R0801 bot/dashboard_server_routes.py bot/dashboard_server_routes_post.py` (verde).

**Fechamento da Fase 10.3 (ciclo atual)**

- Camada de persistência fatiada em módulos dedicados:
  - `bot/persistence_channel_config_repository.py`;
  - `bot/persistence_agent_notes_repository.py`;
  - `bot/persistence_observability_history_repository.py`;
  - `bot/persistence_cached_channel_repository.py` (base comum para reduzir duplicação);
  - `bot/persistence_utils.py` (normalização/validação compartilhada).
- `bot/persistence_layer.py` passou a atuar como facade enxuta, delegando para repositórios especializados sem alterar o contrato público (`load_*`, `save_*` síncrono/assíncrono).
- Novos testes da etapa em `bot/tests/test_persistence_repositories.py` cobrindo roundtrip de memória, sanitização de notas, timeline/comparativo e consistência de cache entre facade e repositórios.
- Validação executada:
  - `pytest -q --no-cov bot/tests/test_persistence_repositories.py bot/tests/test_persistence_layer.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py` (`93 passed`);
  - `ruff check bot/persistence_cached_channel_repository.py bot/persistence_channel_config_repository.py bot/persistence_agent_notes_repository.py bot/persistence_observability_history_repository.py bot/persistence_layer.py bot/tests/test_persistence_repositories.py` (verde);
  - `ruff format --check bot/persistence_cached_channel_repository.py bot/persistence_channel_config_repository.py bot/persistence_agent_notes_repository.py bot/persistence_observability_history_repository.py bot/persistence_layer.py bot/tests/test_persistence_repositories.py` (verde);
  - `PYLINTHOME=/tmp/pylint-cache pylint --disable=all --enable=R0801 bot/persistence_layer.py bot/persistence_channel_config_repository.py bot/persistence_agent_notes_repository.py bot/persistence_observability_history_repository.py bot/persistence_cached_channel_repository.py` (verde).

**Fechamento da Fase 10.4 (ciclo atual)**

- Gate estrutural centralizado em `bot/structural_health_gate.py`, com steps versionados:
  - `ruff C901` nos módulos críticos com orçamento explícito (`lint.mccabe.max-complexity=17`);
  - `pylint R0801` nos módulos críticos de roteamento/persistência.
- Pipeline CI atualizado em `.github/workflows/ci.yml`:
  - instalação de `pylint` no job `lint`;
  - etapa `Structural Health Gate (C901 + R0801)` executando `python -m bot.structural_health_gate`.
- Testes novos da etapa em `bot/tests/test_structural_health_gate.py` cobrindo:
  - construção correta dos comandos/targets do gate;
  - execução completa em cenário de sucesso;
  - fail-fast no primeiro erro;
  - propagação de `env` (`PYLINTHOME`) e `cwd` no runner real.
- Validação executada:
  - `pytest -q --no-cov bot/tests/test_structural_health_gate.py` (`4 passed`);
  - `python -m bot.structural_health_gate` (verde);
  - `pytest -q --no-cov bot/tests/test_dashboard_http_helpers.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py bot/tests/test_persistence_repositories.py` (`71 passed`);
  - `ruff check bot/structural_health_gate.py bot/tests/test_structural_health_gate.py` (verde);
  - `ruff format --check bot/structural_health_gate.py bot/tests/test_structural_health_gate.py` (verde).

### Fase 11: Stream Health Score Multi-Canal ✅ Concluída

**Objetivo da fase**

- Sintetizar o estado operacional por canal em um score único (0-100) versionado, sem perder explicabilidade dos componentes.
- Integrar o score no layout atual da dashboard, sem criar tela paralela nem bloco visual genérico.

**Fechamento da Fase 11 (ciclo atual)**

- Backend:
  - novo módulo `bot/stream_health_score.py` com cálculo determinístico (`version`, `score`, `band`, componentes ponderados);
  - snapshot de observabilidade passou a incluir `stream_health` por canal em `bot/observability_snapshot.py`;
  - endpoint `GET /api/sentiment/scores?channel=` passou a refletir snapshot real por canal via `build_sentiment_scores_payload` em `bot/dashboard_server_routes.py`;
  - contrato persistido do histórico estendido para `sentiment` e `stream_health` em `bot/observability_history_contract.py`.
- Dashboard (layout atual preservado):
  - `dashboard/features/observability/api.js` ganhou `getSentimentScoresSnapshot`;
  - `dashboard/features/observability/controller.js` passou a buscar o endpoint de score no ciclo padrão de observabilidade;
  - `dashboard/features/observability/view.js` renderiza score/band em cards já existentes e nas tabelas históricas persistidas;
  - parciais atualizados sem UI paralela: `dashboard/partials/metrics_health.html`, `dashboard/partials/intelligence_panel.html`, `dashboard/partials/analytics_logs.html`.
- Paridade backend -> dashboard:
  - `bot/dashboard_parity_gate.py` promoveu `/api/sentiment/scores` para `integrated`;
  - cobertura de contrato adicionada em `dashboard/tests/api_contract_parity.test.js` e `dashboard/tests/multi_channel_focus.test.js`.
- Testes novos/ajustados da fase:
  - novo: `bot/tests/test_stream_health_score.py` (cálculo de score por banda + path defensivo);
  - backend ajustado: `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_observability.py`, `bot/tests/test_observability_history_contract.py`, `bot/tests/test_dashboard_parity_gate.py`;
  - dashboard ajustado: `dashboard/tests/api_contract_parity.test.js`, `dashboard/tests/multi_channel_focus.test.js`.
- Validação executada:
  - `pytest -q --no-cov bot/tests/test_stream_health_score.py bot/tests/test_observability.py bot/tests/test_observability_history_contract.py bot/tests/test_dashboard_parity_gate.py bot/tests/test_dashboard_routes_v3.py bot/tests/test_dashboard_routes.py` (`81 passed`);
  - `node --test dashboard/tests/api_contract_parity.test.js dashboard/tests/multi_channel_focus.test.js` (`16 passed`);
  - `python -m bot.dashboard_parity_gate` (`ok integrated=18 headless_approved=2`);
  - `ruff check bot/stream_health_score.py bot/observability_snapshot.py bot/observability_state.py bot/observability_history_contract.py bot/dashboard_server_routes.py bot/dashboard_parity_gate.py bot/tests/test_stream_health_score.py bot/tests/test_observability.py bot/tests/test_observability_history_contract.py bot/tests/test_dashboard_parity_gate.py bot/tests/test_dashboard_routes_v3.py` (verde);
  - `ruff format --check bot/stream_health_score.py bot/observability_snapshot.py bot/observability_state.py bot/observability_history_contract.py bot/dashboard_server_routes.py bot/dashboard_parity_gate.py bot/tests/test_stream_health_score.py bot/tests/test_observability.py bot/tests/test_observability_history_contract.py bot/tests/test_dashboard_parity_gate.py bot/tests/test_dashboard_routes_v3.py` (verde).

---

## 3. Backlog Prioritário Real

1. **Fase 12 (Post-Stream Intelligence Report):** transformar histórico persistido em relatório pós-live acionável.
2. **Fase 13 (Goal-Driven Autonomy 2.0):** evoluir objetivos da autonomia para contrato mensurável por sessão.
3. **Fase 14 (Ops Playbooks):** adicionar trilha determinística sobre a action queue para operações críticas.
4. **Fase 15 (Per-Channel Identity):** perfil estruturado por canal para persona operacional consistente.
5. **Fase 16 (Coaching + Churn Risk no HUD):** alertas táticos e risco de perda de audiência no layout atual.
6. **Fase 17 (Revenue Attribution Trace):** fechar loop de ROI com correlação temporal entre ação e conversão.
7. **Fase 18 (Outbound Webhook API):** camada de integração B2B com retry e assinatura.
8. **Fase 19 (Autonomous Clip Suggestion Intelligence):** camada de detecção ao vivo no pipeline de clips já existente.
9. **Vector memory:** manter explicitamente fora do caminho crítico do dashboard operacional.

---

## 4. Roadmap de Posicionamento Validado no Código (Fases 11-19)

### 4.1 Triagem crítica do report (`byte_positioning_report.docx.md`)

| Item do report                         | Situação real (código/plano atual)                                                                          | Decisão aplicada neste plano                                 |
| :------------------------------------- | :---------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------- |
| **F1 Stream Health Score**             | ✅ Implementado na Fase 11 com score 0-100 por canal (`v1` + bandas + componentes).                        | Entregue sem duplicação no layout atual da dashboard.        |
| **F2 Ops Playbooks**                   | ❌ Não existe motor determinístico de playbooks.                                                            | Entrou como **Fase 14** (nova).                              |
| **F3 Per-Channel Identity**            | ⚠️ Parcial: `agent_notes` e config por canal existem, mas sem identidade estruturada.                       | Entrou como **Fase 15** (evolução).                          |
| **F4 Post-Stream Intelligence Report** | ❌ Não existe relatório pós-stream narrativo.                                                               | Entrou como **Fase 12** (nova).                              |
| **F5 Viewer Churn Risk Signal**        | ❌ Não existe sinal explícito de risco de churn por viewer.                                                 | Entrou como **Fase 16** (nova, junto com coaching HUD).      |
| **F6 Goal-Driven Autonomy Session**    | ⚠️ Parcial: goals no control plane já existem, mas sem contrato KPI por sessão.                             | Entrou como **Fase 13** (evolução, sem retrabalho).          |
| **F7 Revenue Attribution Trace**       | ❌ Não existe correlação de ações com follow/sub/cheer; EventSub hoje está centrado em chat message.        | Entrou como **Fase 17** (nova).                              |
| **F8 Outbound Webhook API**            | ❌ Não existem rotas/config de webhook outbound.                                                            | Entrou como **Fase 18** (nova).                              |
| **F9 Streamer Coaching Mode**          | ⚠️ Parcial: HUD já existe (`/dashboard/hud` + painel principal), mas sem camada de coaching tático.         | Entrou como **Fase 16** (evolução sobre HUD existente).      |
| **F10 Autonomous Clip Suggestion**     | ⚠️ Parcial: pipeline de clips + `clip_candidate` existem, mas sem detecção inteligente de momento clipável. | Entrou como **Fase 19** (evolução sobre pipeline existente). |

### 4.2 Fases novas (sem duplicação)

#### Fase 11: Stream Health Score Multi-Canal

- **Status atual:** ✅ Concluída no ciclo atual.
- **Escopo backend:** calcular score 0-100 por canal com base em sentimento, velocidade de chat, trigger hit rate e anomalias.
- **Escopo dashboard:** exibir score no painel de observabilidade já existente (sem criar nova tela).
- **DoD:** endpoint/versionamento do score, visualização por canal, testes unitários do cálculo e testes de rota/UI.

#### Fase 12: Post-Stream Intelligence Report

- **Escopo backend:** sumarização pós-live usando `observability_channel_history`, métricas de ação/aprovação/rejeição e custo operacional.
- **Escopo dashboard:** relatório acessível no fluxo atual de observabilidade/contexto.
- **DoD:** geração manual + automática ao fim de sessão, persistência do relatório, testes de integração e regressão.

#### Fase 13: Goal-Driven Autonomy 2.0

- **Escopo backend:** evoluir goals para contrato com KPI/target/janela/resultado da sessão.
- **Escopo dashboard:** ampliar editor de goals no control plane existente (incluindo riscos hoje não expostos na UI, como `clip_candidate`).
- **DoD:** objetivos avaliáveis no fim da sessão, telemetria de cumprimento, testes de lógica/autonomia/UI.

#### Fase 14: Ops Playbooks Determinísticos

- **Escopo backend:** engine de playbooks (state machine) disparada por condições operacionais, integrada à action queue.
- **Escopo dashboard:** CRUD de playbooks no layout atual do control plane.
- **DoD:** execução auditável e reproduzível, fallback seguro quando condição falhar, testes de fluxo completo.

#### Fase 15: Per-Channel Identity Estruturada

- **Escopo backend:** modelo persistido por canal para `persona_name`, `tone`, `emote_vocab`, `lore`.
- **Escopo dashboard:** editor no bloco de configuração por canal já existente.
- **Restrições técnicas explícitas:** nome de usuário Twitch no chat depende da conta autenticada; escopo desta fase cobre identidade textual/comportamental sem prometer troca de login por canal.
- **DoD:** injeção consistente no prompt/runtime, restore persistido, testes de sanitização e integração.

#### Fase 16: Coaching em Tempo Real + Viewer Churn Risk

- **Escopo backend:** heurísticas de coaching + sinal de risco por ausência/queda de participação recorrente.
- **Escopo dashboard/HUD:** mensagens táticas no HUD e dashboard principal, respeitando layout atual.
- **DoD:** alertas com cooldown/antirruído, trilha histórica curta para auditoria, testes de regra e apresentação.

#### Fase 17: Revenue Attribution Trace

- **Escopo backend:** ampliar ingestão EventSub para eventos de conversão (follow/sub/cheer) e correlacionar temporalmente com ações do agente.
- **Escopo dashboard:** visão de correlação em observabilidade histórica/comparativa já existente.
- **DoD:** correlação explicável (não causal), janela configurável, testes de ingestão/correlação/API.

#### Fase 18: Outbound Webhook API (Agency Integration Layer)

- **Escopo backend:** cadastro de destinos, assinatura/HMAC, retries, DLQ simples e observabilidade de entrega.
- **Escopo dashboard:** gestão de endpoints e eventos no painel operacional atual.
- **DoD:** contrato versionado de payload, segurança mínima (assinatura + segredo rotacionável), testes de entrega e reprocessamento.

#### Fase 19: Autonomous Clip Suggestion Intelligence Layer

- **Escopo backend:** detector de momento clipável em tempo real (spike de sentimento + densidade de chat + padrão de emotes) acoplado ao pipeline de clips existente.
- **Escopo dashboard/HUD:** sugestões operacionais no painel de clips e HUD, sem UI paralela.
- **DoD:** precisão mínima inicial definida por baseline, feedback approve/reject para calibragem, testes de detector e fluxo E2E.

### 4.3 Gate obrigatório de integração visual (para Fases 11-19)

- Toda fase nova deve iniciar por **discovery do layout atual** (componentes/painéis existentes) antes de qualquer UI.
- Toda capacidade backend deve ter mapeamento explícito `endpoint/runtime -> painel existente -> teste`.
- Não criar dashboard paralela nem blocos genéricos fora da linguagem visual atual.

---

## 5. Matriz Atual de Controles

| Controle                                                                                        | Status no código | Observação                                                                                                         |
| :---------------------------------------------------------------------------------------------- | :--------------- | :----------------------------------------------------------------------------------------------------------------- |
| **Channel join/part/list**                                                                      | ✅               | Runtime IRC + dashboard                                                                                            |
| **Action queue approve/reject**                                                                 | ✅               | Fluxo operacional ativo                                                                                            |
| **Manual Tick**                                                                                 | ✅               | `/api/autonomy/tick`                                                                                               |
| **Streamer HUD**                                                                                | ✅               | Embutida + overlay standalone                                                                                      |
| **Panic Suspend/Resume**                                                                        | ✅               | Backend + dashboard + bloqueio operacional implementados                                                           |
| **Persistent global observability rollup**                                                      | ✅               | `observability_rollups` + restore automático + chip de status na dashboard                                         |
| **Observability per-channel real**                                                              | ✅               | `channel_scopes` no rollup (schema v2) + snapshot isolado por canal                                                |
| **Per-channel temperature/top_p**                                                               | ✅               | Persistido em `channels_config`, aplicado na inferência e exposto na dashboard                                     |
| **Pause/Silence por canal (`agent_paused`)**                                                    | ✅               | Persistido em `channels_config`, aplicado no runtime e respeitado no prompt/autonomia                              |
| **Dashboard focused channel + persisted context**                                               | ✅               | Selector persistido, `/api/observability?channel=` e `/api/channel-context`                                        |
| **Histórico persistido + comparativo multi-canal na observabilidade**                           | ✅               | `observability_channel_history` + `/api/observability/history` + tabelas no painel `Agent Context & Internals`     |
| **Thought Injection (`agent_notes`)**                                                           | ✅               | Persistido em `agent_notes`, restaurado no contexto, injetado com sanitização na inferência e exposto na dashboard |
| **Contrato backend -> dashboard (paridade visual por capability)**                              | ✅               | Fase 9 concluída com gate obrigatório (`bot/dashboard_parity_gate.py`) e checklist de release ativo na CI          |
| **Saneamento anti-espaguete/anti-duplicação**                                                   | ✅               | Fase 10 concluída (10.1-10.4) com gate automatizado ativo no pipeline CI                                           |
| **Stream Health Score multi-canal (score + banda + histórico persistido)**                     | ✅               | Fase 11 concluída com endpoint por canal (`/api/sentiment/scores`) e render no layout atual                        |
| **Roadmap de posicionamento (F1-F10 do report) convertido em fases executáveis sem duplicação** | ✅               | Triado contra código atual e consolidado nas Fases 11-19                                                           |
| **Vector Memory**                                                                               | ❌               | Ainda não implementado                                                                                             |

---

## 6. Conclusão

O plano anterior estava correto no direcionamento, mas subestimava o que já foi entregue e misturava itens já implementados com itens ainda futuros. O estado real em 27/02/2026 é:

- base stateful funcional;
- boot dinâmico por `channels_config` funcional;
- dashboard operacional funcional;
- HUD standalone funcional e agora exposta na dashboard;
- observabilidade per-channel real entregue no backend da dashboard operacional;
- dashboards históricos multi-canal e comparativo por canal entregues no painel operacional existente;
- soberania por canal já cobre tuning + notes + pause/silence;
- contrato formal de paridade backend -> dashboard concluído, com gate de release/CI ativo e discovery de layout aplicado;
- saneamento estrutural foi concluído (Fase 10) com gate automatizado de complexidade/duplicação no pipeline;
- stream health score multi-canal foi concluído (Fase 11) com contrato versionado e exposição no layout operacional existente;
- roadmap do report de posicionamento foi convertido em fases técnicas executáveis (F11-F19), com filtragem de itens já parciais no código para evitar duplicação;
- memória vetorial ainda fora do escopo implementado.

### Fechamento da Etapa Atual

- Etapa entregue: Fase 11 (Stream Health Score Multi-Canal) concluída sem regressão funcional.
- Backend/infra de qualidade:
  - `bot/stream_health_score.py` centraliza score determinístico por canal e componentes explicáveis;
  - `bot/dashboard_parity_gate.py` passou a classificar `/api/sentiment/scores` como `integrated` com evidência backend + dashboard.
- Pipeline:
  - gates de `ruff` + `pytest` + `node --test` + `python -m bot.dashboard_parity_gate` executados e verdes no ciclo;
  - contrato visual manteve o encaixe no layout existente (`metrics_health`, `agent context`, `intelligence`) sem tela paralela.
- Escopo validado: score e banda por canal fluem de runtime/persistência até UI comparativa histórica com cobertura de regressão.
- Testes da etapa: suíte nova Python de score + ajustes de contratos backend/dashboard + regressão multi-canal preservada.
- Planejamento: backlog priorizado passa a iniciar na Fase 12, com Fases 9-11 fechadas.

_Plano validado contra o código, incrementado com a etapa implementada e reajustado para execução real._
