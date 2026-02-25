# Plano Completo de Implementacao - Dashboard Byte (UI/UX + Funcional)

Data: 2026-02-21
Status: rascunho para execucao

## 1) Objetivo de produto

Transformar a dashboard atual em um produto usavel por operador leigo e avancado, com foco principal em controle de canais IRC/Twitch, sem perder observabilidade.

Objetivos praticos:
- Tornar "controle de canais" a acao primaria da pagina.
- Garantir layout consistente, simetrico e responsivo em mobile/tablet/desktop.
- Definir design system Twitch-inspired com tema claro e escuro.
- Blindar fluxos de conectar/desconectar/trocar canal contra falhas e estados ambiguos.
- Reduzir acoplamento tecnico e manter todos os arquivos de app com <= 300 linhas.

## 2) Diagnostico atual (baseado no codigo)

Referencias:
- `dashboard/index.html` (estrutura longa e muitas secoes no mesmo nivel).
- `dashboard/styles.css` (tema neon dark-only, sem tema claro real).
- `dashboard/app.js` (render e fetch centralizados em um arquivo).
- `dashboard/channel-terminal.js` (comando textual para canal, sem UX guiada).

Problemas centrais:
- Hierarquia fraca: funcao principal (canal) fica no meio da tela.
- Excesso de dados no primeiro viewport, sem priorizacao por tarefa.
- Responsividade parcial, com quebra tardia e sem desenho mobile-first.
- Sem sistema de design formal (tokens semanticos, escalas, estados).
- Controle de canais orientado a "terminal", ruim para usuario nao tecnico.
- Falta de fluxo transacional forte para switch de canal (estado intermediario, confirmacao, rollback visual).

### 2.1 Baseline confirmado (funcionando hoje)

- Endpoint de controle ativo: `POST /api/channel-control` (nao existe GET equivalente).
- Payload aceito no backend: `{ command }` e `{ action, channel }`.
- Acoes suportadas: `list`, `join`, `part`.
- `join/part` aguardam confirmacao no runtime IRC e retornam `channels` atualizado na resposta.
- O frontend atual ja possui acao de sincronizacao manual (`List`), que mapeia para `list`.
- `GET /api/observability` nao expoe bloco de channel control (`active_channel`, `pending_action`).

### 2.2 Limites atuais do contrato (nao tratar como bug)

- Nao existe `active_channel` no payload atual de `/api/channel-control`.
- Nao existe `request_id` no payload atual de `/api/channel-control`.
- Nao existe `GET /api/channel-control` no backend atual.
- UI dependente desses campos deve ser classificada como evolucao de backend, nao como requisito ja disponivel.

## 3) Pesquisa visual Twitch (insumos reais)

Fontes consultadas:
- `https://brand.twitch.tv`
- `https://www.twitch.tv` (shell de carregamento)

Tokens observados em uso real:
- Roxo principal: `#9147FF`
- Accent claro para dark-hover: `#BF94FF`
- Dark base/surface: `#16161D`, `#18181B`, `#2B2B38`
- Neutros de texto: `#747484`, `#848494`
- Light base: `#FAFAFA`, `#F5F4F8`
- Neutro de borda/spinner: `#D9D8DD`

Diretriz:
- Nao copiar UI da Twitch, mas usar linguagem visual consistente com paleta, contraste e comportamento de tema.

## 4) Estrategia UX e arquitetura de informacao

Principio de produto:
- "Canal primeiro, observabilidade depois."

Nova hierarquia da pagina:
1. Header utilitario (brand, status bot, ambiente, refresh).
2. Bloco primario "Controle de Canais" (hero funcional).
3. Cards KPI essenciais (saude, mensagens, erros, latencia, canais conectados).
4. Observabilidade operacional (eventos recentes e alertas).
5. Analytics detalhado (tabelas e historico).
6. Rodape tecnico (timestamp, versao frontend, latencia de API).

Arquitetura em tabs para reduzir ruido cognitivo:
- `Operacao` (default): controle de canais + estado bot + eventos criticos.
- `Observabilidade`: metricas, timeline, top chatters, rotas.
- `Contexto`: prompts/replies/context items e detalhes de memoria.
- `Configuracoes`: tema, refresh interval, preferencias de visualizacao.

## 5) Plano visual (UI)

### 5.1 Design tokens semanticos

