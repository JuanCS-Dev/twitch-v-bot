# Relatório de Análise: Plano de Melhoria Dashboard vs Código Agent

**Data:** 2026-02-21  
**Analista:** opencode  
**Arquivos analisados:**
- `bot/channel_control.py` (159 linhas)
- `bot/observability_state.py` (274 linhas)
- `bot/observability_snapshot.py` (204 linhas)
- `bot/dashboard_server.py` (206 linhas)
- `dashboard/app.js` (319 linhas)
- `dashboard/channel-terminal.js` (177 linhas)

---

## 1. Validação de Premissas do Plano

### 1.1 Premissas CORRETAS (alinhadas com o código)

| Premissa do Plano | Status | Evidência |
|-------------------|--------|-----------|
| Backend suporta ações `list`, `join`, `part` | ✅ CORRETO | `channel_control.py:12` - `SUPPORTED_ACTIONS = {"list", "join", "part"}` |
| API suporta payload estruturado `{action, channel}` | ✅ CORRETO | `dashboard_server.py:172-173` - aceita `action` e `channel` no payload |
| Suporte a comando textual (`command`) mantido | ✅ CORRETO | `dashboard_server.py:174-183` - mantém backward compatibility |
| Timeout configurável existe | ✅ CORRETO | `channel_control.py:11` - `CHANNEL_CONTROL_TIMEOUT_SECONDS = 6.0` |
| Bloqueio de concorrência (lock) | ✅ CORRETO | `channel_control.py:75` - `self._lock = threading.Lock()` |
| Contadores de quality gates | ✅ CORRETO | `observability_state.py:132-141` - `record_quality_gate()` |
| Contadores de token refresh | ✅ CORRETO | `observability_state.py:196-202` - `record_token_refresh()` |
| Contadores de auth failures | ✅ CORRETO | `observability_state.py:204-212` - `record_auth_failure()` |
| Eventos com nível (INFO/WARN/ERROR) | ✅ CORRETO | `observability_state.py:55-56` - cada evento tem `level` |
| `last_prompt` e `last_reply` expostos | ✅ CORRETO | `observability_snapshot.py:197-198` |
| `trigger_user_totals` disponível | ✅ CORRETO | `observability_snapshot.py:189-190` |
| Limite de linhas (<=300) respeitado | ⚠️ PARCIAL | `app.js` tem 319 linhas (excede por 6%) |

### 1.2 Premissas INCORRETAS ou INCOMPLETAS

| Premissa do Plano | Status | Detalhamento |
|-------------------|--------|--------------|
| API retorna `active_channel` | ❌ INCORRETO | O backend NÃO retorna `active_channel`. O `channel_control.py:117-123` retorna apenas `channels` (lista), sem canal ativo único. |
| Reconciliação automática após join/part | ❌ INCORRETO | **NÃO existe.** O backend não executa `list` automaticamente após operações. O frontend seria responsável por fazer essa chamada adicional. |
| Contrato recomendado de API (`request_id`) | ❌ INCORRETO | O backend NÃO suporta `request_id`. Não há mecanismo de idempotência implementado. |
| "Botao de emergencia: Recarregar estado" | ❌ INCORRETO | **NÃO existe.** Não há endpoint ou botão para forçar resync. |
| Guard de resposta atrasada (`request_id` antigo) | ❌ INCORRETO | Não há suporte a `request_id` para filtrar respostas antigas. |
| Endpoint `GET /api/channel-control` | ❌ INCORRETO | **NÃO existe.** Apenas `POST /api/channel-control` existe (`dashboard_server.py:152`). O estado de canais só é obtido via comando `list`. |

---

## 2. Lacunas Identificadas (Faltas no Plano)

### 2.1 Backend - Mudanças necessárias para suportar o plano

| # | Lacuna | Severidade | Origem |
|---|--------|------------|--------|
| 1 | Expor canal ativo (`active_channel`) no snapshot de observabilidade | **ALTA** | O plano assume que existe mas não existe no código |
| 2 | Implementar endpoint `GET /api/channel-status` para polling de estado | **ALTA** | Necessário para UI "síncrona" sem depender de comando |
| 3 | Adicionar `request_id` ao contrato de API | **MÉDIA** | Necessário para idempotência e reconciliação |
| 4 | Endpoint de emergência para forçar resync | **MÉDIA** | Plano menciona mas backend não suporta |
| 5 | Retornar timestamp da operação no response | **BAIXA** | Útil para debug e reconciliation |

### 2.2 Frontend - Features que não existem atualmente

