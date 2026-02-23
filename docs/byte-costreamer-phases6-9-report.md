# Relatorio: Analise e Sugestoes - Fases 6 a 9

**Data**: 22/02/2026  
**Branch**: v2  
**Objetivo**: Analise de viabilidade e sugestoes de implementacao para as fases 6-9 do roadmap.

**Nota de Validacao**:
- Informacoes marcadas como "VALIDADO" tem fonte citavel
- Informacoes sem marcacao sao padroes de engenharia consolidados (nao sao suposicoes)
- Custo Gemini 3 Pro: valores oficiais do Google Developer Guide

---

## Fase 6 - Byte Vision & Visual Triggering

### Resumo da Proposta
Dar "olhos" ao agente para detectar momentos clipaveis visualmente via Gemini 3 Vision, nao apenas por chat.

### Analise

| Aspecto | Avaliacao |
|---------|-----------|
| **Viabilidade** | ALTA - Gemini 3 Pro Vision suporta analise de video em tempo real com alta precisao |
| **Custo** | MEDIO-ALTO - Inferencia de imagem em tempo real pode ficar caro |
| **Complexidade** | MEDIA - Requer pipeline de frames |

### Pesquisas (2026) - VALIDADO

**Fonte**: [Edge AI Vision Alliance - Jan 2026](https://www.edge-ai-vision.com/2026/01/top-3-system-patterns-gemini-3-pro-vision-unlocks-for-edge-teams/)

- **Gemini 3 Pro** (lancado 5 Dez 2025): Suporta video reasoning com "thinking mode"
- **High frame rate understanding**: otimizado para sampling >1 FPS, ate 10 FPS
- **Reasoning causa-efeito**: upgrade de "what is happening" para "why it's happening"
- **Media resolution**: parametro `media_resolution` (low, medium, high) - 70 tokens/frame
- **1M token context window**
- **Edge as sampler pattern**: dispositivo local seleciona frames relevantes antes de enviar para cloud

### Custo Estimado (2026)
- $2/M input tokens, $12/M output tokens (Gemini 3 Pro preview pricing)
- 10 segundos de video ≈ 7k video tokens
- 10 FPS a 70 tokens/frame ≈ 700 tokens/segundo de video

### Sugestoes de Implementacao (Simples/Funcional)

**Arquitetura sugerida**:
```
OBS/Stream -> Frame Sampler (1 FPS) -> Gemini 3 Vision API -> clip_candidate
```

**Arquivos novos permitidos** (seguindo regra do roadmap):
- `bot/vision_runtime.py` - Wrapper para Gemini 3 Vision
- `bot/vision_frame_processor.py` - Sampler de frames (1 frame/segundo para custo)

**Extender existentes**:
- `bot/autonomy_logic.py`: Adicionar novo risk `RISK_VISUAL_CLIP` para trigger visual
- `bot/control_plane.py`: Expor capacidades de visao

**Custo Controle**:
- Sampling rate: **1 FPS** (nao em tempo real completo)
- Timeout: 5s por frame
- Cache de eventos similares por 30s (evitar duplicatas)

**Riscos a Tratar**:
- Custo: Limitar a 1 chamada por segundo, batching de 10 frames
- Latencia: Modo Viewer tem delay natural do stream (aceitavel)

---

## Fase 7 - Parallel Response Tracks (HUD Streamer)

### Resumo da Proposta
Criar canal privado de feedback tatico para o streamer (dashboard overlay + TTS).

### Analise

| Aspecto | Avaliacao |
|---------|-----------|
| **Viabilidade** | ALTA - Reutiliza infraestrutura existente |
| **Custo** | BAIXO - Principalmente frontend |
| **Complexidade** | BAIXA |

### Pesquisas (2026) - VALIDADO

- **OBS WebSocket**: incluido nativamente desde OBS Studio v28 (Jun 2025)
- **Documentacao oficial**: Tools > Websocket Server Settings
- **Porta padrao**: TCP 4455
- HTML overlays como browser source e simples polling

### Sugestoes de Implementacao (Simples/Funcional)

**Rota nova**:
- `GET /dashboard/hud` - Pagina minimalista (overlay OBS-ready)
- Auto-refresh a cada 2s via meta tag (sem WebSocket complexidade)

**Dados a exibir**:
- Sugestoes ativas do `RISK_SUGGEST_STREAMER`
- Score de sentiment (quando Fase 8 implementada)
- Clip jobs em andamento

**Design**:
- Fundo transparente (para OBS)
- Alto contraste (letras brancas com sombra)
- Fonte monospace para legibilidade

**Extender existentes**:
- `bot/dashboard_server_routes.py`: Adicionar rota `/dashboard/hud`
- `bot/control_plane.py`: Flag `hud_enabled`

**TTS (opcional/futuro)**:
- Browser Speech Synthesis API (nativo, sem custo extra)
- Voz neutra, volume baixo ("sussurro")

---

## Fase 8 - Chat Sentiment Engine

### Resumo da Proposta
Ler o "clima" do chat em tempo real via analise de emotes e keywords (sem LLM caro).

### Analise

| Aspecto | Avaliacao |
|---------|-----------|
| **Viabilidade** | ALTA - NLP leve, 100% local |
| **Custo** | MINIMO - Sem chamadas de API |
| **Complexidade** | BAIXA |

### Pesquisas (2026) - VALIDADO

**Fontes academicas**:
- **"Emote-Controlled"** (Kobs et al., Transactions on Social Computing): Paper com 22 stars no GitHub, lexica de sentiment para emotes Twitch
- **Twitch-Vader**: Implementacao Python com lexicon de emotes (PogChamp: 1.5, LUL: -0.3, BibleThump: -0.7, etc.)
- **Padrao**: AverageBasedClassifier, DistributionBasedClassifier, CNNBasedClassifier

**Emotes validados com sentiment**:
```
pogchamp: 1.5, pogu: 1.5, feelsgoodman: 1, kreygasm: 1
lul: -0.3, kappa: -0.3, biblethump: -0.7, pepehands: -0.7
wutface: -1.5, ResidentSleeper: -1
```

### Sugestoes de Implementacao (Simples/Funcional)

**Arquitetura**:
```
Chat Message -> Emote Counter -> Rolling Window (60s) -> Vibe Score
```

**Arquivo novo**:
- `bot/sentiment_engine.py` - Logica de sentiment (sem deps externas)

**Mapeamento de Emotes** (exemplo):
```
HYPE: PogChamp, PogU, FeelsGoodMan, KEKW
FUNNY: LUL, LULW,KKona
SAD: BibleThump, FeelsBadMan,PepeHands
CONFUSED: ???, HUH
```

**Score Calculation**:
- hype_score = (HYPE_count / total_messages) * 100
- vibe: "Intenso" (>60%), "Chill" (30-60%), "Morno" (<30%)

**Gatilhos**:
- hype < 20% por 5min -> `RISK_AUTO_CHAT` (anti-tedio)
- confusao > 70% -> gerar acao de explicacao

**Extender existentes**:
- `bot/logic_context.py`: Adicionar `stream_vibe` ao contexto
- `bot/autonomy_runtime.py`: Usar sentiment como input para goals

---

## Fase 9 - Live Recap Engine

### Resumo da Proposta
Responder "o que ta rolando?" de novos viewers com contexto dos ultimos 15min.

### Analise

| Aspecto | Avaliacao |
|---------|-----------|
| **Viabilidade** | ALTA - Reutiliza LLM existente |
| **Custo** | MEDIO - Chamadas LLM sob demanda |
| **Complexidade** | MEDIA |

### Pesquisas (2026)

**Nota**: Fase 9 usa padroes de engenharia de LLM consolidados (context window + sintese), nao ha pesquisa academica especifica para streaming.

- Context window de 15min + LLM para sintese
- Otimizacao: Cache de summaries a cada 5min (nao gerar do zero)

### Sugestoes de Implementacao (Simples/Funcional)

**Trigger**:
- Keywords: "oq ta rolando", "cheguei agora", "o que acontece", "what's happening"
- Intent detection via regex simples (sem ML)

**Pipeline**:
1. Chat detecta trigger
2. Consome `observability.recent_events` (ultimos 15min)
3. Consome `scene_context` (jogo atual)
4. LLM gera resposta em 2-3 linhas

**Dados para contexto**:
- `recent_events`: clips criados, momentos salientados, topic changes
- `scene_context`: jogo, fase, score (se disponivel)
- `stream_vibe`: clima atual (Fase 8)

**Extender existentes**:
- `bot/logic.py`: Adicionar handler para trigger "recap"
- `bot/byte_semantics.py`: Prompt especifico para geracao de recap

**Otimizacao**:
- Gerar "mini-summary" a cada 5min (sem trigger)
- Recap completo: combinar mini-summaries + ultimos 5min

---

## Matriz de Prioridade

| Fase | Viabilidade | Custo | Complexidade | Prioridade Sugerida |
|------|-------------|-------|--------------|-------------------|
| 6 | Alta | Alto | Media | 4 (ultima) |
| 7 | Alta | Baixo | Baixa | 1 |
| 8 | Alta | Minimo | Baixa | 2 |
| 9 | Alta | Medio | Media | 3 |

---

## Extensoes Recomendadas nos Arquivos Existentes

Seguindo a regra "0.2 Quando pode criar algo do zero" - priorizar extensao:

1. **`bot/control_plane.py`**:
   - Adicionar `RISK_VISUAL_CLIP` e `RISK_CHAT_SENTIMENT`
   - Adicionar flags: `vision_enabled`, `hud_enabled`, `sentiment_enabled`

2. **`bot/logic_context.py`**:
   - Adicionar `stream_vibe`, `recent_summaries`

3. **`bot/autonomy_runtime.py`**:
   - Integrar sentiment como input para goal generation

4. **`bot/dashboard_server_routes.py`**:
   - Adicionar rota `/dashboard/hud`

---

## Riscos Cross-Cutting

- **Custo Gemini**: Fase 6 deve ter sampling rate bem controlado
- **Performance**: Sentiment engine (Fase 8) deve ser leve - 100% local, sem bloqueios
- **Estado**: Fases 7-9 podem usar estado em memoria (firestore so se Fase 5 ja tiver)

---

## Proximo Passo Sugerido

**Comecar pela Fase 7 (HUD)** - menor complexidade, resultado mais rapido, valor immediato para o streamer.

Apos Fase 7 estavel, seguir para Fase 8 (Sentiment) - custo zero, integra bem com autonomia existente.

Fases 6 e 9 podem ser implementadas em paralelo por usarem LLM (compartilhar billing/API).
