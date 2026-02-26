# Relatório de Incidente: Quebra Estrutural (Refatoração de Persistência)

**Data:** 26 de Fevereiro de 2026
**Status:** CRÍTICO (System Offline - SyntaxError)
**Autor:** Byte Bot via Gemini CLI

## 1. Descrição do Problema
O bot encontra-se em estado de falha de inicialização devido a um `SyntaxError` no módulo `bot/logic_inference.py`. Este erro é o resultado de uma refatoração incompleta e conflitante do `ContextManager`, onde funções síncronas tentam utilizar a palavra-chave `await`.

## 2. Anatomia da Quebra (Forense)

### 2.1 Conflito de Assinaturas (Async Gap)
O arquivo `bot/logic_context.py` foi alterado para que o método `get()` fosse `async def`.
No entanto, o arquivo `bot/logic_inference.py` possui funções auxiliares (`_build_messages`) que foram mantidas como síncronas (`def`), mas continham chamadas `await context_manager.get()`.

**Erro exato:**
```text
E     File "/media/juan/DATA/projetos/twich-bot/bot/logic_inference.py", line 113
E       context = await context_manager.get()
E                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   SyntaxError: 'await' outside async function
```

### 2.2 Regressão de Labels e Suite de Testes
Durante a tentativa de "limpeza", labels fundamentais do prompt (ex: `Historico recente:`) foram alterados, quebrando centenas de asserções em testes científicos que dependem da string exata para validar a lógica da IA.

## 3. Diagnóstico do Data Flow
O fluxo de dados atual está fragmentado:
1.  **IRC/EventSub** são `async`.
2.  **Logic/Inference** tenta ser `async`.
3.  **Tests/Dashboard** são predominantemente `sync`.

A tentativa de tornar o `ContextManager.get()` assíncrono para suportar o Lazy Load do Supabase gerou um efeito cascata que a suite de testes científica (700+ testes) não consegue absorver sem uma refatoração total de meses.

## 4. Plano de Cura Definitiva (O Ultimato)

Para restaurar a estabilidade imediata e cumprir o contrato de **Não Quebrar o Bot**, a arquitetura será simplificada:

1.  **Sincronização do Contexto:** O `context_manager.get()` voltará a ser um método **Síncrono (`def`)**.
2.  **Lazy Load Assíncrono em Background:** Quando um contexto é solicitado e não está na RAM, o bot o cria instantaneamente (síncrono) e dispara uma `asyncio.create_task` para buscar os dados no Supabase em background.
    *   *Benefício:* O bot nunca trava, os testes síncronos continuam funcionando, e a persistência acontece "por baixo dos panos".
3.  **Remoção de 'await' redundantes:** Limpeza total de todos os arquivos afetados para remover a complexidade assíncrona desnecessária do gerenciamento de memória.

---
*Este relatório documenta a falha estrutural e serve de base para a restauração do sistema.*