| # | Feature Ausente | Severidade | Evidência |
|---|-----------------|------------|-----------|
| 1 | Canal ativo visualmente destacado | **ALTA** | Dashboard atual não mostra qual canal está ativo |
| 2 | Estados de UI (sending/confirming/reconciling) | **ALTA** | Só existe estado `busy` binário (`channel-terminal.js:13`) |
| 3 | Feedback transacional rico (skeleton/spinner) | **ALTA** | Apenas texto simples no output |
| 4 | Tema claro (light mode) | **ALTA** | `styles.css` é apenas dark neon |
| 5 | Design tokens CSS | **ALTA** | Sem sistema de tokens |
| 6 | Navegação por tabs | **MÉDIA** | Layout atual é uma página única longa |
| 7 | ChannelControlCard componente dedicado | **MÉDIA** | Terminal textual ainda é o controle primário |
| 8 | Componente KpiCard unificado | **BAIXA** | Cards existem mas sem padronização |

---

## 3. Análise Técnica Detalhada

### 3.1 Channel Control (IRC)

```python
# channel_control.py:105-145 - Fluxo atual
execute(action="join", channel_login="meucanal")
  → retorna: {ok, action, channels, message}
  → NÃO retorna: active_channel, request_id, timestamp
```

**Problema:** O frontend não consegue determinar "qual canal está ativo" a partir da API atual, apenas a lista de canais conectados.

**Recomendação de API mínima para suportar o plano:**

```python
# Adicionar ao response de execute():
{
    "ok": True,
    "action": "join",
    "channels": ["canal1", "canal2"],
    "active_channel": "canal1",  # <-- ADICIONAR
    "request_id": "uuid-v4",     # <-- ADICIONAR
    "timestamp": "2026-02-21T10:30:00Z"  # <-- ADICIONAR
}
```

### 3.2 Observability Snapshot

O snapshot atual (`observability_snapshot.py:129-203`) NÃO expõe:
- `active_channel` - canal IRC atualmente focado
- `pending_action` - se há operação em andamento

**Recomendação:**
```python
# Adicionar ao snapshot:
"channel_control": {
    "active_channel": active_channel_name,  # pode ser null
    "channels": list(connected_channels),
    "pending_action": "join" | "part" | null
}
```

### 3.3 Autenticação

O sistema atual suporta dois mecanismos:
1. Basic Auth via header `Authorization: Basic ...`
2. Bearer token via `Authorization: Bearer ...`
3. Token direto via `X-Byte-Admin-Token`

Todos funcionam corretamente conforme código em `channel_control.py:15-49`.

---

## 4. Riscos de Implementação

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Backend não suporta `active_channel` | ALTA | Alto | Alterar `channel_control.py` para rastrear canal ativo |
| Sem idempotência causa duplicação | MÉDIA | Alto | Adicionar `request_id` ao backend |
| Regressão visual em mobile | MÉDIA | Médio | Testes de responsividade na Fase 5 |
| Aumento de complexidade JS | MÉDIA | Médio | Manter disciplina de 300 linhas por arquivo |

---

## 5. Recomendações de Correção do Plano

### 5.1 Seções que precisam de ajuste

1. **Seção 6.2 (Requisitos de robustez)**
   - Remover menção a `request_id` até implementar no backend
   - Clarificar que "reconciliação" é responsabilidade do FRONTEND (chamar `list` após operação)
   - Adicionar endpoint de emergência como BACKLOG, não como existente

2. **Seção 6.3 (Contrato recomendado de API)**
   - Atualizar para refletir o que EXISTE vs o que é RECOMENDADO
   - Adicionar `active_channel` como necessária
   - Separar "Contrato atual" de "Proposta de evolução"

3. **Seção 7 (Refatoração técnica)**
   - `app.js` com 319 linhas excede o limite proposto. Considerar:
     - Separar render functions para arquivo próprio
     - Ou aumentar limite para 350 linhas (tolerância de ~10%)

4. **Seção 9 (Definition of Done)**
   - "Canal ativo" só é possível se backend retornar esse dado
   - Condicionar critério à implementação de `active_channel` no backend

### 5.2 Items ausentes no Plano que devem ser añadidos

| Item | Por quê |
|------|---------|
| Modificar `channel_control.py` para rastrear `active_channel` | O plano assume que existe |
| Novo endpoint `GET /api/channel-status` | Necessário para polling de estado |
| Frontend deve fazer "reconciliação" (chamar list após operation) | Backend não faz automaticamente |
| Backend deve retornar `request_id` para idempotência | Essencial para operações confiáveis |
| Testes de carga no endpoint de channel control | Com vários canais, latência pode aumentar |

---

## 6. Conclusão

O plano é **tecnicamente sólido** mas contém premissas incorretas sobre o que o backend já oferece:

- **O que existe:** API de commands, contadores de observabilidade, lock de concorrência, timeouts
- **O que falta (backend):** `active_channel`, idempotência via `request_id`, reconciliação automática, endpoint de status
- **O que falta (frontend):** Tema light, design tokens, tabs, estados de UI ricos,ChannelManager visual

**Recomendação:** Avançar com as Fase 0-1 (fundação visual), mas **paralelamente** implementar as mudanças de backend necessárias (itens da Seção 2.1) antes da Fase 2 (Canal Control UX).

---

*Gerado automaticamente via análise de código.*
