# IMPLEMENTATION PLAN - Dashboard UX em Abas e Hierarquia

Data: 2026-02-27
Status: em evolucao (fases 1-12 concluidas; fase 14 em progresso; fase 13 planejada)
Escopo: frontend dashboard (`dashboard/`) sem mudanca de contrato de API
Diretriz global: padronizacao da linguagem da UI em ingles (en-US), sem mistura PT-BR/EN em labels e fluxos visuais; conteudo de prompt pode permanecer em portugues para rollout nacional.

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
- padronizar toda a linguagem da interface em ingles (en-US), incluindo tabs, headers, hints, status e estados vazios.
- manter textos de prompt editaveis/localizaveis, com PT-BR permitido quando fizer sentido operacional.

## 3) Arquitetura de informacao proposta

### 3.1 Regiao global fixa (sempre visivel)

- Topbar atual (brand, connection chips).
- "Canal ativo e conexoes" do `hero_channel.html` (compactado).
- Resumo rapido: `Risk Queue pending`, `Stream Health`, `Autonomy`.

### 3.2 Abas principais

1. `Operation` (default)

- `Risk Queue` + `Ops Playbooks`.
- `Autonomy Runtime` (acoes de tick e telemetria operacional).
- `Operational Events` (feed de eventos).
- KPIs criticos (cards principais de saude/erros/latencia).

2. `Intelligence`

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

5. `Configuration`

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

### Fase 7 - Integracao com historico do navegador (back/forward)

- Sincronizar aba ativa quando o usuario navegar com `back/forward` (`popstate`).
- Atualizar somente estado visual + persistencia local nesse fluxo (sem reescrever URL).
- Manter comportamento estavel quando o `?tab=` recebido no `popstate` ja for a aba ativa.

Entrega:

- Navegacao de abas consistente com historico do browser.

### Fase 8 - Regressao cientifica (matriz de invariantes)

- Adicionar suite deterministica de regressao com sequencias multi-passo de navegacao.
- Validar invariantes a cada transicao:
  - exatamente uma aba ativa (`aria-selected=true`, `tabIndex=0`);
  - exatamente um painel visivel (`hidden=false`, `aria-hidden=false`);
  - coerencia entre estado visual, `localStorage`, URL e historico.
- Cobrir cenarios invalidos de `?tab=` (bootstrap e `popstate`) sem degradar estado valido existente.

Entrega:

- Protecao forte contra regressao comportamental da UX em abas.

### Fase 9 - Ergonomia de navegacao horizontal (auto-reveal da aba ativa)

- Garantir que a aba ativa seja trazida para visibilidade no tablist horizontal (mobile/tablet) com `scrollIntoView`.
- Cobrir ativacoes por bootstrap (`?tab=`), clique/teclado e `popstate`.
- Manter opcao de desligar reveal em ativacao imperativa para cenarios controlados de teste/integração.

Entrega:

- Descoberta da aba ativa consistente em navegacao horizontal, sem regressao do fluxo atual.

### Fase 10 - Sub-hierarquia interna da aba Inteligencia

- Reorganizar `intelligence_panel.html` em blocos operacionais claros:
  - `Coaching Tatico`
  - `Post-Stream Report`
  - `Semantic Memory`
  - `Revenue Attribution`
- Mover blocos secundarios para `details.advanced-settings` quando nao forem acao primaria de live.
- Reduzir ruido visual por separadores repetidos (`hr`) e padronizar titulos/descricao por bloco.

Entrega:

- Aba `Inteligencia` com fluxo escaneavel e decisao mais rapida sem perda de funcionalidade.

### Fase 11 - Densidade e governanca no Control Plane

- Quebrar `control_plane.html` em secoes de governanca com disclosure progressivo:
  - `Operational Control`
  - `Channel Directives`
  - `Identity + Agent Notes`
  - `Goals Scheduler`
  - `Advanced Budget/Cooldowns/Webhooks`
- Padronizar hint/status chips para reduzir carga de leitura.
- Preservar todos os IDs e contratos de controller.

Entrega:

- Aba `Configuracao` mais legivel para operacao sob pressao e manutencao sem regressao.

### Fase 12 - Refino de Analytics para leitura orientada a decisao

- Criar camada de "quick insight" no topo da aba `Analytics` (sinais chave antes das tabelas densas).
- Separar claramente:
  - contexto/runtime;
  - timeline realtime;
  - historico persistido/comparativo.
