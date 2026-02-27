# Plano de Implementação: Camada de Persistência Stateful (Supabase)

**Versão:** 1.4
**Data:** 26 de Fevereiro de 2026
**Status:** FASES 1-3 CONCLUÍDAS ✅ | FASES 4-8 PLANEJADAS
**Objetivo:** Transicionar o Byte Bot para um modelo stateful, resiliente e totalmente controlável (Soberania do Agente).

---

## 1. Arquitetura: Stateful & Command-Driven [CONSOLIDADO]

1.  **RAM:** Cache de alta performance.
2.  **Supabase:** Fonte de verdade para Memória, Vibe e Configurações.
3.  **Command Flow:** Dashboard -> Persistence Layer -> Agente (via Reactive Polling ou Injeção).

---

## 2. Roteiro de Implementação (Fases 4-8)

### Fase 4: Canais Dinâmicos e Boot Sequence [PRÓXIMA]
*   **Ação:** Implementar comando `byte join` salvando em `channels_config`.
*   **Refatoração:** `resolve_irc_channel_logins` passa a ler do banco.

### Fase 5: Observabilidade Stateful (Métricas Globais)
*   Persistência de contadores e métricas acumuladas.

### Fase 6: Dashboard Integrada (Multi-Channel UI)
*   Seletor de canal e visualização de histórico persistente.

### Fase 7: Soberania e Comando (Controle de Elite) [NOVO]
*   **Panic Button:** Rota `/api/agent/suspend` para silenciar o bot globalmente em 100ms.
*   **Override de Parâmetros:** Controle deslizante na Dashboard para `Temperature` e `Top_P` por canal.
*   **Thought Injection:** Tabela `agent_notes` no Supabase. O bot lerá "notas do Juan" antes de cada inferência para alinhar o tom.
*   **Manual Tick:** Botão para disparar o loop de autonomia instantaneamente.

### Fase 8: Gestão de Memória Semântica (Vector Memory) [NOVO]
*   **Integração pgvector:** Salvar fatos marcantes como embeddings.
*   **Interface de Memória:** Dashboard permite apagar ou editar "memórias" que o bot criou, evitando que ele repita erros passados.

---

## 3. Matriz de Controles do Agente (Dashboard)

| Controle | Ação | Destino |
| :--- | :--- | :--- |
| **Silence Mode** | Pausa todas as respostas | RAM (Flags de Voo) |
| **Reset Context** | Limpa memória recente | RAM + DB |
| **Inject Instruction** | Adiciona contexto temporário | Tabela `agent_notes` |
| **Model Switch** | Troca entre Flash/Pro/Reasoning | Tabela `channels_config` |

---

## 4. Conclusão da Auditoria de Controle
A arquitetura multi-tenant criada nas Fases 1-3 foi o alicerce. Agora, as Fases 4-7 darão o "volante" do bot para você. O bot deixará de ser apenas "isolado" e passará a ser **governança-ready**.

---
*Plano de Soberania do Agente consolidado para execução.*
