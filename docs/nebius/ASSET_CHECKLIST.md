# Nebius Partnership — Asset Checklist
## Materials Juan needs to prepare

---

## Required (Before First Contact)

### 1. Screenshots / Screen Recordings

- [ ] **Dashboard Overview**: Full screenshot of the main dashboard with all panels visible (Observability, Intelligence, Control Plane)
- [ ] **Tactical Calendar**: Screenshot of the new timeline showing upcoming cron/fixed events
- [ ] **Clips Pipeline (Visual)**: Screenshot showing the clips list with real thumbnails and loading spinners
- [ ] **Twitch Chat — ASCII Art**: Screenshot of the agent delivering high-density Braille ASCII art in chat
- [ ] **Control Plane — Persona Studio**: Screenshot showing the persona studio section with filled-in fields (name, tone, emote vocab, model routing)
- [ ] **Observability Panel**: Screenshot showing real-time stream health, sentiment scores, event timeline
- [ ] **Action Queue**: Screenshot showing clip candidates in the approval queue
- [ ] **Clip Jobs Panel**: Screenshot showing clips in various states (queued, polling, ready)
- [ ] **HUD Overlay**: Screenshot of the streamer overlay view
- [ ] **Terminal running**: Screenshot of the agent running in terminal with Nebius inference logs visible

### 2. Demo Video (1-3 min)

- [ ] **Live demo clip** showing: Agent responding in Twitch chat → Dashboard updating in real-time → Approval flow for an autonomous action
- [ ] Can be recorded with OBS or screen capture. Show the chat + dashboard side by side.

### 3. Architecture Diagram (High-Res)

- [ ] The `assets/architecture-byte-flow-novo.png` from the README — verify it's current and mentions Nebius prominently
- [ ] If outdated, update to show: Nebius as the "brain", Supabase as "memory", Twitch as "arms", Dashboard as "eyes"

### 4. Personal / Company Info

- [ ] Your professional email (for the contact section)
- [ ] LinkedIn profile URL
- [ ] Brief 2-line bio for the proposal

---

## Recommended (Nice to Have)

### 5. Metrics / Logs

- [ ] **Inference log sample**: Anonymized log showing a chat session with Nebius API calls (model, tokens, latency)
- [ ] **Token usage estimate**: Monthly tokens consumed during the current single-streamer testing phase
- [ ] **Uptime data**: How long has the HF Space been running? Any uptime screenshots from HF dashboard?

### 6. User Testimonials / Community

- [ ] Any feedback from streamers who tested Byte?
- [ ] Community Discord or Twitch clips showing Byte in action?

### 7. Competitive Landscape Slide

- [ ] Simple comparison table: Byte vs. manual moderation vs. Nightbot vs. StreamElements
- [ ] Key differentiator: Byte is an **autonomous agent**, not a command-response bot

---

## File Naming Convention

Save all assets to: `/docs/nebius/assets/`

```
docs/nebius/
├── PARTNERSHIP_PROPOSAL.md     ← Main document (DONE)
├── TECHNICAL_BRIEF.md          ← Technical architecture (DONE)
├── ASSET_CHECKLIST.md          ← This file (DONE)
└── assets/
    ├── dashboard-overview.png
    ├── persona-studio.png
    ├── observability-panel.png
    ├── action-queue.png
    ├── clip-jobs.png
    ├── hud-overlay.png
    ├── terminal-running.png
    ├── architecture-diagram.png
    └── demo-video.mp4
```

---

## Nebius Contact Channels

| Channel | URL | Notes |
|---|---|---|
| Partners page | https://nebius.ai/partners | Check for application form |
| Developer Relations | Look for devrel@ or partnerships@ | Usually listed on careers/about |
| LinkedIn | Search "Nebius AI" company page | DM to head of partnerships |
| Twitter/X | @nebaborai or similar | Public visibility, DM for intro |
| Discord / Community | Check nebius.ai for community links | Developer community channel |

> **Tip:** Start with LinkedIn. Find the **Head of Developer Relations** or **Partnerships Lead** at Nebius. Send a brief message referencing Byte's open source nature and production Nebius usage, then offer to share the full proposal.

---

## Email Template (First Contact)

```
Subject: Partnership Proposal — Production AI Agent powered by Nebius Inference

Hi [Name],

I'm Juan Carlos, developer of Byte — an open-source AI Agent Runtime
for Twitch streaming operations. Byte is 100% powered by Nebius AI
(Kimi K2.5 / K2-Thinking) and is currently deployed on HuggingFace
Spaces.

The system has 89 Python modules, 1,000 passing tests, and a full
operational dashboard. Every intelligent decision the agent makes
uses Nebius inference.

I'm looking to scale from single-streamer to multi-tenant (agencies
managing 20+ streamers). I'd love to explore a partnership:
inference credits, co-marketing, or infrastructure support.

Happy to share the full technical brief and a live demo.

Best,
Juan Carlos
GitHub: JuanCS-Dev
```
