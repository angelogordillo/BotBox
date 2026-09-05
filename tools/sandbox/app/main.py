from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import Principal, require_bot, issue_token
from .models import (
    ApproveChannelRequest,
    ChannelOut,
    CreateChannelRequest,
    HealthOut,
    MessageOut,
    RegisterBotRequest,
    RegisterBotResponse,
    SendMessageRequest,
    TokenRequest,
    TokenResponse,
)
from .store import STORE

app = FastAPI(
    title="BotBox Secure Sandbox Relay",
    version="0.1.0",
    description=(
        "Local v0 prototype: mutual-consent channels between bots of different users. "
        "web.fetch is disabled. Peer message bodies are untrusted data."
    ),
)

STATIC = Path(__file__).resolve().parent.parent / "static"
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def _ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def channel_out(ch) -> ChannelOut:
    a = STORE.bots[ch.bot_a_id]
    b = STORE.bots[ch.bot_b_id]
    return ChannelOut(
        id=ch.id,
        status=ch.status,
        bot_a_id=ch.bot_a_id,
        bot_b_id=ch.bot_b_id,
        bot_a_handle=a.handle,
        bot_b_handle=b.handle,
        approvals=dict(ch.approvals),
        scopes=list(ch.scopes),
        created_at=_ts(ch.created_at),
    )


def message_out(m) -> MessageOut:
    handle = "system"
    if m.from_bot_id in STORE.bots:
        handle = STORE.bots[m.from_bot_id].handle
    return MessageOut(
        id=m.id,
        channel_id=m.channel_id,
        from_user_id=m.from_user_id,
        from_bot_id=m.from_bot_id,
        from_bot_handle=handle,
        kind=m.kind,
        text=m.text,
        correlation_id=m.correlation_id,
        created_at=_ts(m.created_at),
        ttl_seconds=m.ttl_seconds,
    )


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/v0/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version="0.1.0", web_fetch="disabled")


@app.post("/v0/bots/register", response_model=RegisterBotResponse)
def register_bot(body: RegisterBotRequest) -> RegisterBotResponse:
    try:
        bot = STORE.register_bot(body.user_handle, body.bot_handle, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return RegisterBotResponse(
        user_id=bot.user_id,
        bot_id=bot.id,
        bot_handle=bot.handle,
        client_id=bot.client_id,
        client_secret=bot.client_secret,
    )


@app.post("/v0/oauth/token", response_model=TokenResponse)
def token(body: TokenRequest) -> TokenResponse:
    if body.grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")
    bot = STORE.bots_by_client.get(body.client_id)
    if not bot or bot.client_secret != body.client_secret:
        raise HTTPException(status_code=401, detail="invalid_client")
    access, ttl = issue_token(bot)
    return TokenResponse(
        access_token=access, expires_in=ttl, bot_id=bot.id, user_id=bot.user_id
    )


@app.post("/v0/channels", response_model=ChannelOut)
def create_channel(
    body: CreateChannelRequest, principal: Principal = Depends(require_bot)
) -> ChannelOut:
    if not STORE.check_rate(f"chcreate:{principal.bot_id}"):
        raise HTTPException(status_code=429, detail="rate_limited")
    try:
        ch = STORE.create_channel(principal.bot, body.peer_bot_handle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return channel_out(ch)


@app.get("/v0/channels", response_model=list[ChannelOut])
def list_channels(principal: Principal = Depends(require_bot)) -> list[ChannelOut]:
    return [channel_out(c) for c in STORE.channels_for_bot(principal.bot_id)]


@app.get("/v0/channels/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel_id: str, principal: Principal = Depends(require_bot)
) -> ChannelOut:
    ch = STORE.channels.get(channel_id)
    if not ch or principal.bot_id not in (ch.bot_a_id, ch.bot_b_id):
        raise HTTPException(status_code=404, detail="channel_not_found")
    return channel_out(ch)


@app.post("/v0/channels/{channel_id}/approve", response_model=ChannelOut)
def approve_channel(
    channel_id: str,
    body: ApproveChannelRequest,
    principal: Principal = Depends(require_bot),
) -> ChannelOut:
    try:
        ch = STORE.approve(
            channel_id, principal.user_id, [s.value for s in body.scopes]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return channel_out(ch)


@app.post("/v0/channels/{channel_id}/revoke", response_model=ChannelOut)
def revoke_channel(
    channel_id: str, principal: Principal = Depends(require_bot)
) -> ChannelOut:
    try:
        ch = STORE.revoke(channel_id, principal.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return channel_out(ch)


@app.post("/v0/channels/{channel_id}/messages", response_model=MessageOut)
def send_message(
    channel_id: str,
    body: SendMessageRequest,
    principal: Principal = Depends(require_bot),
) -> MessageOut:
    if not STORE.check_rate(f"msg:{principal.bot_id}"):
        raise HTTPException(status_code=429, detail="rate_limited")
    try:
        msg = STORE.send_message(
            channel_id,
            principal.bot,
            body.text,
            body.correlation_id,
            body.ttl_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return message_out(msg)


@app.get("/v0/channels/{channel_id}/messages", response_model=list[MessageOut])
def list_messages(
    channel_id: str,
    after: int = Query(0, ge=0),
    principal: Principal = Depends(require_bot),
) -> list[MessageOut]:
    ch = STORE.channels.get(channel_id)
    if not ch or principal.bot_id not in (ch.bot_a_id, ch.bot_b_id):
        raise HTTPException(status_code=404, detail="channel_not_found")
    if ch.status == "open" and "msg.recv" not in ch.scopes:
        raise HTTPException(status_code=403, detail="missing_scope_msg_recv")
    return [message_out(m) for m in STORE.list_messages(channel_id, after_seq=after)]


@app.get("/v0/console/state")
def console_state() -> dict:
    """Owner-facing snapshot for the local console (dev only)."""
    channels = []
    for ch in STORE.channels.values():
        channels.append(channel_out(ch).model_dump())
    bots = [
        {
            "bot_id": b.id,
            "handle": b.handle,
            "user_id": b.user_id,
            "user_handle": STORE.users[b.user_id].handle,
            "display_name": b.display_name,
        }
        for b in STORE.bots.values()
    ]
    return {"bots": bots, "channels": channels}


@app.get("/", response_class=HTMLResponse)
def console() -> str:
    path = STATIC / "console.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "<h1>BotBox Sandbox</h1><p>Console missing.</p>"
