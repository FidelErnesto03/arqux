"""Canonical text/voice session bus owned by ArqUX.

This module contains no model client and no audio implementation.  It
serialises turns, assigns the only semantic sequence, persists safe event
records, and forwards user turns to the current host adapter.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .handlers.session_adapter import CurrentAgentAdapter
from .session_metrics import SessionLatencyRecorder
from .session_models import (
    BridgeLease,
    BridgeUnavailable,
    ConversationEvent,
    ConversationSession,
    DuplicateEvent,
    LeaseExpired,
    NoActiveSession,
    SequenceConflict,
    SessionMismatch,
    opaque_id,
)


class CanonicalEventLog:
    """Append-only JSONL event store with idempotent replay support."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self._events: list[ConversationEvent] = []
        self._event_ids: set[str] = set()
        self._idempotency_keys: set[str] = set()
        self._lock = threading.RLock()
        if self.path and self.path.exists():
            self._load()

    def _load(self) -> None:
        assert self.path is not None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            event = ConversationEvent(**raw)
            self._events.append(event)
            self._event_ids.add(event.event_id)
            key = event.metadata.get("idempotency_key")
            if key:
                self._idempotency_keys.add(str(key))

    def append(self, event: ConversationEvent) -> ConversationEvent:
        with self._lock:
            if event.event_id in self._event_ids:
                raise DuplicateEvent(event.event_id)
            key = event.metadata.get("idempotency_key")
            if key and str(key) in self._idempotency_keys:
                raise DuplicateEvent(str(key))
            if self._events:
                previous = self._events[-1]
                if event.conversation_session_id == previous.conversation_session_id \
                        and event.sequence != previous.sequence + 1:
                    raise SequenceConflict(
                        f"expected {previous.sequence + 1}, got {event.sequence}"
                    )
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
            self._events.append(event)
            self._event_ids.add(event.event_id)
            if key:
                self._idempotency_keys.add(str(key))
            return event

    def events(self, session_id: str | None = None) -> list[ConversationEvent]:
        with self._lock:
            if session_id is None:
                return list(self._events)
            return [e for e in self._events
                    if e.conversation_session_id == session_id]

    def contains_idempotency(self, key: str) -> bool:
        with self._lock:
            return key in self._idempotency_keys

    def find_idempotency(self, key: str) -> ConversationEvent | None:
        with self._lock:
            for event in self._events:
                if str(event.metadata.get("idempotency_key", "")) == key:
                    return event
        return None


