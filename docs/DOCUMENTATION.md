# Byte Documentation (Complete Guide)

## 1. Product Summary

Byte is a Twitch AI chat agent that runs on Gemini 3 Flash (Vertex AI) and is deployable on Cloud Run.

Main goals:

- Real-time chat assistance for live streams.
- Short, direct, readable responses for chat flow.
- Better factual reliability for current-events and technical prompts.
- Production deployment path with observability and cost tracking.

## 2. Core Capabilities

- Trigger-based natural chat responses via `byte`, `@byte`, or `!byte`.
- Built-in short help/status flows.
- Movie fact-sheet handling with context carryover.
- Current-events prompt enrichment with verification instructions.
- Serious/technical mode that can split into up to 2 chat messages.
- Automatic live context updates from trusted YouTube/X links.
- Token refresh flow for IRC mode when refresh credentials are configured.

## 3. Architecture

### Runtime Components

- `bot/main.py`: Twitch integration, mode routing, health endpoint, token handling.
- `bot/logic.py`: LLM orchestration, prompt construction, response limits, live context memory.
- `bot/byte_semantics.py`: trigger parsing, prompt enrichment rules, reply splitting heuristics.

### Infrastructure Components

- Twitch chat transport:
  - `irc` mode: direct IRC socket mode (demo-friendly).
  - `eventsub` mode: official cloud chatbot path.
- Gemini model provider: Vertex AI (`gemini-3-flash-preview`, `global`).
- Secret store: Google Secret Manager.
- Runtime host: Cloud Run.

## 4. Operating Modes

### Mode A: `TWITCH_CHAT_MODE=irc`

Use this when you need quick demo behavior without streamer authorization.

- Byte account joins target channel as viewer.
- Byte reads chat and sends responses.
- Required credentials are user-based (`TWITCH_USER_TOKEN`, optionally refresh token).

### Mode B: `TWITCH_CHAT_MODE=eventsub`

Use this for official cloud chatbot architecture.

- Requires app credentials and EventSub subscription flow.
- In third-party channels, broadcaster authorization is required (`channel:bot`).

## 5. Environment Variables

### Required in All Modes

- `GOOGLE_CLOUD_PROJECT`: GCP project ID.
- `TWITCH_CHAT_MODE`: `irc` or `eventsub`.
- `BYTE_TRIGGER`: chat trigger token (default: `byte`).

### EventSub Mode (`TWITCH_CHAT_MODE=eventsub`)

- `TWITCH_CLIENT_ID`
- `TWITCH_BOT_ID`
- `TWITCH_CHANNEL_ID`
- Secret in Secret Manager: `twitch-client-secret`

### IRC Mode (`TWITCH_CHAT_MODE=irc`)

- `TWITCH_BOT_LOGIN`
- `TWITCH_CHANNEL_LOGIN`
- `TWITCH_USER_TOKEN`
- Optional but recommended:
  - `TWITCH_REFRESH_TOKEN`
  - `TWITCH_CLIENT_ID`
  - `TWITCH_CLIENT_SECRET` or `TWITCH_CLIENT_SECRET_SECRET_NAME`
  - `TWITCH_TOKEN_REFRESH_MARGIN_SECONDS`

### Optional Runtime Tuning

- `TWITCH_IRC_HOST` (default: `irc.chat.twitch.tv`)
- `TWITCH_IRC_PORT` (default: `6697`)
- `TWITCH_IRC_TLS` (default: `true`)
- `AUTO_SCENE_CACHE_TTL_SECONDS`
- `AUTO_SCENE_METADATA_TIMEOUT_SECONDS`
- `AUTO_SCENE_REQUIRE_METADATA`

## 6. Twitch Setup (2026)

### 6.1 Create Twitch App

Open: `https://dev.twitch.tv/console/apps/create`

Use:

- Name: `Byte Agent`
- Redirect URL: `http://localhost:3000/callback`
- Category: `Chat Bot`

Collect:

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`

### 6.2 Generate User Token for IRC Mode

```bash
twitch token --user-token --dcf \
  --client-id "$TWITCH_CLIENT_ID" \
  --secret "$TWITCH_CLIENT_SECRET" \
  --scopes "chat:read chat:edit"
