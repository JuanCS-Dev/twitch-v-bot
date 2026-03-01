# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.34
**Data:** 01 de Março de 2026
**Status:** Fases 1-25 concluídas ✅ | Evolução ANN por escala no backlog

---

## 1. Auditoria de Conclusão (Fases Antigas)

**Escopo auditado:** Fases 1-13 do plano operacional.
**Método:** validação por evidência de código (runtime/rotas/dashboard), testes automatizados e gates de qualidade/paridade.

**Resultado:** **13 de 13 fases antigas concluídas** no escopo definido em cada fase.

**Ressalva explícita de escopo (atualizada):**

- Fase 8 (memória semântica) segue concluída no escopo **operacional**.
- Otimização ANN com `pgvector` foi implementada como evolução na Fase 20, com fallback determinístico para preservar comportamento em ambientes sem função RPC disponível.

---

## 2. Matriz de Rastreabilidade por Fase (Planejamento -> Implementação -> Validação)

| Fase    | Planejamento (resumo)                                    | Implementação validada no código                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Validação (testes/gates)                                                                                                                                                                                                                                                                                                                                                                                                                                  | Status |
| :------ | :------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----- |
| **1-3** | Persistência base + lazy restore por canal               | `bot/persistence_layer.py`, `bot/logic_context.py` (load/restore de estado/config/notas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `bot/tests/test_persistence_layer.py`, `bot/tests/test_logic_context.py`                                                                                                                                                                                                                                                                                                                                                                                  | ✅     |
| **4**   | Canais dinâmicos e boot sequence com fallback ENV        | `bot/bootstrap_runtime.py` (`resolve_irc_channel_logins`, fallback `TWITCH_CHANNEL_LOGINS/TWITCH_CHANNEL_LOGIN`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `bot/tests/test_bootstrap_runtime.py`, `bot/tests/test_bootstrap_runtime_v2.py`, `bot/tests/test_bootstrap_runtime_v3.py`, `bot/tests/test_bootstrap_runtime_v4.py`                                                                                                                                                                                                                                                                                       | ✅     |
| **5**   | Observabilidade stateful persistida e restaurável        | `bot/observability_state.py`, `bot/observability_snapshot.py`, `observability_rollups` em `bot/persistence_layer.py`, rota `/api/observability`                                                                                                                                                                                                                                                                                                                                                                                                                                             | `bot/tests/test_observability.py`, `bot/tests/test_dashboard_routes_v3.py`                                                                                                                                                                                                                                                                                                                                                                                | ✅     |
| **6**   | Dashboard multi-canal integrada ao runtime real          | `dashboard/features/channel-control/*`, `dashboard/features/observability/*`, rotas `/api/channel-context` e `/api/observability/history`                                                                                                                                                                                                                                                                                                                                                                                                                                                   | `dashboard/tests/multi_channel_focus.test.js`, `bot/tests/test_dashboard_routes_v3.py`                                                                                                                                                                                                                                                                                                                                                                    | ✅     |
| **7**   | Soberania e comando operacional                          | `/api/autonomy/tick`, `/api/agent/suspend`, `/api/agent/resume` em `bot/dashboard_server_routes_post.py`; overrides `temperature/top_p/agent_paused`; `agent_notes` persistido                                                                                                                                                                                                                                                                                                                                                                                                              | `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/multi_channel_focus.test.js`, `bot/tests/test_logic_context.py`                                                                                                                                                                                                                                                                                                                               | ✅     |
| **8**   | Memória semântica operacional por canal                  | `bot/semantic_memory.py`, `bot/persistence_semantic_memory_repository.py`, `/api/semantic-memory` (`GET/PUT`), integração no `Intelligence Overview`                                                                                                                                                                                                                                                                                                                                                                                                                                        | `bot/tests/test_semantic_memory.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_parity_gate.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                                                                                                                                                                                              | ✅     |
| **9**   | Paridade formal backend -> dashboard                     | `bot/dashboard_parity_gate.py`, `dashboard/tests/api_contract_parity.test.js`, CI em `.github/workflows/ci.yml`                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | `python -m bot.dashboard_parity_gate`, `node --test dashboard/tests/api_contract_parity.test.js`                                                                                                                                                                                                                                                                                                                                                          | ✅     |
| **10**  | Saneamento estrutural (anti-espaguete/duplicação)        | `bot/dashboard_http_helpers.py`, fatiamento de persistência (repositórios dedicados), `bot/structural_health_gate.py`, CI com C901+R0801                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `python -m bot.structural_health_gate`, `bot/tests/test_structural_health_gate.py`                                                                                                                                                                                                                                                                                                                                                                        | ✅     |
| **11**  | Stream Health Score multi-canal                          | `bot/stream_health_score.py`, snapshot/histórico com `stream_health`, `/api/sentiment/scores`, render no layout atual                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `bot/tests/test_stream_health_score.py`, `bot/tests/test_observability.py`, `dashboard/tests/multi_channel_focus.test.js`, parity gate                                                                                                                                                                                                                                                                                                                    | ✅     |
| **12**  | Post-Stream Intelligence Report                          | `bot/post_stream_report.py`, `bot/persistence_post_stream_report_repository.py`, `/api/observability/post-stream-report`, geração automática em `part`                                                                                                                                                                                                                                                                                                                                                                                                                                      | `bot/tests/test_post_stream_report.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_server_extra.py`, parity gate                                                                                                                                                                                                                                                                                                                  | ✅     |
| **13**  | Goal-Driven Autonomy 2.0 (KPI por sessão)                | `bot/control_plane_constants.py`, `bot/control_plane_config_helpers.py`, `bot/control_plane_config.py`, `bot/autonomy_runtime.py`, UI em `dashboard/features/control-plane/view.js`                                                                                                                                                                                                                                                                                                                                                                                                         | `bot/tests/test_control_plane_config.py`, `bot/tests/test_control_plane.py`, `bot/tests/test_autonomy_runtime.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                                                                                                                                                                                                                                          | ✅     |
| **14**  | Ops Playbooks determinísticos                            | `bot/ops_playbooks.py`, integração em `bot/control_plane.py` + `bot/autonomy_runtime.py`, rotas `/api/ops-playbooks` e `/api/ops-playbooks/trigger`, UI integrada em `dashboard/features/action-queue/*` + `dashboard/partials/risk_queue.html`                                                                                                                                                                                                                                                                                                                                             | `bot/tests/test_ops_playbooks.py`, `bot/tests/test_control_plane.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_post.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/api_contract_parity.test.js`, `bot/tests/test_dashboard_parity_gate.py`                                                                                                                                                                  | ✅     |
| **15**  | Per-Channel Identity Estruturada                         | `bot/persistence_channel_identity_repository.py`, facade em `bot/persistence_layer.py`, restore/aplicação em `bot/logic_context.py`, injeção de prompt em `bot/logic_inference.py`, rotas `GET/PUT /api/channel-config` e `GET /api/channel-context` em `bot/dashboard_server_routes.py`, UI integrada no `Control Plane` (`dashboard/partials/control_plane.html`, `dashboard/features/control-plane/view.js`)                                                                                                                                                                             | `bot/tests/test_persistence_repositories.py`, `bot/tests/test_persistence_layer.py`, `bot/tests/test_logic_context.py`, `bot/tests/test_logic.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`, `dashboard/tests/api_contract_parity.test.js`, `bot/tests/test_structural_health_gate.py`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate` | ✅     |
| **16**  | Coaching em tempo real + Viewer Churn Risk               | motor determinístico `bot/coaching_churn_risk.py`, runtime antirruído `bot/coaching_runtime.py`, integração no snapshot de observabilidade (`bot/dashboard_server_routes.py`) e render no layout atual (`dashboard/partials/intelligence_panel.html`, `dashboard/features/observability/view.js`, `dashboard/features/hud/view.js`)                                                                                                                                                                                                                                                         | `bot/tests/test_coaching_churn_risk.py`, `bot/tests/test_coaching_runtime.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate`                                                                                                                                                                                                      | ✅     |
| **17**  | Revenue Attribution Trace                                | correlação temporal de follow/sub/cheer com ação via `bot/revenue_attribution_engine.py`, persistência via `bot/persistence_revenue_attribution_repository.py`, rotas `/api/observability/conversion(s)`, render em `dashboard/partials/intelligence_panel.html`                                                                                                                                                                                                                                                                                                                            | `bot/tests/test_revenue_attribution_engine.py`, `bot/tests/test_persistence_revenue_repository.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/multi_channel_focus.test.js`, `python -m bot.dashboard_parity_gate`                                                                                                                                                                              | ✅     |
| **18**  | Outbound Webhook API                                     | `bot/outbound_webhooks.py` (engine hmac/retry), `bot/persistence_webhook_repository.py`, endpoints `/api/webhooks` e `/api/webhooks/test`, UI agregada no Control Plane.                                                                                                                                                                                                                                                                                                                                                                                                                    | `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/api_contract_parity.test.js`, `dashboard/tests/multi_channel_focus.test.js`, `python -m bot.dashboard_parity_gate`                                                                                                                                                                                             | ✅     |
| **19**  | Autonomous Clip Suggestion Intelligence                  | Exposição de métricas e ingest manual em `dashboard/partials/clips_section.html`, engine visual acoplada ao Autonomy (`bot/vision_runtime.py`), endpoints `/api/vision/status` e `/api/vision/ingest` consolidados como `integrated`.                                                                                                                                                                                                                                                                                                                                                       | `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/api_contract_parity.test.js`, `bot/dashboard_parity_gate.py`                                                                                                                                                                                                                                                                                         | ✅     |
| **20**  | Otimização ANN de Memória Semântica com `pgvector`       | `bot/persistence_semantic_memory_repository.py` com busca via RPC (`semantic_memory_search_pgvector`/`semantic_memory_search`) e fallback automático para ranking determinístico atual; flags `SEMANTIC_MEMORY_PGVECTOR_ENABLED` e `SEMANTIC_MEMORY_PGVECTOR_RPC`.                                                                                                                                                                                                                                                                                                                          | `bot/tests/test_persistence_semantic_memory_pgvector.py`, `bot/tests/test_persistence_repositories.py`, `bot/tests/test_persistence_layer.py`, `bot/tests/test_semantic_memory.py`, `bot/tests/test_dashboard_routes_v3.py -k semantic_memory`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate`, `node --test dashboard/tests/api_contract_parity.test.js`                                                                  | ✅     |
| **21**  | Tuning operacional ANN + diagnóstico de engine semântica | `bot/persistence_semantic_memory_repository.py` com `SEMANTIC_MEMORY_MIN_SIMILARITY`, busca com `min_similarity`/`force_fallback`, `search_settings_sync()` e `search_entries_with_diagnostics_sync()`; facade expandida em `bot/persistence_layer.py`; rota `/api/semantic-memory` com query params de tuning e payload com `search_settings`/`search_diagnostics`; UI integrada no painel atual em `dashboard/partials/intelligence_panel.html`, `dashboard/features/observability/api.js`, `dashboard/features/observability/controller.js`, `dashboard/features/observability/view.js`. | `bot/tests/test_persistence_semantic_memory_pgvector.py`, `bot/tests/test_persistence_repositories.py`, `bot/tests/test_persistence_layer.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/api_contract_parity.test.js`, `dashboard/tests/multi_channel_focus.test.js`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate`                                                 | ✅     |
| **22**  | Prompt & Persona Studio + model routing por atividade    | `bot/persistence_persona_profile_repository.py` (novo `CachedChannelRepository` para `persona_profiles` com `base_identity`, `tonality_engine`, `behavioral_constraints`, `model_routing`), facade em `bot/persistence_layer.py`, extensão de `StreamContext` + `ContextManager.apply_persona_profile` em `bot/logic_context.py`, routing per-channel em `_select_model` + instrução expandida (`sentence_style`, `banned_topics`, `cta_triggers`) em `bot/logic_inference.py`, rotas `GET/PUT /api/persona-profile` em `bot/dashboard_server_routes.py`, UI integrada no Control Plane (`dashboard/partials/control_plane.html`, `dashboard/features/control-plane/view.js`, `api.js`, `controller.js`). | `bot/tests/scientific/test_phase22_persona_routing.py` (18 testes: repo roundtrip, model routing, identity instruction, facade cache, context propagation), `bot/tests/test_dashboard_routes_v3.py` (GET/PUT persona-profile), `dashboard/tests/api_contract_parity.test.js`, `bot/tests/test_dashboard_parity_gate.py`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate` | ✅     |
| **23**  | Geração de arte ASCII sob demanda no chat Twitch         | **Concluída**: `bot/ascii_art_runtime.py` (334 linhas) com geração Braille 2x4, busca de imagem via DuckDuckGo, cooldown por canal (`AsciiArtCooldown`), sanitização IRC, handler de alto nível (`handle_ascii_art_prompt`), parsing em `bot/byte_semantics_base.py`, envio raw multi-linha em `bot/irc_state.py`/`bot/eventsub_runtime.py`. | Testes integrados no prompt_flow e envio raw, mantendo paridade de health e integridade multi-canal. | ✅     |
| **24**  | Calendário Tático (Tactical Calendar) nativo no Dashboard| **Concluída**: Evolução do sistema de Goals em `bot/control_plane_config.py` suportando cron-jobs e horários fixos via `croniter`. Dashboard com nova aba "Calendar" em Vanilla JS/HTML (`dashboard/partials/calendar_tab.html`), componentes nativos `<input type="datetime-local">`, mantendo o ciclo nativo do `autonomy_runtime.py`.                                                                                                                                                                                                                                                                                              | **Concluída**: Expansão do `bot/tests/test_control_plane_config.py`, `bot/tests/test_autonomy_runtime.py` e rotas no backend. Atualização dos gates de paridade e testes do frontend (`api_contract_parity.test.js`).                                                                                                                                                                                                                                             | ✅     |

| **25**  | Dashboard UX Upgrade: Thumbs de Clips | **Concluída**: Injeção da tag `<img src="...">` no card de clipes consumindo o payload real `thumbnail_url` retornado pela API da Twitch e adição de um spinner em CSS Vanilla para os status `creating` e `polling`. Otimização do layout com aspect-ratio 16:9. | **Concluída**: Teste interativo via UI e gates de integridade estrutural. | ✅     |

---

## 3. Rastreabilidade Operacional (Contrato Backend -> UI -> Teste)

| Capability                             | Backend (endpoint/runtime)                                                                                                                | Dashboard (layout atual)                                                                                          | Testes de rastreio                                                                                                                                                                                                                                               |
| :------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Contexto por canal focado              | `/api/observability?channel=`, `/api/channel-context`, `/api/observability/history`                                                       | `Agent Context & Internals`                                                                                       | `dashboard/tests/multi_channel_focus.test.js`, `bot/tests/test_dashboard_routes_v3.py`                                                                                                                                                                           |
| Memória semântica                      | `/api/semantic-memory` (`GET/PUT`) + busca ANN opcional via `pgvector` no `SemanticMemoryRepository` com fallback determinístico          | `Intelligence Overview`                                                                                           | `bot/tests/test_semantic_memory.py`, `bot/tests/test_persistence_semantic_memory_pgvector.py`, `bot/tests/test_dashboard_routes.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                               |
| Memória semântica (tuning operacional) | `/api/semantic-memory?min_similarity=&force_fallback=` + `search_settings/search_diagnostics` para leitura de engine/threshold/resultados | `Intelligence Overview` (controles `Min Similarity`, `Deterministic Fallback`, chip de engine e hint diagnóstico) | `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_persistence_layer.py`, `dashboard/tests/api_contract_parity.test.js`, `dashboard/tests/multi_channel_focus.test.js`                                               |
| Stream health score                    | `/api/sentiment/scores`                                                                                                                   | `metrics_health`, `intelligence_panel`, `agent_context_internals`                                                 | `bot/tests/test_stream_health_score.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                                                                                                                           |
| Post-stream report                     | `/api/observability/post-stream-report` (`generate=1`) + auto em `part`                                                                   | `Intelligence Overview` (mesmo painel)                                                                            | `bot/tests/test_post_stream_report.py`, `bot/tests/test_dashboard_server_extra.py`, `bot/tests/test_dashboard_routes_v3.py`                                                                                                                                      |
| Coaching churn risk em tempo real      | `/api/observability` com bloco `coaching` + emissão HUD via `coaching_runtime` (`source=coaching`)                                        | `Intelligence Overview` + `Streamer HUD` (mesmo layout/painéis atuais)                                            | `bot/tests/test_coaching_churn_risk.py`, `bot/tests/test_coaching_runtime.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                                            |
| Goal KPI por sessão                    | runtime `register_goal_session_result` + telemetria `kpi_met/kpi_missed`                                                                  | `Control Plane` (editor de goals existente)                                                                       | `bot/tests/test_control_plane_config.py`, `bot/tests/test_autonomy_runtime.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                                                                                    |
| Identidade estruturada por canal       | `channel_identity` via `PersistenceLayer`, `/api/channel-config` (`GET/PUT`) e `/api/channel-context`                                     | `Control Plane` (card `Channel Directives`, sem dashboard paralela)                                               | `bot/tests/test_persistence_repositories.py`, `bot/tests/test_persistence_layer.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`, `dashboard/tests/api_contract_parity.test.js` |
| Soberania operacional                  | `/api/autonomy/tick`, `/api/agent/suspend`, `/api/agent/resume`                                                                           | `Control Plane` + HUD                                                                                             | `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/multi_channel_focus.test.js`                                                                                                                                                                         |
| Ops playbooks determinísticos          | `/api/ops-playbooks` (`GET`) + `/api/ops-playbooks/trigger` (`POST`) + execução em `autonomy_runtime`                                     | `Risk Queue` (mesmo painel/layout atual)                                                                          | `bot/tests/test_ops_playbooks.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/api_contract_parity.test.js`                                                                                                |
| Atribuição de Conversões (Trace)       | `/api/observability/conversions` (`GET`) + `/api/observability/conversion` (`POST`)                                                       | `Intelligence Overview` (Fim do painel, trace list)                                                               | `bot/tests/test_revenue_attribution_engine.py`, `dashboard/tests/api_contract_parity.test.js`, `bot/dashboard_parity_gate.py`                                                                                                                                    |
| Outbound Webhooks                      | `/api/webhooks` (`GET`/`PUT`) + `/api/webhooks/test` (`POST`)                                                                             | `Control Plane` (Embaixo do Budget diário)                                                                        | `bot/tests/test_dashboard_routes.py`, `dashboard/tests/api_contract_parity.test.js`, `bot/dashboard_parity_gate.py`                                                                                                                                              |
| Autonomous Clip Suggestion             | `/api/vision/status` (`GET`) + `/api/vision/ingest` (`POST`)                                                                              | `Clips Pipeline` (Painel lateral visual_clip_widget)                                                              | `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/api_contract_parity.test.js`, `bot/dashboard_parity_gate.py`                                                                                                                                           |

---

## 4. Backlog Prioritário (Fases Futuras)

1. **Fase 22 (prioridade alta): Prompt & Persona Studio + model routing por atividade.**
2. **Fase 23 (prioridade alta): geração de arte ASCII sob demanda no chat Twitch.**
3. **Evolução ANN:** índices avançados (`ivfflat`/HNSW) e política dinâmica de probes/latência por volume real.

### 4.1 Escopo planejado da Fase 22: Persona Studio & Nebius Industrial Routing

**Objetivo**: Transformar o Byte em um Agent Runtime multi-tenant de alta performance, utilizando o estado da arte do Nebius Token Factory (2026) com segurança de nível bancário e roteamento dinâmico de modelos.

#### 4.1.1 Nebius Intelligent Router (Inference-as-a-Service 2026)
- **Estratégia de Model Tiering (Brutal Reality)**:
  - **Tier 1: Ultra-Low Latency (<300ms TTFT)**: Uso de `deepseek-ai/DeepSeek-V3-Fast` ou `google/gemma-3-27b-it-fast` para chat interativo e comandos IRC.
  - **Tier 2: Reasoning/Coaching**: Uso obrigatório de `deepseek-ai/DeepSeek-R1` (0528) para análise de sentimento profunda, coaching tático e geração de relatórios.
  - **Tier 3: Structured/Tools**: Uso de `Qwen/Qwen3-Coder-30B` para parsing de JSON complexo e chamadas de ferramentas (MCP - Model Context Protocol).
- **Implementação do Router (`bot/logic_inference.py`)**:
  - Middleware de seleção baseado em metadados da tarefa (`intent_classifier` leve antes da inferência).
  - **Manual Override Dashboard**: Tabela `channel_model_routing` no Supabase permitindo que a agência force um modelo específico por canal/atividade.
  - **Circuit Breaker & Fallback**: Degradação graciosa automática (ex: se R1 falhar ou rate-limit, cai para V3-Fast) para manter 99.9% de uptime no chat.

#### 4.1.2 Persona Studio (Dynamic Identity Injection)
- **Persistência Estruturada**: Migrar identidade para objeto `persona_profile` no Supabase:
  - `base_identity`: Nome, Pronomes, Lore (contexto histórico).
  - `tonality_engine`: Slang mapping, Emote density, Sentence length (short/punchy vs long/analytical).
  - `behavioral_constraints`: Banned topics, specific CTA triggers.
- **Runtime Orchestrator**:
  - Compilação dinâmica do System Prompt JIT (Just-In-Time) injetando a identidade estruturada acima do baseline de segurança do Byte.
  - Suporte a "Hot Swap" de persona via Dashboard sem necessidade de restart do bot.

#### 4.1.3 Segurança e Escalabilidade Industrial (B2B Ready)
- **Auth Middleware (Zero Trust)**:
  - Implementação de autenticação via Bearer Token (JWT) em todas as rotas `/api/*`.
  - Desativação automática de endpoints de configuração se `BYTE_DASHBOARD_ADMIN_TOKEN` não atingir entropia mínima (32+ chars).
- **Async-First Persistence**:
  - Refatoração completa da `PersistenceLayer` para remover `asyncio.to_thread`.
  - Uso de `httpx` asíncrono para chamadas Supabase/PostgREST para suportar 100+ canais concorrentes sem jitter no event loop.
- **Audit & Analytics**:
  - Endpoint `/api/observability/roi` agregando custo Nebius vs. conversões rastreadas (Fase 17).
  - Log de auditoria de alteração de configuração (quem mudou o quê e quando).

### 4.2 Escopo planejado da Fase 23 (ASCII Art no Chat Twitch)

- Objetivo operacional: permitir comandos naturais do tipo `byte arte ascii do goku` e retornar arte ASCII no chat do mesmo canal, sem quebrar o contrato multi-canal e sem dashboard paralela.
- Escopo de trigger inicial:
  - `byte arte ascii do <tema>`
  - `byte ascii <tema>`
  - `@byte ascii <tema>`
- Token/scopes Twitch: sem novos escopos. A fase reutiliza os fluxos já ativos (`chat:edit/chat:read` no IRC e `user:write:chat/user:read:chat/user:bot` + `channel:bot` no EventSub), mantendo envio com `Client-Id` + `Authorization`.

#### 4.2.1 Pesquisa técnica consolidada (biblioteca especializada)

| Opção | Cobertura real para pedido "arte ASCII do goku" | Prós | Contras | Decisão |
| :--- | :--- | :--- | :--- | :--- |
| `ascii-magic` (`ascii_magic`) | **Alta** (imagem -> ASCII com controle de colunas) | Python puro, qualidade visual superior para silhueta/personagem, integração simples com Cloud Run | depende de imagem de entrada (pipeline de busca/download) | **Escolhida** |
| `pyfiglet` | Baixa (texto estilizado, não personagem) | leve, estável | não resolve "desenho de personagem", só tipografia | Rejeitada |
| `art` | Baixa/média (catálogo fixo + text2art) | simples para arte pronta | cobertura limitada e não escalável para temas livres | Rejeitada |
| `chafa` (CLI) | Alta qualidade | render excelente | dependência binária de sistema, pior portabilidade no runtime atual | Rejeitada |

- Biblioteca selecionada para implementação da fase:
  - adicionar `ascii-magic>=2.3.0,<3.0.0` em `bot/requirements.txt`.
  - usar `duckduckgo_search` já existente para buscar imagem (`DDGS().images`) e converter em ASCII (sem novo provedor externo).

#### 4.2.2 Formato ideal para Twitch Chat (baseline 2026)

- Premissas da plataforma:
  - envio de chat é mensagem única por chamada (sem multiline nativo no payload).
  - limite efetivo seguro no projeto permanece `<=460` chars por mensagem para paridade entre EventSub/Helix e IRC.
  - risco operacional explícito: `msg_duplicate`/`msg_slowmode` quando houver burst ou repetição.
- Contrato de entrega da ASCII Art (fase 23):
  - render em **micro-bloco**: até `8` linhas por pedido.
  - largura alvo: `28-36` colunas para preservar legibilidade em desktop e mobile.
  - cada linha enviada como mensagem independente no canal de origem.
  - cooldown por canal para esse recurso (recomendado: `45-90s`).
  - throttling entre linhas (recomendado: `350-650ms`) para reduzir risco de drop.
- Guardrail técnico obrigatório no código atual:
  - não usar `format_chat_reply -> enforce_reply_limits -> flatten_chat_text` para ASCII, porque esse pipeline remove quebras/indentação e destrói a arte.
  - criar caminho de envio raw por linha, preservando espaços à esquerda.

#### 4.2.3 Caminho de implementação (incremental, sem reescrever base)

- Parsing/semântica:
  - `bot/byte_semantics_base.py`: adicionar detector `is_ascii_art_prompt` e extrator `extract_ascii_subject`.
- Runtime de geração:
  - novo módulo `bot/ascii_art_runtime.py` com pipeline:
    - resolver tema solicitado.
    - buscar imagem candidata (DuckDuckGo image search).
    - converter para ASCII com `ascii_magic` (modo mono, colunas controladas).
    - sanitizar para ASCII imprimível e limitar linhas/colunas.
- Orquestração de prompt:
  - `bot/prompt_flow.py`: criar rota explícita `ascii_art` antes do fluxo LLM padrão.
  - `bot/prompt_runtime.py`: integrar handler novo sem impactar intents existentes (`help`, `status`, `movie_fact_sheet`, `recap`, LLM default).
- Transporte de chat:
  - `bot/irc_state.py`: adicionar envio raw por linha (sem `flatten_chat_text`) para blocos ASCII.
  - `bot/eventsub_runtime.py`: enviar linhas sequenciais no canal correto, mantendo isolamento multi-canal.
- Observabilidade:
  - registrar rota dedicada (`ascii_art`) em `record_byte_interaction`.
  - registrar falhas específicas (`ascii_not_found`, `ascii_rate_limited`, `ascii_cooldown`).

#### 4.2.4 Estratégia de validação da Fase 23

- Testes backend planejados:
  - `bot/tests/test_ascii_art_runtime.py` (parser, busca mockada, render e sanitização).
  - extensão de `bot/tests/test_prompt_flow_v2.py` para rota `ascii_art`.
  - extensão de `bot/tests/test_irc_state_v3.py` e `bot/tests/test_eventsub_runtime_v5.py` para envio multi-linha raw no canal correto.
- Gates de fechamento:
  - `pytest -q --no-cov bot/tests/test_ascii_art_runtime.py bot/tests/test_prompt_flow_v2.py bot/tests/test_irc_state_v3.py bot/tests/test_eventsub_runtime_v5.py`
  - `python -m bot.dashboard_parity_gate`
  - `python -m bot.structural_health_gate`
  - atualização desta seção com evidências (pass/fail e contagem).

### 4.3 Escopo planejado da Fase 24 (Calendário Tático Nativo)

**Objetivo**: Expandir o sistema nativo de `goals` (objetivos autônomos) para suportar agendamentos precisos (horário fixo) e recorrentes complexos (Cron Jobs), integrando uma nova aba "Calendar" na interface Vanilla JS do painel de controle, preservando 100% da performance e sem dependências externas no frontend.

#### 4.3.1 Atualização do Modelo de Dados e Backend (`bot/control_plane_config.py` e `bot/autonomy_runtime.py`)
- O dicionário `goals` será expandido com os seguintes campos mantendo compatibilidade reversa:
  - `schedule_type`: `"interval"` (padrão), `"fixed_time"`, ou `"cron"`.
  - `scheduled_at`: ISO 8601 string para o agendamento `fixed_time`.
  - `cron_expression`: String no padrão Unix Cron para eventos recorrentes.
- A função `consume_due_goals()` fará o parse de `scheduled_at` e usará a biblioteca leve `croniter` (backend) para calcular o exato próximo disparo de cron-jobs e atualizar o mapa `_next_goal_due_at`.
- Não será adicionado `APScheduler`. O loop contínuo já existente em `_heartbeat_loop` (`asyncio.sleep()`) e a chamada `_run_tick` do `AutonomyRuntime` consumirão as tarefas no tempo exato, garantindo impacto zero de processamento.
- Novas validações na rota `PUT /api/channel-config` (em `bot/dashboard_server_routes.py`) assegurarão que crons inválidos ou horários passados não corrompam o estado do runtime.

#### 4.3.2 Implementação Visual no Dashboard (Vanilla JS)
- **Aba Dedicated "Calendar"**: Criação de uma nova sub-aba na seção Control Plane (ao lado de Agent Identity e Goals).
- **Sem overengineering visual**: A tela será focada em uma "Timeline de Agendamentos Táticos" listando os eventos futuros de forma limpa, seguindo a estética dark-mode/flat do sistema (`dashboard/styles/...`). Não haverá bibliotecas externas (React/calendários gigantes).
- **Editor de Goal Expandido**: O modal de criação de ações ganha novos inputs HTML5 nativos (`<input type="datetime-local">` para horário fixo e text input simples para Cron), aproveitando o formulário já existente em `dashboard/features/control-plane/view.js`.

#### 4.3.3 Estratégia de Validação da Fase 24
- `bot/tests/test_control_plane_config.py`: Garantir que `croniter` avança o loop corretamente.
- `bot/tests/test_autonomy_runtime.py`: Verificar se horários fixos expiram do runtime e não entram em loop.
- Extensão do teste de paridade de UI `dashboard/tests/api_contract_parity.test.js`.
- Verificação nos gates padrões: `python -m bot.dashboard_parity_gate`.

---

## 5. Evidências de Validação (ciclo de auditoria atual)

- `pytest -q --no-cov bot/tests/test_persistence_semantic_memory_pgvector.py bot/tests/test_persistence_repositories.py bot/tests/test_persistence_layer.py bot/tests/test_semantic_memory.py`
  **Resultado:** `58 passed`.
- `pytest -q --no-cov bot/tests/test_dashboard_routes_v3.py -k semantic_memory`
  **Resultado:** `2 passed, 44 deselected`.
- `node --test dashboard/tests/api_contract_parity.test.js`
  **Resultado:** `2 passed`.
- `pytest -q --no-cov bot/tests/`
  **Resultado:** `927 passed, 4 skipped, 0 warnings`.
- `node --test dashboard/tests/api_contract_parity.test.js dashboard/tests/multi_channel_focus.test.js`
  **Resultado:** `23 passed`.
- `python -m bot.dashboard_parity_gate`
  **Resultado:** `ok integrated=30 headless_approved=0`.
- `python -m bot.structural_health_gate`
  **Resultado:** `ok`.
- `bash validate_plan.sh`
  **Resultado:** `Auditoria concluída sem inconsistências`.
- `pre-commit run --all-files`
  **Resultado:** todos os hooks passaram (`black`, `ruff`, `ruff-format`, checks auxiliares).
- `pytest -q --no-cov bot/tests/test_persistence_semantic_memory_pgvector.py bot/tests/test_persistence_repositories.py bot/tests/test_persistence_layer.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py`
  **Resultado:** `136 passed`.
- `node --test dashboard/tests/api_contract_parity.test.js dashboard/tests/multi_channel_focus.test.js dashboard/tests/dashboard_asset_import_integrity.test.js dashboard/tests/dashboard_semantic_consistency.test.js dashboard/tests/tabs_responsiveness_contract.test.js`
  **Resultado:** `30 passed`.

---

## 6. Regras de Execução por Etapa (Contrato Operacional)

Toda etapa segue o fluxo obrigatório:

1. Implementação.
2. Validação funcional.
3. Novos testes para linhas novas (fluxo real).
4. Ajuste de testes antigos impactados.
5. Execução dos testes/gates.
6. Atualização deste plano com rastreabilidade da etapa.
7. Commit com hook verde (corrigir falhas até passar).

---

## 7. Notas de Governança

- Não criar dashboard paralela nem UI genérica desconectada do layout atual.
- Toda feature backend operacional deve ter mapeamento explícito: `endpoint/runtime -> painel atual -> teste`.
- Exceções headless só com justificativa formal no gate de paridade.
