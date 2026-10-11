"""Host adapter contract for the canonical ArqUX conversation.

The adapter is intentionally an interface.  A voice daemon may attach to it,
but it cannot manufacture one.  The real host integration must provide the
currently active ArqUX session and agent response stream.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from ..session_models import BridgeUnavailable, ConversationEvent


class CurrentAgentAdapter(Protocol):
    """Submit a native user turn to the already active host conversation."""

    adapter_id: str

    def submit_input(self, event: ConversationEvent) -> str | Iterable[str]:
        """Return response text or response chunks from the current agent."""

    def status(self) -> dict[str, Any]:
        """Return adapter health without exposing secrets or audio."""


class UnavailableSessionAdapter:
    """Fail-closed adapter used until the host bridge is supplied."""

    adapter_id = "unavailable"

    def submit_input(self, event: ConversationEvent) -> str:
        del event
        raise BridgeUnavailable(
            "current ArqUX host session bridge is unavailable; "
            "voice cannot create a substitute agent session"
        )

    def status(self) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "available": False}
