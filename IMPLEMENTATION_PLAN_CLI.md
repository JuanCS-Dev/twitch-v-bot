# Plano de Implementação: Byte Agent CLI

> **✅ STATUS: IMPLEMENTAÇÃO COMPLETA — 2026-03-03**
> - 20 arquivos criados (17 CLI + 1 endpoint backend + 2 testes)
> - 80/80 testes E2E passando (4.23s)
> - 43 comandos operacionais
> - 0 dependências adicionadas

## Objetivo

Construir uma CLI (`bytecli`) que oferece **100% de cobertura de controle** sobre o agente Byte.
A CLI opera como ponte de comandos: o operador digita `bytecli <comando>` e a CLI traduz isso em chamadas HTTP ao Dashboard API do agente (que já roda em `localhost:7860`).
Sem overengenharia — um módulo Python puro com `argparse`, zero dependências externas além de `requests`.

---

## Contexto Arquitetural do Agente (para o revisor)

### Visão Geral

O agente **Byte** é um bot de Twitch com IA (Nebius/OpenAI-compatible), composto por:

```
┌──────────────────────────────────────────────────────────────────┐
│                         ENTRY POINT                              │
│  bot/main.py → IRC/EventSub mode + Dashboard HTTP thread         │
└────────────┬──────────────────────────────────┬──────────────────┘
             │                                  │
     ┌───────▼───────┐                ┌─────────▼──────────┐
     │  IRC Runtime   │                │  Dashboard Server  │
     │  (Twitch Chat) │                │  (HTTP API :7860)  │
     └───────┬───────┘                └─────────┬──────────┘
             │                                  │
     ┌───────▼────────────────────────┬─────────▼──────────┐
     │        Core Singletons (in-process state)           │
     ├─────────────────────────────────────────────────────┤
     │  control_plane    → Agent state, goals, actions     │
     │  observability    → Telemetry, costs, interactions  │
     │  autonomy_runtime → Heartbeat loop, goal execution  │
     │  context_manager  → StreamContext per channel       │
     │  persistence      → Supabase (state, history, etc.) │
     │  sentiment_engine → Chat sentiment NLP              │
     │  vision_runtime   → Frame analysis pipeline         │
     │  clip_jobs        → Clip pipeline                   │
     │  webhook_engine   → Outbound webhook delivery       │
     └─────────────────────────────────────────────────────┘
```

### Dashboard HTTP API (a interface da CLI)

O agente já expõe uma API HTTP completa em `bot/dashboard_server.py` + rotas em `bot/dashboard_server_routes.py` e `bot/dashboard_server_routes_post.py`. Todas as rotas requerem autenticação via header `X-Byte-Admin-Token` ou `Authorization: Bearer <token>`.

#### GET Routes (17 endpoints):
| Rota | Funcionalidade |
|------|----------------|
| `/api/observability` | Snapshot completo de telemetria (counters, interactions, errors, cost) |
| `/api/channel-context` | Contexto do canal (game, vibe, persona, histórico, state persistido) |
| `/api/observability/history` | Timeline de snapshots históricos do canal |
| `/api/control-plane` | Estado do control plane (config, goals, budget, suspend status) |
| `/api/channel-config` | Configuração do canal (temperature, top_p, agent_paused, persona) |
| `/api/agent-notes` | Notas de runtime do agente para o canal |
| `/api/action-queue` | Fila de ações (pending/approved/rejected/expired) |
| `/api/clip-jobs` | Jobs do pipeline de clips |
| `/api/hud/messages` | Mensagens do HUD overlay |
| `/api/sentiment/scores` | Scores de sentimento do chat + stream health |
| `/api/observability/post-stream-report` | Relatório pós-stream (pode gerar ao vivo) |
| `/api/semantic-memory` | Memória semântica do canal (busca por query) |
| `/api/ops-playbooks` | Status dos ops playbooks |
| `/api/vision/status` | Status do pipeline de visão |
| `/api/observability/conversions` | Conversões de revenue attribution |
| `/api/webhooks` | Webhooks registrados para o canal |
| `/api/persona-profile` | Perfil de persona completo |

