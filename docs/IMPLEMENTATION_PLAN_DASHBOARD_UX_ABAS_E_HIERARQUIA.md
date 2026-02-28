# IMPLEMENTATION PLAN - Dashboard UX em Abas e Hierarquia

Data: 2026-02-27
Status: concluido (fases 1-6 entregues)
Escopo: frontend dashboard (`dashboard/`) sem mudanca de contrato de API

## 1) Diagnostico atual (baseado no codigo)

Estado atual em `dashboard/index.html`:

- A pagina injeta 7 partials em sequencia dentro de `.layout`:
  - `heroChannelContainer`
  - `metricsHealthContainer`
  - `controlPlaneContainer`
  - `intelligencePanelContainer`
  - `clipsSectionContainer`
  - `riskQueueContainer`
  - `analyticsLogsContainer`
- Resultado: scroll muito longo, sem navegacao por contexto de tarefa.

Acoplamentos que nao podem quebrar:

- `dashboard/main.js` inicializa todos os controllers no bootstrap e inicia 4 pollers.
- `dashboard/features/*/view.js` depende de IDs especificos (`document.getElementById(...)`).
- Reorganizacao visual deve preservar IDs e contratos de eventos existentes.

## 2) Objetivo de UX

Reduzir carga cognitiva e criar hierarquia operacional com abas:

- juntar o que e usado junto na mesma tarefa;
- separar configuracao profunda de operacao ao vivo;
- manter "contexto global de canal" visivel em qualquer aba.

## 3) Arquitetura de informacao proposta

### 3.1 Regiao global fixa (sempre visivel)

- Topbar atual (brand, connection chips).
- "Canal ativo e conexoes" do `hero_channel.html` (compactado).
- Resumo rapido: `Risk Queue pending`, `Stream Health`, `Autonomy`.

### 3.2 Abas principais

1. `Operacao` (default)

- `Risk Queue` + `Ops Playbooks`.
- `Autonomy Runtime` (acoes de tick e telemetria operacional).
- `Operational Events` (feed de eventos).
- KPIs criticos (cards principais de saude/erros/latencia).

2. `Inteligencia`

- `Streamer HUD`.
- `Intelligence Overview`.
- `Post-Stream Report`.
- `Semantic Memory`.
- `Revenue Attribution`.

3. `Clips & Vision`

- `Clips Pipeline`.
- `Autonomous Vision` (ingest, status, analise de cena).

4. `Analytics`

- `Timeline Logs Realtime`.
- `Deep Analytics (60m)`.
- `Top Chatters/Triggers/Lifetime`.
- `Persisted Snapshot`, `Persisted History`, `Persisted Timeline`, `Multi-Channel Comparison`.

5. `Configuracao`

- `Control Plane` (autonomia, budget, cooldowns, webhooks, goals).
- `Channel Directives`, `Channel Identity`, `Agent Notes`.

## 4) Mapa de migracao (origem -> destino)

| Origem atual                            | Destino                                                  |
| --------------------------------------- | -------------------------------------------------------- |
| `hero_channel.html`                     | Regiao global fixa                                       |
| `metrics_health.html`                   | `Operacao` (cards criticos) + `Analytics` (cards densos) |
| `control_plane.html` (Control Plane)    | `Configuracao`                                           |
| `control_plane.html` (Autonomy Runtime) | `Operacao`                                               |
| `intelligence_panel.html`               | `Inteligencia`                                           |
| `clips_section.html`                    | `Clips & Vision`                                         |
| `risk_queue.html`                       | `Operacao`                                               |
| `analytics_logs.html`                   | `Analytics`                                              |

## 5) Fases de implementacao

### Fase 1 - Shell de abas (sem mover logica)

- Adicionar nav de abas no `index.html` abaixo da regiao global.
- Criar containers por aba (`data-tab-panel`) mantendo partials/IDs intactos.
- Implementar `dashboard/features/navigation/tabs.js` (state, troca de aba, persistencia em `localStorage`).

Entrega:

- Dashboard com abas funcionais, sem alteracao de endpoints.

### Fase 2 - Re-housing de secoes por dominio

- Reposicionar blocos atuais para os novos containers de aba.
- Preservar IDs originais para nao quebrar controllers.
- Garantir que secao oculta nao remove elemento do DOM (usar `hidden`/classe, nao `innerHTML` dinamico).

Entrega:

- Conteudo agrupado por tarefa, sem regressao funcional.

### Fase 3 - Hierarquia visual e densidade

- Criar "summary strip" global com 3-5 sinais operacionais.
- Reduzir ruido textual e padronizar titulos/subtitulos por aba.
- Mover informacoes secundarias para `details`/accordion dentro de cada aba.

Entrega:

- Menos scroll por tarefa e leitura mais rapida em live.

### Fase 4 - Responsividade por abas

- Mobile/tablet: barra de abas horizontal com scroll e alvo de toque >= 44px.
- Desktop: abas fixas no topo da area de conteudo.
- Garantir que tabelas longas continuam com `overflow-x` controlado.