Definir em `dashboard/styles/tokens.css`:
- Cores de marca:
  - `--color-accent: #9147FF`
  - `--color-accent-soft: #BF94FF`
- Tema dark:
  - `--bg-base: #0E0E10`
  - `--bg-surface: #18181B`
  - `--bg-elevated: #2B2B38`
  - `--text-primary: #EFEFF1`
  - `--text-muted: #ADADB8`
  - `--border-default: #3A3A45`
- Tema light:
  - `--bg-base: #FAFAFA`
  - `--bg-surface: #F5F4F8`
  - `--bg-elevated: #FFFFFF`
  - `--text-primary: #0E0E10`
  - `--text-muted: #53535F`
  - `--border-default: #D9D8DD`
- Semanticas de estado:
  - `--status-ok`, `--status-warn`, `--status-error`, `--status-pending`

### 5.2 Tipografia e escala

- Fonte principal: `Roobert` (fallback: `IBM Plex Sans`, `Segoe UI`, sans-serif).
- Escala base: 12/14/16/20/24/32.
- Tamanho minimo interativo: 44px.
- Grid de espacamento: 4, 8, 12, 16, 24, 32.

### 5.3 Layout e responsividade

Breakpoints:
- Mobile: 360-599
- Tablet: 600-1023
- Desktop: 1024-1439
- Wide: 1440+

Regras:
- Mobile-first com unica coluna na base.
- Hero de controle sempre no topo em todos os breakpoints.
- Desktop com grid de 12 colunas; bloco de controle ocupando 7-8 colunas.
- Tabelas longas com horizontal scroll controlado e resumo acima.

### 5.4 Componentes obrigatorios

- `ChannelControlCard` (principal).
- `BotStatusStrip` (online/offline/connecting + uptime + versao).
- `KpiCard` (padrao unico para metricas).
- `AlertFeed` (erros/warns recentes).
- `EventLogList` (eventos com filtro rapido).
- `DataTable` (rotas/timeline/rankings padronizados).

## 6) Plano funcional (controle de canais blindado)

### 6.1 Fluxo de operacao alvo

Acoes de primeira classe:
- `Conectar canal`
- `Desconectar canal`
- `Trocar canal` (operacao atomica orientada)
- `Sincronizar estado`

Estados de UI por acao:
- `idle`
- `sending`
- `confirming`
- `success`
- `error`
- `reconciling`

### 6.2 Requisitos de robustez

- 1 operacao por vez na UI (estado `busy`) e sem submit concorrente.
- Timeout explicito (12s) com erro acionavel e opcao de retry.
- Pos `join/part`: usar `channels` da propria resposta como fonte primaria de estado.
- Sincronizacao manual obrigatoria: acao "Sincronizar estado" deve disparar `list`.
- Em falha/timeout: preservar ultimo estado confirmado e orientar reconciliacao via `list`.
- Nao inferir "canal ativo" sem dado real de backend; exibir apenas canais conectados.

### 6.3 Contrato de API (AS-IS obrigatorio)

Contrato AS-IS (obrigatorio para Fase 2):
- `POST /api/channel-control`
  - request: `{ command }` ou `{ action, channel }`
  - response sucesso: `{ ok, action, channels, message }`
  - response erro: `{ ok: false, error, message }`
- `GET /api/observability`
  - permanece separado do controle de canais
  - nao retorna `active_channel`/`pending_action`

Compatibilidade:
- Manter suporte a `command` no backend durante transicao.

### 6.4 Evolucao de contrato (somente com milestone de backend)

- Introduzir `request_id` apenas com suporte real no backend e testes de idempotencia.
- Expor `active_channel` apenas quando o runtime publicar esse dado de forma consistente.
- Avaliar `GET /api/channel-control` somente se houver necessidade operacional comprovada.
- Habilitar guard de resposta atrasada apenas quando `request_id` existir ponta-a-ponta.

## 7) Refatoracao tecnica (escalabilidade e <= 300 linhas)

Estrutura alvo frontend:
- `dashboard/index.html`
- `dashboard/main.js`
- `dashboard/styles/tokens.css`
- `dashboard/styles/base.css`
- `dashboard/styles/layout.css`
- `dashboard/styles/components.css`
- `dashboard/features/channel-control/api.js`
- `dashboard/features/channel-control/state.js`
- `dashboard/features/channel-control/view.js`
- `dashboard/features/observability/api.js`
- `dashboard/features/observability/view.js`
- `dashboard/features/shared/dom.js`
- `dashboard/features/shared/format.js`
- `dashboard/features/shared/events.js`

