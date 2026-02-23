# Relatório de Validação: byte-costreamer-roadmap.md

**Data:** 2026-02-21  
**Analista:** opencode (análise profunda de código)  
**Arquivos analisados:** ~40 arquivos Python + frontend JS/HTML  

---

## Resumo Executivo

O roadmap analisado é **tecnicamente sólido e bem fundamentado**, mas contém **premissas incorretas sobre o estado atual do código** e **algumas duplicações de esforços planejados**. A maioria das features descritas no roadmap NÃO existe ainda no código - o que é esperado para um roadmap, mas algumas afirmações são incorretas.

---

## 1. Estado Atual: Análise do Código vs. Roadmap

### 1.1 O que EXISTE (confirmado no código)

| Feature | Arquivo | Status |
|---------|---------|--------|
| Runtime IRC + EventSub | `bootstrap_runtime.py` | ✅ Implementado |
| Contexto in-memory singleton | `logic_context.py:114` | ✅ `context = StreamContext()` |
| Prompt + Inferência | `prompt_flow.py`, `logic_inference.py` | ✅ Implementado |
| Autonomia com goals/budget | `autonomy_runtime.py`, `control_plane.py` | ✅ Implementado |
| Observabilidade (snapshots) | `observability_state.py`, `observability_snapshot.py` | ✅ Implementado |
| Dashboard operacional | `dashboard_server_routes.py`, `dashboard/main.js` | ✅ Implementado |
| Auto-contexto por links | `scene_runtime.py` (SceneMetadataService) | ✅ Implementado |
| Canal de risco (sugestões) | `control_plane_actions.py` (action queue) | ✅ Implementado |
| Commands `!vibe`, `!style`, `!scene` | `eventsub_runtime.py` | ✅ Implementado |
| Quality gates (retry/fallback) | `byte_semantics_quality.py` | ✅ Implementado |
| Contrato 1 msg / 4 linhas | `logic_constants.py:4` | ✅ Implementado |
| Channel control (IRC only) | `channel_control.py` | ✅ Implementado |

### 1.2 O que NÃO EXISTE (gap real)

| Feature | Mencionada no Roadmap | Existe no Código? |
|---------|----------------------|-------------------|
| Chat Sentiment Engine | Fase 1 | ❌ NÃO EXISTE |
| Streamer Intent Layer (modos) | Fase 1 | ❌ PARCIAL - só existe `stream_vibe` manual |
| Live Recap Engine | Fase 1 | ❌ NÃO EXISTE |
| Track privado (dashboard/webhook) | Fase 2 | ❌ NÃO EXISTE |
| Clip & Highlight Intelligence | Fase 2 | ❌ NÃO EXISTE |
| Memória persistente | Fase 3 | ❌ NÃO EXISTE - só in-memory |
| Isolamento por canal | Fase 3 | ❌ NÃO EXISTE - singleton |
| Vision Assist (screenshots) | Fase 4 | ❌ NÃO EXISTE |
| Pipeline assíncrono de clips | Fase 5 | ❌ NÃO EXISTE |

---

## 2. Problemas Críticos do Roadmap

### 2.1 Previsões Incorretas sobre o Código Atual

**PROBLEMA 1: "stream_vibe ainda é simples"**
- O roadmap diz que `stream_vibe` é simples e que não existe motor de sentimento
- **REALIDADE:** `stream_vibe` é configurável via comando `!vibe` em `eventsub_runtime.py:70-77` e está presente no context
- **PROBLEMA:** Não existe motor de sentimento automatico - isso está CORRETO no roadmap
- **VEREDICTO:** Afirmação parcialmente correta

**PROBLEMA 2: "Arquitetura ainda é majoritariamente singleton"**
- O roadmap afirma corretamente que há singletons
- **REALIDADE:** há no mínimo 5 singletons globais:
  - `context = StreamContext()` em `logic_context.py:114`
  - `control_plane = ControlPlaneState()` em `control_plane.py:162`
  - `autonomy_runtime = AutonomyRuntime()` em `autonomy_runtime.py:293`
  - `observability = ObservabilityState()` em `observability.py:3`
  - `scene_metadata_service = SceneMetadataService()` em `scene_runtime.py:16`
- **VEREDICTO:** Afirmação correta

**PROBLEMA 3: "Fase 1 - Chat Sentiment Engine"**
- O roadmap planeja criar um agregador leve sem inferência por mensagem
- **PROBLEMA:** Não há dados de chat sendo agregados para análise de sentimento no código atual. O `recent_chat_entries` store apenas mensagens brutas, sem processamento de sentimento.
- **VEREDICTO:** Feature nova necessária

### 2.2 Duplicações Planejadas

**DUPLICAÇÃO 1: Fase 2 - Track Privado vs. Fase 3 - Ação RISK_SUGGEST_STREAMER**

O `control_plane.py:63-82` e `control_plane_actions.py:65-116` **já implementam** uma fila de ações com risco `RISK_SUGGEST_STREAMER`. O roadmap na Fase 2 propõe:
> "Reusar eventos `RISK_SUGGEST_STREAMER` da fila de risco."

**PROBLEMA:** O roadmap sugere "Track privado inicial via dashboard (e webhook opcional)", mas isso **já existe parcialmente**:
- A fila de ações (`/api/action-queue`) já mostra sugestões pendentes
- Já existe `decide_action` com approve/reject em `dashboard_server_routes.py:218-272`
- O que NÃO existe é:
  - Notificação em tempo real (polling apenas)
  - Webhook para Telegram/outro canal
  - Track privado diferenciado do público

