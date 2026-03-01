# Byte — Technical Architecture Brief
## For Nebius AI Partnership Evaluation

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    BYTE AI AGENT RUNTIME                        │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  Twitch   │  │   Prompt     │  │    Inference Engine       │ │
│  │  IRC /    │→ │   Flow       │→ │    (Nebius AI Studio)     │ │
│  │  EventSub │  │  + Context   │  │                           │ │
│  └──────────┘  │   Assembly   │  │  ┌─────────────────────┐  │ │
│                └──────────────┘  │  │ Kimi K2.5 (default) │  │ │
│  ┌──────────┐                    │  │ Kimi K2.5 (search)  │  │ │
│  │  Control  │  ┌──────────────┐ │  │ Kimi K2-Think (rsn) │  │ │
│  │  Plane    │→ │  Autonomy    │→│  │ Kimi K2.5 (vision)  │  │ │
│  │  Config   │  │  Runtime     │ │  └─────────────────────┘  │ │
│  └──────────┘  └──────────────┘  └───────────────────────────┘ │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  Persona  │  │  Sentiment   │  │    Dashboard Server       │ │
│  │  Studio   │  │  Engine      │  │    (32 API routes)        │ │
│  │  + Model  │  │  + Stream    │  │    (7 feature panels)     │ │
│  │  Routing  │  │  Health      │  │    (real-time polling)    │ │
│  └──────────┘  └──────────────┘  └───────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Persistence Layer (Supabase)                 │  │
│  │  Channel State │ Persona Profiles │ Semantic Memory       │  │
│  │  Agent Notes   │ Obs History      │ Revenue Attribution   │  │
│  │  Webhooks      │ Post-Stream Rpts │ Clip Jobs (Firestore) │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Nebius API Usage Pattern

### Client Initialization
```python
from openai import OpenAI

client = OpenAI(
    api_key=NEBIUS_API_KEY,
    base_url="https://api.studio.nebius.ai/v1"
)
```

### Model Routing Logic
```python
def _select_model(enable_grounding, is_serious, *, context=None):
    routing = getattr(context, "channel_model_routing", None) or {}

    if enable_grounding:
        override = routing.get("search")
        return override if override else NEBIUS_MODEL_SEARCH

    if is_serious:
        override = routing.get("reasoning")
        return override if override else NEBIUS_MODEL_REASONING

    override = routing.get("chat")
    return override if override else NEBIUS_MODEL_DEFAULT
```

### Inference Call (Streaming)
```python
response = client.chat.completions.create(
    model=selected_model,
    messages=assembled_messages,
    temperature=context.inference_temperature or 0.72,
    top_p=context.inference_top_p or 0.85,
    max_tokens=max_tokens,
    stream=True,
)
```

## Module Inventory (89 files)

| Category | Files | Description |
|---|---|---|
| **Inference** | logic_inference, logic_grounding, logic_context | Core LLM interaction via Nebius |
| **Autonomy** | autonomy_runtime, autonomy_logic, control_plane* | Goal-driven autonomous behavior |
| **Chat** | irc_*, eventsub_*, prompt_flow, prompt_runtime | Twitch integration layer |
| **Observability** | observability_*, stream_health_score, sentiment_* | Real-time monitoring |
| **Persistence** | persistence_*, supabase_client | 9 repository modules (Supabase) |
| **Dashboard** | dashboard_server*, dashboard_http_helpers | HTTP server + 32 API routes |
| **Features** | clips, coaching, vision, semantic_memory, webhooks | Specialized capabilities |
| **Engagement** | ascii_art_runtime | Proprietary 2x4 Braille ASCII rendering engine |

## Quality Metrics

| Metric | Value |
|---|---|
| Test count | 1,000 |
| Test pass rate | 100% |
| Resilience | Native retry/backoff logic for 429 & timeout errors |
| Scientific test suites | 12 |
| Parity routes covered | 32/32 |
| Structural health score | 10.00/10 |
| Ruff lint errors | 0 |
| McCabe complexity violations | 0 |
| Code duplication violations | 0 |

## Scaling Architecture (Proposed)

```
                    ┌──────────────────────┐
                    │    Load Balancer      │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
    │  Agent Pool A  │ │ Agent Pool B │ │ Agent Pool C │
    │  (Agency 1)    │ │ (Agency 2)   │ │ (Agency 3)   │
    │  5 streamers   │ │ 12 streamers │ │ 20 streamers │
    └─────────┬──────┘ └──────┬───────┘ └──────┬───────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Nebius AI Studio    │
                    │   (Shared Inference)  │
                    │                       │
                    │   Kimi K2.5 Pool      │
                    │   Kimi K2-Thinking    │
                    └──────────────────────┘
```

**Per-agency isolation:** Each agency gets isolated Supabase schema + dedicated agent pool. All share Nebius inference with per-tenant API key tracking.