#### PUT Routes (6 endpoints — escrita de configuração):
| Rota | Funcionalidade |
|------|----------------|
| `/api/control-plane` | Atualiza config do control plane (goals, budgets, flags) |
| `/api/channel-config` | Atualiza config + identidade do canal |
| `/api/agent-notes` | Atualiza notas do agente |
| `/api/semantic-memory` | Cria/atualiza entrada de memória semântica |
| `/api/webhooks` | Registra/atualiza webhook |
| `/api/persona-profile` | Atualiza perfil de persona |

#### POST Routes (8 endpoints — ações):
| Rota | Funcionalidade |
|------|----------------|
| `/api/channel-control` | Controle IRC: join/part/list canais |
| `/api/autonomy/tick` | Força tick de autonomia (executa goals) |
| `/api/agent/suspend` | Suspende o agente |
| `/api/agent/resume` | Retoma o agente |
| `/api/action-queue/{action_id}/decision` | Aprova/rejeita ação via payload `{decision: "approve"\|"reject"}` |
| `/api/ops-playbooks/trigger` | Trigger manual de ops playbook |
| `/api/vision/ingest` | Ingest de frame de visão |
| `/api/observability/conversion` | Registra conversão de revenue |
| `/api/webhooks/test` | Testa um webhook |

### Autenticação

Todas as rotas `/api/*` exigem o header `X-Byte-Admin-Token` com o valor da env var `BYTE_DASHBOARD_ADMIN_TOKEN`. A CLI lê esse token de `~/.byterc` ou da env var `BYTE_ADMIN_TOKEN`.

### Goals (Sistema de Objetivos)

Goals são tarefas recorrentes com schedule cron. Cada goal tem:
- `id`, `name`, `prompt` (instrução para a IA)
- `risk` (auto_chat / suggest_streamer / moderation_action / clip_candidate)
- `interval_seconds` ou `cron_expression`
- `enabled` (flag on/off)
- KPIs: `kpi_name`, `target_value`, `window_minutes`, `comparison`
- `session_result` (resultado da última execução)

Goals default: `chat_pulse` (900s), `streamer_hint` (600s), `safety_watch` (300s), `detect_clip` (600s, disabled).

---

## Proposta de Implementação

### Estrutura de Arquivos

```
cli/
├── __init__.py
├── __main__.py          # Entry point: python -m cli
├── main.py              # CLI dispatcher (argparse)
├── client.py            # HTTP client wrapper (requests → Dashboard API)
├── config.py            # Lê ~/.byterc e env vars para token/URL
├── formatters.py        # Formatação de output (tabelas, JSON, human-readable)
└── commands/
    ├── __init__.py
    ├── status.py         # bytecli status
    ├── observe.py        # bytecli observe [observability|sentiment|history|health]
    ├── control.py        # bytecli agent [suspend|resume|tick|config]
    ├── goals.py          # bytecli goals [list|show|create|update|delete|enable|disable]
    ├── actions.py        # bytecli actions [list|approve|reject|pending]
    ├── channel.py        # bytecli channel [context|config|notes|join|part|list]
    ├── memory.py         # bytecli memory [list|search|add]
    ├── persona.py        # bytecli persona [show|update]
    ├── clips.py          # bytecli clips [jobs|vision]
    ├── playbooks.py      # bytecli playbooks [list|trigger]
    ├── webhooks.py       # bytecli webhooks [list|add|test]
    ├── report.py         # bytecli report [show|generate]
    └── chat.py           # bytecli chat <mensagem> — envia mensagem via agente
```

### Dependências

Nenhuma nova dependência. Usa apenas:
- `argparse` (stdlib)
- `json` (stdlib)
- `urllib.request` (stdlib) — para evitar dependência de `requests`
- `os`, `pathlib` (stdlib)

> **Decisão**: usar apenas stdlib para manter zero dependências novas. Se o projeto já tem `requests` instalado, podemos usá-lo, mas o default é `urllib.request`.

---

### Detalhamento por Módulo

---

#### [NEW] `cli/__init__.py`
Arquivo vazio, marca o diretório como pacote Python.

---

#### [NEW] `cli/__main__.py`
```python
from cli.main import main
main()
```
Permite `python -m cli` como entry point.

