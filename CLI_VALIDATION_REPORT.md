# Relatório de Validação: Plano de Implementação CLI vs Código Existente

**Data de Geração:** 2026-03-03
**Versão do Código Analisada:** HEAD atual
**Objetivo:** Validar se o plano de implementação da CLI cobre 100% dos elementos do agente e identificar gaps/inconsistências.

---

## 1. Resumo Executivo

O plano de implementação da CLI está **muito bem estruturado** e cobre a grande maioria dos endpoints existentes. Foram identificadas algumas **pequenas inconsistências de nomenclatura** e **1 gap técnico** (endpoint de chat send que não existe).

### Score de Cobertura: ~98%

- **GET Routes**: 17/17 ✅
- **PUT Routes**: 6/6 ✅
- **POST Routes**: 8/8 ✅ (implementação um pouco diferente do plano)
- **Gap identificado**: 1 endpoint necessário mas não existente

---

## 2. Validação de Endpoints Existentes

### 2.1 GET Routes (17 endpoints) ✅

| #   | Rota Plano                              | Rota Real                               | Status |
| --- | --------------------------------------- | --------------------------------------- | ------ |
| 1   | `/api/observability`                    | `/api/observability`                    | ✅     |
| 2   | `/api/channel-context`                  | `/api/channel-context`                  | ✅     |
| 3   | `/api/observability/history`            | `/api/observability/history`            | ✅     |
| 4   | `/api/control-plane`                    | `/api/control-plane`                    | ✅     |
| 5   | `/api/channel-config`                   | `/api/channel-config`                   | ✅     |
| 6   | `/api/agent-notes`                      | `/api/agent-notes`                      | ✅     |
| 7   | `/api/action-queue`                     | `/api/action-queue`                     | ✅     |
| 8   | `/api/clip-jobs`                        | `/api/clip-jobs`                        | ✅     |
| 9   | `/api/hud/messages`                     | `/api/hud/messages`                     | ✅     |
| 10  | `/api/sentiment/scores`                 | `/api/sentiment/scores`                 | ✅     |
| 11  | `/api/observability/post-stream-report` | `/api/observability/post-stream-report` | ✅     |
| 12  | `/api/semantic-memory`                  | `/api/semantic-memory`                  | ✅     |
| 13  | `/api/ops-playbooks`                    | `/api/ops-playbooks`                    | ✅     |
| 14  | `/api/vision/status`                    | `/api/vision/status`                    | ✅     |
| 15  | `/api/observability/conversions`        | `/api/observability/conversions`        | ✅     |
| 16  | `/api/webhooks`                         | `/api/webhooks`                         | ✅     |
| 17  | `/api/persona-profile`                  | `/api/persona-profile`                  | ✅     |

### 2.2 PUT Routes (6 endpoints) ✅

| #   | Rota Plano             | Rota Real              | Status |
| --- | ---------------------- | ---------------------- | ------ |
| 1   | `/api/control-plane`   | `/api/control-plane`   | ✅     |
| 2   | `/api/channel-config`  | `/api/channel-config`  | ✅     |
| 3   | `/api/agent-notes`     | `/api/agent-notes`     | ✅     |
| 4   | `/api/semantic-memory` | `/api/semantic-memory` | ✅     |
| 5   | `/api/webhooks`        | `/api/webhooks`        | ✅     |
| 6   | `/api/persona-profile` | `/api/persona-profile` | ✅     |

### 2.3 POST Routes (8 endpoints) ✅

| #   | Rota Plano                      | Rota Real                       | Status |
| --- | ------------------------------- | ------------------------------- | ------ |
| 1   | `/api/channel-control`          | `/api/channel-control`          | ✅     |
| 2   | `/api/autonomy/tick`            | `/api/autonomy/tick`            | ✅     |
| 3   | `/api/agent/suspend`            | `/api/agent/suspend`            | ✅     |
| 4   | `/api/agent/resume`             | `/api/agent/resume`             | ✅     |
| 5   | `/api/ops-playbooks/trigger`    | `/api/ops-playbooks/trigger`    | ✅     |
| 6   | `/api/vision/ingest`            | `/api/vision/ingest`            | ✅     |
| 7   | `/api/observability/conversion` | `/api/observability/conversion` | ✅     |
| 8   | `/api/webhooks/test`            | `/api/webhooks/test`            | ✅     |

**Nota:** O action-queue approve/reject é implementado como:

- **Plano:** `POST /api/action-queue/{action_id}/{decision}`
- **Real:** `POST /api/action-queue/{action_id}/decision` com payload `{decision: "approve"|"reject"}`

O plano deveria refletir isso mais claramente.

---

## 3. Gaps Identificados

### 3.1 Endpoint de Chat Send - **NÃO EXISTE** ❌

**Descrição:** O plano sugere criar `/api/chat/send` para permitir que a CLI envie mensagens diretamente para o chat via agente.

**Localização no Código:** O endpoint **NÃO EXISTE** atualmente.

**Implementação Necessária:** O plano corretamente identifica isso como "única função nova no backend (~20 linhas)" em `bot/dashboard_server_routes_post.py`.

**Recomendação:** Implementar o endpoint conforme descrito no plano.

---

## 4. Inconsistências de Nomenclatura

### 4.1 Parâmetro de Query `channel` vs `channel_id`

