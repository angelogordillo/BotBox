from __future__ import annotations

import os
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .store import STORE, Bot

SECRET = os.environ.get("SANDBOX_SECRET", "dev-sandbox-secret-not-for-prod")
TTL = int(os.environ.get("SANDBOX_TOKEN_TTL_SECONDS", "3600"))
bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    bot: Bot
    user_id: str
    bot_id: str


def issue_token(bot: Bot) -> tuple[str, int]:
    now = int(time.time())
    payload = {
        "sub": bot.id,
        "uid": bot.user_id,
        "cid": bot.client_id,
        "iat": now,
        "exp": now + TTL,
        "iss": "botbox-sandbox",
    }
    return jwt.encode(payload, SECRET, algorithm="HS256"), TTL


def require_bot(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"], issuer="botbox-sandbox")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"invalid_token:{e}") from e
    bot = STORE.bots.get(payload.get("sub", ""))
    if not bot or bot.user_id != payload.get("uid"):
        raise HTTPException(status_code=401, detail="unknown_bot")
    return Principal(bot=bot, user_id=bot.user_id, bot_id=bot.id)