**VEREDICTO:** Duplicação PARCIAL - o roadmap corretamente identifica que deve reusar, mas não deixa claro que isso já existe.

**DUPLICAÇÃO 2: Fase 1 - Live Recap Engine vs. existing movie_fact_sheet**

Em `prompt_flow.py:162-170` existe `handle_movie_fact_sheet_prompt` que gera "ficha técnica" de filmes.

O roadmap propõe:
> "Classificador de pedido de recap em `byte_semantics`. Prompt curto de recap com base em `recent_chat_entries` + `live_observability`."

**PROBLEMA:** Isso é DIFERENTE do movie fact sheet, mas usa a mesma infraestrutura de prompt/quality gates.

**VEREDICTO:** Não é duplicação, mas depende de infra existente.

**DUPLICAÇÃO 3: Fase 3 - Persistência vs. Fase 5 - Observabilidade por tenant**

O roadmap sugere persistência epiódica (Fase 3) e depois observabilidade multi-tenant (Fase 5).

**PROBLEMA:** Não há nenhuma estrutura de banco de dados ou cache persistente no código atual. A Fase 3 assume que haverá persistência, mas não há infraestrutura para isso.

---

## 3. Análise de Qualidade do Roadmap

### 3.1 Pontos Fortes

1. **Arquitetura bem descrita** - O resumo arquitetural está preciso
2. **Fases bem separadas** - Escopo incremental faz sentido
3. **Contrato de resposta preservado** - Mantém 1 msg / 4 linhas
4. **Considera custo** - TTL, limites, budget anti-spam já existem
5. **Dashboard paridade** - Já está implementado parcialmente

### 3.2 Pontos Fracos

| Issue | Severidade | Detalhamento |
|-------|------------|--------------|
| Sem estimativas de esforço | ALTA | Sem breakdown de story points/dias-homem |
| Sem dependências explícitas | ALTA | Não mostra o que cada fase Blocking/depende |
| Testes não mencionados | MÉDIA | Sem plano de testes em nenhuma fase |
| Sem rollback strategy | MÉDIC | Cada fase deveria ter plano de rollback |
| Métricas de saída vagas | MÉDIA | "deixa de ser manual" é subjetivo |

---

## 4. Recomendações de Correção

### 4.1 Correções ao Roadmap

**C1: Atualizar "Estado Atual"**
Remover/suprimir as seções que claims features que existem:

```
- ❌ REMOVER: "stream_vibe ainda é simples" (mudar para "stream_vibe configurável manualmente, sem automação")
- ✅ CORRETO: "Memória in-memory (reinício perde histórico)"
- ✅ CORRETO: "Arquitetura singleton"
```

**C2: Adicionar explicitamente o que já existe**
Adicionar uma seção "Features já implementadas (não fazer)" para evitar retrabalho:

```markdown
## Features Já Implementadas (Baseline)

- [x] Contrato 1 msg / 4 linhas
- [x] Autonomia com goals + budget anti-spam  
- [x] Fila de risco (approve/reject)
- [x] Channel control (IRC mode)
- [x] Observabilidade (snapshots, métricas)
- [x] Dashboard operacional
- [x] Auto-contexto por links (YouTube/X)
- [x] Quality gates (retry/fallback)
```

**C4: Adicionar dependências entre fases**

| Fase | Depende de | Blocking |
|------|------------|----------|
| Fase 1 (Sentiment) | - | N/A |
| Fase 2 (Track privado) | Fase 1 | Não blocking |
| Fase 3 (Persistência) | Fase 2 | Blocking: precisa de Fase 2 estar madura |
| Fase 4 (Vision) | Fase 3 | Blocking: depende de cache/metadata |
| Fase 5 (SaaS) | Fase 3 | Blocking: precisa de persistência primeiro |

**C5: Adicionar critério de saída quantificável**

```markdown
### Fase 1 pronta quando:
- [ ] `stream_vibe` atualiza automaticamente a cada 30s baseado em sentiment score
- [ ] Modos de live (`byte modo foco`) respondem com tom observavelmente diferente (A/B test)
- [ ] Recap responde em < 2 segundos (latência medida)
- [ ] Testes unitários passando: sentiment engine > 85% accuracy
```

---

## 5. Avaliação Final

| Aspecto | Nota | Comentário |
|---------|------|------------|
| Alinhamento com código | 7/10 | Algumas previsões incorretas sobre estado atual |
| Clareza de escopo | 8/10 | Fases bem definidas |
| Duplicação evitada | 6/10 | Há sobreposição entre Fase 2/3 e código existente |
| Viabilidade técnica | 9/10 | Tudo planejado é tecnicamente possível |
| Completude | 5/10 | Falta testes, rollback, dependências |

**NOTA GERAL: 7/10** - Roadmap bom, mas precisa de correções antes de execução.

---

## 6. Próximos Passos Recomendados

1. **Atualizar o roadmap** com as correções C1-C5 acima
2. **Criar spike de sentiment engine** para validar viabilidade (1 semana)
3. **Mapear infraestrutura de persistência** necessária para Fase 3 (banco? Redis? arquivo?)
4. **Definir KPIs quantificáveis** para cada fase
5. **Revisar dependências** entre fases com o time

---

*Este relatório foi gerado por análise profunda de código do repositório twich-bot.*
