# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.10
**Data:** 27 de Fevereiro de 2026
**Status:** FASES 1-4 CONCLUÍDAS ✅ | FASES 5-7 PARCIAIS COM ETAPAS DE PERSISTENT OBSERVABILITY ROLLUP, PANIC CONTROL, CHANNEL TUNING E DASHBOARD FOCUSED CHANNEL ENTREGUES | FASE 8 PLANEJADA
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

### Fase 5: Observabilidade Stateful (Métricas Globais) ⚠️ Parcial

**Já existe**

- Snapshot operacional robusto via `/api/observability`.
- Registro de mensagens, replies e eventos em persistência.
- Runtime de observabilidade consolidado para health, outcomes e fila.
- Rollup global persistente em `observability_rollups` com save throttled e restore automático no bootstrap do `ObservabilityState`.
- Reidratação pós-restart de counters, routes, timeline, recent events, janelas analíticas, leaderboards e status de clips a partir do rollup persistido.
- Snapshot agora expõe metadados de persistência (`enabled/restored/source/updated_at`) e a dashboard mostra o estado do rollup no topo sem criar layout paralelo.

**Ainda falta**

- Definir schema claro para dashboards históricos multi-canal.
- Estratégia de retenção/compactação para histórico observability de longo prazo fora do rollup operacional.

### Fase 6: Dashboard Integrada (Multi-Channel UI) ⚠️ Parcial

**Já existe**

- Dashboard modular com control plane, fila de risco, clips, observabilidade e HUD.
- Channel manager operacional para `list`, `join`, `part`.
- HUD embutida no painel principal e overlay standalone em `/dashboard/hud`.
- Exposição explícita do overlay OBS na UI principal concluída nesta validação.
- Dashboard agora mantém um `focused channel` persistido em `localStorage` e usa esse canal como contexto primário.
- `/api/observability` passou a aceitar `?channel=` para renderizar o `StreamContext` do canal selecionado.
- Novo `GET /api/channel-context` expõe `runtime context + channel_state + channel_history` para inspeção operacional.
- Painel `Agent Context & Internals` agora mostra snapshot persistido e histórico recente por canal sem inventar uma UI paralela.

**Ainda falta**

- Métricas de observabilidade realmente segregadas por canal; hoje os counters continuam globais e só o contexto/histórico é canalizado.
- Visão realmente multi-tenant para comparar canais lado a lado.

### Fase 7: Soberania e Comando ⚠️ Parcial

**Já existe**

- Control plane com config runtime, budgets, action queue e capabilities.
- `POST /api/autonomy/tick` para disparo manual do loop.
- `POST /api/agent/suspend` e `POST /api/agent/resume` implementados com estado explícito no runtime.
- Bloqueio operacional de auto-chat e agenda automática quando o agente está suspenso.
- Dashboard expõe o `panic suspend` / `resume agent` no mesmo padrão visual do control plane atual.
- HUD streamer como trilha paralela de resposta tática.
- Override por canal de `temperature` e `top_p` persistido em `channels_config`.
- Inferência aplica override por canal restaurado do estado persistido.
- Dashboard expõe `Channel Tuning` no painel operacional existente.

**Ainda falta**

- Persistência de notas operacionais (`agent_notes`) para thought injection.
- Pause/silence por canal, não apenas configuração global de runtime.

### Fase 8: Gestão de Memória Semântica (Vector Memory) ❌ Não implementada

- Não há integração `pgvector` no código atual.
- Não existe interface de dashboard para inspeção/edição de memória semântica.
- Deve permanecer como fase futura, separada do escopo operacional imediato.

---

## 3. Backlog Prioritário Real

1. **Thought injection operacional:** tabela `agent_notes` com leitura segura antes de inferência.
2. **Pause/silence por canal:** descer o controle de soberania do escopo global para escopo de canal.
3. **Métricas per-channel reais:** sair do snapshot global e produzir counters/leaderboards isolados por canal.
4. **Dashboards históricos multi-canal:** modelar views persistidas além do rollup global único.
5. **Vector memory:** deixar explicitamente fora do caminho crítico do dashboard operacional.

---

## 4. Matriz Atual de Controles

| Controle | Status no código | Observação |
| :--- | :--- | :--- |
| **Channel join/part/list** | ✅ | Runtime IRC + dashboard |
| **Action queue approve/reject** | ✅ | Fluxo operacional ativo |
| **Manual Tick** | ✅ | `/api/autonomy/tick` |
| **Streamer HUD** | ✅ | Embutida + overlay standalone |
| **Panic Suspend/Resume** | ✅ | Backend + dashboard + bloqueio operacional implementados |
| **Persistent global observability rollup** | ✅ | `observability_rollups` + restore automático + chip de status na dashboard |
| **Per-channel temperature/top_p** | ✅ | Persistido em `channels_config`, aplicado na inferência e exposto na dashboard |
| **Dashboard focused channel + persisted context** | ✅ | Selector persistido, `/api/observability?channel=` e `/api/channel-context` |
| **Thought Injection (`agent_notes`)** | ❌ | Ainda não implementado |
| **Vector Memory** | ❌ | Ainda não implementado |

---

## 5. Conclusão

O plano anterior estava correto no direcionamento, mas subestimava o que já foi entregue e misturava itens já implementados com itens ainda futuros. O estado real em 27/02/2026 é:

- base stateful funcional;
- boot dinâmico por `channels_config` funcional;
- dashboard operacional funcional;
- HUD standalone funcional e agora exposta na dashboard;
- soberania avançada ainda incompleta;
- memória vetorial ainda fora do escopo implementado.

### Fechamento da Etapa Atual

- Etapa entregue: observabilidade persistente via rollup global restaurável.
- Backend: `PersistenceLayer` agora lê/escreve `observability_rollups`, e o `ObservabilityState` serializa/restaura o estado interno relevante com flush throttled e flush forçado em `snapshot()`.
- Runtime: restart do processo preserva counters agregados, routes, timeline de 30 min, recent events, leaderboards/janelas analíticas e status de clips a partir do último rollup salvo.
- Dashboard: o topo ganhou um chip de estado do rollup (`Rollup Restored`, `Rollup Live`, `Volatile Only`) reaproveitando o layout já existente.
- Escopo validado: esta etapa fecha a perda de métricas globais em restart, mas ainda não resolve histórico multi-canal comparativo nem métricas realmente segregadas por canal.
- Testes da etapa: suíte focal Python verde (`69 passed`), suíte `node:test` da dashboard verde, `bot/observability_state.py` em `100%` de cobertura e novos ramos de `bot/persistence_layer.py` exercitados para success/fallback/error.

*Plano validado contra o código, incrementado com a etapa implementada e reajustado para execução real.*
