# Implementação do Calendário Tático (Tactical Calendar)
**Status:** Análise Estrutural Corrigida e Proposta Arquitetural Definitiva

## 1. Análise do Sistema Atual de Goals
Atualmente, o sistema de `goals` (objetivos autônomos do bot) funciona de maneira reativa e periódica:
- O estado e configuração dos goals ficam no `bot/control_plane_config.py` (`ControlPlaneConfigRuntime`).
- O runtime de autonomia (`bot/autonomy_runtime.py`) roda um loop (`_heartbeat_loop`) que chama o `_run_tick` periodicamente.
- O `_run_tick` consome os goals que estão vencidos chamando a função `consume_due_goals` do control plane.
- Atualmente, um goal vence com base no campo `interval_seconds` (ex: rodar a cada 600 segundos). O control plane guarda em memória o `_next_goal_due_at` e verifica se `time.time() >= due_at`.

Isso funciona perfeitamente para "Lembretes a cada 10 minutos", mas **não** atende ao caso de uso de um calendário tático onde o gestor/streamer queira programar: "Disparar a meta X exatamente às 20h00" ou "Rodar o evento Y na sexta-feira às 15h00".

## 2. Abordagens para o Calendário Tático

### Abordagem A: Integração com Google Calendar (Terceiros)
Neste modelo, o streamer cria eventos no seu Google Calendar marcados com tags específicas (ex: `[BOT-GOAL]`). O bot leria esses eventos via polling ou webhooks.
- **Prós:** Interface nativa e familiar pelo celular/web do Google.
- **Contras:** Requer configuração complexa de OAuth2 e credenciais GCP; adiciona ponto de falha externo; difícil de mapear propriedades vitais do bot (risk level, prompt payload) apenas através da descrição do evento do calendário. **(Descartada)**

### Abordagem B: Sistema Nativo Integrado (Recomendada e Validada contra o Código)
Expandir o `ControlPlaneConfigRuntime` e o Dashboard local para aceitarem horários fixos e cron-jobs.
*Nota de Auditoria: O ambiente atual do dashboard é estritamente Vanilla JS (sem bundlers, React ou frameworks), e o backend Python tem um controle de tick já pronto e performático.*
- **Prós:** Nenhuma dependência externa de infraestrutura; controle absoluto do UX; aproveitamento de 100% do loop de autonomia existente (`consume_due_goals`); baixo overhead.
- **Contras:** Interface visual precisará ser construída utilizando Vanilla JS puro.

---

## 3. Plano de Implementação Sugerido (Nativo Integrado)

### Passo 1: Modificar o Modelo de Dados (Backend Python)
O dicionário de configuração de `goals` (`_config["goals"]`) no `bot/control_plane_config.py` será estendido sem quebrar compatibilidade reversa.
Adicionar suporte para novos campos num Goal:
- `schedule_type`: `"interval"` (padrão atual) | `"fixed_time"` | `"cron"`
- `scheduled_at`: (Opcional) Timestamp ISO 8601 para agendamento exato de disparo único (ex: `2026-03-01T20:00:00Z`).
- `cron_expression`: (Opcional) Para eventos recorrentes nativos, ex: `0 20 * * 5` (toda sexta às 20h).

*Solução Backend:* Na função `consume_due_goals`, a lógica atual de `_next_goal_due_at` será mantida. Ao calcular o próximo `due_at`, usaremos a biblioteca leve `croniter` para calcular o exato timestamp do próximo acionamento baseado no cron, ou definiremos o `due_at` com base no `scheduled_at`. **Evitaremos overengineering (como APScheduler)**; o heartbeat atual via `asyncio.sleep` no `_heartbeat_loop` já é perfeito para disparar os checks e acionar o tick.

### Passo 2: Atualizar Endpoints do Control Plane e Persistência
- Ajustar `bot/dashboard_server_routes.py` para receber, validar e armazenar os novos campos `schedule_type`, `scheduled_at` e `cron_expression`.
- Adicionar validação estrita (com `croniter.is_valid`) antes de persistir as configurações para não corromper o estado em runtime.
- Os dados serão mantidos na persistência nativa do Supabase que já gere os configs dos canais e goals.

### Passo 3: Componente Visual no Dashboard (Frontend Vanilla JS)
Como o dashboard (em `dashboard/features/...`) é puramente Vanilla JS/HTML sem build steps, **rejeitamos soluções React/Shadcn**.
- **Estratégia de UI Minimalista (Sem Libs Externas de Calendário):** Para a tela do Control Plane, em vez de um "calendário visual de parede", renderizaremos os Goals em formato de **"Timeline de Agendamentos"**.
- **Formulário de Entrada:** No modal de Action/Goal, usaremos inputs nativos do HTML5 (`<input type="datetime-local">` para horários fixos) e um campo de texto formatado para o Cron Job (com links de ajuda `crontab.guru`).
- **Alternativa Visual (Caso Necessário Efeito UAU):** Se a visão de calendário em grade for obrigatória, importar via CDN a biblioteca `Vanilla Calendar Pro` (zero dependências, compatível com a arquitetura atual) para montar o calendário mensal.

### Passo 4: Execução Tática no Autonomy Runtime
Quando o loop de `autonomy_runtime.py` rodar o tick, ele consumirá os goals pontuais e os removerá do array (ou os marcará como inativos se `schedule_type == "fixed_time"`), enquanto os goals com `cron` apenas atualizarão a variável `_next_goal_due_at` para o próximo período. O runtime repassará a prioridade e fará a chamada LLM/sentiment engine assim como hoje faz com os goals por intervalo.

## Conclusão
Esta correção arquitetural foca no que já existe. Aproveitando o array `_next_goal_due_at` nativo no `control_plane_config.py` em conjunto com a lib `croniter` (backend), resolvemos o tempo de execução e agendamento contínuo. No frontend, abraçamos a natureza Vanilla JS do projeto, utilizando componentes nativos da plataforma Web para garantir performance máxima, em total aderência à atual base de código do Vértice.
