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
3. Cards KPI essenciais (saude, mensagens, erros, latencia, canal ativo).
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

- Bloqueio de concorrencia: 1 operacao de canal por vez.
- Idempotencia: mesmo request nao duplica efeito.
- Timeout explicito (ex: 12s) + mensagem clara.
- Reconciliacao obrigatoria: apos `join/part/switch`, executar `list` para confirmar estado real.
- Guard de resposta atrasada: ignorar resposta com `request_id` antigo.
- Botao de emergencia: "Recarregar estado de canais".
- Feedback de erro acionavel (motivo + proximo passo).

### 6.3 Contrato recomendado de API

Evoluir de comando textual para payload estruturado:
- `POST /api/channel-control`
  - request: `{ action, channel, request_id }`
  - response: `{ ok, request_id, channels, active_channel, message, error_code }`
- `GET /api/channel-control`
  - response: `{ ok, channels, active_channel, pending_action }`

Compatibilidade:
- Manter suporte a `command` no backend durante transicao.

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
- Congelar escopo MVP de Operacao.
- Definir metricas de sucesso.

Fase 1 - Fundacao visual (1-2 dias)
- Criar tokens e temas claro/escuro.
- Refazer layout base e navegao por tabs.
- Aplicar padrao unico de cards/tabelas/listas.

Fase 2 - Canal control UX first (1-2 dias)
- Substituir terminal por painel guiado de acoes.
- Implementar estados de loading/confirmacao/erro/reconciliacao.
- Adicionar trilha de auditoria visivel de ultimas operacoes.

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