---

#### [NEW] `cli/config.py`
Responsabilidades:
- Lê `~/.byterc` (INI simples ou JSON com `url` e `token`)
- Fallback para env vars: `BYTE_API_URL` (default `http://localhost:7860`) e `BYTE_ADMIN_TOKEN`
- Expõe `get_config() → {"url": str, "token": str}`

---

#### [NEW] `cli/client.py`
Responsabilidades:
- Classe `ByteClient` com métodos `get(path, params)`, `put(path, payload)`, `post(path, payload)`
- Adiciona header `X-Byte-Admin-Token` automaticamente
- Parse de resposta JSON
- Tratamento de erros HTTP (401, 404, 500)
- Timeout configurável

---

#### [NEW] `cli/formatters.py`
Responsabilidades:
- `print_json(data)` — pretty-print JSON para mode `--json`
- `print_table(headers, rows)` — tabela ASCII simples (human-readable default)
- `print_kv(dict)` — key-value pairs formatados
- `print_success(msg)` / `print_error(msg)` — output colorido (ANSI básico)
- `format_timestamp(iso)` — converte ISO timestamp para formato legível

---

#### [NEW] `cli/main.py`
Dispatcher principal:
```
bytecli [--json] [--url URL] [--token TOKEN] <command> <subcommand> [args]
```

**Flags globais:**
- `--json` — output em JSON raw (default é human-readable)
- `--url` — override da URL do agente
- `--token` — override do token
- `--channel` — channel do agente (query param `channel`, default: `default`)

**Subcomandos registrados via argparse subparsers.**

---

### Comandos Completos

#### 1. `bytecli status`
- **Ação**: `GET /health` + `GET /api/control-plane` + `GET /api/observability`
- **Output**: Status online/offline, uptime, mode (IRC/EventSub), goals ativos, mensagens processadas, erros recentes, custo estimado, agente suspenso ou não

#### 2. `bytecli agent suspend [--reason REASON]`
- **Ação**: `POST /api/agent/suspend`
- **Output**: Confirmação com timestamp

#### 3. `bytecli agent resume [--reason REASON]`
- **Ação**: `POST /api/agent/resume`
- **Output**: Confirmação com timestamp

#### 4. `bytecli agent tick [--force]`
- **Ação**: `POST /api/autonomy/tick` com `{"force": true/false}`
- **Output**: Goals processados, resultados, ops playbooks executados

#### 5. `bytecli agent config`
- **Ação**: `GET /api/control-plane`
- **Output**: Config completa do control plane (autonomy, budgets, intervals, goals)

#### 6. `bytecli agent config set <key> <value>`
- **Ação**: `PUT /api/control-plane` com `{key: value}`
- **Output**: Config atualizada

#### 7. `bytecli observe`
- **Ação**: `GET /api/observability`
- **Output**: Resumo de observabilidade (counters, interactions, errors, cost)

#### 8. `bytecli observe sentiment [--channel CHANNEL]`
- **Ação**: `GET /api/sentiment/scores?channel=CHANNEL`
- **Output**: Sentiment scores + vibe + stream health

#### 9. `bytecli observe history [--channel CHANNEL] [--limit N]`
- **Ação**: `GET /api/observability/history?channel=CHANNEL&limit=N`
- **Output**: Timeline de snapshots

#### 10. `bytecli goals list`
- **Ação**: `GET /api/control-plane` → extrai `goals` do payload
- **Output**: Tabela com id, name, risk, interval, enabled, cron, last_run

#### 11. `bytecli goals enable <goal_id>`
- **Ação**: `PUT /api/control-plane` com goals atualizado (enabled=true)
- **Output**: Confirmação

#### 12. `bytecli goals disable <goal_id>`
- **Ação**: `PUT /api/control-plane` com goals atualizado (enabled=false)
- **Output**: Confirmação

#### 13. `bytecli goals add --name NAME --prompt PROMPT --risk RISK --interval SECONDS [--cron EXPR]`
- **Ação**: `PUT /api/control-plane` com goal adicionado à lista
- **Output**: Goal criado

#### 14. `bytecli goals remove <goal_id>`
- **Ação**: `PUT /api/control-plane` com goal removido da lista
- **Output**: Confirmação