Entrega:

- Navegacao por aba utilizavel em desktop e mobile.

### Fase 5 - Hardening e rollout

- Ajustar smoke tests da dashboard para a nova estrutura.
- Adicionar testes de comportamento de abas (persistencia, aria, visibilidade).
- Checklist manual de regressao para pollers e acoes criticas.

Entrega:

- Feature pronta para merge.

### Fase 6 - Deep-link e restauracao de aba via URL

- Sincronizar aba ativa com query param `?tab=` usando `history.replaceState`.
- Priorizar `?tab=` sobre `localStorage` na definicao da aba inicial.
- Preservar demais query params (ex.: `channel`) e `hash` ao trocar de aba.
- Manter fallback atual: sem `?tab=`, restaurar por `localStorage`.

Entrega:

- Navegacao por abas compartilhavel por URL, sem regressao de comportamento existente.

## 6) Regras de nao regressao

- Nao alterar contratos de API (`/api/observability`, `/api/channel-control`, etc.).
- Nao renomear IDs usados por `get...Elements()` sem camada de compatibilidade.
- Nao parar pollers por troca de aba.
- Nao duplicar inicializacao de controllers.
- Nao criar "tela paralela": tudo continua dentro da dashboard atual.

## 7) Estrategia de testes para a execucao

Novos testes (dashboard):

- `tabs_navigation.test.js`: troca de aba, aba default, persistencia em `localStorage`.
- `tabs_a11y.test.js`: `aria-selected`, `aria-controls`, navegacao por teclado.
- `tabs_visibility_contract.test.js`: secoes ocultas continuam no DOM para controllers.

Ajustes de testes existentes:

- `dashboard/tests/multi_channel_focus.test.js`: adaptar fixtures para shell de abas.
- `dashboard/tests/api_contract_parity.test.js`: manter verde (nao deve sofrer regressao).

Validacao minima por fase:

- `npm test -- dashboard/tests/<arquivo>.test.js` (focado por arquivo).
- No fechamento da fase de UX: rodar suite de dashboard inteira.

## 8) Criterios de aceite (DoD)

- A pagina deixa de ser "scroll unico" e passa a ter navegacao por abas.
- Operacao ao vivo fica concentrada na aba `Operacao`.
- Configuracao profunda fica isolada na aba `Configuracao`.
- Intelligence, Clips e Analytics ficam separados e coerentes.
- Nenhuma acao operacional atual perde funcionalidade.
- Testes de dashboard ficam verdes apos migracao.

## 9) Progresso executado

### 2026-02-27 - Fase 1 concluida (shell de abas)

- Implementado nav de abas em `dashboard/index.html` com `role=tablist`, `role=tab` e `role=tabpanel`.
- Estrutura por paineis criada sem remover IDs existentes dos partials:
  - `operation`: metrics + risk queue
  - `intelligence`: intelligence panel
  - `clips`: clips section
  - `analytics`: analytics logs
  - `config`: control plane
- Módulo novo: `dashboard/features/navigation/tabs.js` (click, teclado, persistencia em `localStorage`).
- Bootstrap atualizado em `dashboard/main.js` para inicializar abas no carregamento.
- Estilo integrado em `dashboard/styles/layout.css` mantendo tokens e linguagem visual atual.
- Testes novos: `dashboard/tests/tabs_navigation.test.js`.
- Validacao executada:
  - `npx prettier --check dashboard/index.html dashboard/main.js dashboard/styles/layout.css dashboard/features/navigation/tabs.js dashboard/tests/tabs_navigation.test.js`
  - `node --test dashboard/tests/tabs_navigation.test.js dashboard/tests/multi_channel_focus.test.js dashboard/tests/api_contract_parity.test.js`

### 2026-02-27 - Fase 2 concluida (re-housing por dominio)

- Aba `Operacao` consolidada com:
  - `metrics_health`
  - `risk_queue`
  - `autonomy_runtime`
  - `operational_events`
- Aba `Configuracao` isolada com `control_plane` (sem `Autonomy Runtime`).
- `control_plane.html` foi reduzido para manter apenas `cpPanel` e IDs de configuracao.
- `analytics_logs.html` foi reduzido para foco analitico (sem `eventsList`).
- Novos partials:
  - `dashboard/partials/autonomy_runtime.html`
  - `dashboard/partials/operational_events.html`
- Teste novo:
  - `dashboard/tests/layout_partial_mapping.test.js` (contrato de containers + mapeamento de partials + ownership de IDs).
