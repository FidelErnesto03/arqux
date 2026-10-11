"""Transport-to-canonical-session bridge for arqux-voice."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..session_bus import SessionBus
from ..session_models import ConversationEvent


class VoiceSessionBridge:
    """Translate voice transport events into the active ArqUX session."""

    def __init__(self, bus: SessionBus, *, owner: str = "arqux-voice"):
        self.bus = bus
        self.owner = owner
        self._session_id: str | None = None
        self._lease_nonce: str | None = None
        self._tts: Callable[[ConversationEvent], Any] | None = None
        self._attached = False
        self.bus.subscribe(self._on_output)

    def attach(self, session_id: str) -> dict[str, Any]:
        state = self.bus.attach_voice(session_id, self.owner)
        session = self.bus.session
        assert session is not None
        assert session.bridge_lease is not None
        self._session_id = session_id
        self._lease_nonce = session.bridge_lease.nonce
        self._attached = True
        return state

    def detach(self) -> dict[str, Any]:
        if not self._session_id:
            return self.status()
        state = self.bus.detach_voice(self._session_id, self._lease_nonce)
        self._attached = False
        self._lease_nonce = None
        return state

    def submit_voice(self, text: str, *, turn_id: str | None = None,
                     metadata: dict[str, Any] | None = None) -> list[ConversationEvent]:
        if not self._attached or not self._session_id or not self._lease_nonce:
            raise RuntimeError("voice bridge is detached")
        return self.bus.submit_input(
            text,
            modality="voice",
            origin="architect",
            session_id=self._session_id,
            lease_nonce=self._lease_nonce,
            turn_id=turn_id,
            metadata=metadata,
        )

    def set_tts_projection(self, callback: Callable[[ConversationEvent], Any]) -> None:
        self._tts = callback

    def status(self) -> dict[str, Any]:
        status = self.bus.status()
        status.update({
            "owner": self.owner,
            "attached": self._attached,
            "session_id": self._session_id,
            "lease_nonce": self._lease_nonce,
        })
        return status

    def _on_output(self, event: ConversationEvent) -> None:
        if (self._tts and self._attached and event.direction == "output"
                and event.conversation_session_id == self._session_id):
            self._tts(event)
