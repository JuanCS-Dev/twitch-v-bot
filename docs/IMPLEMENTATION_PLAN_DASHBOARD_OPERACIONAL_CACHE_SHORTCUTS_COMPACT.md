# Plano Executavel - Dashboard Operacional (Cache + Shortcuts + Compact Mode)

Data: 2026-02-21
Status: pronto para execucao
Escopo: melhorias de velocidade operacional sem alterar contratos principais do agente.

Links rapidos:

- [Indice de documentacao](INDEX.md)
- [Plano principal de paridade agente/dashboard](IMPLEMENTATION_PLAN_EXECUTAVEL_PARIDADE_AGENT_DASHBOARD.md)
- [Guia tecnico do produto](DOCUMENTATION.md)

## 1) Objetivo

- Reduzir latencia percebida da dashboard em acessos repetidos.
- Acelerar operacao ao vivo com atalhos de teclado.
- Criar visualizacao "second screen" com menor ruido e foco no essencial.

## 2) Escopo fechado (3 features)

F1. Cache seletivo de assets estaticos com `ETag` + `Cache-Control`.
F2. Atalhos de teclado operacionais (`r` refresh, `g` run tick).
F3. Modo compacto para monitoramento continuo.

## 3) Baseline AS-IS (confirmado no codigo)

- `bot/dashboard_server.py` aplica `Cache-Control: no-store` para toda resposta, inclusive assets estaticos.
- Dashboard ja tem botoes para `Re-Sync`, `Refresh Queue` e `Run 1 Tick`, mas sem atalhos de teclado globais.
- Nao existe estado de "compact mode" em `dashboard/index.html`, `dashboard/main.js` e CSS.
- Rotas e autenticacao estao corretas (challenge Basic em `/dashboard`, token para `/api/*`).

## 4) Requisitos obrigatorios

R1. API e HTML continuam sem cache (`no-store`).
R2. Apenas CSS/JS/static recebem cache curto com revalidacao por `ETag`.
R3. `r` dispara refresh operacional sem quebrar foco de campos de input.
R4. `g` dispara `POST /api/autonomy/tick` com feedback visual.
R5. Compact mode preserva controles criticos no topo e oculta blocos densos.
R6. Estado do compact mode persiste em `localStorage`.
R7. Nenhum arquivo novo/alterado passa de 300 linhas.

## 5) Contrato tecnico alvo

## 5.1 Cache seletivo de assets

Backend (`bot/dashboard_server.py`):

- Adicionar branch de resposta para assets estaticos:
- `index.html`: `Cache-Control: no-store`.
- `.css/.js`: `Cache-Control: public, max-age=120, must-revalidate`.
- Gerar `ETag` forte por hash de bytes do arquivo.
- Aceitar `If-None-Match` e retornar `304` sem body quando bater.
- Manter auth exatamente igual (sem bypass por cache).

## 5.2 Shortcuts operacionais

Frontend:

- Novo modulo `dashboard/features/shortcuts/controller.js`.
- `r`: executa sequencia rapida:
- refresh observability;
- refresh action queue;
- `channel-control list` (re-sync de canais).
- `g`: dispara o mesmo handler de `Run 1 Tick`.
- Ignorar atalhos quando foco estiver em `input`, `textarea`, `select` ou elemento `contenteditable`.
- Adicionar throttle de 1.2s para evitar spam por key repeat.

## 5.3 Compact mode

Frontend:

- Toggle visual no topo (`Compact: on/off`) em `dashboard/index.html`.
- Persistencia em `localStorage` com chave `byte.dashboard.compact_mode`.
- Classe `body.compact-mode` para alterar layout.
- Em compact mode:
- manter visiveis: topbar, channel manager, KPIs, autonomy runtime, risk queue.
- recolher/ocultar: tabelas longas de analytics, context internals e listas extensas.
- reduzir paddings e fontes secundarias para caber em second screen.

## 6) Plano por fases

## Fase 0 - Safety baseline (pre-condicao)

- Criar testes de contrato atuais em `bot/tests/scientific/suite_http.py`:
- dashboard asset retorna `200` com body;
- API continua `Cache-Control: no-store`.
- Aceite: baseline travada antes de mudar cache.

## Fase 1 - Cache seletivo de assets

- Implementar helpers de cache em `bot/dashboard_server.py`:
- calculo de `ETag`;
- resposta `304`;
- headers por tipo de recurso.
- Nao alterar `handle_get`/`handle_post` da API.
- Testes:
- `suite_http`: cobertura de `ETag`, `If-None-Match`, `304`, e `no-store` para API.
- Aceite:
- assets repetidos respondem `304`;
- endpoints API continuam sem cache.

## Fase 2 - Shortcuts de teclado

- Criar `dashboard/features/shortcuts/controller.js`.
- Integrar no bootstrap em `dashboard/main.js`.
- Exibir feedback curto no topo ao executar atalho (ex.: `Shortcut: refresh`).
- Testes/smoke:
- validar que `r` e `g` funcionam com foco fora de input;
- validar que nada dispara digitando em campos.
- Aceite:
- operacao principal fica acionavel sem mouse, sem regressao de UX.

## Fase 3 - Compact mode

- Adicionar botao/estado no `index.html`.
- Implementar controlador de estado compacto em `dashboard/main.js` ou modulo proprio.
- Adicionar regras CSS em `dashboard/styles/layout.css` e `dashboard/styles/components.css`.
- Testes/smoke:
- persistencia apos reload;
- layout legivel em 1366x768 e em mobile sem quebrar fluxo atual.
- Aceite:
- visual compacto reduz ruido e mantem controles de operacao ao vivo.

## Fase 4 - Validacao final e deploy

- Rodar testes rapidos:
- `pytest bot/tests/test_scientific.py -v -x`
- `pytest bot/tests/test_observability.py -v -x`
- Smoke manual:
- `/dashboard` auth;
- refresh via teclado;
- tick manual via teclado;
- modo compacto persistente.
- Deploy com rollback simples (reverter revisao Cloud Run anterior).

## 7) Definition of Done

- Cache seletivo ativo apenas para assets estaticos, com `ETag` funcional.
- Shortcuts `r` e `g` operando de forma segura e previsivel.
- Compact mode funcionando e persistente, sem perda de controle critico.
- Sem regressao de auth/dashboard API.
- Documentacao indexada em `docs/INDEX.md`.