class SessionBus:
    """Single-session registry and ordered event router."""

    def __init__(
        self,
        *,
        event_log: CanonicalEventLog | None = None,
        lease_ttl_s: float = 30.0,
        clock: Callable[[], float] = time.time,
        latency: SessionLatencyRecorder | None = None,
    ):
        self.event_log = event_log or CanonicalEventLog()
        self.lease_ttl_s = lease_ttl_s
        self.clock = clock
        self.latency = latency or SessionLatencyRecorder()
        self._session: ConversationSession | None = None
        self._adapter: CurrentAgentAdapter | None = None
        self._subscribers: list[Callable[[ConversationEvent], None]] = []
        self._state_lock = threading.RLock()
        self._turn_lock = threading.Lock()
        self._dedupe_outputs: dict[str, list[ConversationEvent]] = {}

    @property
    def session(self) -> ConversationSession | None:
        with self._state_lock:
            return self._session

    def register_current_session(
        self,
        *,
        conversation_session_id: str,
        parent_arqx_session_id: str,
        active_agent_id: str,
        project: str,
        scope: str,
        blp: str | None = None,
        owner_handler: str = "host-adapter",
        adapter: CurrentAgentAdapter | None = None,
    ) -> ConversationSession:
        with self._state_lock:
            if self._session and self._session.conversation_session_id != conversation_session_id:
                raise SessionMismatch("a different canonical session is already active")
            if self._session is None:
                self._session = ConversationSession(
                    conversation_session_id=conversation_session_id,
                    parent_arqx_session_id=parent_arqx_session_id,
                    active_agent_id=active_agent_id,
                    project=project,
                    scope=scope,
                    blp=blp,
                    owner_handler=owner_handler,
                )
                previous = self.event_log.events(conversation_session_id)
                if previous:
                    self._session.next_sequence = max(
                        event.sequence for event in previous) + 1
            else:
                current = self._session
                expected = (parent_arqx_session_id, active_agent_id, project, scope, blp)
                actual = (current.parent_arqx_session_id, current.active_agent_id,
                          current.project, current.scope, current.blp)
                if actual != expected:
                    raise SessionMismatch("canonical session metadata changed")
            if adapter is not None:
                self._adapter = adapter
            return self._session

    def register_adapter(self, adapter: CurrentAgentAdapter) -> None:
        with self._state_lock:
            if self._session is None:
                raise NoActiveSession("register the canonical session first")
            self._adapter = adapter

    def subscribe(self, callback: Callable[[ConversationEvent], None]) -> None:
        with self._state_lock:
            self._subscribers.append(callback)

    def attach_voice(self, session_id: str, owner: str) -> dict[str, Any]:
        with self._state_lock:
            session = self._require_session(session_id)
            if session.status == "closed":
                raise SessionMismatch("canonical session is closed")
            if session.bridge_lease and session.bridge_lease.valid(self.clock()):
                if session.bridge_lease.owner != owner:
                    raise SessionMismatch("another voice bridge owns the active lease")
                session.status = "attached"
                session.active_modalities.add("voice")
                return self.status()
            session.bridge_lease = BridgeLease.create(
                owner, self.lease_ttl_s, now=self.clock())
            session.status = "attached"
            session.active_modalities.add("voice")
            return self.status()

    def detach_voice(self, session_id: str, lease_nonce: str | None = None) -> dict[str, Any]:
        with self._state_lock:
            session = self._require_session(session_id)
            if session.bridge_lease and lease_nonce and session.bridge_lease.nonce != lease_nonce:
                raise SessionMismatch("voice lease mismatch")
            session.bridge_lease = None
            session.active_modalities.discard("voice")
            session.status = "detached"
            return self.status()

    def submit_input(
        self,
        text: str,
        *,
        modality: str,
        origin: str,
        session_id: str,
        lease_nonce: str,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[ConversationEvent]:
        if modality not in {"text", "voice"}:
            raise ValueError("modality must be text or voice")
        if not text.strip():
            return []
        with self._turn_lock:
            with self._state_lock:
                session = self._require_session(session_id)
                self._require_lease(session, lease_nonce)
                adapter = self._adapter
                if adapter is None:
                    raise BridgeUnavailable("current host adapter is unavailable")
                turn = turn_id or opaque_id("turn")
                idempotency_key = str((metadata or {}).get("idempotency_key", ""))
                if idempotency_key:
                    existing = self.event_log.find_idempotency(idempotency_key)
                    if existing is not None:
                        outputs = [
                            event for event in self.event_log.events(session_id)
                            if event.metadata.get("input_event_id") == existing.event_id
                        ]
                        return [existing, *outputs]
                event = self._append_event(
                    session,
                    turn_id=turn,
                    direction="input",
                    modality=modality,  # type: ignore[arg-type]
                    origin=origin,
                    text=text,
                    metadata=metadata,
                )
                self.latency.mark(turn, "speech_end" if modality == "voice" else "text_end")
                self.latency.mark(turn, "bus_submit")
            response = adapter.submit_input(event)
            outputs: list[ConversationEvent] = []
            if isinstance(response, str):
                chunks: Iterable[str] = (response,)
            else:
                chunks = response
            for chunk in chunks:
                if chunk:
                    self.latency.mark(turn, "agent_first_token")
                    outputs.append(self.publish_output(
                        str(chunk), turn_id=turn, modality=modality,
                        metadata={"input_event_id": event.event_id},
                    ))
            self._dedupe_outputs[event.event_id] = outputs
            return [event, *outputs]

    def publish_output(
        self,
        text: str,
        *,
        turn_id: str,
        modality: str = "voice",
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        with self._state_lock:
            session = self._require_session(None)
            event = self._append_event(
                session,
                turn_id=turn_id,
                direction="output",
                modality=modality if modality in {"text", "voice"} else "voice",  # type: ignore[arg-type]
                origin=session.active_agent_id,
                text=text,
                metadata=metadata,
            )
            subscribers = list(self._subscribers)
        for callback in subscribers:
            callback(event)
        return event

    def cancel_output(self, turn_id: str, reason: str = "barge-in") -> ConversationEvent:
        return self.publish_output(
            "", turn_id=turn_id, modality="voice",
            metadata={"projection": "voice", "status": "cancelled", "reason": reason},
        )

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "session": self._session.to_dict() if self._session else None,
                "adapter": self._adapter.status() if self._adapter else None,
                "event_count": len(self.event_log.events(
                    self._session.conversation_session_id if self._session else None)),
                "bridge_available": self._adapter is not None,
                "latency": self.latency.report(),
            }

    def _append_event(self, session: ConversationSession, **kwargs: Any) -> ConversationEvent:
        event = ConversationEvent.create(
            session_id=session.conversation_session_id,
            sequence=session.next_sequence,
            **kwargs,
        )
        self.event_log.append(event)
        session.next_sequence += 1
        return event

    def _require_session(self, session_id: str | None) -> ConversationSession:
        session = self._session
        if session is None:
            raise NoActiveSession("no canonical ArqUX session is registered")
        if session_id is not None and session.conversation_session_id != session_id:
            raise SessionMismatch("session id does not match the active session")
        return session

    def _require_lease(self, session: ConversationSession, nonce: str) -> None:
        lease = session.bridge_lease
        if lease is None or lease.nonce != nonce:
            raise LeaseExpired("voice bridge lease is missing or does not match")
        if not lease.valid(self.clock()):
            raise LeaseExpired("voice bridge lease expired")