- Manter tabelas densas acessiveis, mas com prioridade visual secundarizada.

Entrega:

- Aba `Analytics` com menor custo cognitivo para diagnostico rapido.

### Fase 13 - Consolidacao visual (remocao de estilos inline)

- Extrair estilos inline para classes CSS reutilizaveis em `layout.css`/`components.css`.
- Padronizar composicoes repetidas (`form-row`, blocos de status, cards internos) com tokens existentes.
- Reduzir variacao visual ad-hoc para melhorar consistencia de UX e manutencao.

Entrega:

- Dashboard com linguagem visual consistente e menor debito tecnico de markup.

### Fase 14 - Coerencia semantica, UI em ingles e resiliencia responsiva

- Padronizar idioma da UI em ingles (en-US) e ajustar `lang="en"` no shell.
- Traduzir labels/titulos/hints/status chips/empty states para ingles sem quebrar IDs e contratos.
- Preservar conteudo de prompts operacionalmente localizavel (PT-BR permitido).
- Eliminar offsets sticky hardcoded quando possivel, usando variavel de layout ou medicao robusta.
- Garantir foco/teclado e leitura sem ambiguidade em navegacao por abas e controles criticos.

Entrega:

- UX mais intuitiva e resiliente em desktop/mobile, com semantica consistente e linguagem unificada em ingles.

## 6) Regras de nao regressao

- Nao alterar contratos de API (`/api/observability`, `/api/channel-control`, etc.).
- Nao renomear IDs usados por `get...Elements()` sem camada de compatibilidade.
- Nao parar pollers por troca de aba.
- Nao duplicar inicializacao de controllers.
- Nao criar "tela paralela": tudo continua dentro da dashboard atual.
- Nao introduzir novas strings visuais de UI em PT-BR; textos novos de interface devem ser ingles (en-US).
- Conteudo de prompt (ex.: goals/instrucoes) pode permanecer em PT-BR quando necessario para operacao local.

## 7) Estrategia de testes para a execucao

Novos testes (dashboard):

- `tabs_navigation.test.js`: troca de aba, aba default, persistencia em `localStorage`.
- `tabs_a11y.test.js`: `aria-selected`, `aria-controls`, navegacao por teclado.
- `tabs_visibility_contract.test.js`: secoes ocultas continuam no DOM para controllers.

Ajustes de testes existentes:

- `dashboard/tests/multi_channel_focus.test.js`: adaptar fixtures para shell de abas.
- `dashboard/tests/api_contract_parity.test.js`: manter verde (nao deve sofrer regressao).

Novos testes planejados para fases 10-14:

- `dashboard/tests/intelligence_hierarchy_contract.test.js`: estrutura e disclosure da aba `Inteligencia`.
- `dashboard/tests/control_plane_information_density.test.js`: agrupamento, ordem e contratos de IDs no `Control Plane`.
- `dashboard/tests/analytics_information_architecture.test.js`: prioridade visual e separacao de dominio em `Analytics`.
- `dashboard/tests/dashboard_style_consolidation_contract.test.js`: reducao/control de `style=""` inline em shell/partials.
- `dashboard/tests/dashboard_semantic_consistency.test.js`: consistencia de idioma (ingles), semantica e comportamento sticky responsivo.

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

DoD adicional do ciclo de refinamento UX (fases 10-14):

- Fluxos de decisao primaria (live ops) aparecem antes de configuracoes secundarias em cada aba.
- `Inteligencia` e `Configuracao` deixam de concentrar blocos longos sem sub-hierarquia.
- Reducao mensuravel de estilos inline nos partials.
- Sem regressao de contratos de API, IDs e pollers.
- Interface final sem mistura de idiomas na camada visual: tabs e textos operacionais de UI em ingles (en-US), com prompts podendo permanecer em PT-BR.

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

### 2026-02-28 - Fase 7 concluida (historico back/forward)

- Modulo de abas `dashboard/features/navigation/tabs.js` atualizado com listener de `popstate`:
  - leitura de `?tab=` na URL ao navegar no historico;
  - troca de aba sem `history.replaceState` (evita loop/rewrite de URL);
  - persistencia da aba restaurada no `localStorage`.
- API de inicializacao ampliada com `eventTargetRef` para teste deterministico do fluxo de historico.
- Teste novo em `dashboard/tests/tabs_navigation.test.js`:
  - back/forward (`popstate`) atualiza aba ativa e paineis sem side-effect de rewrite na URL.