Regras:
- Cada modulo com responsabilidade unica.
- Sem arquivo > 300 linhas (exceto testes).
- Sem selectors espalhados; centralizar mapa de elementos por feature.
- Testes de unidade para formatadores, reducers e fluxos de canal.

## 8) Plano de implementacao por fases

Fase 0 - Descoberta e alinhamento (0.5 dia)
- Inventario de componentes atuais.
- Congelar escopo MVP de Operacao com contrato AS-IS.
- Registrar explicitamente limites: sem `GET /api/channel-control`, sem `request_id`, sem `active_channel` inferido.
- Definir metricas de sucesso.

Fase 1 - Fundacao visual (1-2 dias)
- Criar tokens e temas claro/escuro.
- Refazer layout base e navegao por tabs.
- Aplicar padrao unico de cards/tabelas/listas.

Fase 2 - Canal control UX first (1-2 dias)
- Substituir terminal por painel guiado de acoes.
- Implementar estados de loading/confirmacao/erro/reconciliacao usando apenas contrato AS-IS.
- Adicionar acao "Sincronizar estado" mapeada para `list`.
- Adicionar trilha de auditoria visivel de ultimas operacoes.

Fase 2.5 - Evolucao backend opcional (0.5-1 dia)
- Incluir `request_id` no backend e frontend apenas se idempotencia for requisito de produto.
- Expor `active_channel` no contrato apenas com fonte canonica no runtime.
- Criar `GET /api/channel-control` apenas se polling for necessario apos medir uso real.

Fase 3 - Modularizacao JS (1-2 dias)
- Separar `app.js` e `channel-terminal.js` por features.
- Introduzir event bus leve para comunicacao entre modulos.
- Garantir regra de <= 300 linhas por arquivo.

Fase 4 - Observabilidade orientada a tarefa (1 dia)
- Priorizar cards criticos no topo.
- Reorganizar analytics para leitura progressiva.
- Melhorar filtros de eventos (nivel e janela de tempo).

Fase 5 - QA final e hardening (1 dia)
- Testes funcionais manuais de canal (join/part/switch/retry).
- Testes de responsividade em 360, 768, 1024, 1440.
- Acessibilidade basica (teclado, foco, contraste AA).

## 9) Criterios de aceite (Definition of Done)

- Controle de canais e o primeiro bloco da dashboard em todos os breakpoints.
- Troca de canal confirma estado real apos reconciliacao.
- Nao existe estado "parece conectado" quando backend diverge.
- Frontend nao chama endpoint inexistente (`GET /api/channel-control`).
- Frontend nao depende de `active_channel` nem `request_id` antes da milestone de backend.
- Tema claro e escuro funcionam com tokens semanticos.
- Navegacao e operacao completa apenas com teclado.
- Nenhum arquivo de app ultrapassa 300 linhas.
- Lighthouse (Performance/Best Practices/Accessibility) >= 85 em desktop.

## 10) Plano de validacao

Checklist funcional:
- Join em canal novo.
- Join em canal ja conectado.
- Part em canal inexistente.
- Switch com falha intermediaria.
- Timeout de API com recuperacao.
- Refresh durante operacao em andamento.
- Acao "Sincronizar estado" faz `list` e reconcilia UI.
- Nenhuma chamada para `GET /api/channel-control` no fluxo MVP.

Checklist UX:
- Usuario novo encontra "trocar canal" em <= 5s.
- Mensagens de erro sao claras e acionaveis.
- Visual consistente entre light/dark.
- Layout sem sobreposicoes em mobile.

## 11) Riscos e mitigacao

Risco: backend nao suporta contrato estruturado.
- Mitigacao: camada adapter mantendo `command` ate migracao completa.

Risco: regressao visual em telas pequenas.
- Mitigacao: snapshots por breakpoint e smoke test visual por PR.

Risco: aumento de complexidade JS.
- Mitigacao: separar por feature + testes de unidade + lint estrito.

## 12) Entregaveis finais

