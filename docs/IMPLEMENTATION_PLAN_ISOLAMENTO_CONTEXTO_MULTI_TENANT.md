# Plano de Implementação: Isolamento de Contexto Multi-Canal (SaaS-Ready)

**Versão:** 1.0
**Status:** Planejado / Auditoria Concluída
**Objetivo:** Resolver o vazamento de dados (Cross-Channel Data Leakage) entre canais Twitch, isolando o histórico de chat e a análise de sentimento por canal.

---

## 1. Diagnóstico do Estado Atual (Airgap Detected)

A auditoria confirmou que:
1.  `bot/logic_context.py` instancia um objeto único `context` (Singleton).
2.  `bot/sentiment_engine.py` instancia um objeto único `sentiment_engine` (Singleton).
3.  O `irc_handlers.py` alimenta esses objetos globais com mensagens de todos os canais conectados.
4.  O Prompt de IA é construído usando o histórico global, misturando conversas do Canal A com o Canal B.

---

## 2. Nova Arquitetura: Hybrid Namespace Isolation

A infraestrutura permanece compartilhada (eficiência de recursos), mas os dados mutáveis (Contexto e Vibe) são isolados por uma chave `channel_id`.

### 2.1 Componentes a serem Refatorados

| Componente | Mudança | Impacto |
| :--- | :--- | :--- |
| `StreamContext` | Transformar em `ContextManager` (dict de instâncias) | Isolamento total do histórico |
| `SentimentEngine` | Refatorar para gerenciar deques por canal | Vibe independente por live |
| `PromptRuntime` | Aceitar `StreamContext` dinâmico em vez de singleton | Flexibilidade no fluxo de prompt |
| `IRC Handlers` | Injetar o contexto correto baseado na origem da mensagem | Fim do vazamento de dados |

---

## 3. Roteiro de Execução

### Fase 1: Isolamento de Contexto (Core) [CONCLUÍDA ✅]
1.  **`bot/logic_context.py`**:
    *   Renomear `context` para `_global_context_legacy` (temporário) e depois remover. [OK]
    *   Criar a classe `ContextManager` com **`threading.Lock()`** para garantir operações atômicas em ambientes multi-thread. [OK]
    *   Implementar métodos `get(channel_id)` e `cleanup(channel_id)` protegidos pelo lock. [OK]
    *   Garantir que `get()` instancie um novo `StreamContext` caso não exista. [OK]
2.  **`bot/logic.py`**:
    *   Atualizar exportações para incluir o `context_manager`. [OK]
3.  **`bot/prompt_runtime.py`**:
    *   Atualizar `handle_byte_prompt_text` para aceitar um argumento opcional `channel_id` ou `context_obj`. [OK]
    *   Modificar `build_prompt_runtime` para receber o contexto específico. [OK]

### Fase 2: Isolamento de Sentimento
1.  **`bot/sentiment_engine.py`**:
    *   Modificar `_events` para ser um `dict[str, deque]` mapeado por canal.
    *   Atualizar `ingest_message`, `get_scores` e `get_vibe` para exigir o `channel_id`.
2.  **`bot/sentiment_constants.py`**:
    *   Manter constantes, mas validar se os limites fazem sentido por canal.

### Fase 3: Integração no Runtime
1.  **`bot/irc_handlers.py`**:
    *   Em `_handle_privmsg`, capturar o `channel` da mensagem.
    *   Recuperar o contexto específico via `context_manager.get(channel)`.
    *   Passar este contexto para todas as chamadas subsequentes (`ingest_message`, `remember_user_message`, `handle_byte_prompt_text`).
2.  **`bot/autonomy_logic.py`**:
    *   *Nota Crítica:* Autonomia atualmente é global. Precisamos decidir se o loop de autonomia rodará para "o canal principal" ou se criaremos instâncias de tick por canal (Recomendado: Iniciar com o canal principal mas permitir expansão).

### Fase 4: Autolimpeza (Memory Management)
1.  Implementar um `cleanup_task` no `ContextManager` que remove contextos de canais que não enviam mensagens há mais de 2 horas.
2.  **Agendamento**: Utilizar `asyncio.create_task()` para rodar um loop de purga periódico (ex: a cada 30 minutos).
    *   *Mecanismo:* Um método `async def start_cleanup_loop(self)` que executa um `while True` com `await asyncio.sleep(1800)`.
    *   *Integração:* Iniciar a tarefa no `run_with_channel_control` em `bootstrap_runtime.py`, garantindo que o ciclo de vida da purga esteja atrelado ao ciclo de vida do bot.

---

## 4. Validação e Testes

O plano só será considerado concluído após a passagem dos seguintes testes:

1.  **`bot/tests/audit_data_leak.py`**: Deve falhar na detecção de vazamento (ou seja, o segredo do Canal A não pode aparecer no prompt do Canal B).
2.  **Novo Teste de Concorrência**: Simular 10 mensagens por segundo em 5 canais e verificar se a `vibe` de cada um permanece coerente com suas próprias mensagens.
3.  **Teste de Regressão "Se Apresente"**: Confirmar que o atalho de intro funciona em múltiplos canais sem fallback.

---

## 5. Cronograma Estimado (Dev Senior Pace)
*   **Fase 1**: 60 min
*   **Fase 2**: 30 min
*   **Fase 3**: 45 min
*   **Fase 4**: 20 min
*   **Total**: \~2.5 horas de execução cirúrgica.

---
*Assinado: Executor Tático - Byte Bot v1.4*
