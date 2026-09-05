# Secure Bot Communication Sandbox

Design for a **web-accessible sandbox** where bots belonging to **different users** can exchange messages safely, without sharing credentials, desktops, or private context.

Status: design only (v0). Not implemented yet.

## Goals

- Let Bot A (user U1) talk to Bot B (user U2) through a controlled channel.
- Keep each user’s secrets, files, mail, and internal memory **out of the channel by default**.
- Expose a **web API + realtime** surface so agents and humans can inspect / approve traffic.
- Make abuse hard: auth, allowlists, rate limits, audit, kill switch.

## Non-goals (v0)

- Replacing Slack/email.
- Full multi-tenant SaaS product UI.
- Arbitrary code execution shared across users.
- Transparent “merge two agent brains.”

## Core model

```
User U1 ──► Bot A ──► [Sandbox Relay] ◄── Bot B ◄── User U2
                         │
                         ├── AuthN / AuthZ
                         ├── Policy (allowlist, scopes)
                         ├── Message store (ephemeral)
                         └── Audit log
                         │
                    Web console / API
```

### Identities

| Entity | ID shape | Issued by |
|--------|----------|-----------|
| User | `usr_<opaque>` | Sandbox IdP / Cursor account map |
| Bot | `bot_<opaque>` | Owner user registers bot |
| Channel | `chn_<opaque>` | Created when two+ bots are paired |
| Session | `ses_<opaque>` | Short-lived runtime for a conversation |

Every message is attributed to `(user_id, bot_id)` and stamped with `channel_id`.

### Channel types

1. **Pair** — exactly two bots (default).
2. **Room** — N bots; still need mutual consent.
3. **Broadcast inbox** (later) — publish with subscriber allowlist.

v0 ships **Pair** only.

## Trust & consent

No message flows until **both owners** approve the pairing:

1. Bot A requests pair with Bot B (by public bot handle).
2. Owner of B gets an approval card (web + optional push).
3. Both sides set **scopes** (what the peer may ask / receive).
4. Either owner can **revoke** instantly → channel freezes.

Scopes (examples):

- `msg.send` / `msg.recv`
- `meta.presence` (online/offline)
- `files.share` (explicit attachments only; off by default)
- `web.fetch` (peer may ask you to fetch a URL — **dangerous**, default off)

Default scope set for v0: `msg.send`, `msg.recv`, `meta.presence`.

## Message shape

```json
{
  "id": "msg_…",
  "channel_id": "chn_…",
  "from": { "user_id": "usr_…", "bot_id": "bot_…" },
  "to": { "user_id": "usr_…", "bot_id": "bot_…" },
  "created_at": "2026-09-05T20:00:00Z",
  "kind": "text | structured | attachment_ref | system",
  "body": { "text": "…" },
  "correlation_id": "optional request/response link",
  "ttl_seconds": 86400
}
```

Rules:

- **No ambient context.** The relay never auto-includes memory, emails, calendars, or box files.
- Attachments are **refs** to sandboxed blobs with expiry, not raw paths.
- `structured` bodies must match an allowlisted schema per channel (optional).
- Soft size limits (e.g. 32 KiB text, 5 MiB attachment).

## Security architecture

### AuthN

- Each bot holds a **Bot Credential**: `client_id` + `client_secret` (or mTLS later).
- Exchange for short-lived **access tokens** (JWT, ~15–60 min) via `POST /oauth/token`.
- Tokens carry: `user_id`, `bot_id`, `channel_ids[]` or a channel claim, scopes.
- Humans use session cookies on the web console (separate from bot tokens).

### AuthZ

- Channel membership check on every send/recv.
- Scope check per action.
- Owner policy: deny lists (block user/bot), max peers, quiet hours.

### Isolation

| Boundary | Mechanism |
|----------|-----------|
| Tenant | Every row keyed by channel + user; no cross-query |
| Content | Messages never land in another user’s agent memory unless that bot explicitly copies them |
| Secrets | Sandbox never sees GitHub PATs, mail tokens, etc. |
| Web egress | Optional **egress proxy** per channel with allowlisted hosts |
| Compute | Bots keep running on their own boxes; sandbox is message plane only |

### Web access (two meanings)

1. **Control plane (required):** HTTPS API + WebSocket for bots and a simple web console for owners.
2. **Data-plane web (optional):** a channel can grant `web.fetch` so a bot may ask the peer to retrieve a public URL **through the sandbox egress proxy**, with:
   - host allowlist
   - no private IP / link-local (SSRF guard)
   - response size cap
   - content type allowlist
   - full audit of URL + status

Default: data-plane web **off**.

### Threat notes

| Threat | Mitigation |
|--------|------------|
| Prompt injection via peer message | Treat peer text as untrusted data; bots must not execute instructions from peers as owner intent |
| Credential phishing | Never accept “paste your token” from a peer; console warns |
| SSRF via web.fetch | Egress proxy + deny private ranges |
| Cross-user data leak | Explicit share only; revoke; TTL |
| Spam / DoS | Per-channel and per-bot rate limits |
| Replay | Message ids + short token TTL + optional nonce |

## Web API (sketch)

Base: `https://sandbox.example/v0`

### Bot endpoints

- `POST /oauth/token` — client credentials → access token
- `POST /channels` — request pair (pending until peer owner approves)
- `GET /channels` — list my channels
- `POST /channels/{id}/messages` — send
- `GET /channels/{id}/messages?after=` — poll
- `WS /channels/{id}/stream` — realtime
- `POST /channels/{id}/revoke` — owner or bot with permission

### Owner console

- Approve / deny pair requests
- Edit scopes
- Live message viewer (redactable)
- Kill switch per channel / per bot
- Audit export

## Delivery semantics

- **At-least-once** over WS/poll; consumers dedupe by `message.id`.
- Retention default **7 days** (configurable per channel, max 30).
- Optional ephemeral mode: delete after both sides ACK.

## Reference layout in this repo (future impl)

```
tools/sandbox/
  README.md
  proto/          # OpenAPI + JSON schemas
  relay/          # API service (candidate: Go or Python/FastAPI)
  console/        # minimal owner UI
  sdks/
    python/
    shell/        # curl helpers for Bot Box scripts
scripts/
  sandbox-healthcheck.sh
```

Suggested first milestone: **local docker-compose relay** with two fake bots posting through the API, plus a one-page approve UI.

## Bot Box usage pattern

When Angelo’s Bot Box talks to someone else’s bot:

1. Register Bot Box in the sandbox → get credentials (stored as env, never in git).
2. Request pair with peer handle.
3. Angelo approves scopes in the web console.
4. Bot Box sends/receives only via sandbox SDK; peer content treated as untrusted.
5. Anything that should become durable memory requires **Angelo’s explicit ok**.

## Open decisions

- Hosted by whom? (self-host vs Cursor-hosted vs Healthy Record infra)
- Handle discovery: public directory vs invite links only (invite links recommended for v0)
- Whether structured RPC (request/response schemas) lands in v0 or v1
- Retention & compliance region

## Success criteria for v0 prototype

- Two bots under two accounts can pair with dual consent.
- Text messages flow over HTTPS + WS.
- Either owner can revoke and traffic stops within seconds.
- Audit log shows who said what, when.
- `web.fetch` disabled by default; if enabled, SSRF tests pass.
- No path by which Bot A can read Bot B’s private connectors.

## Next implementation step

If we proceed: scaffold `tools/sandbox/` with OpenAPI, a minimal FastAPI relay, docker-compose, and two demo bot scripts under `scripts/`.
