# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.2
**Data:** 26 de Fevereiro de 2026
**Status:** PLANEJADO (Com Cláusulas de Segurança)
**Objetivo:** Transicionar o Byte Bot para um modelo stateful com resiliência de elite.

---

## 1. Arquitetura: Write-Through Cache com Fallback

1.  **Leitura:** Preferencialmente em RAM.
2.  **Lazy Load (Async):** Busca no Supabase se não estiver em RAM.
3.  **Escrita (Non-blocking):** Disparada via `asyncio.create_task` ou `run_coroutine_threadsafe`.
4.  **Resiliência:** Em caso de queda do Supabase, o bot utiliza variáveis de ambiente como fallback para lista de canais.

---

## 2. Roteiro de Implementação Atualizado

### Fase 1: Camada de Persistência e Fallback [CONCLUÍDA ✅]
*   Criar `PersistenceLayer` com suporte a timeouts curtos. [OK]
*   Implementar lógica de boot: `get_active_channels()` -> `try Supabase else Env`. [OK]
*   Unificar telemetria do `supabase_client.py`. [OK]

### Fase 2: ContextManager Assíncrono e Thread-Safe
*   **Refatoração:** `async def get(channel_id)`.
*   **Mapeamento de Callers:**
    *   Handlers IRC/EventSub: Atualizar para `await`.
    *   Dashboard (Thread Síncrona): Implementar `asyncio.run_coroutine_threadsafe` para acessar o `get()`.
*   **Garantia:** Injetar o `main_event_loop` no `ContextManager` durante o boot para permitir chamadas cross-thread.

### Fase 3: Hooks de Auto-Salvamento Robustos
*   Modificar `StreamContext._touch()` com o guardião de loop:
    ```python
    try:
        asyncio.get_running_loop().create_task(...)
    except RuntimeError:
        asyncio.run_coroutine_threadsafe(..., main_loop)
    ```

---

## 3. Matriz de Riscos e Mitigação

| Risco | Impacto | Mitigação |
| :--- | :--- | :--- |
| Supabase Offline no Boot | Bot não entra em canais | Fallback automático para `TWITCH_CHANNEL_LOGINS`. |
| Latência no Supabase | Atraso na resposta do chat | Escritas são 100% assíncronas (fire-and-forget). |
| Race Condition no Dashboard | Dados inconsistentes na UI | Uso de Lock assíncrono e `run_coroutine_threadsafe`. |

---

## 4. Validação Científica (Durabilidade e Resiliência)
*   **Teste de Queda:** Simular banco offline e garantir que o bot entra no canal via ENV.
*   **Teste de Cross-Thread:** Atualizar contexto via Dashboard e validar se o save foi disparado corretamente no loop principal.

---
*Plano revisado e validado contra regressões de concorrência.*
