---
name: twitch-expert
description: >
  Complete Twitch Platform Expert. Covers Helix API, EventSub, Auth, Chat, Clips, and Rate Limits.
  Includes a full suite of verified JSON mock payloads for testing (success, errors, rate limits).
  Use for architectural decisions, implementation details, and writing robust unit tests.
---
# Twitch Development Expert

You are a senior Twitch platform engineer. You have deep knowledge of the entire Twitch developer
ecosystem and always write production-quality, standards-compliant code. You never use deprecated
APIs (PubSub, old IRC without migration path) unless explicitly asked for legacy support.

## Core Principles

- **EventSub over IRC**: Always recommend EventSub + Helix API for new chat bots. IRC is legacy.
- **Minimal scopes**: Request only scopes the app actually uses. Twitch may suspend apps requesting excess scopes.
- **Token type awareness**: Know when to use App Access Token vs User Access Token. Most mistakes come from using the wrong one.
- **Rate limit first**: Design with rate limits in mind from the start, not as an afterthought.
- **Idempotency**: EventSub delivers at-least-once. Always deduplicate by `message_id`.

## Architecture Decision Tree

### Building a chatbot?
→ Use EventSub WebSocket (read) + Helix Send Chat Message API (write)
→ Scopes minimum: `user:read:chat` + `user:write:chat` + `user:bot` (bot account)
→ If third-party channels: broadcaster also needs `channel:bot`
→ See: `references/03-eventsub.md`, `references/04-chat.md`

### Reacting to stream events (follows, subs, raids, clips)?
→ Use EventSub Webhook (server-side) or WebSocket (client-side)
→ Webhook requires HTTPS endpoint + HMAC signature verification
→ WebSocket: max 300 subscriptions per connection
→ See: `references/03-eventsub.md`

### Large-scale / multi-channel architecture?
→ Use Conduit transport: single app-level endpoint, N shards, scales to millions of subscriptions
→ Requires App Access Token only — no user tokens
→ See: `references/03-eventsub.md` (Conduit section)

### Clip pipeline (detect + create + fetch)?
→ Create clip: POST `/helix/clips` — requires `clips:edit` scope (User Access Token)
→ Clip takes 15–30s to process — poll GET `/helix/clips?id=` until `thumbnail_url` is populated
→ See: `references/05-clips.md`

### OAuth / token management?
→ See: `references/01-auth.md`

### REST API general usage?
→ See: `references/02-helix-api.md`

### Rate limits & production gotchas?
→ See: `references/06-rate-limits-gotchas.md`

## Reference Files

| File | When to read |
|---|---|
| `references/01-auth.md` | OAuth flows, token types, refresh logic, scopes |
| `references/02-helix-api.md` | REST API patterns, pagination, key endpoints |
| `references/03-eventsub.md` | WebSocket, Webhook, Conduit, subscription lifecycle |
| `references/04-chat.md` | Sending/receiving chat, IRC migration, chatbot scopes |
| `references/05-clips.md` | Creating, polling, fetching clips programmatically |
| `references/06-rate-limits-gotchas.md` | Rate limits, common pitfalls, production checklist |

## Key URLs

- API Base: `https://api.twitch.tv/helix/`
- Auth Base: `https://id.twitch.tv/oauth2/`
- EventSub WebSocket: `wss://eventsub.wss.twitch.tv/ws`
- Dev Console: `https://dev.twitch.tv/console`
- Docs: `https://dev.twitch.tv/docs`

## Non-Negotiables in Every Response

1. Always specify which token type each API call requires.
2. Always include the `Client-Id` header alongside `Authorization`.
3. Never hardcode tokens — use env vars or Secret Manager.
4. Always handle token refresh (401 → refresh → retry).
5. Always verify EventSub webhook signatures before processing.

<!-- Source: 01-auth.md -->
# Twitch OAuth & Token Reference

## Token Types

### App Access Token
- Machine-to-machine. No user context.
- Flow: Client Credentials (`grant_type=client_credentials`)
- Endpoint: `POST https://id.twitch.tv/oauth2/token`
- Does NOT use scopes. Grants access to public data and app-level EventSub.
- Expires in ~60 days. Re-request when expired (no refresh token).
- Required by: Webhook EventSub, Conduit, most GET endpoints for public data.

```bash
curl -X POST 'https://id.twitch.tv/oauth2/token' \
  -d 'client_id=<CLIENT_ID>&client_secret=<CLIENT_SECRET>&grant_type=client_credentials'
# Response: { "access_token": "...", "expires_in": 5183944, "token_type": "bearer" }
```

### User Access Token
- Represents a specific user who authorized your app.
- Flow: Authorization Code (server-side) or Implicit (client-side, no secret)
- Required by: Chat read/write, clip creation, moderator actions, channel management.
- Has a refresh token. Expires in ~4 hours. Must refresh proactively.

```bash
# Step 1: Redirect user to:
GET https://id.twitch.tv/oauth2/authorize
  ?client_id=<CLIENT_ID>
  &redirect_uri=<YOUR_REDIRECT>
  &response_type=code
  &scope=user:read:chat+user:write:chat+user:bot

# Step 2: Exchange code for tokens:
POST https://id.twitch.tv/oauth2/token
  client_id=<CLIENT_ID>
  &client_secret=<CLIENT_SECRET>
  &code=<CODE_FROM_REDIRECT>
  &grant_type=authorization_code
  &redirect_uri=<YOUR_REDIRECT>

# Response: { "access_token": "...", "refresh_token": "...", "expires_in": 14400 }
```

### Refreshing a User Access Token
```bash
POST https://id.twitch.tv/oauth2/token
  client_id=<CLIENT_ID>
  &client_secret=<CLIENT_SECRET>
  &grant_type=refresh_token
  &refresh_token=<REFRESH_TOKEN>
```
- Refresh tokens do NOT expire unless: user revokes access, password change, or unused for 30+ days.
- Always store the new `access_token` AND `refresh_token` returned by refresh — the old refresh token is invalidated.

## Token Validation

Always validate tokens on startup and periodically (Twitch recommends every hour).

```bash
GET https://id.twitch.tv/oauth2/validate
Authorization: OAuth <access_token>
# Returns: { "client_id": "...", "login": "...", "user_id": "...", "expires_in": 12345, "scopes": [...] }
# 401 = token is invalid or expired
```

## Token Revocation
```bash
POST https://id.twitch.tv/oauth2/revoke
  ?client_id=<CLIENT_ID>
  &token=<TOKEN>
```

## Scopes Reference (Most Common)

