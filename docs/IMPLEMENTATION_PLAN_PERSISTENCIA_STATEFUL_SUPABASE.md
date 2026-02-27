# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.8
**Data:** 27 de Fevereiro de 2026
**Status:** FASES 1-4 CONCLUÍDAS ✅ | FASES 5-7 PARCIAIS COM ETAPAS DE PANIC CONTROL E CHANNEL TUNING ENTREGUES | FASE 8 PLANEJADA
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

**Ainda falta**

- Persistir contadores agregados/rollups como fonte de verdade global.
- Reidratar métricas históricas de observabilidade após restart.
- Definir schema claro para dashboards históricos multi-canal.

### Fase 6: Dashboard Integrada (Multi-Channel UI) ⚠️ Parcial

**Já existe**

- Dashboard modular com control plane, fila de risco, clips, observabilidade e HUD.
- Channel manager operacional para `list`, `join`, `part`.
- HUD embutida no painel principal e overlay standalone em `/dashboard/hud`.
- Exposição explícita do overlay OBS na UI principal concluída nesta validação.

**Ainda falta**

- Seletor de canal como contexto primário da dashboard.
- Visualização de histórico persistente por canal vindo do Supabase.
- Visão realmente multi-tenant para comparar ou alternar canais sem depender do runtime default.

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

1. **Dashboard multi-canal de verdade:** seletor de canal + leitura de estado/histórico persistido.
2. **Observabilidade persistente:** armazenar agregados globais para não perder histórico em restart.
3. **Thought injection operacional:** tabela `agent_notes` com leitura segura antes de inferência.
4. **Pause/silence por canal:** descer o controle de soberania do escopo global para escopo de canal.
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
| **Per-channel temperature/top_p** | ✅ | Persistido em `channels_config`, aplicado na inferência e exposto na dashboard |
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

- Etapa entregue: overrides por canal de `temperature` e `top_p`.
- Backend: `PersistenceLayer` passou a salvar/carregar tuning por canal em `channels_config`, com fallback em memória e validação de intervalo.
- Runtime: lazy restore injeta os parâmetros no `StreamContext`, e a inferência passa a respeitar `temperature/top_p` por canal.
- API: novas rotas `GET /api/channel-config` e `PUT /api/channel-config`, com aplicação imediata no contexto carregado.
- Dashboard: control plane ganhou a faixa `Channel Tuning`, mantendo o mesmo padrão visual do layout atual.
- Testes da etapa: suíte focal verde (`94 passed`) e cobertura dos arquivos alterados validada; `bot/dashboard_server_routes.py` ficou em `100%`.

*Plano validado contra o código, incrementado com a etapa implementada e reajustado para execução real.*