- Validacao executada:
  - `npx prettier --check dashboard/features/navigation/tabs.js dashboard/tests/tabs_navigation.test.js docs/IMPLEMENTATION_PLAN_DASHBOARD_UX_ABAS_E_HIERARQUIA.md`
  - `node --test dashboard/tests/tabs_navigation.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 8 concluida (regressao cientifica)

- Robustez de inicializacao em `dashboard/features/navigation/tabs.js`:
  - `?tab=` invalido nao sobrepoe estado valido de `localStorage`/markup;
  - `popstate` com `?tab=` ausente/invalido e ignorado (sem troca espuria de aba).
- Nova suite de regressao em `dashboard/tests/tabs_regression_matrix.test.js`:
  - fallback de bootstrap com URL invalida + storage valido;
  - protecao de estado em `popstate` invalido/ausente;
  - matriz deterministica multi-passo com invariantes de `aria`, visibilidade, URL, historico e persistencia.
- Validacao executada:
  - `npx prettier --check dashboard/features/navigation/tabs.js dashboard/tests/tabs_navigation.test.js dashboard/tests/tabs_regression_matrix.test.js docs/IMPLEMENTATION_PLAN_DASHBOARD_UX_ABAS_E_HIERARQUIA.md`
  - `node --test dashboard/tests/tabs_navigation.test.js dashboard/tests/tabs_regression_matrix.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 9 concluida (ergonomia de navegacao horizontal)

- Modulo de abas `dashboard/features/navigation/tabs.js` atualizado para revelar a aba ativa via `scrollIntoView`:
  - aplicado na ativacao normal, bootstrap por URL e fluxo de `popstate`;
  - fallback seguro para ambientes sem suporte completo;
  - opcao `reveal: false` mantida para controle imperativo quando necessario.
- Cobertura nova em `dashboard/tests/tabs_navigation.test.js`:
  - reveal no bootstrap com `?tab=`;
  - reveal em troca por clique e restauracao via `popstate`;
  - desativacao explicita de reveal na API imperativa.