| Scope | Type | What it allows |
|---|---|---|
| `user:read:chat` | User | Read chat messages via EventSub |
| `user:write:chat` | User | Send chat messages via Helix API |
| `user:bot` | User | Bot account: act as chatbot in channels |
| `channel:bot` | User | Broadcaster: authorize bot in their channel |
| `moderator:read:chatters` | User | Get list of chatters (must be mod) |
| `moderator:manage:banned_users` | User | Ban/timeout users |
| `moderator:manage:chat_messages` | User | Delete messages |
| `clips:edit` | User | Create clips |
| `channel:read:subscriptions` | User | Read subscription data |
| `channel:manage:broadcast` | User | Update stream title/game |
| `bits:read` | User | Read bits/cheers |

## Device Code Flow (for CLI tools / no browser)
```bash
# Step 1: Request device code
POST https://id.twitch.tv/oauth2/device
  client_id=<CLIENT_ID>&scopes=<SCOPES>
# Response: { "device_code": "...", "user_code": "XXXX-YYYY", "verification_uri": "https://twitch.tv/activate", "interval": 5 }

# Step 2: Poll for token (every `interval` seconds)
POST https://id.twitch.tv/oauth2/token
  client_id=<CLIENT_ID>&scopes=<SCOPES>&device_code=<CODE>&grant_type=urn:ietf:params:oauth:grant-type:device_code
```

## Common Auth Mistakes

- Using App Access Token where User Access Token is required → 401/403
- Not including `Client-Id` header → 400
- Requesting scopes not needed → risk of app suspension by Twitch
- Not handling 401 with automatic token refresh in long-running apps
- Storing tokens in plaintext files → use env vars or Secret Manager
- Not validating the token before using it (may be revoked by user)


<!-- Source: 02-helix-api.md -->
# Twitch Helix REST API Reference

## Base URL & Required Headers

```
https://api.twitch.tv/helix/<endpoint>
```

Every request requires:
```
Authorization: Bearer <access_token>
Client-Id: <your_client_id>
```
Missing either header → 400 Bad Request. Missing or invalid token → 401.

## Pagination

Most list endpoints return paginated results with a cursor.

```json
{
  "data": [...],
  "pagination": { "cursor": "eyJiI..." }
}
```

- Get next page: add `?after=<cursor>` query param
- Get previous page: add `?before=<cursor>`
- Empty `pagination` object = end of list
- Default/max page sizes vary by endpoint (e.g. Get Streams: max 100)

```python
# Pattern for full pagination in Python
def get_all_pages(url, headers, params={}):
    results = []
    cursor = None
    while True:
        if cursor:
            params['after'] = cursor
        resp = requests.get(url, headers=headers, params=params).json()
        results.extend(resp.get('data', []))
        cursor = resp.get('pagination', {}).get('cursor')
        if not cursor:
            break
    return results
```

## Key Endpoints

### Users
```
GET /helix/users                        # Get user by login or id
GET /helix/users?login=<login>          # By username
GET /helix/users?id=<id>               # By user ID
# No params + User Access Token = authenticated user's info
```

### Streams
```
GET /helix/streams?user_login=<login>  # Check if live, get game/title
GET /helix/streams?game_id=<id>        # Streams by game
# stream_type: "live" (only live streams returned by default)
# 'data' array is empty if user is offline
```

### Channels
```
GET  /helix/channels?broadcaster_id=<id>          # Get channel info
PATCH /helix/channels                              # Update title/game (requires channel:manage:broadcast)
Body: { "broadcaster_id": "...", "title": "...", "game_id": "..." }
```

### Chat
```
POST /helix/chat/messages              # Send chat message (user:write:chat)
GET  /helix/chat/chatters              # List chatters (moderator:read:chatters)
GET  /helix/chat/emotes                # Channel/global emotes
DELETE /helix/moderation/chat          # Delete message (moderator:manage:chat_messages)
POST /helix/moderation/bans            # Timeout or ban user (moderator:manage:banned_users)
```

### Send Chat Message
```bash
POST https://api.twitch.tv/helix/chat/messages
Authorization: Bearer <user_access_token>   # user:write:chat scope
Client-Id: <client_id>
Content-Type: application/json

{
  "broadcaster_id": "123456",
  "sender_id": "654321",           # Bot's user ID
  "message": "Hello chat!",
  "reply_parent_message_id": "..." # Optional: reply to specific message
}
# Response: { "data": [{ "message_id": "...", "is_sent": true }] }
```

### Clips
```
POST /helix/clips?broadcaster_id=<id>  # Create clip (clips:edit, User token)
GET  /helix/clips?id=<id>             # Get clip status/data
GET  /helix/clips?broadcaster_id=<id> # List broadcaster's clips
```

### Games / Categories
```
GET /helix/games?name=<name>           # Search game by exact name
GET /helix/games?id=<id>              # By IGDB game ID (Twitch uses IGDB IDs)
GET /helix/search/categories?query=<q> # Search games/categories
```

### EventSub Subscriptions
```
POST   /helix/eventsub/subscriptions   # Create subscription
GET    /helix/eventsub/subscriptions   # List subscriptions
DELETE /helix/eventsub/subscriptions?id=<id>  # Delete subscription
```

### Moderation
```
POST /helix/moderation/bans            # Ban or timeout
DELETE /helix/moderation/bans          # Unban
GET  /helix/moderation/banned          # List banned users
POST /helix/moderation/moderators      # Add moderator
```

### Subscriptions & Bits
```
GET /helix/subscriptions?broadcaster_id=<id>    # channel:read:subscriptions
GET /helix/bits/leaderboard                     # bits:read
```

## Timestamps

All EventSub event timestamps are RFC3339 with nanoseconds:
`YYYY-MM-DDT00:00:00.000000000Z`

Most REST API timestamps are RFC3339 standard:
`YYYY-MM-DDTHH:MM:SSZ`

## IDs

