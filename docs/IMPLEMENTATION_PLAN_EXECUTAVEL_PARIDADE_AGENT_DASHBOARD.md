# Plano de Implementacao Executavel - Blindagem IRC + Paridade Total Agent/Dashboard

Data: 2026-02-21  
Status: pronto para execucao  
Escopo: este plano substitui rascunhos para implementacao final sem ambiguidade.

Links rapidos:

- [Indice de documentacao](INDEX.md)
- [Guia completo do produto e operacao](DOCUMENTATION.md)
- [README do projeto](../README.md)

## 1) Objetivo

- Blindar o fluxo atual em `irc` (incluindo entrar/operar como viewer) sem regressao.
- Garantir controle total do streamer em uma dashboard intuitiva e rapida.
- Fechar paridade total: toda capacidade do agente deve ter controle e estado visivel na dashboard.
- Manter contrato de resposta curta: 1 mensagem, no maximo 4 linhas, com alta densidade.

## 2) Baseline AS-IS (confirmado no codigo)

- `GET /api/observability` retorna `bot.mode` e `metrics` (nao retorna `counters` no payload raiz).
- Dashboard de health em `dashboard/features/observability/view.js` ainda le `safeData.counters` para alguns cards.
- `POST /api/channel-control` existe e depende da bridge IRC (`bot/channel_control.py`).
- Bridge de channel control so fica `bind()` no modo IRC (`bot/bootstrap_runtime.py`).
- No modo serio, ainda existe caminho para 2 mensagens com `[BYTE_SPLIT]` (`bot/prompt_flow.py`, `bot/byte_semantics_quality.py`).

## 3) Requisitos obrigatorios (nao negociaveis)

R1. Corrigir payload de Health na dashboard: `counters -> metrics`.  
R2. Channel Control mode-aware no UI/UX: em `eventsub`, desabilitar `join/part` e explicar claramente.  
R3. Enforcar contrato estrito: 1 mensagem com ate 4 linhas, removendo split em 2 partes no modo serio.  
R4. Implantar loop autonomo com agenda: heartbeat + goal scheduler + budget anti-spam.  
R5. Separar acoes por risco: auto chat, sugestao ao streamer, moderacao com confirmacao obrigatoria.  
R6. Adicionar metricas de resultado do agente: engajamento util, taxa de ignorados, taxa de correcao, custo/token.  
R7. Paridade total na dashboard: todo controle novo no agente deve existir na UI, com estado atual e historico.

## 4) Principios anti-debito tecnico

- Uma unica fonte de verdade para configuracao runtime: `ControlPlaneConfig` versionado.
- Capability-driven UI: dashboard habilita/desabilita controles por `capabilities` vindas do backend.
- Guardrails duplos: bloqueio no frontend e bloqueio no backend para operacoes nao suportadas.
- Tudo com telemetria: cada acao, bloqueio, retry e confirmacao gera evento observavel.
- Defaults seguros: autonomia e acoes moderativas iniciam em modo conservador.

## 5) Contrato de API alvo (v1)

## 5.1 `GET /api/observability` (expandido)

Adicionar:

- `capabilities.channel_control.enabled`
- `capabilities.channel_control.reason`
- `capabilities.channel_control.supported_actions`
- `capabilities.autonomy.enabled`
- `capabilities.risk_actions.enabled`
- `autonomy` (estado runtime resumido)
- `agent_outcomes` (metricas de resultado)

## 5.2 `POST /api/channel-control` (modo-aware)

- Se `bot.mode != "irc"`:
- `join`/`part` devem retornar `409 unsupported_mode`.
- `message` deve explicar: "Channel control de runtime so funciona em TWITCH_CHAT_MODE=irc."
- Em `irc`, manter contrato atual (`list|join|part`) com retorno de `channels`.

## 5.3 Novos endpoints de controle (com token admin)