```

Store:

- Access token -> `TWITCH_USER_TOKEN`
- Refresh token -> `TWITCH_REFRESH_TOKEN` (recommended)

## 7. Local Run

```bash
pip install -r bot/requirements.txt
python bot/main.py
```

Expected behavior:

- Health server on `0.0.0.0:$PORT` (default `8080`).
- Twitch connection starts based on selected mode.

## 8. Cloud Run Deployment

### 8.1 Recommended Path

Use the deployment helper:

```bash
./deploy.sh
```

Deployment defaults in `deploy.sh`:

- Region: `us-central1`
- Service name: `byte-bot`
- CPU: `1`
- Memory: `512Mi`
- Min instances: `1`
- Max instances: `1`
- Timeout: `3600s`
- Concurrency: `200`

### 8.2 Important Notes

- The script enables required APIs automatically.
- For `eventsub`, the script expects `twitch-client-secret` in Secret Manager.
- For `irc` + refresh, set `TWITCH_CLIENT_ID` and provide client secret (inline or Secret Manager).

## 9. Chat Behavior Contract

### 9.1 Reply Length

- Default max lines: `8`.
- Default max length: bounded to fit chat safely.
- Serious technical prompts can split into up to 2 messages.

### 9.2 Built-in Trigger Intents

- Help intent.
- Intro intent (`byte introduce yourself` style trigger).
- Status intent.
- Movie fact-sheet intent.
- General question intent with LLM response.

### 9.3 Reliability Rules

The prompt pipeline adds extra instructions when needed:

- Current-events: ask for verifiable and recent facts.
- Direct questions: force immediate first-line answer.
- Follow-up prompts: resolve pronouns from recent chat context.
- Serious technical prompts: prioritize stronger evidence and practical framing.

## 10. Moderation and Auto-Context

Byte can automatically update scene context from messages posted by trusted curators.

Trusted curators:

- Channel owner (`TWITCH_OWNER_ID`)
- Moderators

Supported sources:

- YouTube links
- X/Twitter links

Safety controls:

- Unsafe term filter.
- Blocked-domain filter.
- Optional metadata requirement before context update.

## 11. Token Refresh Automation

In IRC mode, automatic token refresh is active when all values exist:

- `TWITCH_REFRESH_TOKEN`
- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET` (or Secret Manager-backed secret)

Flow:

- Validate access token.
- Refresh if invalid or close to expiration.
- Retry connection with refreshed token.

## 12. Cost Tracking and Monthly Projection

Script: `scripts/estimate_monthly_cost.sh`

What it does:

- Reads Cloud Monitoring usage for Cloud Run + Gemini tokens.
- Pulls live SKU prices from your billing account.
- Computes interval cost and run-rate monthly estimate.

Example:

```bash
CLOUD_RUN_SERVICE=byte-bot \
REGION=us-central1 \
GEMINI_MODEL_FILTER=gemini-3-flash-preview \
./scripts/estimate_monthly_cost.sh
```

End-of-day snapshot:

```bash
START_TIME="$(date -u +%Y-%m-%dT00:00:00Z)" \
END_TIME="$(date -u +%Y-%m-%dT23:59:59Z)" \
CLOUD_RUN_SERVICE=byte-bot \
REGION=us-central1 \
GEMINI_MODEL_FILTER=gemini-3-flash-preview \
./scripts/estimate_monthly_cost.sh
```

## 13. Testing and Validation

Run unit tests:

```bash
python -m unittest discover -s bot/tests
```

Focused checks:

```bash
python -m unittest bot.tests.test_logic
python -m unittest bot.tests.test_scientific
```

## 14. Troubleshooting

### Byte does not answer in chat

- Confirm `TWITCH_CHAT_MODE`.
- Confirm trigger message starts with `byte`, `@byte`, or `!byte`.
- Confirm tokens are valid and bot login/channel login are lowercase.

### `invalid client` during auth

- Confirm app `Client ID` is correct.
- Confirm redirect URI exactly matches app settings.
- Confirm you are authorizing the correct app.

### `invalid scope requested`

- For IRC user token, use `chat:read chat:edit`.
- For EventSub official path, use chat bot scopes (`user:read:chat`, `user:write:chat`, `user:bot`) plus broadcaster scope (`channel:bot`) when required.

### Bot disconnects after token expiry

- Configure refresh variables and client secret source.
- Keep `TWITCH_TOKEN_REFRESH_MARGIN_SECONDS` at a safe value (default `300`).

## 15. Security Checklist

- Never commit secrets (`.env`, OAuth tokens, client secrets).
- Use Secret Manager for `TWITCH_CLIENT_SECRET` in production.
- Restrict IAM roles to minimum required permissions.
- Review staged files before every push.

## 16. Launch Checklist (Before Posting on X)

1. Confirm banner and visual assets exist in `assets/`.
2. Run tests: `python -m unittest discover -s bot/tests`.
3. Validate live chat behavior (`byte help`, `byte status`, free-form question).
4. Run cost script and capture current monthly estimate.
5. Verify README links in `docs/INDEX.md` all resolve correctly.
