# 📖 Guia de Operação: BYTE AI (Manual Antiburro)
**Versão:** 1.0 (Março 2026)
**Objetivo:** Operar o Byte com 100% de eficiência, sem quebras e com o máximo de performance.

---

## 1. Configuração Inicial (The "Must-Have")

### 1.1 Variáveis de Ambiente (.env)
O Byte não perdoa erros no `.env`. Certifique-se de preencher:
- `BYTE_DASHBOARD_ADMIN_TOKEN`: Crie uma senha forte (32+ chars). Sem ela, a dashboard não salva nada.
- `NEBIUS_API_KEY`: Sua chave da Nebius AI.
- `SUPABASE_URL` / `SUPABASE_KEY`: Credenciais do seu banco de dados.
- `TWITCH_USER_TOKEN`: Deve começar com `oauth:`.

### 1.2 O Banco de Dados (Supabase)
Certifique-se de que a extensão `pgvector` está ativa no seu banco Supabase. O Byte usa isso para a **Memória Semântica**.

---

## 2. Dashboard: O Centro de Comando

Acesse via `http://localhost:8080` (ou sua URL de deploy).

### 2.1 Aba: Control Plane (Configuração)
Aqui você define **quem o bot é**.
- **Persona Studio:** No final da página, abra o "Persona Studio".
    - **Lore:** Escreva a história do bot (ex: "Você é um assistente tático de Valorant").
    - **Model Routing:** Escolha `Kimi-K2-Thinking` para coaching e `Kimi-K2.5` para chat.
- **Goals Scheduler:** Adicione metas.
    - **Interval:** "Fale algo a cada 600 segundos".
    - **Fixed Time:** Use para eventos únicos. **IMPORTANTE:** O horário deve ser em **UTC**. Se você está no Brasil (BRT), subtraia 3 horas do horário desejado.
    - **Cron:** Use `0 20 * * 5` para "Toda sexta às 20h UTC".

### 2.2 Aba: Operation (Observabilidade)
- **Stream Health:** Se a barra estiver vermelha, o chat está "morno" ou negativo. O Byte tentará intervir sozinho se a Autonomia estiver ligada.
- **Sentiment Scores:** Veja em tempo real se o público está empolgado (`Hype`) ou confuso.

### 2.3 Aba: Clips Pipeline
- Quando o Byte detectar um momento épico, o card aparecerá aqui.
- O card terá um **spinner** (processando) e depois uma **Thumbnail**.
- Você pode clicar em **Edit** para mudar o título na Twitch antes de postar.

---

## 3. Comandos de Elite (Chat Twitch)

O Byte entende linguagem natural, mas alguns comandos são otimizados:

### 3.1 Arte ASCII (Braille 2x4)
- `byte arte ascii do goku`
- `byte ascii batman`
- **Regra:** Existe um cooldown de 30 segundos por canal. Se pedir rápido demais, ele ignora para evitar ban da Twitch.

### 3.2 Status e Ajuda
- `byte status`: O bot reporta a saúde do sistema e o modelo que está usando.
- `byte help`: Lista as capacidades básicas.

---

## 4. Resolução de Problemas (Troubleshooting)

| Problema | Causa Provável | Solução |
| :--- | :--- | :--- |
| **Dashboard não salva** | Token Admin errado ou ausente. | Verifique o `BYTE_DASHBOARD_ADMIN_TOKEN` no seu `.env` e no campo de login da Dash. |
| **Bot não responde** | Token Twitch expirado. | O bot tenta renovar sozinho, mas se falhar, gere um novo token no Twitch Token Generator. |
| **Erro de Modelo (Inference)** | Saldo na Nebius ou Model Name errado. | Verifique seu dashboard na Nebius AI Studio. |
| **ASCII Art borrada** | Imagem original com pouco contraste. | Tente temas com silhuetas claras (logos, personagens de anime). |

---

## 5. Regras de Ouro (Constituição Vértice)
1. **Nunca force um restart** enquanto um clipe está em `polling`. Você perderá o rastro do job.
2. **Respeite o Orçamento (Budget):** Se você configurou 10 mensagens por hora, o Byte vai parar de falar na 11ª. Ajuste isso no Control Plane se necessário.
3. **UTC é Vida:** Lembre-se sempre que o servidor e o calendário falam em UTC.

---
*Guia mantido por VÉRTICE Core Analytics — 2026*