- `GET /api/control-plane`: retorna configuracao atual editavel na dashboard.
- `PUT /api/control-plane`: atualiza configuracao runtime (com validacao forte).
- `GET /api/action-queue`: fila de sugestoes/moderacao pendente.
- `POST /api/action-queue/<action_id>/decision`: `approve|reject` com auditoria.
- `POST /api/autonomy/tick`: dispara 1 ciclo manual (debug operacional).

## 6) Matriz de paridade agente/dashboard

| Tema | Backend/Agent | Dashboard |
|---|---|---|
| Health metrics | Leitura de `metrics` e metricas derivadas | Cards de saude lendo `metrics` sem fallback ambiguo |
| Channel control mode-aware | Guard por modo + erro semantico `unsupported_mode` | `join/part` desabilitados em `eventsub` com mensagem explicita |
| Resposta 1x4 | Sem split, sem `[BYTE_SPLIT]`, limite unico | Indicador visual de contrato ativo (`1 msg / 4 linhas`) |
| Autonomia com agenda | Heartbeat + scheduler + budget | Tela de agenda, limites, pausa global e execucao manual |
| Risco por tipo de acao | Policy engine + fila de confirmacao | Painel com aprovacao/rejeicao e trilha de auditoria |
| Resultado/custo | `agent_outcomes` + custo/token | KPIs, tendencias 60m/24h, alertas de degradacao |

## 7) Plano por fases (executavel)

## Fase 0 - Hardening baseline (pre-condicao)

Backend:
- Mapear e congelar contrato atual em teste.
- Adicionar `capabilities` minimas em `observability`.
- Garantir erro explicito se channel control for chamado fora de IRC.

Dashboard:
- Exibir `bot.mode` como estado operacional primario.
- Mostrar badge de capacidade: `channel_control enabled/disabled`.

Testes:
- `pytest bot/tests/test_observability.py -v -x`
- Novo teste de contrato em `bot/tests/test_logic.py` para payload base de observability.

Aceite:
- Nenhuma acao de canal falha de forma silenciosa.

## Fase 1 - Fix Health (`counters -> metrics`)

Backend:
- Manter `metrics` como fonte canonica.

Dashboard:
- Corrigir leitura em `dashboard/features/observability/view.js` para usar `safeData.metrics`.
- Ajustar calculo de fallback/retry usando `metrics.quality_fallback_total` e `metrics.quality_retry_total`.

Testes:
- Smoke manual: cards de health atualizam com dados reais.
- Teste de regressao em snapshot fake de observability.

Aceite:
- Todos os cards de health refletem valores corretos sem depender de `counters`.

## Fase 2 - Channel Control mode-aware (UI e backend)

Backend:
- Em `bot/dashboard_server.py`, retornar `409 unsupported_mode` para `join/part` fora de IRC.
- Padronizar payload de erro com `ok:false`, `error`, `message`, `mode`.

Dashboard:
- Em `dashboard/main.js` e `dashboard/features/channel-control/view.js`, desabilitar `join/part` quando `bot.mode != "irc"`.
- Exibir mensagem fixa no painel: controle de canal de runtime disponivel apenas em IRC.
- Manter acao de sync apenas quando houver suporte real.

Testes:
- Teste backend para `eventsub -> 409`.
- Teste manual de UX: botoes desativados e explicacao visivel.

Aceite:
- Streamer entende em 1 olhar se pode ou nao operar canais.

## Fase 3 - Contrato estrito 1 mensagem / 4 linhas

Backend/Agent:
- Remover envio multi-parte no modo serio em `bot/prompt_flow.py`.
- Remover instrucao `[BYTE_SPLIT]` em `bot/byte_semantics_quality.py`.
- Alinhar limites: `SERIOUS_REPLY_MAX_LENGTH == MAX_CHAT_MESSAGE_LENGTH`.
- Sanitizar resposta para nunca publicar marcador de split.

