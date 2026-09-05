from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@dataclass
class User:
    id: str
    handle: str


@dataclass
class Bot:
    id: str
    user_id: str
    handle: str
    display_name: str
    client_id: str
    client_secret: str


@dataclass
class Channel:
    id: str
    bot_a_id: str
    bot_b_id: str
    status: str  # pending | open | revoked
    approvals: dict[str, bool]  # user_id -> approved
    scopes: list[str]
    created_at: float


@dataclass
class Message:
    id: str
    channel_id: str
    from_user_id: str
    from_bot_id: str
    kind: str
    text: str
    correlation_id: str | None
    created_at: float
    ttl_seconds: int
    seq: int


@dataclass
class RateBucket:
    count: int = 0
    window_start: float = field(default_factory=time.time)


class Store:
    def __init__(self) -> None:
        self.lock = Lock()
        self.users_by_handle: dict[str, User] = {}
        self.users: dict[str, User] = {}
        self.bots_by_handle: dict[str, Bot] = {}
        self.bots: dict[str, Bot] = {}
        self.bots_by_client: dict[str, Bot] = {}
        self.channels: dict[str, Channel] = {}
        self.messages: dict[str, list[Message]] = {}
        self.seq = 0
        self.rate: dict[str, RateBucket] = {}

    def get_or_create_user(self, handle: str) -> User:
        h = handle.strip().lower()
        if h in self.users_by_handle:
            return self.users_by_handle[h]
        user = User(id=_id("usr"), handle=h)
        self.users_by_handle[h] = user
        self.users[user.id] = user
        return user

    def register_bot(self, user_handle: str, bot_handle: str, display_name: str | None) -> Bot:
        with self.lock:
            bh = bot_handle.strip().lower()
            if bh in self.bots_by_handle:
                raise ValueError("bot_handle_taken")
            user = self.get_or_create_user(user_handle)
            bot = Bot(
                id=_id("bot"),
                user_id=user.id,
                handle=bh,
                display_name=display_name or bh,
                client_id=_id("cli"),
                client_secret=secrets.token_urlsafe(24),
            )
            self.bots_by_handle[bh] = bot
            self.bots[bot.id] = bot
            self.bots_by_client[bot.client_id] = bot
            return bot

    def create_channel(self, requester: Bot, peer_handle: str) -> Channel:
        with self.lock:
            peer = self.bots_by_handle.get(peer_handle.strip().lower())
            if not peer:
                raise ValueError("peer_not_found")
            if peer.id == requester.id:
                raise ValueError("cannot_pair_self")
            # reuse pending/open pair if exists
            for ch in self.channels.values():
                ids = {ch.bot_a_id, ch.bot_b_id}
                if ids == {requester.id, peer.id} and ch.status != "revoked":
                    return ch
            ch = Channel(
                id=_id("chn"),
                bot_a_id=requester.id,
                bot_b_id=peer.id,
                status="pending",
                approvals={requester.user_id: True, peer.user_id: False},
                scopes=["msg.send", "msg.recv", "meta.presence"],
                created_at=time.time(),
            )
            self.channels[ch.id] = ch
            self.messages[ch.id] = []
            return ch

    def approve(self, channel_id: str, user_id: str, scopes: list[str]) -> Channel:
        with self.lock:
            ch = self.channels.get(channel_id)
            if not ch:
                raise ValueError("channel_not_found")
            if ch.status == "revoked":
                raise ValueError("channel_revoked")
            if user_id not in ch.approvals:
                raise ValueError("not_a_party")
            ch.approvals[user_id] = True
            if scopes:
                # intersection-ish: keep requested if both will agree via last approver
                ch.scopes = scopes
            if all(ch.approvals.values()):
                ch.status = "open"
                # system message
                self._append_unlocked(
                    ch.id,
                    from_user_id="system",
                    from_bot_id="system",
                    kind="system",
                    text="channel open",
                    correlation_id=None,
                    ttl_seconds=86_400,
                )
            return ch

    def revoke(self, channel_id: str, user_id: str) -> Channel:
        with self.lock:
            ch = self.channels.get(channel_id)
            if not ch:
                raise ValueError("channel_not_found")
            if user_id not in ch.approvals:
                raise ValueError("not_a_party")
            ch.status = "revoked"
            self._append_unlocked(
                ch.id,
                from_user_id="system",
                from_bot_id="system",
                kind="system",
                text="channel revoked",
                correlation_id=None,
                ttl_seconds=86_400,
            )
            return ch

    def _append_unlocked(
        self,
        channel_id: str,
        *,
        from_user_id: str,
        from_bot_id: str,
        kind: str,
        text: str,
        correlation_id: str | None,
        ttl_seconds: int,
    ) -> Message:
        self.seq += 1
        msg = Message(
            id=_id("msg"),
            channel_id=channel_id,
            from_user_id=from_user_id,
            from_bot_id=from_bot_id,
            kind=kind,
            text=text,
            correlation_id=correlation_id,
            created_at=time.time(),
            ttl_seconds=ttl_seconds,
            seq=self.seq,
        )
        self.messages.setdefault(channel_id, []).append(msg)
        return msg

    def send_message(
        self,
        channel_id: str,
        bot: Bot,
        text: str,
        correlation_id: str | None,
        ttl_seconds: int,
    ) -> Message:
        with self.lock:
            ch = self.channels.get(channel_id)
            if not ch:
                raise ValueError("channel_not_found")
            if ch.status != "open":
                raise ValueError("channel_not_open")
            if bot.id not in (ch.bot_a_id, ch.bot_b_id):
                raise ValueError("not_a_member")
            if "msg.send" not in ch.scopes:
                raise ValueError("missing_scope_msg_send")
            return self._append_unlocked(
                channel_id,
                from_user_id=bot.user_id,
                from_bot_id=bot.id,
                kind="text",
                text=text,
                correlation_id=correlation_id,
                ttl_seconds=ttl_seconds,
            )

    def list_messages(self, channel_id: str, after_seq: int = 0) -> list[Message]:
        with self.lock:
            now = time.time()
            out = []
            for m in self.messages.get(channel_id, []):
                if m.seq <= after_seq:
                    continue
                if now - m.created_at > m.ttl_seconds:
                    continue
                out.append(m)
            return out

    def channels_for_bot(self, bot_id: str) -> list[Channel]:
        with self.lock:
            return [
                c
                for c in self.channels.values()
                if bot_id in (c.bot_a_id, c.bot_b_id)
            ]

    def check_rate(self, key: str, limit: int = 60, window: float = 60.0) -> bool:
        with self.lock:
            now = time.time()
            b = self.rate.get(key)
            if not b or now - b.window_start >= window:
                self.rate[key] = RateBucket(count=1, window_start=now)
                return True
            if b.count >= limit:
                return False
            b.count += 1
            return True


STORE = Store()