- Validacao executada:
  - `npx prettier --check dashboard/index.html dashboard/partials/control_plane.html dashboard/partials/autonomy_runtime.html dashboard/partials/analytics_logs.html dashboard/partials/operational_events.html dashboard/tests/layout_partial_mapping.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 3 concluida (hierarquia visual e densidade)

- Summary strip global integrado em `dashboard/index.html` com sinais operacionais:
  - canal focado + runtime/persistencia;
  - stream health (score + banda);
  - risco pendente (fila);
  - estado/autonomia e budget 60m.
- Intro por aba adicionada com hierarquia semantica (`dashboard-tab-intro`) para reduzir ruido e orientar tarefa.
- Densidade reduzida com disclosure progressivo:
  - `dashboard/partials/metrics_health.html`: blocos `agentHealthCards` e `agentOutcomeCards` movidos para `details.advanced-settings`.
  - `dashboard/partials/analytics_logs.html`: snapshot/historico/timeline/comparativo persistidos movidos para `details.advanced-settings`.
- Renderizacao real conectada no summary strip:
  - `dashboard/features/observability/view.js`
  - `dashboard/features/action-queue/view.js`
  - `dashboard/features/autonomy/view.js`
- Testes novos:
  - `dashboard/tests/layout_hierarchy_density.test.js`
  - `dashboard/tests/summary_strip_runtime.test.js`
- Validacao executada:
  - `npx prettier --check dashboard/index.html dashboard/partials/metrics_health.html dashboard/partials/analytics_logs.html dashboard/features/observability/view.js dashboard/features/action-queue/view.js dashboard/features/autonomy/view.js dashboard/tests/layout_hierarchy_density.test.js dashboard/tests/summary_strip_runtime.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 4 concluida (responsividade por abas)

- Navegacao por abas reforcada para tablet/mobile em `dashboard/styles/layout.css`:
  - breakpoint `@media (max-width: 1024px)` com barra horizontal, `overflow-x: auto` e scroll touch.
  - alvo de toque padronizado com `min-height: 44px` em `dashboard-tab-btn`.
  - `scroll-snap` leve para melhorar navegacao horizontal em dispositivos menores.
- Contrato de overflow horizontal de tabelas validado:
  - `.table-wrap { overflow-x: auto; }` em `dashboard/styles/components.css`.
  - cobertura automatizada para garantir wrapper de tabelas em partials.
- Testes novos:
  - `dashboard/tests/tabs_responsiveness_contract.test.js`
  - `dashboard/tests/tables_overflow_contract.test.js`
- Validacao executada:
  - `npx prettier --check dashboard/styles/layout.css dashboard/tests/tabs_responsiveness_contract.test.js dashboard/tests/tables_overflow_contract.test.js`
  - `node --test dashboard/tests/tabs_responsiveness_contract.test.js dashboard/tests/tables_overflow_contract.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 5 concluida (hardening e rollout)

- Hardening no modulo de abas `dashboard/features/navigation/tabs.js`:
  - inicializacao idempotente por `document` (evita listeners duplicados em reinit);
  - atualizacao de `aria-hidden` nos `tabpanel` junto com `hidden`.
- Testes novos de fase:
  - `dashboard/tests/tabs_a11y.test.js`:
    - contrato de markup (`role=tab`, `aria-controls`, `role=tabpanel`, `aria-labelledby`);
    - comportamento teclado (`Arrow`, `Home`, `End`);
    - sincronizacao de `aria-selected` e `aria-hidden`;
    - garantia de init idempotente.
  - `dashboard/tests/tabs_visibility_contract.test.js`:
    - visibilidade por `hidden` sem remover containers do DOM;
    - contrato de unicidade de IDs de containers por painel.
- Checklist de regressao operacional validado:
  - pollers continuam iniciados no bootstrap (`observability`, `action queue`, `clips`, `hud`);
  - troca de aba nao interfere no ciclo de controllers (sem unmount/remount dinamico);
  - contratos de API e fluxos criticos seguem verdes via suite de dashboard.
- Validacao executada:
  - `npx prettier --check dashboard/features/navigation/tabs.js dashboard/tests/tabs_a11y.test.js dashboard/tests/tabs_visibility_contract.test.js docs/IMPLEMENTATION_PLAN_DASHBOARD_UX_ABAS_E_HIERARQUIA.md`
  - `node --test dashboard/tests/tabs_a11y.test.js dashboard/tests/tabs_visibility_contract.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 6 concluida (deep-link de abas via URL)

- Modulo de navegacao de abas atualizado em `dashboard/features/navigation/tabs.js` para:
  - ler aba inicial de `?tab=`;
  - priorizar query param sobre estado persistido em `localStorage`;
  - sincronizar troca de aba em URL com `history.replaceState`;
  - preservar query params existentes e `hash`.
- API de inicializacao ampliada com `locationRef` e `historyRef` para suporte testavel sem acoplamento ao `window`.
- Testes novos em `dashboard/tests/tabs_navigation.test.js`:
  - prioridade de `?tab=` sobre storage;
  - sincronizacao de URL mantendo params existentes.
- Validacao executada:
  - `npx prettier --check dashboard/features/navigation/tabs.js dashboard/tests/tabs_navigation.test.js`
  - `node --test dashboard/tests/tabs_navigation.test.js`
  - `node --test dashboard/tests/*.test.js`