- Novo design system (tokens + componentes).
- Dashboard reorganizada com foco em operacao.
- Fluxo de canal robusto e auditavel.
- Arquitetura modular com limite de tamanho por arquivo.
- Suite minima de testes e checklist de QA documentado.

## 13) Adendo: Auditoria de Observabilidade e Controle (Zero Mock)

*Auditoria realizada sobre `/bot/dashboard_server.py`, `/bot/observability_state.py` e `/bot/channel_control.py`.*

### A. Oportunidades de Observabilidade (Dados Reais Disponíveis)
O `observability_state.py` expõe métricas valiosas que o frontend MVP atual subutiliza ou agrupa sem hierarquia. Podemos expô-las de forma visualmente rica (tipografia limpa, cards estruturados), sem gerar mocks:
1. **Agent Health & Quality Gates:** O state rastreia `quality_checks_total`, outcomes de retry/fallback, falhas de auth e `token_refreshes_total`.
   - *Sugestão:* Criar um painel de "System Health" exibindo a taxa de rejeição/correção do LLM e a saúde das credenciais em tempo real.
2. **Live AI Activity:** O state expõe `last_prompt` e `last_reply`.
   - *Sugestão:* Um feed minimalista listando a última interação do bot, permitindo leitura rápida do operador sobre o que a IA acabou de processar.
3. **Métricas de Engajamento Estrito:** A contagem de `trigger_user_totals` (quem mais invoca o bot) e volume segmentado por rotas (`route_counts`, diferenciando queries dinâmicas de comandos estáticos).
4. **Log Direcionado e Filtrável:** Os eventos em `recent_events` já possuem nível (`INFO`, `WARN`, `ERROR`) e categoria explícita.
   - *Sugestão:* Uma tabela de eventos profissional com filtros rápidos (chips visuais), abandonando a lista de texto plano atual.

### B. Oportunidades de Controle (Ações Reais Disponíveis)
O `channel_control.py` processa comandos transacionais precisos via API POST (`list`, `join`, `part`), sem necessidade de alterar a lógica interna de IRC.
1. **Fim do Terminal Falso:** Substituir o bloco "Channel Terminal" (comandos em texto) por um genuíno "Channel Manager" visual.
2. **Ações Guiadas (Zero CLI):** Listagem automática dos canais conectados (via action `list`) renderizados em cards/chips com botão nativo "Disconnect", exigindo apenas 1 clique.
3. **Feedback Transacional:** Ao engatilhar "Connect", a UI deve assumir estado transitório claro (spinner leve ou skeleton mode nas tabelas) interpretando os erros nativos e convertendo em alertas humanos visíveis na tela.

### C. Refinamento de UI/UX (Profissionalismo e Leveza)
1. **Sem Renderização Pesada:** Nenhuma dependência de Canvas, re-renders exagerados ou frameworks pesados. As microanimações baseadas exclusivamente em transições leves CSS (`transform` e `opacity`). Exemplo: elevação sutil `translateY(-2px)` e highlights ao hover.
2. **Linguagem Visual Twitch:** Utilização consciente dos tokens inspirados no branding (`#9147FF`, temas focados em alto contraste - claro autêntico e escuro). A tipografia seguirá hierarquias estritas (pesos fortes para KPIs), garantindo altíssima legibilidade ("crispness") sem "embaçar" a tela.
3. **Responsividade Pura:** O bloco gerencial "Channel Manager" deve continuar absoluto no mobile. Paineis de dados intensos ganham controle nativo de `overflow-x` (scroll horizontal) sem poluir ou quebrar a coluna principal.

## 14) Guia de execucao sem ambiguidade (obrigatorio)

Fazer:
1. Implementar UX de canais com o contrato atual (`POST /api/channel-control` + `list/join/part`).
2. Tratar `channels` da resposta como estado oficial do frontend.
3. Manter suporte a `command` durante toda a migracao.
4. Cobrir fluxo com testes unitarios e smoke manual (join/part/list/timeout/forbidden).

Nao fazer:
1. Nao criar chamadas para `GET /api/channel-control` antes de existir backend.
2. Nao inventar `active_channel`, `pending_action` ou `request_id` no frontend sem contrato real.
3. Nao esconder erro de runtime; sempre exibir feedback acionavel para operador.
4. Nao introduzir acoplamento que quebre a regra de modulos e limite de tamanho por arquivo.
