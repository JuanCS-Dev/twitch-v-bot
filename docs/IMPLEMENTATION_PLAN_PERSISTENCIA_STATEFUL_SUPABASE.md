# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.28
**Data:** 27 de Fevereiro de 2026
**Status:** Fases antigas (1-13) + Fases 14-16 concluídas ✅ | Backlog ativo: Fases 17-19 + otimização `pgvector` (futuro)

---

## 1. Auditoria de Conclusão (Fases Antigas)

**Escopo auditado:** Fases 1-13 do plano operacional.
**Método:** validação por evidência de código (runtime/rotas/dashboard), testes automatizados e gates de qualidade/paridade.

**Resultado:** **13 de 13 fases antigas concluídas** no escopo definido em cada fase.

**Ressalva explícita de escopo (já prevista):**
- Fase 8 (memória semântica) está concluída no escopo **operacional**.
- Otimização ANN com `pgvector` permanece como evolução futura (não bloqueia conclusão operacional da fase).

---

## 2. Matriz de Rastreabilidade por Fase (Planejamento -> Implementação -> Validação)

| Fase | Planejamento (resumo) | Implementação validada no código | Validação (testes/gates) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1-3** | Persistência base + lazy restore por canal | `bot/persistence_layer.py`, `bot/logic_context.py` (load/restore de estado/config/notas) | `bot/tests/test_persistence_layer.py`, `bot/tests/test_logic_context.py` | ✅ |
| **4** | Canais dinâmicos e boot sequence com fallback ENV | `bot/bootstrap_runtime.py` (`resolve_irc_channel_logins`, fallback `TWITCH_CHANNEL_LOGINS/TWITCH_CHANNEL_LOGIN`) | `bot/tests/test_bootstrap_runtime.py`, `bot/tests/test_bootstrap_runtime_v2.py`, `bot/tests/test_bootstrap_runtime_v3.py`, `bot/tests/test_bootstrap_runtime_v4.py` | ✅ |
| **5** | Observabilidade stateful persistida e restaurável | `bot/observability_state.py`, `bot/observability_snapshot.py`, `observability_rollups` em `bot/persistence_layer.py`, rota `/api/observability` | `bot/tests/test_observability.py`, `bot/tests/test_dashboard_routes_v3.py` | ✅ |
| **6** | Dashboard multi-canal integrada ao runtime real | `dashboard/features/channel-control/*`, `dashboard/features/observability/*`, rotas `/api/channel-context` e `/api/observability/history` | `dashboard/tests/multi_channel_focus.test.js`, `bot/tests/test_dashboard_routes_v3.py` | ✅ |
| **7** | Soberania e comando operacional | `/api/autonomy/tick`, `/api/agent/suspend`, `/api/agent/resume` em `bot/dashboard_server_routes_post.py`; overrides `temperature/top_p/agent_paused`; `agent_notes` persistido | `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/multi_channel_focus.test.js`, `bot/tests/test_logic_context.py` | ✅ |
| **8** | Memória semântica operacional por canal | `bot/semantic_memory.py`, `bot/persistence_semantic_memory_repository.py`, `/api/semantic-memory` (`GET/PUT`), integração no `Intelligence Overview` | `bot/tests/test_semantic_memory.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_parity_gate.py`, `dashboard/tests/multi_channel_focus.test.js` | ✅ |
| **9** | Paridade formal backend -> dashboard | `bot/dashboard_parity_gate.py`, `dashboard/tests/api_contract_parity.test.js`, CI em `.github/workflows/ci.yml` | `python -m bot.dashboard_parity_gate`, `node --test dashboard/tests/api_contract_parity.test.js` | ✅ |
| **10** | Saneamento estrutural (anti-espaguete/duplicação) | `bot/dashboard_http_helpers.py`, fatiamento de persistência (repositórios dedicados), `bot/structural_health_gate.py`, CI com C901+R0801 | `python -m bot.structural_health_gate`, `bot/tests/test_structural_health_gate.py` | ✅ |
| **11** | Stream Health Score multi-canal | `bot/stream_health_score.py`, snapshot/histórico com `stream_health`, `/api/sentiment/scores`, render no layout atual | `bot/tests/test_stream_health_score.py`, `bot/tests/test_observability.py`, `dashboard/tests/multi_channel_focus.test.js`, parity gate | ✅ |
| **12** | Post-Stream Intelligence Report | `bot/post_stream_report.py`, `bot/persistence_post_stream_report_repository.py`, `/api/observability/post-stream-report`, geração automática em `part` | `bot/tests/test_post_stream_report.py`, `bot/tests/test_dashboard_routes_v3.py`, `bot/tests/test_dashboard_server_extra.py`, parity gate | ✅ |
| **13** | Goal-Driven Autonomy 2.0 (KPI por sessão) | `bot/control_plane_constants.py`, `bot/control_plane_config_helpers.py`, `bot/control_plane_config.py`, `bot/autonomy_runtime.py`, UI em `dashboard/features/control-plane/view.js` | `bot/tests/test_control_plane_config.py`, `bot/tests/test_control_plane.py`, `bot/tests/test_autonomy_runtime.py`, `dashboard/tests/multi_channel_focus.test.js` | ✅ |
| **14** | Ops Playbooks determinísticos | `bot/ops_playbooks.py`, integração em `bot/control_plane.py` + `bot/autonomy_runtime.py`, rotas `/api/ops-playbooks` e `/api/ops-playbooks/trigger`, UI integrada em `dashboard/features/action-queue/*` + `dashboard/partials/risk_queue.html` | `bot/tests/test_ops_playbooks.py`, `bot/tests/test_control_plane.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_post.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/api_contract_parity.test.js`, `bot/tests/test_dashboard_parity_gate.py` | ✅ |
| **15** | Per-Channel Identity Estruturada | `bot/persistence_channel_identity_repository.py`, facade em `bot/persistence_layer.py`, restore/aplicação em `bot/logic_context.py`, injeção de prompt em `bot/logic_inference.py`, rotas `GET/PUT /api/channel-config` e `GET /api/channel-context` em `bot/dashboard_server_routes.py`, UI integrada no `Control Plane` (`dashboard/partials/control_plane.html`, `dashboard/features/control-plane/view.js`) | `bot/tests/test_persistence_repositories.py`, `bot/tests/test_persistence_layer.py`, `bot/tests/test_logic_context.py`, `bot/tests/test_logic.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`, `dashboard/tests/api_contract_parity.test.js`, `bot/tests/test_structural_health_gate.py`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate` | ✅ |
| **16** | Coaching em tempo real + Viewer Churn Risk | motor determinístico `bot/coaching_churn_risk.py`, runtime antirruído `bot/coaching_runtime.py`, integração no snapshot de observabilidade (`bot/dashboard_server_routes.py`) e render no layout atual (`dashboard/partials/intelligence_panel.html`, `dashboard/features/observability/view.js`, `dashboard/features/hud/view.js`) | `bot/tests/test_coaching_churn_risk.py`, `bot/tests/test_coaching_runtime.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`, `python -m bot.dashboard_parity_gate`, `python -m bot.structural_health_gate` | ✅ |

---

## 3. Rastreabilidade Operacional (Contrato Backend -> UI -> Teste)

| Capability | Backend (endpoint/runtime) | Dashboard (layout atual) | Testes de rastreio |
| :--- | :--- | :--- | :--- |
| Contexto por canal focado | `/api/observability?channel=`, `/api/channel-context`, `/api/observability/history` | `Agent Context & Internals` | `dashboard/tests/multi_channel_focus.test.js`, `bot/tests/test_dashboard_routes_v3.py` |
| Memória semântica | `/api/semantic-memory` (`GET/PUT`) | `Intelligence Overview` | `bot/tests/test_semantic_memory.py`, `bot/tests/test_dashboard_routes.py`, `dashboard/tests/multi_channel_focus.test.js` |
| Stream health score | `/api/sentiment/scores` | `metrics_health`, `intelligence_panel`, `agent_context_internals` | `bot/tests/test_stream_health_score.py`, `dashboard/tests/multi_channel_focus.test.js` |
| Post-stream report | `/api/observability/post-stream-report` (`generate=1`) + auto em `part` | `Intelligence Overview` (mesmo painel) | `bot/tests/test_post_stream_report.py`, `bot/tests/test_dashboard_server_extra.py`, `bot/tests/test_dashboard_routes_v3.py` |
| Coaching churn risk em tempo real | `/api/observability` com bloco `coaching` + emissão HUD via `coaching_runtime` (`source=coaching`) | `Intelligence Overview` + `Streamer HUD` (mesmo layout/painéis atuais) | `bot/tests/test_coaching_churn_risk.py`, `bot/tests/test_coaching_runtime.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js` |
| Goal KPI por sessão | runtime `register_goal_session_result` + telemetria `kpi_met/kpi_missed` | `Control Plane` (editor de goals existente) | `bot/tests/test_control_plane_config.py`, `bot/tests/test_autonomy_runtime.py`, `dashboard/tests/multi_channel_focus.test.js` |
| Identidade estruturada por canal | `channel_identity` via `PersistenceLayer`, `/api/channel-config` (`GET/PUT`) e `/api/channel-context` | `Control Plane` (card `Channel Directives`, sem dashboard paralela) | `bot/tests/test_persistence_repositories.py`, `bot/tests/test_persistence_layer.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_v3.py`, `dashboard/tests/multi_channel_focus.test.js`, `dashboard/tests/api_contract_parity.test.js` |
| Soberania operacional | `/api/autonomy/tick`, `/api/agent/suspend`, `/api/agent/resume` | `Control Plane` + HUD | `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/multi_channel_focus.test.js` |
| Ops playbooks determinísticos | `/api/ops-playbooks` (`GET`) + `/api/ops-playbooks/trigger` (`POST`) + execução em `autonomy_runtime` | `Risk Queue` (mesmo painel/layout atual) | `bot/tests/test_ops_playbooks.py`, `bot/tests/test_dashboard_routes.py`, `bot/tests/test_dashboard_routes_post.py`, `dashboard/tests/api_contract_parity.test.js` |

---

## 4. Backlog Prioritário (Fases Futuras)

1. **Fase 17 - Revenue Attribution Trace:** correlação temporal entre ação do agente e conversão (follow/sub/cheer).
2. **Fase 18 - Outbound Webhook API:** destinos, assinatura/HMAC, retry e observabilidade de entrega.
3. **Fase 19 - Autonomous Clip Suggestion Intelligence:** detecção de momento clipável acoplada ao pipeline já existente.
4. **Evolução futura:** otimização ANN com `pgvector` para memória semântica (escala/performance).

---

## 5. Evidências de Validação (ciclo de auditoria atual)

- `pytest -q --no-cov bot/tests/test_persistence_layer.py bot/tests/test_logic_context.py bot/tests/test_bootstrap_runtime.py bot/tests/test_bootstrap_runtime_v2.py bot/tests/test_bootstrap_runtime_v3.py bot/tests/test_bootstrap_runtime_v4.py bot/tests/test_observability.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py bot/tests/test_dashboard_routes_post.py bot/tests/test_semantic_memory.py bot/tests/test_dashboard_parity_gate.py bot/tests/test_structural_health_gate.py bot/tests/test_stream_health_score.py bot/tests/test_post_stream_report.py bot/tests/test_control_plane_config.py bot/tests/test_control_plane.py bot/tests/test_autonomy_runtime.py`
  **Resultado:** `198 passed, 2 skipped, 4 warnings`.
- `node --test dashboard/tests/api_contract_parity.test.js dashboard/tests/multi_channel_focus.test.js`
  **Resultado:** `20 passed`.
- `python -m bot.dashboard_parity_gate`
  **Resultado:** `ok integrated=21 headless_approved=2`.
- `python -m bot.structural_health_gate`
  **Resultado:** `ok`.
- `ruff check bot/coaching_churn_risk.py bot/coaching_runtime.py bot/dashboard_server_routes.py bot/structural_health_gate.py bot/tests/test_coaching_churn_risk.py bot/tests/test_coaching_runtime.py bot/tests/test_dashboard_routes_v3.py`
  **Resultado:** `All checks passed!`.
- `pytest -q --no-cov bot/tests/test_coaching_churn_risk.py bot/tests/test_coaching_runtime.py bot/tests/test_dashboard_routes_v3.py bot/tests/test_dashboard_routes.py bot/tests/test_structural_health_gate.py`
  **Resultado:** `81 passed`.
- `node --test dashboard/tests/multi_channel_focus.test.js dashboard/tests/api_contract_parity.test.js`
  **Resultado:** `23 passed`.
- `python -m bot.dashboard_parity_gate`
  **Resultado:** `ok integrated=23 headless_approved=2`.
- `python -m bot.structural_health_gate`
  **Resultado:** `ok`.
- `pytest --no-cov bot/tests/test_ops_playbooks.py bot/tests/test_control_plane.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_post.py bot/tests/test_dashboard_routes_v3.py bot/tests/test_dashboard_parity_gate.py bot/tests/test_autonomy_runtime.py`
  **Resultado:** `108 passed, 2 warnings`.
- `node --test dashboard/tests/api_contract_parity.test.js dashboard/tests/multi_channel_focus.test.js`
  **Resultado:** `20 passed`.
- `python -m bot.dashboard_parity_gate`
  **Resultado:** `ok integrated=23 headless_approved=2`.
- `pytest -q --no-cov bot/tests/test_persistence_repositories.py bot/tests/test_persistence_layer.py bot/tests/test_logic_context.py bot/tests/test_logic.py bot/tests/test_dashboard_routes.py bot/tests/test_dashboard_routes_v3.py bot/tests/test_structural_health_gate.py`
  **Resultado:** `148 passed`.
- `node --test dashboard/tests/api_contract_parity.test.js dashboard/tests/multi_channel_focus.test.js`
  **Resultado:** `22 passed`.
- `python -m bot.dashboard_parity_gate`
  **Resultado:** `ok integrated=23 headless_approved=2`.
- `python -m bot.structural_health_gate`
  **Resultado:** `ok`.

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
