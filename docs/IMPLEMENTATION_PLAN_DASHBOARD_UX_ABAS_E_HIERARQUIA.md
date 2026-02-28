# IMPLEMENTATION PLAN - Dashboard UX em Abas e Hierarquia

Data: 2026-02-27
Status: em execucao
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

| Origem atual | Destino |
| --- | --- |
| `hero_channel.html` | Regiao global fixa |
| `metrics_health.html` | `Operacao` (cards criticos) + `Analytics` (cards densos) |
| `control_plane.html` (Control Plane) | `Configuracao` |
| `control_plane.html` (Autonomy Runtime) | `Operacao` |
| `intelligence_panel.html` | `Inteligencia` |
| `clips_section.html` | `Clips & Vision` |
| `risk_queue.html` | `Operacao` |
| `analytics_logs.html` | `Analytics` |

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