Docs:
- Atualizar `README.md` e `docs/DOCUMENTATION.md` para remover regra de 2 mensagens.

Testes:
- Atualizar `bot/tests/test_scientific.py` (remover expectativa de split e adicionar garantia de mensagem unica).
- Rodar:
- `pytest bot/tests/test_logic.py -v -x`
- `pytest bot/tests/test_scientific.py -v -x`

Aceite:
- Todas as respostas do agente saem em uma unica mensagem com ate 4 linhas.

## Fase 4 - Loop autonomo com agenda e budget anti-spam

Backend/Agent:
- Criar `AutonomyEngine` com:
- heartbeat configuravel;
- scheduler por objetivos;
- budget por janela (10m, 60m, diario);
- cooldown minimo entre mensagens.
- Integrar com runtime IRC/EventSub sem bloquear fluxo reativo.

Dashboard:
- Criar painel "Autonomia":
- toggle liga/desliga;
- heartbeat interval;
- agenda de objetivos;
- budget e cooldown;
- botao `Run 1 cycle`.

Testes:
- Unitarios de scheduler e budget.
- Cenarios de anti-spam (estouro de budget bloqueia envio e registra evento).

Aceite:
- Agente age de forma proativa sem ultrapassar limites configurados.

## Fase 5 - Acoes por risco (auto/sugestao/moderacao)

Backend/Agent:
- Criar `RiskPolicyEngine` com 3 niveis:
- `auto_chat` (baixo risco, execucao automatica);
- `suggest_streamer` (medio risco, fila de sugestao);
- `moderation_action` (alto risco, confirmacao obrigatoria).
- Nenhuma acao moderativa executa sem `approve`.

Dashboard:
- Painel "Risco e Confirmacoes":
- matriz de politicas por tipo de acao;
- inbox de pendencias;
- aprovar/rejeitar com nota de auditoria.

Testes:
- Regras de bloqueio por risco.
- Fluxo completo de decisao (`pending -> approved/rejected`).

Aceite:
- Acoes sensiveis ficam sob controle explicito do streamer.

## Fase 6 - Metricas de resultado do agente

Backend/Observability:
- Adicionar `agent_outcomes` com:
- `useful_engagement_rate_60m`;
- `ignored_rate_60m`;
- `correction_rate_60m`;
- `token_input_total`, `token_output_total`, `estimated_cost_usd_60m`.
- Registrar eventos que alimentam cada indicador.

Dashboard:
- Novos KPIs e tendencia por janela (60m/24h).
- Alertas de degradacao quando `ignored_rate` subir acima do limite configurado.

Testes:
- Testes de agregacao no snapshot de observability.

Aceite:
- Streamer consegue medir valor real, qualidade e custo do agente em tempo real.

## Fase 7 - Fechamento de paridade, QA e deploy

Checklist:
- Todos os controles do `ControlPlaneConfig` estao na dashboard.
- Todas as acoes criticas tem feedback, estado e auditoria.
- Sem endpoint morto ou controle "fantasma".
- Sem regressao no fluxo IRC atual.

Validacao:
- `pytest bot/tests/test_observability.py -v -x`
- `pytest bot/tests/test_logic.py -v -x`
- `pytest bot/tests/test_scientific.py -v -x`
- Smoke manual em `TWITCH_CHAT_MODE=irc` e `TWITCH_CHAT_MODE=eventsub`.

Rollout:
- Deploy com autonomia desligada por default.
- Habilitacao progressiva por flags via dashboard.
- Rollback rapido: desligar autonomia e manter fluxo reativo.

## 8) Definition of Done final

- Fluxo atual IRC/viewer blindado e sem regressao funcional.
- Dashboard com controle total, rapido e intuitivo para o streamer.
- Paridade completa agente/dashboard para os 6 itens obrigatorios.
- Contrato de resposta sempre em 1 mensagem com ate 4 linhas.
- Telemetria suficiente para operar por resultado (qualidade + custo + risco).