#### 15. `bytecli goals show <goal_id>`
- **Ação**: `GET /api/control-plane` → filtra goal pelo id
- **Output**: Detalhes do goal (id, name, prompt, risk, interval, cron, enabled, kpi_name, target_value, window_minutes, comparison, session_result)

#### 16. `bytecli actions list [--status STATUS] [--limit N]`
- **Ação**: `GET /api/action-queue?status=STATUS&limit=N`
- **Output**: Tabela com id, kind, risk, title, status, created_at

#### 17. `bytecli actions approve <action_id> [--note NOTE]`
- **Ação**: `POST /api/action-queue/<action_id>/decision` com `{"decision": "approve", "note": NOTE}`
- **Output**: Confirmação

#### 18. `bytecli actions reject <action_id> [--note NOTE]`
- **Ação**: `POST /api/action-queue/<action_id>/decision` com `{"decision": "reject", "note": NOTE}`
- **Output**: Confirmação

#### 19. `bytecli channel context [--channel CHANNEL]`
- **Ação**: `GET /api/channel-context?channel=CHANNEL`
- **Output**: Context completo (game, vibe, persona, recent chat, state)

#### 20. `bytecli channel config [--channel CHANNEL]`
- **Ação**: `GET /api/channel-config?channel=CHANNEL`
- **Output**: Config do canal

#### 21. `bytecli channel config set <key> <value> [--channel CHANNEL]`
- **Ação**: `PUT /api/channel-config` com `{key: value, channel_id: CHANNEL}`
- **Output**: Config atualizada

#### 22. `bytecli channel notes [--channel CHANNEL]`
- **Ação**: `GET /api/agent-notes?channel=CHANNEL`
- **Output**: Notas do agente

#### 23. `bytecli channel notes set <notes> [--channel CHANNEL]`
- **Ação**: `PUT /api/agent-notes` com `{notes: notes, channel_id: CHANNEL}`
- **Output**: Notas atualizadas

#### 24. `bytecli channel join <channel_login>`
- **Ação**: `POST /api/channel-control` com `{action: "join", channel_login: CHANNEL}`
- **Output**: Resultado do join

#### 25. `bytecli channel part <channel_login>`
- **Ação**: `POST /api/channel-control` com `{action: "part", channel_login: CHANNEL}`
- **Output**: Resultado do part

#### 26. `bytecli channel list`
- **Ação**: `POST /api/channel-control` com `{action: "list"}`
- **Output**: Lista de canais conectados

#### 27. `bytecli memory list [--channel CHANNEL] [--limit N]`
- **Ação**: `GET /api/semantic-memory?channel=CHANNEL&limit=N`
- **Output**: Entradas de memória semântica

#### 28. `bytecli memory search <query> [--channel CHANNEL] [--limit N]`
- **Ação**: `GET /api/semantic-memory?channel=CHANNEL&query=QUERY&limit=N`
- **Output**: Resultados da busca semântica

#### 29. `bytecli memory add <content> [--channel CHANNEL] [--type TYPE] [--tags TAGS]`
- **Ação**: `PUT /api/semantic-memory` com payload
- **Output**: Entrada criada

#### 30. `bytecli persona show [--channel CHANNEL]`
- **Ação**: `GET /api/persona-profile?channel=CHANNEL`
- **Output**: Perfil de persona completo

#### 31. `bytecli persona update [--channel CHANNEL] [--name NAME] [--tone TONE] [--lore LORE]`
- **Ação**: `PUT /api/persona-profile` com payload
- **Output**: Perfil atualizado

#### 32. `bytecli clips jobs`
- **Ação**: `GET /api/clip-jobs`
- **Output**: Lista de clip jobs

#### 33. `bytecli clips vision`
- **Ação**: `GET /api/vision/status`
- **Output**: Status do pipeline de visão

#### 34. `bytecli playbooks list [--channel CHANNEL]`
- **Ação**: `GET /api/ops-playbooks?channel=CHANNEL`
- **Output**: Lista de playbooks com status

#### 35. `bytecli playbooks trigger <playbook_id> [--channel CHANNEL] [--force]`
- **Ação**: `POST /api/ops-playbooks/trigger` com payload
- **Output**: Resultado do trigger