- Validacao executada:
  - `npx prettier --check dashboard/features/navigation/tabs.js dashboard/tests/tabs_navigation.test.js docs/IMPLEMENTATION_PLAN_DASHBOARD_UX_ABAS_E_HIERARQUIA.md`
  - `node --test dashboard/tests/tabs_navigation.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 10 concluida (sub-hierarquia em Inteligencia)

- `dashboard/partials/intelligence_panel.html` reorganizado com blocos operacionais explicitos:
  - `Tactical Coaching` (fluxo primario de live visivel);
  - `Post-Stream Report`;
  - `Semantic Memory`;
  - `Revenue Attribution`.
- Blocos secundarios movidos para disclosure progressivo com `details.advanced-settings`:
  - summary `Post-Live Intelligence Tools`;
  - mantendo contratos de IDs usados por `dashboard/features/observability/*`.
- Reducao de ruido visual:
  - separadores `hr` removidos da aba `Intelligence`;
  - estrutura por secoes com headings consistentes por bloco.
- Cobertura nova:
  - `dashboard/tests/intelligence_hierarchy_contract.test.js`
    - garante ordem dos blocos operacionais;
    - garante ausencia de `hr` repetitivo;
    - garante unicidade e preservacao de IDs criticos;
    - garante que fluxos secundarios fiquem dentro de disclosure.
- Validacao executada:
  - `npx prettier --check dashboard/partials/intelligence_panel.html dashboard/tests/intelligence_hierarchy_contract.test.js docs/IMPLEMENTATION_PLAN_DASHBOARD_UX_ABAS_E_HIERARQUIA.md`
  - `node --test dashboard/tests/intelligence_hierarchy_contract.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 11 concluida (densidade e governanca no Control Plane)

- `dashboard/partials/control_plane.html` reorganizado por dominios de governanca:
  - `Operational Control`;
  - `Channel Directives`;
  - `Identity + Agent Notes` (progressive disclosure);
  - `Goals Scheduler`;
  - `Advanced Budget, Cooldowns and Webhooks` (progressive disclosure).
- Contratos de IDs preservados para controllers existentes em `dashboard/features/control-plane/view.js` e fluxos associados.
- Cobertura nova:
  - `dashboard/tests/control_plane_information_density.test.js`
    - valida ordem/hierarquia dos blocos de governanca;
    - valida exatamente dois blocos `details.advanced-settings`;
    - valida mapeamento de IDs criticos para os blocos corretos;
    - valida unicidade de IDs de acoes principais.
- Validacao executada:
  - `npx prettier --write dashboard/partials/control_plane.html dashboard/tests/control_plane_information_density.test.js`
  - `node --test dashboard/tests/control_plane_information_density.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Fase 12 concluida (analytics orientado a decisao)

- `dashboard/partials/analytics_logs.html` reorganizado com separacao clara por dominio:
  - `Analytics Decision Brief` no topo (quick insights antes de tabelas densas);
  - `Runtime Context` e `Timeline Logs Realtime` no mesmo bloco operacional;
  - `Deep Analytics` e leaderboards em bloco intermediario;
  - historico persistido/multi-canal isolado em `Persisted History and Comparison` com disclosure progressivo.
- `dashboard/features/observability/view.js` atualizado para renderizar sinais reais de decisao no topo:
  - foco de canal, runtime/persistencia, stream health, ignored rate, mpm, trigger rate, custo e erros;
  - hint dinamico orientado a risco operacional.
- Cobertura nova e ampliada:
  - `dashboard/tests/analytics_information_architecture.test.js`
    - valida hierarquia deterministica da aba `Analytics`;
    - valida separacao por blocos (`quick`, `runtime`, `diagnostics`, `persisted`);
    - valida contratos de IDs nos blocos corretos.
  - `dashboard/tests/multi_channel_focus.test.js`
    - estendido para validar render real dos novos `Quick Insights` (snapshot + contexto por canal).
- Validacao executada:
  - `npx prettier --check dashboard/partials/analytics_logs.html dashboard/features/observability/view.js dashboard/tests/analytics_information_architecture.test.js dashboard/tests/multi_channel_focus.test.js`
  - `node --test dashboard/tests/analytics_information_architecture.test.js dashboard/tests/multi_channel_focus.test.js`
  - `node --test dashboard/tests/*.test.js`

### 2026-02-28 - Auditoria UX pos-fase 9 (baseline para fases 10-14)

Classificacao operacional:

- Legibilidade: boa.
- Hierarquia macro (abas + resumo global): boa.
- Intuitividade de microfluxo dentro das abas: media.

Evidencias levantadas no codigo atual:

- `intelligence_panel.html` concentra muitos blocos operacionais no mesmo painel (`391` linhas), com separacao majoritariamente por `hr`.
- `control_plane.html` permanece muito denso (`471` linhas), apesar de disclosure parcial.
- `analytics_logs.html` mistura contexto interno, timeline e historico persistido no mesmo fluxo inicial.
- Existem `144` ocorrencias de `style=""` inline em `dashboard/index.html` + `dashboard/partials/*.html`, com maior concentracao em:
  - `dashboard/partials/control_plane.html` (`50`)
  - `dashboard/partials/intelligence_panel.html` (`45`)
- Offsets sticky fixos em `dashboard/styles/layout.css` (`top: 86px` e `top: 130px`) podem degradar em variacoes reais de header.
- Idioma da UI ainda esta majoritariamente em PT-BR, com necessidade de padronizacao para ingles (en-US).

Gaps priorizados para execucao:

- P0: sub-hierarquia interna em `Inteligencia` e `Configuracao` para reduzir carga cognitiva.
- P0: padronizacao de linguagem para ingles (en-US) em toda a UI operacional.
- P1: refino de `Analytics` para leitura orientada a decisao.
- P1: consolidacao de estilo (extracao de inline para classes).
- P2: coerencia semantica e robustez de sticky/foco.

Validacao executada (baseline da auditoria):

- `node --test dashboard/tests/*.test.js` -> `54/54` passando.

### 2026-02-28 - Fase 14 em progresso (contrato de idioma da UI)

- Ajuste de copy operacional para ingles (en-US) em views/controllers da dashboard, sem alterar contratos de IDs/fluxo.
- Correcao de residuos PT-BR na UI:
  - `dashboard/features/control-plane/controller.js` -> `"Control plane synced."`
  - `dashboard/features/control-plane/view.js` -> hint de suspensao com `since`.
- Regra explicitada: UI/layout em ingles; conteudo de prompt pode permanecer em portugues.
- Cobertura adicionada:
  - `dashboard/tests/dashboard_semantic_consistency.test.js`
    - verifica `lang="en"` + labels principais em ingles;
    - verifica copy operacional em ingles e preservacao do fallback de prompt `Objetivo ...`.
- Ajustes em regressao existente:
  - `dashboard/tests/multi_channel_focus.test.js` atualizado para novo contrato textual de UI em ingles.
- Validacao executada:
  - `npx prettier --check dashboard/tests/multi_channel_focus.test.js dashboard/tests/dashboard_semantic_consistency.test.js dashboard/features/control-plane/controller.js dashboard/features/control-plane/view.js docs/IMPLEMENTATION_PLAN_DASHBOARD_UX_ABAS_E_HIERARQUIA.md`
  - `node --test dashboard/tests/dashboard_semantic_consistency.test.js dashboard/tests/multi_channel_focus.test.js`
  - `node --test dashboard/tests/*.test.js`

## 10) Matriz consolidada de rastreabilidade (planejamento -> implementacao)

| Fase | Objetivo sintetico                                         | Status       | Evidencia de implementacao principal                                                              | Evidencia de validacao principal                                                        |
| ---- | ---------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Shell de abas                                              | Concluida    | `index.html`, `main.js`, `features/navigation/tabs.js`                                            | `dashboard/tests/tabs_navigation.test.js`                                               |
| 2    | Re-housing por dominio                                     | Concluida    | novos partials + redistribuicao por painel                                                        | `dashboard/tests/layout_partial_mapping.test.js`                                        |
| 3    | Hierarquia visual e densidade                              | Concluida    | summary strip + intro por aba + disclosure progressivo                                            | `dashboard/tests/layout_hierarchy_density.test.js`, `summary_strip_runtime`             |
| 4    | Responsividade por abas                                    | Concluida    | tablist horizontal + alvo de toque + contrato de overflow                                         | `tabs_responsiveness_contract`, `tables_overflow_contract`                              |
| 5    | Hardening e rollout                                        | Concluida    | init idempotente + sincronia `aria-hidden`                                                        | `tabs_a11y.test.js`, `tabs_visibility_contract.test.js`                                 |
| 6    | Deep-link por URL (`?tab=`)                                | Concluida    | sync de URL com `history.replaceState` e preservacao de params                                    | cobertura nova em `tabs_navigation.test.js`                                             |
| 7    | Historico do navegador (`popstate`)                        | Concluida    | sync visual por `popstate` sem loop de rewrite                                                    | cobertura nova em `tabs_navigation.test.js`                                             |
| 8    | Regressao cientifica (invariantes)                         | Concluida    | robustez para URL invalida e matriz multi-passo                                                   | `tabs_regression_matrix.test.js`                                                        |
| 9    | Ergonomia horizontal (auto-reveal aba ativa)               | Concluida    | `scrollIntoView` em bootstrap/click/popstate                                                      | cobertura nova em `tabs_navigation.test.js`                                             |
| 10   | Sub-hierarquia interna em Inteligencia                     | Concluida    | `dashboard/partials/intelligence_panel.html` (blocos + disclosure progressivo)                    | `dashboard/tests/intelligence_hierarchy_contract.test.js`                               |
| 11   | Densidade e governanca no Control Plane                    | Concluida    | `dashboard/partials/control_plane.html` (secoes de governanca + disclosure progressivo)           | `dashboard/tests/control_plane_information_density.test.js`                             |
| 12   | Refino de Analytics orientado a decisao                    | Concluida    | `dashboard/partials/analytics_logs.html` (decision brief + separacao runtime/timeline/persisted)  | `dashboard/tests/analytics_information_architecture.test.js`, `multi_channel_focus`     |
| 13   | Consolidacao visual (reduzir inline styles)                | Planejada    | alvo: `dashboard/styles/layout.css`, `dashboard/styles/components.css`                            | alvo: `dashboard/tests/dashboard_style_consolidation_contract.test.js`                  |
| 14   | Coerencia semantica, UI em ingles e resiliencia responsiva | Em progresso | `index.html` (`lang=en`) + traducao de strings em views/controllers + regra de prompt localizavel | `dashboard/tests/dashboard_semantic_consistency.test.js`, `multi_channel_focus.test.js` |

Sequencia recomendada de execucao a partir do baseline atual:

1. Fase 13 (consolidacao visual e reducao de inline).
2. Fase 14 (coerencia semantica final e resiliencia responsiva).