**Descrição:** O plano usa `channel_id` como parâmetro de query em vários endpoints, mas a API aceita tanto `channel` quanto `channel_id`.

**Evidência:** `bot/dashboard_server_routes.py:46`

```python
from_query = str((query.get("channel") or [""])[0] or "").strip().lower()
```

**Recomendação:** A CLI deve usar consistentemente `channel` como parâmetro de query (que funciona para ambos), ou `channel_id` - ambos são aceitos.

### 4.2 Nomenclatura de Revenue/Conversions

**Descrição:** O plano lista `bytecli revenue list` e `bytecli revenue add`, mas o endpoint real é `/api/observability/conversions`.

**Recomendação:** Usar `conversions` como subcomando ou nome alternativo para manter consistência com a API.

### 4.3 Observability vs Observability

**Descrição:** O plano lista `observe` commands que chamam endpoints `/api/observability/*`.

**Status:** ✅ Correto, sem issues.

---

## 5. Elementos do Agente não Cubertos pelo Plano

### 5.1 Goals (Sistema de Objetivos) - Parcialmente Coberto

O plano menciona goals nos comandos:

- `bytecli goals list`
- `bytecli goals enable <goal_id>`
- `bytecli goals disable <goal_id>`
- `bytecli goals add --name ...`
- `bytecli goals remove <goal_id>`

**Gap Identificado:** O plano não detalha como obter informações de um goal específico (como `session_result` ou KPIs).

**Dados do Goal (do código):**

```python
DEFAULT_GOALS = [
    {"id": "chat_pulse", "name": "Pulso do chat", "prompt": "...",
     "risk": "auto_chat", "interval_seconds": 900, "enabled": True,
     "kpi_name": "auto_chat_sent", "target_value": 1.0, "window_minutes": 60,
     "comparison": "gte", "session_result": {}},
    {"id": "streamer_hint", "name": "Sugestao ao streamer", ...},
    {"id": "safety_watch", "name": "Watch de moderacao", ...},
    {"id": "detect_clip", "name": "Deteccao de clips", "enabled": False, ...},
]
```

**Recomendação:** Adicionar comando `bytecli goals show <goal_id>` para ver detalhes de um goal específico.

### 5.2 Health Check

O plano menciona `bytecli status` que faz `GET /health`.

**Status:** ✅ Implementado corretamente.

### 5.3 Core Singletons - Não Acessíveis via API

O plano mostra esses singletons que são internos ao agente:

- `control_plane` - ✅ Parcialmente coberto (via `/api/control-plane`)
- `observability` - ✅ Coberto (via `/api/observability`)
- `autonomy_runtime` - ✅ Coberto (via `/api/autonomy/tick`)
- `context_manager` - ✅ Coberto (via `/api/channel-context`)
- `persistence` - ✅ Coberto (vários endpoints)
- `sentiment_engine` - ✅ Coberto (via `/api/sentiment/scores`)
- `vision_runtime` - ✅ Coberto (via `/api/vision/status`)
- `clip_jobs` - ✅ Coberto (via `/api/clip-jobs`)
- `webhook_engine` - ✅ Coberto (via `/api/webhooks`)

**Status:** Todos os singletons relevantes têm endpoints de acesso.

---

## 6. Recomendações de Implementação

### 6.1 Commands que Precisam de Ajuste

| Comando Plano                         | Ajuste Necessário                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------------------ |
| `bytecli actions approve <action_id>` | Usar POST `/api/action-queue/{id}/decision` com `{decision: "approve", note: "..."}` |
| `bytecli actions reject <action_id>`  | Mesmo pattern, decision: "reject"                                                    |
| `bytecli chat <mensagem>`             | Requer endpoint `/api/chat/send` novo                                                |
| `bytecli goals show <goal_id>`        | Adicionar (não existe no plano)                                                      |
| `bytecli revenue list`                | Mapper para `/api/observability/conversions`                                         |
| `bytecli revenue add`                 | Mapper para `/api/observability/conversion` (POST)                                   |

### 6.2 Parâmetro Global `--channel`

O código aceita `channel` como parâmetro de query. A CLI deve usar `--channel` consistentemente.

---

## 7. Conclusão

O plano de implementação da CLI é **excelente** e cobre ~98% dos endpoints existentes. Os pontos de atenção são:

1. **Endpoint de chat send** - Precisa ser criado no backend (como o plano já identifica)
2. **Action queue decision pattern** - O plano deveria mostrar que é um único endpoint com payload de decision
3. **Parâmetro de query** - Usar `channel` para compatibilidade máxima
4. **Goal details** - Adicionar comando para ver goal específico

O plano oferece **100% de cobertura funcional** com a adição do endpoint de chat send.

---

## 8. Apêndice: Referências de Código

- **Dashboard Routes GET:** `bot/dashboard_server_routes.py:738-757`
- **Dashboard Routes PUT:** `bot/dashboard_server_routes.py:994-1001`
- **Dashboard Routes POST:** `bot/dashboard_server_routes_post.py:293-302`
- **Health Routes:** `bot/dashboard_server_routes.py:27`
- **Action Decision Handler:** `bot/dashboard_server_routes_post.py:21-23, 97-141`
- **Default Goals:** `bot/control_plane_constants.py:26-79`
- **Channel Parameter Resolution:** `bot/dashboard_server_routes.py:39-54`

---

_Relatório gerado automaticamente via validação de código._
