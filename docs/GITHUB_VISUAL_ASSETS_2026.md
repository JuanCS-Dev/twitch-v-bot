# Byte - Guia de Assets Visuais para GitHub (2026)

Objetivo: definir um kit visual que faca o `Byte` parecer premium, tecnico e com personalidade de live.

## Benchmark rapido (repos observados)

Referencias analisadas em 2026-02:

- `sogebot/sogeBot`: usa faixa forte de badges + galeria de screenshots + links de comunidade no topo.
- `ardha27/AI-Waifu-Vtuber`: abre com screenshot hero e bloco curto de demos (YouTube).
- `open-sauced/beybot`: usa GIF curto mostrando comportamento real no chat.
- `Koischizo/AI-Vtuber`: usa thumbnails clicaveis de demos para reduzir friccao.
- `Kichi779/Twitch-Chat-Bot`: preview visual + GIF didatico de onboarding.
- `AkagawaTsurunaki/ZerolanLiveRobot`: badge wall para comunicar stack/capabilities em segundos.

## O que "vende" melhor no GitHub

1. Hero visual no topo com nome do agente + proposta em uma frase.
2. Prova de funcionamento em 3-8 segundos (GIF curto de chat real).
3. Arquitetura visual simples (Twitch -> Byte -> Gemini -> resposta).
4. Cards de comandos com poucos exemplos de alto impacto.
5. Screenshot de producao (Cloud Run revision + uptime/status).
6. Identidade consistente (mesma paleta, tipografia e tom "premium + zoeira").

## Kit recomendado para o Byte

Estrutura:

```text
assets/
  hero-banner-byte.png
  demo-chat-loop.gif
  architecture-byte-flow.png
  command-cards.png
  cloudrun-proof.png
  social-cover-1280x640.png
```

Dimensoes sugeridas:

- `hero-banner-byte.png`: 1600x900
- `demo-chat-loop.gif`: 1280x720 (5-8s, loop)
- `architecture-byte-flow.png`: 1920x1080
- `command-cards.png`: 1600x900
- `cloudrun-proof.png`: 1600x900
- `social-cover-1280x640.png`: 1280x640

## Ordem ideal no README

1. Hero banner + tagline curta.
2. GIF de demo (comando real no chat).
3. Bloco "Como funciona" com diagrama.
4. Cards de comandos.
5. Screenshot de producao e links de docs.

## Prompts prontos para gerador de imagem

Use sempre este estilo base:

`estilo visual cinematic tech, clean UI overlays, high contrast, premium streaming brand, playful hacker energy, sem logos de terceiros, sem texto ilegivel, composicao horizontal 16:9`

### 1) Hero banner

`Crie um banner 16:9 para um agente de Twitch chamado Byte. Tema: AI co-host premium com humor inteligente. Cenario: estacao futurista com telas mostrando chat em tempo real, graficos de latencia baixa e fluxo Gemini. Paleta: cyan, electric blue, graphite, acentos neon verdes. Deixar area limpa para titulo no lado esquerdo. Sem marcas registradas.`

### 2) Demo chat loop cover

`Crie uma cena 16:9 de chat da Twitch em destaque com uma mensagem acionando "byte status" e resposta curta e precisa. Visual de overlay de live moderna, linguagem visual gamer-tech, foco em legibilidade da conversa. Mostrar senso de velocidade e confiabilidade do bot.`

### 3) Arquitetura

`Infografico 16:9 minimalista mostrando fluxo: Twitch Chat -> Byte Agent -> Gemini 3 Flash (Vertex AI) -> Resposta no Chat -> Cloud Run. Usar icones genericos, setas limpas, blocos com hierarquia clara, design premium e tecnico. Fundo escuro grafite com linhas suaves neon cyan.`

### 4) Cards de comandos

`Painel 16:9 com quatro cards visuais de comandos: "byte ajuda", "byte status", "byte ficha tecnica", "byte <pergunta>". Estilo UI futurista com cantos suaves, micro-ilustracoes, contraste alto, layout pronto para README.`

### 5) Prova de producao

`Tela 16:9 estilo dashboard de operacao mostrando deploy cloud estavel: status online, uptime, revision ativa, logs limpos, chat respondendo. Visual serio, profissional, sem texto pequeno demais, clima de confiabilidade para demo tecnica.`

### 6) Social cover

`Capa horizontal 1280x640 para GitHub social preview do projeto Byte Twitch AI Bot. Elementos: bot mascot abstrato, chat bubbles, fluxo AI, estilo premium + zoeira controlada, tipografia forte, espaco para titulo grande.`

## Regras para nao gerar arte fraca

1. Evite excesso de texto dentro da imagem.
2. Prefira 1 mensagem principal por asset.
3. Mantenha a mesma paleta em todos os arquivos.
4. Teste leitura em mobile (thumbnail pequena).
5. Gere 3 variacoes por prompt e escolha a mais limpa.
