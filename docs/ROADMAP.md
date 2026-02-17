# 🤖 Twitch V-Bot — Gemini 3 Flash + Vertex AI + Cloud Run
> Roadmap de Produção 2026 · Invisible Producer Pattern · 94% Test Coverage

---

## 🏗️ Arquitetura Evoluída (Standard 2026)

```
Twitch Chat (EventSub WebSocket)
        ↓   
    bot/main.py (Infra) ←→ bot/logic.py (Inteligência)
            ↑                   ↓
    TwitchIO 3.2.1       google-genai SDK 1.51+
            ↑                   ↓
    Secret Manager      Vertex AI (Gemini 3 Flash)
            ↑                   ↓
    Cloud Run Port 8080 ← Grounding: Google Search
```

---

## FASE 1 — GCloud Mastery (10 min)
*(Status: Pronto para Execução)*
- Setup de Projeto e APIs (`run`, `aiplatform`, `secretmanager`).
- Criação de Service Account com roles `aiplatform.user` e `secretmanager.secretAccessor`.
- Configuração de Segredos (Twitch Client Secret).

---

## FASE 2 — Core & Raciocínio (Implementado)
*(Status: ✅ Concluído)*
- **logic.py:** Lógica de negócio pura, sem dependência de IO.
- **main.py:** Casco de integração com TwitchIO e Healthchecks.
- **StreamContext:** Engine de contexto dinâmico (Vibe, Game, Uptime).
- **Proactive AI:** Reação inteligente a saudações e frases sem comandos.

---

## FASE 2.5 — Rigor Científico (Implementado)
*(Status: ✅ Concluído - 94% Coverage)*
- Suíte de Testes Unitários e Científicos em `bot/tests/`.
- Mocking de alta fidelidade para Vertex AI e Twitch API.
- **Regra de Ouro:** "Se não testou, não existe".

---

## FASE 3 — Deploy & Escalonamento (Amanhã)
*(Status: 🕒 Agendado)*
- Build via Google Cloud Build.
- Deploy no Cloud Run com `min-instances: 1` para evitar cold starts no chat.
- Configuração de Variáveis de Ambiente via `gcloud`.

---

## FASE 4 — Dashboard de Controle (Implementado)
*(Status: ✅ Concluído)*
- Interface React + Vite em `/dashboard`.
- Monitoramento de métricas e Playground de inferência.

---

## 🛠️ Comandos Disruptivos (2026)
- `!ask`: Inteligência com Grounding (Pesquisa Google).
- `!vibe`: (Owner Only) Altera o tom de voz do bot dinamicamente.
- `!status`: Diagnóstico de uptime e estado do agente.
- `!wiki/!clima/!historia`: Comandos semânticos integrados.

---
*Roadmap atualizado para refletir a soberania da lógica sobre o código.*
