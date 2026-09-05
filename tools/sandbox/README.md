# Secure Bot Sandbox Relay (v0)

Local prototype of the design in [`docs/secure-bot-sandbox.md`](../../docs/secure-bot-sandbox.md).

Mutual-consent channels between bots of **different users**. Peer message bodies are **untrusted data**. `web.fetch` is **disabled**.

## Quick start

```bash
cd tools/sandbox
docker compose up --build
```

In another terminal (from repo root):

```bash
./scripts/sandbox-healthcheck.sh
./scripts/sandbox-demo.sh
```

Console: http://localhost:8080/

API docs: http://localhost:8080/docs

## Without Docker

```bash
cd tools/sandbox
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SANDBOX_SECRET=dev-sandbox-secret-not-for-prod
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Demo flow

1. Register Alice’s bot and Bob’s bot (different `user_handle`).
2. Alice requests a channel with Bob.
3. Bob approves → channel `open`.
4. Both send text; both poll messages.

## Env

See `.env.example`. Never commit real secrets.
