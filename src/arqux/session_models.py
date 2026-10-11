"""Canonical multimodal session contracts for ArqUX.

The voice process is deliberately not a conversation owner.  These small,
serialisable models are shared by the canonical session bus and the voice
bridge so text and speech can be correlated without introducing a second
agent conversation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

Modality = Literal["text", "voice"]
Direction = Literal["input", "output", "system"]
SessionStatus = Literal["detached", "attached", "stopping", "closed"]


class SessionError(RuntimeError):
    """Base class for canonical session failures."""


class NoActiveSession(SessionError):
    """No canonical ArqUX session is registered."""


class SessionMismatch(SessionError):
    """An event or lease does not belong to the active session."""


class LeaseExpired(SessionError):
    """The voice/session bridge lease is missing or expired."""


class SequenceConflict(SessionError):
    """An event would violate the canonical sequence."""


class DuplicateEvent(SessionError):
    """An event or idempotency key was already accepted."""


class BridgeUnavailable(SessionError):
    """The host adapter is not attached; fail closed."""


def opaque_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


@dataclass(frozen=True)
class BridgeLease:
    nonce: str
    owner: str
    expires_at: float

    @classmethod
    def create(
        cls, owner: str, ttl_s: float = 30.0, now: float | None = None
    ) -> BridgeLease:
        return cls(opaque_id("lease"), owner, (now if now is not None else time.time()) + ttl_s)

    def valid(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "nonce": self.nonce,
            "owner": self.owner,
            "expires_at": self.expires_at,
        }


@dataclass
class ConversationSession:
    conversation_session_id: str
    parent_arqx_session_id: str
    active_agent_id: str
    project: str
    scope: str
    blp: str | None = None
    owner_handler: str = "host-adapter"
    status: SessionStatus = "detached"
    next_sequence: int = 1
    active_modalities: set[Modality] = field(default_factory=lambda: {"text"})
    bridge_lease: BridgeLease | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_session_id": self.conversation_session_id,
            "parent_arqx_session_id": self.parent_arqx_session_id,
            "active_agent_id": self.active_agent_id,
            "project": self.project,
            "scope": self.scope,
            "blp": self.blp,
            "owner_handler": self.owner_handler,
            "status": self.status,
            "next_sequence": self.next_sequence,
            "active_modalities": sorted(self.active_modalities),
            "bridge_lease": self.bridge_lease.to_dict()
            if self.bridge_lease else None,
        }


@dataclass(frozen=True)
class ConversationEvent:
    event_id: str
    conversation_session_id: str
    turn_id: str
    sequence: int
    direction: Direction
    modality: Modality
    origin: str
    text: str
    ts: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        turn_id: str,
        sequence: int,
        direction: Direction,
        modality: Modality,
        origin: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        return cls(
            event_id=opaque_id("evt"),
            conversation_session_id=session_id,
            turn_id=turn_id,
            sequence=sequence,
            direction=direction,
            modality=modality,
            origin=origin,
            text=text,
            ts=time.time(),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "conversation_session_id": self.conversation_session_id,
            "turn_id": self.turn_id,
            "sequence": self.sequence,
            "direction": self.direction,
            "modality": self.modality,
            "origin": self.origin,
            "text": self.text,
            "ts": self.ts,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Projection:
    event_id: str
    channel: Literal["chat", "voice"]
    status: Literal["queued", "speaking", "written", "cancelled"]

    def to_dict(self) -> dict[str, str]:
        return {
            "event_id": self.event_id,
            "channel": self.channel,
            "status": self.status,
        }