#### 36. `bytecli webhooks list [--channel CHANNEL]`
- **Ação**: `GET /api/webhooks?channel=CHANNEL`
- **Output**: Lista de webhooks registrados

#### 37. `bytecli webhooks add <url> [--channel CHANNEL] [--events EVENTS] [--secret SECRET]`
- **Ação**: `PUT /api/webhooks` com payload
- **Output**: Webhook criado

#### 38. `bytecli webhooks test <webhook_id> [--channel CHANNEL]`
- **Ação**: `POST /api/webhooks/test` com payload
- **Output**: Resultado do teste

#### 39. `bytecli report show [--channel CHANNEL]`
- **Ação**: `GET /api/observability/post-stream-report?channel=CHANNEL`
- **Output**: Relatório pós-stream

#### 40. `bytecli report generate [--channel CHANNEL]`
- **Ação**: `GET /api/observability/post-stream-report?channel=CHANNEL&generate=true`
- **Output**: Relatório gerado ao vivo

#### 41. `bytecli chat <mensagem> [--channel CHANNEL]`
- **Ação**: Usa `POST /api/autonomy/tick` com `force=true` para forçar o agente a enviar mensagem, OU uma futura rota dedicada `/api/chat/send`
- **Nota**: Esse é o caso de uso "eu peço posta no chat um ASCII do Goku, vc aciona o agent via CLI e ele posta"

> **Decisão de Design para `bytecli chat`**: O sistema atual não tem um endpoint direto "envie essa mensagem no chat". O mecanismo mais próximo é forçar um tick de autonomia com um goal customizado. Para o MVP, podemos criar um endpoint leve `/api/chat/send` em `dashboard_server_routes_post.py` que recebe `{text, channel_id}` e chama `send_reply` na bridge IRC. Isso é uma **única função nova no backend** (~20 linhas).

#### 42. `bytecli conversions list [--channel CHANNEL] [--limit N]`
- **Ação**: `GET /api/observability/conversions?channel=CHANNEL&limit=N`
- **Output**: Conversões de revenue attribution
- **Alias**: `bytecli revenue list` (alias para compatibilidade)

#### 43. `bytecli conversions add [--channel CHANNEL] --event EVENT --value VALUE`
- **Ação**: `POST /api/observability/conversion` com payload
- **Output**: Conversão registrada
- **Alias**: `bytecli revenue add` (alias para compatibilidade)

---

## Fluxo de Dados da CLI

```
                      ┌──────────────────┐
                      │   Operador CLI   │
                      │  bytecli <cmd>   │
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │  cli/main.py     │
                      │  argparse parse  │
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │ cli/client.py    │
                      │ HTTP + Auth      │
                      └────────┬─────────┘
                               │ HTTP (localhost:7860)
                      ┌────────▼─────────┐
                      │   Dashboard API  │
                      │  (bot/dashboard) │
                      └────────┬─────────┘
                               │ in-process calls
                      ┌────────▼─────────┐
                      │  Core Singletons │
                      │  (control_plane, │
                      │   observability, │
                      │   persistence…)  │
                      └──────────────────┘
```

---

## Novo Endpoint no Backend (único código novo no backend)

#### [MODIFY] `bot/dashboard_server_routes_post.py`

Adicionar handler `_handle_chat_send`:
```python
def _handle_chat_send(handler: Any) -> None:
    payload = require_auth_and_read_payload(handler)
    if payload is None:
        return
    text = str(payload.get("text", "")).strip()
    channel = str(payload.get("channel_id", "")).strip() or None
    if not text:
        send_invalid_request(handler, "text is required")
        return
    # Dispatch via IRC bridge
    from bot.runtime_config import irc_channel_control
    # For direct chat, we use prompt_runtime
    import asyncio
    from bot.prompt_runtime import handle_byte_prompt_text
    loop = asyncio.new_event_loop()
    replies = []
    async def collect_reply(t: str) -> None:
        replies.append(t)
    try:
        loop.run_until_complete(
            handle_byte_prompt_text(text, "cli_operator", collect_reply, channel_id=channel)
        )
    finally:
        loop.close()
    handler._send_json({"ok": True, "replies": replies, "text": text})
```

