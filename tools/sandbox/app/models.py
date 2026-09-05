from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Scope(str, Enum):
    MSG_SEND = "msg.send"
    MSG_RECV = "msg.recv"
    META_PRESENCE = "meta.presence"


DEFAULT_SCOPES = [Scope.MSG_SEND, Scope.MSG_RECV, Scope.META_PRESENCE]


class RegisterBotRequest(BaseModel):
    user_handle: str = Field(min_length=1, max_length=64)
    bot_handle: str = Field(min_length=1, max_length=64)
    display_name: str | None = None


class RegisterBotResponse(BaseModel):
    user_id: str
    bot_id: str
    bot_handle: str
    client_id: str
    client_secret: str


class TokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    bot_id: str
    user_id: str


class CreateChannelRequest(BaseModel):
    peer_bot_handle: str


class ApproveChannelRequest(BaseModel):
    scopes: list[Scope] = Field(default_factory=lambda: list(DEFAULT_SCOPES))


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=32_768)
    correlation_id: str | None = None
    ttl_seconds: int = Field(default=86_400, ge=60, le=2_592_000)


class MessageOut(BaseModel):
    id: str
    channel_id: str
    from_user_id: str
    from_bot_id: str
    from_bot_handle: str
    kind: str = "text"
    text: str
    correlation_id: str | None = None
    created_at: str
    ttl_seconds: int


class ChannelOut(BaseModel):
    id: str
    status: str
    bot_a_id: str
    bot_b_id: str
    bot_a_handle: str
    bot_b_handle: str
    approvals: dict[str, bool]
    scopes: list[str]
    created_at: str


class HealthOut(BaseModel):
    status: str
    version: str
    web_fetch: str = "disabled"


class ErrorOut(BaseModel):
    detail: str
    code: str | None = None
