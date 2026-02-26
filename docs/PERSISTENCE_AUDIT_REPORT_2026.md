# Relatório de Auditoria: Persistência e Memória de Longo Prazo (Supabase)

**Data:** 26 de Fevereiro de 2026
**Status:** DISCREPÂNCIA DETECTADA (Pronto para Planejamento)
**Autor:** Byte Bot via Gemini CLI

---

## 1. Sumário Executivo
A auditoria técnica da camada de persistência revelou que, embora o Byte Bot esteja conectado ao Supabase, a utilização do banco de dados é predominantemente **unidirecional (telemetria)** e não **funcional (estado)**. O bot "cospe" logs para o banco, mas não "lê" dele para restaurar sua inteligência ou configurações após um reinício.

---

## 2. Diagnóstico Técnico

### 2.1 Fragmentação de Conexão
Existem duas implementações paralelas e desconectas:
1.  **`supabase_client.py`**: Usa o SDK oficial da Supabase. Focado em logs de mensagens, respostas e eventos (Telemetria). É do tipo "fire-and-forget".
2.  **`clip_jobs_store.py`**: Usa `psycopg2` (conexão direta Postgres). Focado em persistência de estado dos jobs de clips. É a única parte do sistema que realmente "lembra" de algo após o restart.

### 2.2 O "Gargalo da Amnésia"
*   **Contexto Multi-Tenant:** O `ContextManager` e o `SentimentEngine` são **100% in-memory**. Se o bot for reiniciado, todos os contextos de canais, vibes e aprendizados recentes são perdidos.
*   **Configuração:** Configurações de canais dependem de variáveis de ambiente. Não há gestão dinâmica e persistente de presença.

---

## 3. Sugestões de Upgrade (Roteiro de Elite)

1.  **Estado Híbrido (Write-through Cache)**: Snapshot do `StreamContext` no Supabase.
2.  **Configuração Dinâmica**: Tabela `channels_config` para gerenciar presença via comando.
3.  **Memória Vetorial (RAG)**: Uso de **pgvector** para buscas semânticas em históricos passados.

---

## 4. Blueprint Arquitetural (Para o Agente Planner)

Esta seção detalha a estrutura interna do bot para que um especialista possa projetar a implementação de persistência.

### 4.1 Entidades de Dados (Estado Atual em RAM)

#### A. `StreamContext` (Classe em `bot/logic_context.py`)
Representa a "consciência imediata" de um canal.
*   `current_game` (str): Jogo sendo jogado.
*   `stream_vibe` (str): Vibe calculada (ex: Hyped, Chill).
*   `last_event` (str): Último log descritivo.
*   `style_profile` (str): Tom de voz do bot para aquele canal.
*   `live_observability` (dict): Chaves fixas (`game`, `movie`, `series`, `youtube`, `x`, `topic`) com valores textuais.
*   `recent_chat_entries` (list[str]): Últimas 12 mensagens (histórico de trabalho).
*   `last_byte_reply` (str): O que o bot disse por último.
*   `last_activity` (float): Timestamp unix para controle de TTL.

#### B. `ContextManager` (Classe em `bot/logic_context.py`)
Gerencia o dicionário de instâncias de `StreamContext`.
*   `self._contexts`: `dict[str, StreamContext]` mapeado por `channel_id`.
*   `self._lock`: `threading.Lock` garantindo thread-safety.

#### C. `SentimentEngine` (Classe em `bot/sentiment_engine.py`)
Motor de vibração isolado.
*   `self._channel_events`: `dict[str, deque]` com timestamps e scores.
*   `self._last_activity`: `dict[str, float]` mapeando canais.

### 4.2 Fluxo de Mensagem e Pontos de Injeção

```text
IRC/EventSub Message ->
  irc_handlers._handle_privmsg ->
    1. ContextManager.get(channel_id) -> Retorna StreamContext
    2. SentimentEngine.ingest_message(channel_id, text)
    3. StreamContext.remember_user_message(author, text)
    4. agent_inference(prompt, author, client, context_obj) -> Chama IA
    5. StreamContext.remember_bot_reply(reply)
```

### 4.3 Recomendação de Mudança para Persistência

O Agent Planner deve focar nos seguintes **Hot Spots**:

1.  **Middleware de Persistência**: Criar um `bot/persistence_layer.py` que abstraia tanto o `supabase-py` quanto o `psycopg2`.
2.  **Update em `ContextManager.get()`**:
    *   *Lógica:* Tentar buscar em memória -> Se não existir, tentar buscar no Supabase (tabela `channel_state`) -> Se não existir, criar novo.
3.  **Hook em `StreamContext._touch()`**:
    *   *Lógica:* Sempre que o contexto mudar, disparar um `save_to_db` (preferencialmente assíncrono para não travar o bot).
4.  **Schema Supabase Sugerido**:
    *   `channel_state`: `channel_id (PK)`, `vibe`, `observability (jsonb)`, `last_reply`, `updated_at`.
    *   `channel_history`: `id`, `channel_id`, `author`, `message`, `ts` (para reconstruir o `recent_chat_entries`).

---
## 5. Conclusão
O Byte tem um "diário" (logs), mas não tem uma "memória de trabalho persistente". A infraestrutura de hardware (Supabase) está pronta, mas o software ainda opera como um "processo efêmero".

**Objetivo para o Planner:** Transformar o bot de "Volátil" para "Stateful".

---
*Relatório gerado para o Especialista Planner via Executor Tático.*
