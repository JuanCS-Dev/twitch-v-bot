---
title: Byte Bot
sdk: docker
emoji: 🤖
colorFrom: purple
colorTo: blue
---

# Byte - AI Agent Runtime para Operações de Streaming

![Byte Banner](assets/hero-banner-novo.png)

[![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Space-blue)](https://huggingface.co/spaces/JuanCS-Dev/twitch-byte-bot)
[![Nebius Inference](https://img.shields.io/badge/Inference-Nebius%20AI-green)](https://nebius.ai/)
[![Supabase Database](https://img.shields.io/badge/Database-Supabase-blueviolet)](https://supabase.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`Byte` é um agente de chat para Twitch de próxima geração, agora totalmente migrado para a stack soberana de 2026: **Nebius AI** para inferência MoE e **Supabase** para persistência de dados em tempo real.

## ✅ Posicionamento Certo

**"AI Agent Runtime para Operações de Streaming"**

- **Categoria:** infraestrutura de operações de streaming.
- **Alternativa comparada:** gerenciar manualmente, contratar stream manager ou cobrir a operação com 5 ferramentas.
- **Resultado:** Byte é o único produto nessa categoria.
- **Diferencial operacional:** `action queue` como controle operacional profissional.

## 🏗️ Arquitetura

![Byte Architecture](assets/architecture-byte-flow-novo.png)

O sistema opera como um "ML Operating System" distribuído:
- **Runtime:** Hugging Face Spaces (Docker)
- **Cérebro:** Nebius Token Factory (Kimi K2.5 / Llama 3.1 70B)
- **Memória:** Supabase PostgreSQL (via Supavisor IPv4 Pooler)
- **Busca:** DuckDuckGo Search para eventos em tempo real

## 🚀 O que o Byte Faz

- **Integração Nativa:** Entra no chat da Twitch como viewer (`irc`) ou chatbot oficial (`eventsub`).
- **Respostas Inteligentes:** Gatilhos naturais como `byte ...`, `@byte ...`, ou `!byte ...`.
- **Concisão Extrema:** Hard limit de 8 linhas para não poluir a live.
- **Grounding Real-time:** Pesquisa web automática para notícias e eventos atuais.
- **Observabilidade:** Dashboard operacional integrada para monitoramento de saúde e custos.

## 🛠️ Comandos e Padrões de Gatilho

- `byte help` - Lista ajuda.
- `byte status` - Saúde do sistema e latência.
- `byte movie fact sheet <movie>` - Ficha técnica de filmes.
- `byte <pergunta livre>` - Inferência direta via Nebius.

Também suporta prefixos: `@byte <pergunta>` ou `!byte <pergunta>`.

## 📦 Configuração de Produção (HF Secrets)

O bot utiliza o cofre de segredos do Hugging Face (**Settings -> Variables and Secrets**):

| Variável | Descrição |
|----------|-----------|
| `NEBIUS_API_KEY` | Chave de acesso ao Nebius AI Studio |
| `SUPABASE_DB_URL` | DSN absoluto (Pooler IPv4 Porta 5432) |
| `TWITCH_USER_TOKEN` | Token OAuth do bot |
| `BYTE_DASHBOARD_ADMIN_TOKEN` | Token de acesso à Dashboard |

## 🧪 Quick Start Local

1. `cp .env.example .env`
2. `pip install -r bot/requirements.txt`
3. `python bot/main.py`

## 📑 Documentação

- [Report de Cura (Forense)](docs/BYTE_AGENT_HEALING_REPORT_2026-02-24.md)
- [Guia Geral de Operações](docs/DOCUMENTATION.md)
- [Runbook de Deploy HF Spaces](docs/HF_SPACES_DEPLOY_RUNBOOK.md)
- [Índice de Documentos](docs/INDEX.md)

---

## 🛡️ Segurança e Governança

Este projeto segue a **Constituição Vértice v3.0**.
- Nenhuma credencial é logada ou comitada.
- Commits assinados via GPG.
- Scanning automático de malware e segredos via HF HubOps.

## 📄 Licença

Open source sob a licença **MIT**. Veja `LICENSE` para detalhes.

---
*Desenvolvido por Juan Carlos (VÉRTICE Core Analytics x BYTE AI)*