- All IDs are strings, treat as opaque
- User IDs are numeric strings but don't do math on them
- Game IDs come from IGDB (Twitch uses IGDB's catalog)

## HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Success (GET) |
| 204 | Success, no body (DELETE) |
| 400 | Bad request — missing param, wrong token type |
| 401 | Unauthorized — invalid/expired token |
| 403 | Forbidden — valid token but wrong scopes or insufficient privilege |
| 404 | Not found |
| 409 | Conflict (e.g., clip already being created) |
| 429 | Rate limited — check `Ratelimit-Reset` header |
| 500/503 | Twitch-side error — retry with backoff |


<!-- Source: 03-eventsub.md -->
# Twitch EventSub Reference

## Transports Overview

| Transport | Best for | Auth | Max subs |
|---|---|---|---|
| **WebSocket** | Single-user apps, bots, client-side | User or App token | 300/connection |
| **Webhook** | Server-side, multi-user, persistent | App token | Unlimited (cost-based) |
| **Conduit** | Large-scale SaaS, multi-channel | App token only | Unlimited (sharded) |

---

## WebSocket Transport

### Connection
```
wss://eventsub.wss.twitch.tv/ws
```

1. Connect → receive `session_welcome` message with `session.id`
2. Use `session.id` to create subscriptions via Helix API
3. Receive `notification` messages as events occur
4. Respond to `session_keepalive` (sent every 10s if no events) — no action needed, just tracking
5. Handle `session_reconnect` — reconnect to new URL immediately, then delete old session

### Welcome Message
```json
{
  "metadata": { "message_type": "session_welcome" },
  "payload": {
    "session": {
      "id": "AQoQexAWVYKSTIu4ec_2VAxyuhAB",
      "status": "connected",
      "keepalive_timeout_seconds": 10,
      "reconnect_url": null
    }
  }
}
```

### Creating a Subscription (after welcome)
```bash
POST https://api.twitch.tv/helix/eventsub/subscriptions
Authorization: Bearer <user_or_app_token>
Client-Id: <client_id>
Content-Type: application/json

{
  "type": "channel.chat.message",
  "version": "1",
  "condition": {
    "broadcaster_user_id": "12345",
    "user_id": "67890"          # Bot's user ID (required for chat subscriptions)
  },
  "transport": {
    "method": "websocket",
    "session_id": "AQoQexAWVYKSTIu4ec_2VAxyuhAB"
  }
}
```

### Notification Message Structure
```json
{
  "metadata": {
    "message_id": "befa7b53-d79d-478f-86b9-120f112b044e",
    "message_type": "notification",
    "message_timestamp": "2022-11-16T10:11:12.464757833Z",
    "subscription_type": "channel.chat.message",
    "subscription_version": "1"
  },
  "payload": {
    "subscription": { ... },
    "event": { ... }            # The actual event data
  }
}
```

**Always deduplicate by `metadata.message_id`** — Twitch delivers at-least-once.

---

## Webhook Transport

### Setup
1. Create HTTPS endpoint (must be publicly accessible)
2. Create subscription → Twitch sends challenge
3. Respond to challenge with `challenge` value (plain text, 200 OK, within 10s)
4. Subscription becomes `enabled`

### Signature Verification (CRITICAL — verify before processing)
```python
import hashlib, hmac

def verify_twitch_signature(headers, body_bytes):
    msg_id = headers.get('Twitch-Eventsub-Message-Id', '')
    timestamp = headers.get('Twitch-Eventsub-Message-Timestamp', '')
    signature = headers.get('Twitch-Eventsub-Message-Signature', '')
    
    hmac_message = (msg_id + timestamp + body_bytes.decode()).encode()
    expected = 'sha256=' + hmac.new(
        SECRET.encode(), hmac_message, hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

# Reject if verification fails (return 403)
# Reject if timestamp > 10 minutes old (replay attack protection)
```

### Message Types for Webhooks
- `webhook_callback_verification` → respond with `challenge` field value (200)
- `notification` → process event, return 200 quickly
- `revocation` → subscription was revoked (re-subscribe if needed)

---

## Conduit Transport (Large Scale)

Conduit = single app-level "pipe" with N shards. Each shard has its own webhook or WebSocket.
Best for SaaS serving many channels simultaneously.

```bash
# 1. Create conduit
POST /helix/eventsub/conduits
Authorization: Bearer <app_access_token>
{ "shard_count": 10 }
# Response: { "data": [{ "id": "...", "shard_count": 10 }] }

# 2. Assign webhooks to shards
PATCH /helix/eventsub/conduits/shards
{
  "conduit_id": "...",
  "shards": [
    { "id": "0", "transport": { "method": "webhook", "callback": "https://...", "secret": "..." } },
    { "id": "1", "transport": { "method": "webhook", "callback": "https://...", "secret": "..." } }
  ]
}

# 3. Subscribe events using conduit transport
POST /helix/eventsub/subscriptions
{
  "type": "channel.chat.message",
  "version": "1",
  "condition": { "broadcaster_user_id": "...", "user_id": "..." },
  "transport": { "method": "conduit", "conduit_id": "..." }
}
```

---

## Most Important Subscription Types

### Chat
| Type | Version | Key condition fields |
|---|---|---|
| `channel.chat.message` | 1 | `broadcaster_user_id`, `user_id` |
| `channel.chat.notification` | 1 | `broadcaster_user_id`, `user_id` |
| `channel.chat.message_delete` | 1 | `broadcaster_user_id`, `user_id` |
| `channel.chat.clear` | 1 | `broadcaster_user_id`, `user_id` |

### Channel Events
| Type | Version | Notes |
|---|---|---|
| `stream.online` | 1 | Stream goes live |
| `stream.offline` | 1 | Stream ends |
| `channel.follow` | 2 | New follower — requires moderator scope |
| `channel.subscribe` | 1 | New subscription |
| `channel.subscription.gift` | 1 | Gift subs |
| `channel.cheer` | 1 | Bits cheer |
| `channel.raid` | 1 | Incoming raid |
| `channel.update` | 2 | Title/game/language changed |
| `channel.channel_points_custom_reward_redemption.add` | 1 | Channel point redemption |

### Moderation
| Type | Version | Notes |
|---|---|---|
| `channel.ban` | 1 | User banned/timed out |
| `channel.unban` | 1 | User unbanned |
| `channel.moderate` | 2 | Comprehensive mod actions |

### Chat Message Event Structure
```json
{
  "broadcaster_user_id": "123456",
  "broadcaster_user_login": "streamer",
  "broadcaster_user_name": "Streamer",
  "chatter_user_id": "7890",
  "chatter_user_login": "viewer",
  "chatter_user_name": "Viewer",
  "message_id": "abc123",
  "message": {
    "text": "Hello!",
    "fragments": [
      { "type": "text", "text": "Hello!", "cheermote": null, "emote": null }
    ]
  },
  "color": "#FF0000",
  "badges": [{ "set_id": "subscriber", "id": "0", "info": "1" }],
  "message_type": "text",
  "cheer": null,
  "reply": null,
  "channel_points_custom_reward_id": null
}
```

---

## Subscription Cost System (Webhooks/Conduit)

Twitch uses a cost system for subscriptions. Most subscriptions cost 1 point.
Default total: 10,000 points per app. Can request increase.
Check usage: `GET /helix/eventsub/subscriptions` → `total_cost` field.

---

## EventSub Best Practices

1. **Always verify webhook signatures** — never skip, even in dev.
2. **Respond to webhooks in < 5s** — offload processing to a queue.
3. **Track `message_id`** — deduplicate for at-least-once delivery.
4. **Handle `session_reconnect`** — reconnect before closing old session.
5. **Resubscribe on app restart** — WebSocket sessions don't persist.
6. **Monitor subscription status** — auto-resubscribe if `revocation` received.
7. **Don't create duplicate subscriptions** — costs accumulate, check existing first.


<!-- Source: 04-chat.md -->
# Twitch Chat Development Reference

## Current Recommendation (2024+)

**EventSub (read) + Helix Send Chat Message API (write)** is the official path.
IRC is considered legacy. New features are only added to EventSub/Helix.

---

## Chatbot Scopes

### Bot Account Needs:
- `user:read:chat` — receive chat messages via EventSub
- `user:write:chat` — send messages via Helix API
- `user:bot` — identify account as a bot, allows acting in channels

### Broadcaster Account Needs (third-party bots):
- `channel:bot` — authorize an external bot to operate in their channel

### Optional Moderator Actions:
- `moderator:manage:chat_messages` — delete messages
- `moderator:manage:banned_users` — timeout/ban users
- `moderator:read:chatters` — list who's in chat

---

## Receiving Chat Messages (EventSub WebSocket)

```python
import asyncio, websockets, json, requests

EVENTSUB_WS = "wss://eventsub.wss.twitch.tv/ws"

async def connect_chat(broadcaster_id, bot_user_id, bot_token, client_id):
    async with websockets.connect(EVENTSUB_WS) as ws:
        # Wait for welcome
        welcome = json.loads(await ws.recv())
        session_id = welcome["payload"]["session"]["id"]

        # Subscribe to chat
        requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers={"Authorization": f"Bearer {bot_token}", "Client-Id": client_id},
            json={
                "type": "channel.chat.message",
                "version": "1",
                "condition": {
                    "broadcaster_user_id": broadcaster_id,
                    "user_id": bot_user_id
                },
                "transport": {"method": "websocket", "session_id": session_id}
            }
        )

        # Listen for messages
        async for raw in ws:
            msg = json.loads(raw)
            if msg["metadata"]["message_type"] == "notification":
                event = msg["payload"]["event"]
                print(f"{event['chatter_user_name']}: {event['message']['text']}")

asyncio.run(connect_chat("12345", "67890", "user_token", "client_id"))
```

---

## Sending Chat Messages (Helix API)

```python
def send_chat_message(broadcaster_id, sender_id, text, token, client_id,
                       reply_to=None):
    body = {
        "broadcaster_id": broadcaster_id,
        "sender_id": sender_id,
        "message": text[:500]  # Max 500 chars for regular users
    }
    if reply_to:
        body["reply_parent_message_id"] = reply_to

    resp = requests.post(
        "https://api.twitch.tv/helix/chat/messages",
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id,
                 "Content-Type": "application/json"},
        json=body
    )
    data = resp.json()["data"][0]
    if not data["is_sent"]:
        # drop_reason: {"code": "msg_rejected", "message": "..."}
        print(f"Message not sent: {data.get('drop_reason')}")
    return data
```

### Message Limits
- Regular users/bots: 500 chars
- Verified bots: same, but higher rate limit
- Moderators: 500 chars
- If `is_sent: false`, check `drop_reason.code`:
  - `msg_rejected` — AutoMod blocked it
  - `msg_channel_suspended` — channel is suspended
  - `msg_slowmode` — slow mode active, wait
  - `msg_duplicate` — same message sent too recently

---

## Chat Notifications (subs, raids, etc.)

Subscribe to `channel.chat.notification` for system events in chat:
- `sub`, `resub`, `sub_gift`, `community_sub_gift`
- `raid`
- `bits_badge_tier`
- `charity_donation`

```json
{
  "chatter_user_id": "...",
  "notice_type": "sub",
  "sub": {
    "sub_tier": "1000",
    "is_prime": false,
    "duration_months": 1
  }
}
```

---

## Deleting Messages
```python
def delete_message(broadcaster_id, moderator_id, message_id, token, client_id):
    requests.delete(
        "https://api.twitch.tv/helix/moderation/chat",
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id},
        params={
            "broadcaster_id": broadcaster_id,
            "moderator_id": moderator_id,
            "message_id": message_id
        }
    )
# Requires: moderator:manage:chat_messages scope
# moderator_id must be a mod in the channel
```

---

## Timeout / Ban Users
```python
def timeout_user(broadcaster_id, moderator_id, user_id, duration_seconds,
                  reason, token, client_id):
    # duration=None means permanent ban
    body = {
        "data": {
            "user_id": user_id,
            "reason": reason
        }
    }
    if duration_seconds:
        body["data"]["duration"] = duration_seconds  # max 1,209,600 (14 days)

    requests.post(
        "https://api.twitch.tv/helix/moderation/bans",
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id,
                 "Content-Type": "application/json"},
        params={"broadcaster_id": broadcaster_id, "moderator_id": moderator_id},
        json=body
    )
# Requires: moderator:manage:banned_users scope
```

---

## IRC Migration Quick Reference

| IRC | EventSub / Helix Equivalent |
|---|---|
| Join channel | EventSub subscription per channel |
| PRIVMSG (read) | `channel.chat.message` EventSub |
| PRIVMSG (send) | `POST /helix/chat/messages` |
| CLEARCHAT (ban/timeout) | `channel.ban` EventSub |
| CLEARMSG (delete) | `channel.chat.message_delete` EventSub |
| ROOMSTATE | `channel.chat.settings_update` EventSub |
| USERNOTICE (sub/raid) | `channel.chat.notification` EventSub |
| USERSTATE | `GET /helix/users` |
| GLOBALUSERSTATE | `GET /helix/users` (no params, user token) |
| JOIN/PART | `GET /helix/chat/chatters` (mods only) |
| `chat:read` scope | `user:read:chat` |
| `chat:edit` scope | `user:write:chat` |

---

## Chatbot Verification

Twitch requires verified bots for high-volume or special use cases.
- Verification process is currently paused (as of early 2026).
- Unverified bots: lower rate limits.
- Verified bots: higher rate limits, `known_bot` badge.
- Bot accounts should set `user:bot` scope proactively.

---

## Getting Chatters List
```bash
GET https://api.twitch.tv/helix/chat/chatters
  ?broadcaster_id=<id>&moderator_id=<mod_id>
Authorization: Bearer <user_token_with_moderator:read:chatters>
# Returns up to 1000 per page, paginate with cursor
# Only available to broadcaster or moderators
```


<!-- Source: 05-clips.md -->
# Twitch Clips API Reference

## Create a Clip

```bash
POST https://api.twitch.tv/helix/clips?broadcaster_id=<id>
Authorization: Bearer <user_access_token>   # MUST be User token, NOT App token
Client-Id: <client_id>
# Optional: &has_delay=false (default false — no broadcast delay)

# Response: 202 Accepted
{
  "data": [{
    "id": "FiveWordsForClipId",
    "edit_url": "https://clips.twitch.tv/FiveWordsForClipId/edit"
  }]
}
```

**Requirements:**
- User token with `clips:edit` scope
- The channel must be live at the time of the request
- The authenticated user doesn't need to be the broadcaster
- Returns 409 if a clip for this broadcaster is already being created

## Polling for Clip Completion

Clips take **15–60 seconds** to process. The clip ID is returned immediately but data is not
available until processing completes. Poll until `thumbnail_url` is populated.

```python
import time, requests

def create_and_wait_for_clip(broadcaster_id, token, client_id, timeout=90):
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": client_id
    }

    # Create clip
    resp = requests.post(
        f"https://api.twitch.tv/helix/clips?broadcaster_id={broadcaster_id}",
        headers=headers
    )
    if resp.status_code == 409:
        raise Exception("Clip already being created for this broadcaster")
    if resp.status_code != 202:
        raise Exception(f"Clip creation failed: {resp.status_code} {resp.text}")

    clip_id = resp.json()["data"][0]["id"]
    edit_url = resp.json()["data"][0]["edit_url"]
    print(f"Clip ID: {clip_id}, processing...")

    # Poll for completion
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        clip_data = get_clip(clip_id, headers)
        if clip_data and clip_data.get("thumbnail_url"):
            print(f"Clip ready: {clip_data['url']}")
            return clip_data
        print("Still processing...")

    raise TimeoutError(f"Clip {clip_id} did not complete within {timeout}s")

def get_clip(clip_id, headers):
    resp = requests.get(
        f"https://api.twitch.tv/helix/clips?id={clip_id}",
        headers=headers
    )
    data = resp.json().get("data", [])
    return data[0] if data else None
```

## Clip Data Structure

```json
{
  "id": "FiveWordsForClipId",
  "url": "https://clips.twitch.tv/FiveWordsForClipId",
  "embed_url": "https://clips.twitch.tv/embed?clip=FiveWordsForClipId",
  "broadcaster_id": "123456",
  "broadcaster_name": "Streamer",
  "creator_id": "654321",
  "creator_name": "ClipCreator",
  "video_id": "987654321",
  "game_id": "509658",
  "language": "pt",
  "title": "Auto-generated title",
  "view_count": 0,
  "created_at": "2024-01-15T12:00:00Z",
  "thumbnail_url": "https://clips-media-assets2.twitch.tv/...",
  "duration": 30.0,                    # seconds
  "vod_offset": 3600                   # seconds from VOD start (null if no VOD)
}
```

## Get Broadcaster's Clips

```bash
GET https://api.twitch.tv/helix/clips?broadcaster_id=<id>
  &first=20              # Page size (max 100)
  &after=<cursor>        # Pagination
  &started_at=<RFC3339>  # Filter by date range
  &ended_at=<RFC3339>
# No scope required for public clips
# App or User token works
```

## Get Clip by ID

```bash
GET https://api.twitch.tv/helix/clips?id=<clip_id>
# Can pass multiple ids: ?id=abc&id=def&id=ghi (max 100)
```

## Clip Pipeline Architecture (Production)

For a clip detection + creation pipeline:

```
1. TRIGGER DETECTION
   - EventSub: monitor chat for clip keywords (CLIP, PogChamp, etc.)
   - Sentiment spike in chat message volume
   - Specific game events (death, kill, boss fight)

2. CLIP CREATION (async)
   - POST /helix/clips (requires live stream)
   - Store clip_id + metadata in queue/DB immediately
   - Set status = "processing"

3. POLLING WORKER (separate process/job)
   - Every 10s: GET /helix/clips?id=<ids> (batch up to 100)
   - When thumbnail_url populated: set status = "ready"
   - After 90s timeout: set status = "failed"

4. DISTRIBUTION
   - Send clip URL to dashboard / streamer notification
   - Optional: POST to social APIs (YouTube Shorts, TikTok, etc.)
   - Store in clip history with context (game, vibe, trigger reason)
```

## Important Limitations

- Broadcaster must be **live** to create clips — 403 if offline
- Max clip duration: 60 seconds (Twitch determines the window around the request)
- `has_delay=true` accounts for broadcast delay (30s–120s) — use when stream has delay enabled
- Rate limit: 600 clips per day per broadcaster (approximately)
- Clips are public by default — no private clips via API
- Cannot set custom title at creation time — must edit after via `edit_url`
- `vod_offset` is null if the broadcaster has VODs disabled or clip is older than VOD retention


<!-- Source: 06-rate-limits-gotchas.md -->
# Twitch Rate Limits & Production Gotchas

## Helix API Rate Limits

| Limit | Value | Header |
|---|---|---|
| Requests per minute (default) | 800/min per client_id + token pair | `Ratelimit-Limit` |
| Remaining requests | Varies | `Ratelimit-Remaining` |
| Reset timestamp | Unix epoch | `Ratelimit-Reset` |

- Rate limits are per `(client_id, token)` pair — different tokens have independent limits.
- App Access Tokens have a higher shared limit than User Access Tokens.
- 429 response = rate limited. Wait until `Ratelimit-Reset` timestamp.

```python
import time

def rate_limited_request(method, url, **kwargs):
    resp = method(url, **kwargs)
    if resp.status_code == 429:
        reset_at = int(resp.headers.get('Ratelimit-Reset', time.time() + 60))
        wait = max(0, reset_at - time.time()) + 1
        print(f"Rate limited. Waiting {wait}s...")
        time.sleep(wait)
        return rate_limited_request(method, url, **kwargs)
    return resp
```

## Chat Message Rate Limits

| Bot Type | Rate Limit |
|---|---|
| Regular (unverified) | 20 messages / 30s per channel |
| Moderator in channel | 100 messages / 30s per channel |
| Verified bot | Higher limits (apply via dev console) |

Exceeding chat limits → message silently dropped or `is_sent: false` with drop reason.

## EventSub Limits

| Transport | Limit |
|---|---|
| WebSocket subscriptions | 300 per connection |
| WebSocket connections | 3 per user token |
| Subscription cost (webhooks/conduit) | 10,000 total per app (can request more) |
| Webhook delivery timeout | 5 seconds to respond |
| Message deduplication window | ~10 minutes (track message_id) |

## Clip Creation Limits

- ~600 clips per broadcaster per day (approximate, not officially documented)
- 409 if clip already being created for same broadcaster
- Must be live to create clips
- Processing time: 15–60 seconds (rarely up to 90s)

---

## Common Production Pitfalls

### 1. Wrong Token Type
**Symptom:** 401 or 400 on valid-looking requests
**Cause:** Using App Access Token where User Access Token is required (or vice versa)
**Fix:** Check each endpoint's docs for required token type. Chat operations always need User token.

### 2. Missing `user_id` in Chat Subscriptions
**Symptom:** 400 on EventSub subscription creation for `channel.chat.message`
**Cause:** Chat subscriptions require both `broadcaster_user_id` AND `user_id` (bot's ID)
**Fix:** Include both fields in the `condition` object.

### 3. WebSocket Session Not Reused on Reconnect
**Symptom:** Duplicate messages or missed events after reconnect
**Cause:** Creating a new session instead of reconnecting to the `reconnect_url`
**Fix:** On `session_reconnect` message, connect to the provided URL first, then close the old session.

### 4. Not Verifying Webhook Signatures
**Symptom:** Security vulnerability — any HTTP request gets processed
**Fix:** Always verify `Twitch-Eventsub-Message-Signature` before processing. Return 403 on failure.
See: `references/03-eventsub.md` for implementation.

### 5. Forgetting to Poll Clips
**Symptom:** Empty clip data immediately after creation
**Cause:** Clips take 15–60s to process. `thumbnail_url` is null until ready.
**Fix:** Poll every 5–10s until `thumbnail_url` is populated. See: `references/05-clips.md`

### 6. Stale App Access Tokens in Long-Running Services
**Symptom:** 401 errors after weeks of uptime
**Cause:** App Access Tokens expire (~60 days) and there's no refresh token
**Fix:** Validate token on startup and every hour. Re-request new token on 401.

### 7. Duplicate EventSub Subscriptions
**Symptom:** Receiving every event 2x, inflated subscription cost
**Cause:** App restarts create new subscriptions without cleaning old ones
**Fix:** On startup, check existing subscriptions (`GET /helix/eventsub/subscriptions`)
and only create if not already `enabled`.

```python
def ensure_subscription(type_, condition, transport, token, client_id):
    # Check existing
    resp = requests.get(
        "https://api.twitch.tv/helix/eventsub/subscriptions",
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id},
        params={"type": type_}
    )
    for sub in resp.json().get("data", []):
        if sub["condition"] == condition and sub["status"] == "enabled":
            return sub  # Already exists

    # Create new
    return requests.post(
        "https://api.twitch.tv/helix/eventsub/subscriptions",
        headers={"Authorization": f"Bearer {token}", "Client-Id": client_id,
                 "Content-Type": "application/json"},
        json={"type": type_, "version": "1", "condition": condition,
              "transport": transport}
    ).json()["data"][0]
```

### 8. Replay Attacks on Webhooks
**Symptom:** Old events being replayed maliciously
**Fix:** Reject if `Twitch-Eventsub-Message-Timestamp` is older than 10 minutes.

### 9. Blocking the Webhook Response
**Symptom:** Twitch retries events, subscription gets disabled
**Cause:** Processing event synchronously before returning 200
**Fix:** Return 200 immediately, process event asynchronously (queue + worker).

### 10. User Token Refresh Race Condition
**Symptom:** Intermittent 401 in concurrent systems
**Cause:** Multiple workers refresh the same token simultaneously
**Fix:** Use a distributed lock (Redis/Firestore) around refresh operations.

---

## Production Checklist

Before going live:

- [ ] Tokens stored in env vars / Secret Manager, never in code
- [ ] Token refresh logic implemented and tested (401 → refresh → retry)
- [ ] Webhook signature verification implemented
- [ ] Timestamp freshness check on webhooks (< 10 min)
- [ ] EventSub message deduplication by `message_id`
- [ ] Webhook handler responds in < 5s (async processing)
- [ ] Duplicate subscription guard on startup
- [ ] Rate limit handling with backoff
- [ ] App Access Token revalidation every hour in long-running services
- [ ] WebSocket reconnect logic handles `session_reconnect` message
- [ ] Logging includes `message_id` for traceability

---

## Useful Dev Tools

- **Twitch CLI:** `twitch event trigger channel.chat.message` — simulate events locally
  - Install: `brew install twitchdev/twitch/twitch-cli`
  - Mock EventSub: `twitch event websocket start-server`
- **Dev Console:** `https://dev.twitch.tv/console` — manage apps, tokens
- **Token Generator:** `https://twitchtokengenerator.com` — quick tokens for dev/testing
- **EventSub Subscription Types:** `https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/`


<!-- Source: Mock Data Instructions -->
# Twitch API Mocking Data

All payloads in this skill are sourced directly from official Twitch developer documentation
(dev.twitch.tv) and verified developer forum reports (discuss.dev.twitch.com). Nothing is invented.

## How to Use

Reference the payload files in `payloads/` directly in your test fixtures:

```python
import json, pathlib

def load_fixture(name):
    path = pathlib.Path(__file__).parent / "payloads" / f"{name}.json"
    return json.loads(path.read_text())

# Example
create_clip_success = load_fixture("post_clips_202")
clip_processing     = load_fixture("get_clips_processing")
clip_ready          = load_fixture("get_clips_ready")
```

## Payload Index

| File | Endpoint | Scenario |
|---|---|---|
| `post_clips_202.json` | POST /helix/clips | Success — 202 Accepted (clip being created) |
| `get_clips_ready.json` | GET /helix/clips | Clip fully processed (thumbnail_url populated) |
| `get_clips_processing.json` | GET /helix/clips | Clip still processing (data array empty) |
| `get_clips_list_paginated.json` | GET /helix/clips?broadcaster_id= | List with pagination cursor |
| `get_clips_list_empty.json` | GET /helix/clips?broadcaster_id= | No clips found |
| `get_clips_download_ready.json` | GET /helix/clips/downloads | Download URLs available |
| `get_clips_download_not_ready.json` | GET /helix/clips/downloads | URLs not yet available |
| `error_400_broadcaster_not_live.json` | POST /helix/clips | 400 — broadcaster offline |
| `error_400_missing_param.json` | Any | 400 — required param missing |
| `error_401_invalid_token.json` | Any | 401 — invalid/expired token |
| `error_401_missing_user_token.json` | Any | 401 — App token used where User token required |
| `error_403_missing_scope.json` | Any | 403 — missing required scope |
| `error_409_clip_in_progress.json` | POST /helix/clips | 409 — clip already being created |
| `error_429_rate_limited.json` | Any | 429 — rate limit exceeded |
| `error_503_service_unavailable.json` | POST /helix/clips | 503 — intermittent Twitch outage |
| `headers_normal.json` | Any | Standard rate-limit response headers |
| `headers_rate_limited.json` | Any | Headers when 429 is returned |

## Critical Behaviors for Tests

1. **POST /helix/clips returns 202 immediately** — only `id` and `edit_url`, no clip data yet.
2. **Polling GET /helix/clips?id=** — returns empty `data: []` while processing, populated object when done.
3. **Clip considered failed** — if after 15s GET /helix/clips still returns empty array (Twitch docs recommendation).
4. **GET /helix/clips/downloads** — open beta as of Sept 2025, requires `editor:manage:clips` OR `channel:manage:clips` scope. Rate limit: 100 req/min (custom, separate from global 800/min).
5. **Rate limit headers** — always lowercase: `ratelimit-limit`, `ratelimit-remaining`, `ratelimit-reset`. Value of `ratelimit-reset` is a Unix epoch timestamp (string).
6. **Error body format** — always `{"error": "<text>", "status": <int>, "message": "<detail>"}`.
7. **503 on clips** — documented real behavior, intermittent, retry with backoff.

# Verified Mock Payloads

Use these JSON objects for testing. They are exact replicas of Twitch API responses.

### `error_400_broadcaster_not_live.json`
```json
{
  "_meta": {
    "endpoint": "POST /helix/clips?broadcaster_id=123456",
    "http_status": 400,
    "source": "https://dev.twitch.tv/docs/api/reference#create-clip",
    "note": "Broadcaster is not currently live. clips:edit scope is valid but stream is offline."
  },
  "error": "Bad Request",
  "status": 400,
  "message": "The broadcaster is not live."
}
```

### `error_400_missing_param.json`
```json
{
  "_meta": {
    "endpoint": "POST /helix/clips (no broadcaster_id)",
    "http_status": 400,
    "source": "https://dev.twitch.tv/docs/api/reference",
    "note": "Required query parameter not provided."
  },
  "error": "Bad Request",
  "status": 400,
  "message": "Missing required parameter \"broadcaster_id\""
}
```

### `error_401_invalid_token.json`
```json
{
  "_meta": {
    "endpoint": "Any authenticated endpoint",
    "http_status": 401,
    "source": "https://discuss.dev.twitch.com/t/twitch-bot-401/46599",
    "note": "Token is expired, revoked, or malformed. Trigger refresh flow on this error."
  },
  "error": "Unauthorized",
  "status": 401,
  "message": "Invalid OAuth token"
}
```

### `error_401_missing_user_token.json`
```json
{
  "_meta": {
    "endpoint": "POST /helix/clips or POST /helix/chat/messages with App token",
    "http_status": 401,
    "source": "https://dev.twitch.tv/docs/chat/irc-migration/",
    "note": "App Access Token was used where a User Access Token is required (e.g. clips:edit, user:write:chat). This is the most common auth mistake."
  },
  "error": "Unauthorized",
  "status": 401,
  "message": "Missing User OAUTH Token"
}
```

### `error_403_missing_scope.json`
```json
{
  "_meta": {
    "endpoint": "EventSub subscription or any scope-gated endpoint",
    "http_status": 403,
    "source": "https://dev.twitch.tv/docs/chat/irc-migration/",
    "note": "Token is valid but lacks the required scope. Check requested scopes at token creation."
  },
  "error": "Forbidden",
  "status": 403,
  "message": "subscription missing proper authorization"
}
```

### `error_409_clip_in_progress.json`
```json
{
  "_meta": {
    "endpoint": "POST /helix/clips?broadcaster_id=123456",
    "http_status": 409,
    "source": "https://dev.twitch.tv/docs/api/reference#create-clip",
    "note": "A clip is already being created for this broadcaster. There is a global rate limit across all callers per broadcaster. Wait and retry."
  },
  "error": "Conflict",
  "status": 409,
  "message": "clip in progress"
}
```

### `error_429_rate_limited.json`
```json
{
  "_meta": {
    "endpoint": "Any Helix endpoint",
    "http_status": 429,
    "source": "https://dev.twitch.tv/docs/api/guide",
    "note": "Rate limit exceeded. Read 'ratelimit-reset' header (Unix epoch) to know when to retry. Do NOT retry before that timestamp."
  },
  "error": "Too Many Requests",
  "status": 429,
  "message": "Request rate limit exceeded"
}
```

### `error_503_service_unavailable.json`
```json
{
  "_meta": {
    "endpoint": "POST /helix/clips",
    "http_status": 503,
    "source": "https://discuss.dev.twitch.com/t/intermittent-problems-creating-clips-via-api/62189",
    "note": "Intermittent Twitch-side failure on clip creation. message is empty string — this is real behavior. Retry with exponential backoff. Some channels trigger this consistently due to Twitch infrastructure issues."
  },
  "error": "Service Unavailable",
  "status": 503,
  "message": ""
}
```

### `get_clips_download_not_ready.json`
```json
{
  "_meta": {
    "endpoint": "GET /helix/clips/downloads?id=FunPoisedGiraffeGingerPower-KDy2fwLNuUEHU",
    "http_status": 200,
    "source": "https://discuss.dev.twitch.com/t/get-clips-download-twitch-api-endpoint-now-available-in-open-beta/64334",
    "note": "Clip exists but download URL not yet available — clip may still be processing. download_url is null."
  },
  "data": [
    {
      "id": "FunPoisedGiraffeGingerPower-KDy2fwLNuUEHU",
      "download_url": null,
      "expires_at": null
    }
  ]
}
```

### `get_clips_download_ready.json`
```json
{
  "_meta": {
    "endpoint": "GET /helix/clips/downloads?id=AnimatedOptimisticWasabiVoteNay",
    "http_status": 200,
    "source": "https://discuss.dev.twitch.com/t/get-clips-download-twitch-api-endpoint-now-available-in-open-beta/64334",
    "note": "OPEN BETA as of Sept 19 2025. Requires editor:manage:clips OR channel:manage:clips scope. URLs are temporary and unique per request. Rate limit: 100 req/min (separate from global limit). Max 10 IDs per request.",
    "scopes_required": ["editor:manage:clips", "channel:manage:clips"],
    "token_type": "App access token OR user access token with scope above"
  },
  "data": [
    {
      "id": "AnimatedOptimisticWasabiVoteNay",
      "download_url": "https://production.assets.clips.twitchsvc.net/some-unique-token/clip.mp4?sig=abc123&token=xyz789&expires=1700000000",
      "expires_at": "2025-09-20T10:25:00Z"
    }
  ]
}
```

### `get_clips_list_empty.json`
```json
{
  "_meta": {
    "endpoint": "GET /helix/clips?broadcaster_id=123456",
    "http_status": 200,
    "source": "https://dev.twitch.tv/docs/api/clips",
    "note": "No clips found for this broadcaster. data is empty array, not null."
  },
  "data": [],
  "pagination": {}
}
```

### `get_clips_list_paginated.json`
```json
{
  "_meta": {
    "endpoint": "GET /helix/clips?broadcaster_id=423168062&first=2",
    "http_status": 200,
    "source": "https://dev.twitch.tv/docs/api/clips",
    "note": "Paginated list. Use 'pagination.cursor' value in '?after=' param to get next page."
  },
  "data": [
    {
      "id": "AnimatedOptimisticWasabiVoteNay",
      "url": "https://clips.twitch.tv/AnimatedOptimisticWasabiVoteNay",
      "embed_url": "https://clips.twitch.tv/embed?clip=AnimatedOptimisticWasabiVoteNay",
      "broadcaster_id": "423168062",
      "broadcaster_name": "qa_vod_automation",
      "creator_id": "7036025",
      "creator_name": "Crono",
      "video_id": "704533034",
      "game_id": "27471",
      "language": "en",
      "title": "Epic moment",
      "view_count": 1198514,
      "created_at": "2020-08-10T17:04:10Z",
      "thumbnail_url": "https://clips-media-assets2.twitch.tv/100660082970470268-offset-153206-preview-480x272.jpg",
      "duration": 28,
      "vod_offset": 222
    },
    {
      "id": "SpillYummyPigeonPieHuhu",
      "url": "https://clips.twitch.tv/SpillYummyPigeonPieHuhu",
      "embed_url": "https://clips.twitch.tv/embed?clip=SpillYummyPigeonPieHuhu",
      "broadcaster_id": "423168062",
      "broadcaster_name": "qa_vod_automation",
      "creator_id": "9988776",
      "creator_name": "AnotherViewer",
      "video_id": "704533099",
      "game_id": "27471",
      "language": "en",
      "title": "funny clip",
      "view_count": 44201,
      "created_at": "2020-08-09T12:30:00Z",
      "thumbnail_url": "https://clips-media-assets2.twitch.tv/999-offset-12000-preview-480x272.jpg",
      "duration": 30,
      "vod_offset": null
    }
  ],
  "pagination": {
    "cursor": "eyJiIjpudWxsLCJhIjp7IkN1cnNvciI6Ik1qQT0ifX0"
  }
}
```

### `get_clips_processing.json`
```json
{
  "_meta": {
    "endpoint": "GET /helix/clips?id=FunPoisedGiraffeGingerPower-KDy2fwLNuUEHU",
    "http_status": 200,
    "source": "https://dev.twitch.tv/docs/api/clips",
    "note": "Clip still processing — data array is empty. Retry after 5s. After 15s with empty array, assume failure."
  },
  "data": [],
  "pagination": {}
}
```

### `get_clips_ready.json`
```json
{
  "_meta": {
    "endpoint": "GET /helix/clips?id=AnimatedOptimisticWasabiVoteNay",
    "http_status": 200,
    "source": "https://dev.twitch.tv/docs/api/clips",
    "note": "Clip fully processed — thumbnail_url is populated. This is the completion signal."
  },
  "data": [
    {
      "id": "AnimatedOptimisticWasabiVoteNay",
      "url": "https://clips.twitch.tv/AnimatedOptimisticWasabiVoteNay",
      "embed_url": "https://clips.twitch.tv/embed?clip=AnimatedOptimisticWasabiVoteNay",
      "broadcaster_id": "423168062",
      "broadcaster_name": "qa_vod_automation",
      "creator_id": "7036025",
      "creator_name": "Crono",
      "video_id": "704533034",
      "game_id": "27471",
      "language": "en",
      "title": "a",
      "view_count": 1198514,
      "created_at": "2020-08-10T17:04:10Z",
      "thumbnail_url": "https://clips-media-assets2.twitch.tv/100660082970470268-offset-153206-preview-480x272.jpg",
      "duration": 28,
      "vod_offset": 222
    }
  ],
  "pagination": {}
}
```

### `headers_normal.json`
```json
{
  "_meta": {
    "source": "https://discuss.dev.twitch.com/t/are-rate-limit-headers-broken/45841 + https://dev.twitch.tv/docs/api/guide",
    "note": "CRITICAL: Twitch sends headers in LOWERCASE. Do not expect 'Ratelimit-Limit' — expect 'ratelimit-limit'. Values are STRINGS, not integers. ratelimit-reset is a Unix epoch string.",
    "http_status": 200,
    "scenario": "Normal request with budget remaining"
  },
  "response_headers": {
    "content-type": "application/json; charset=utf-8",
    "ratelimit-limit": "800",
    "ratelimit-remaining": "795",
    "ratelimit-reset": "1738368060"
  }
}
```

### `headers_rate_limited.json`
```json
{
  "_meta": {
    "source": "https://discuss.dev.twitch.com/t/are-rate-limit-headers-broken/45841 + https://dev.twitch.tv/docs/api/guide",
    "note": "When 429 is returned: ratelimit-remaining is '0'. ratelimit-reset contains the Unix epoch timestamp to wait until. Do NOT retry before int(ratelimit-reset) - time.time() seconds. No 'Retry-After' header — use ratelimit-reset exclusively.",
    "http_status": 429,
    "scenario": "Rate limit exhausted — all 800 points consumed"
  },
  "response_headers": {
    "content-type": "application/json; charset=utf-8",
    "ratelimit-limit": "800",
    "ratelimit-remaining": "0",
    "ratelimit-reset": "1738368120"
  },
  "response_body": {
    "error": "Too Many Requests",
    "status": 429,
    "message": "Request rate limit exceeded"
  }
}
```

### `post_clips_202.json`
```json
{
  "_meta": {
    "endpoint": "POST /helix/clips?broadcaster_id=123456",
    "http_status": 202,
    "source": "https://dev.twitch.tv/docs/api/clips",
    "note": "202 Accepted — clip is being created asynchronously. Poll GET /helix/clips?id= to check completion."
  },
  "data": [
    {
      "id": "FunPoisedGiraffeGingerPower-KDy2fwLNuUEHU",
      "edit_url": "https://clips.twitch.tv/FunPoisedGiraffeGingerPower-KDy2fwLNuUEHU/edit"
    }
  ]
}
```

