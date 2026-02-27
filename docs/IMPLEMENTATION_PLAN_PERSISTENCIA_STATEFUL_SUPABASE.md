# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.15
**Data:** 27 de Fevereiro de 2026
**Status:** FASES 1-7 CONCLUÍDAS ✅ (INCLUINDO HISTÓRICO PERSISTIDO + COMPARAÇÃO MULTI-CANAL NA DASHBOARD OPERACIONAL) | FASE 8 PLANEJADA | FASE 9 EM EXECUÇÃO (CONTRATO DE PARIDADE BACKEND -> DASHBOARD COM DISCOVERY DE LAYOUT APLICADO)
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

### Fase 9: Paridade Backend -> Dashboard (Contrato de Integração Visual) 🆕 Planejada

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

---

## 3. Backlog Prioritário Real

1. **Fase 9 (paridade backend -> dashboard):** transformar o contrato em gate formal de review/release com checklist obrigatório.
2. **Matriz de cobertura visual por capability:** consolidar e manter rastreabilidade backend -> painel UI -> teste.
3. **Vector memory:** deixar explicitamente fora do caminho crítico do dashboard operacional.

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
| **Observability per-channel real** | ✅ | `channel_scopes` no rollup (schema v2) + snapshot isolado por canal |
| **Per-channel temperature/top_p** | ✅ | Persistido em `channels_config`, aplicado na inferência e exposto na dashboard |
| **Pause/Silence por canal (`agent_paused`)** | ✅ | Persistido em `channels_config`, aplicado no runtime e respeitado no prompt/autonomia |
| **Dashboard focused channel + persisted context** | ✅ | Selector persistido, `/api/observability?channel=` e `/api/channel-context` |
| **Histórico persistido + comparativo multi-canal na observabilidade** | ✅ | `observability_channel_history` + `/api/observability/history` + tabelas no painel `Agent Context & Internals` |
| **Thought Injection (`agent_notes`)** | ✅ | Persistido em `agent_notes`, restaurado no contexto, injetado com sanitização na inferência e exposto na dashboard |
| **Contrato backend -> dashboard (paridade visual por capability)** | ⚠️ | Fase 9 planejada para virar gate obrigatório de entrega operacional |
| **Vector Memory** | ❌ | Ainda não implementado |

---

## 5. Conclusão

O plano anterior estava correto no direcionamento, mas subestimava o que já foi entregue e misturava itens já implementados com itens ainda futuros. O estado real em 27/02/2026 é:

- base stateful funcional;
- boot dinâmico por `channels_config` funcional;
- dashboard operacional funcional;
- HUD standalone funcional e agora exposta na dashboard;
- observabilidade per-channel real entregue no backend da dashboard operacional;
- dashboards históricos multi-canal e comparativo por canal entregues no painel operacional existente;
- soberania por canal já cobre tuning + notes + pause/silence;
- contrato formal de paridade backend -> dashboard agora está em execução com discovery de layout aplicado;
- memória vetorial ainda fora do escopo implementado.

### Fechamento da Etapa Atual

- Etapa entregue: visão histórica/multi-canal na dashboard (timeline persistida por canal + comparativo lado a lado).
- Discovery de layout: integração planejada e executada no painel `Agent Context & Internals`, preservando layout e componentes atuais.
- Backend (`observability_state.py` + `persistence_layer.py`): flush agora grava snapshots históricos por canal; novo suporte de leitura/consulta para histórico persistido.
- API (`dashboard_server_routes.py`): novo `GET /api/observability/history` com timeline por canal focado e comparação entre canais.
- Dashboard (`dashboard/features/observability/*` + `dashboard/partials/analytics_logs.html`): novas tabelas de timeline/comparação renderizadas no fluxo existente, sem UI paralela.
- Escopo validado: backlog de histórico persistido e comparação multi-canal da fase 6 foi concluído.
- Testes da etapa: suíte focal Python verde (`95 passed`, `--no-cov`) e suíte `node:test` da dashboard verde para o fluxo multi-channel.

*Plano validado contra o código, incrementado com a etapa implementada e reajustado para execução real.*