E registrar na rota:
```python
_POST_ROUTE_HANDLERS["/api/chat/send"] = _handle_chat_send
```

Isso permite que o operador envie `bytecli chat "desenha um ASCII do Goku"` e o agente processe via prompt_runtime (passando pelo ASCII art detector, grounding, etc.) e poste no chat.

---

## Configuração (`~/.byterc`)

```ini
[default]
url = http://localhost:7860
token = meu-token-admin-aqui
```

---

## Verificação

### Testes Automatizados

1. **Unit tests do client**: Testar `ByteClient` com mock HTTP responses
2. **Unit tests dos comandos**: Testar parse de argumentos e formatação de output
3. **Unit tests do config**: Testar leitura de `~/.byterc` e env vars

```bash
# Rodar testes da CLI
python -m pytest cli/tests/ -v
```

### Teste de Integração (manual, com agente rodando)

1. Iniciar o agente: `python -m bot.main`
2. Verificar saúde: `python -m cli status`
3. Listar goals: `python -m cli goals list`
4. Suspender agente: `python -m cli agent suspend --reason "teste cli"`
5. Resumir agente: `python -m cli agent resume`
6. Enviar mensagem: `python -m cli chat "faz um ASCII do Goku"` (requer endpoint novo)
7. Ver observabilidade: `python -m cli observe`
8. Ver sentimento: `python -m cli observe sentiment`

### Teste Manual Passo a Passo para o Revisor

1. Garanta que o `.env` tenha `BYTE_DASHBOARD_ADMIN_TOKEN=algum-token`
2. Inicie o bot: `python -m bot.main`
3. Em outro terminal: `python -m cli --token algum-token status`
4. Deve retornar status do agente com health check OK

---

## Ordem de Implementação

| Fase | Módulos | Descrição |
|------|---------|-----------|
| 1 | `cli/config.py`, `cli/client.py`, `cli/formatters.py` | Infra base |
| 2 | `cli/main.py`, `cli/__main__.py`, `cli/__init__.py` | Entry point + dispatcher |
| 3 | `cli/commands/status.py`, `cli/commands/control.py` | Comandos core (status + agent) |
| 4 | `cli/commands/goals.py`, `cli/commands/actions.py` | Gestão de goals e ações |
| 5 | `cli/commands/channel.py`, `cli/commands/observe.py` | Canal e observabilidade |
| 6 | `cli/commands/memory.py`, `cli/commands/persona.py` | Memória e persona |
| 7 | `cli/commands/clips.py`, `cli/commands/playbooks.py` | Clips e playbooks |
| 8 | `cli/commands/webhooks.py`, `cli/commands/report.py`, `cli/commands/chat.py` | Webhooks, relatório, chat direto |
| 9 | `bot/dashboard_server_routes_post.py` (MODIFY) | Endpoint `/api/chat/send` |
| 10 | `cli/tests/` | Testes unitários |

---

## Resumo de Impacto

- **Arquivos novos**: ~17 (todo o pacote `cli/`)
- **Arquivos modificados**: 1 (`bot/dashboard_server_routes_post.py` — novo endpoint `/api/chat/send`)
- **Dependências novas**: 0 (apenas stdlib)
- **Risco**: Baixo — a CLI é um cliente HTTP independente, não altera o core do agente
- **Cobertura**: 100% dos 31 endpoints da API + 1 novo endpoint para chat direto
- **Total de comandos**: 43 (incluindo `goals show` e aliases `revenue`→`conversions`)

### Fase 11: Documentação Help Orientada a IA (Completed ✅)
- **Objetivo**: Enriquecer todos os comandos e subcomandos com textos de ajuda semânticos, _epilogs_ (exemplos de uso), meta-variáveis e uma _cheat-sheet_ completa no comando raiz.
- **Implementação**: Todos os 15+ módulos (`memory.py`, `goals.py`, `playbooks.py`, etc) foram atualizados com `argparse.RawDescriptionHelpFormatter` para preservar formatação e fornecer contexto rico para ingestão por LLMs.
- **Status**: Help detalhado validado e funcional.
