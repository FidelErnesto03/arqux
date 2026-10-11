from __future__ import annotations

import threading

import pytest

from arqux.session_bus import CanonicalEventLog, SessionBus
from arqux.session_models import (
    BridgeUnavailable,
    ConversationEvent,
    LeaseExpired,
    SessionMismatch,
)


class Adapter:
    adapter_id = "test-host"

    def __init__(self):
        self.inputs: list[ConversationEvent] = []

    def submit_input(self, event: ConversationEvent) -> str:
        self.inputs.append(event)
        return f"respuesta: {event.text}"

    def status(self) -> dict:
        return {"adapter_id": self.adapter_id, "available": True}


def _bus(tmp_path, adapter=None):
    bus = SessionBus(event_log=CanonicalEventLog(tmp_path / "events.jsonl"))
    bus.register_current_session(
        conversation_session_id="chat-1",
        parent_arqx_session_id="E-1",
        active_agent_id="alfred",
        project="ARQUX",
        scope="CYCLE-12",
        blp="BLP-019",
        adapter=adapter,
    )
    state = bus.attach_voice("chat-1", "voice")
    return bus, state["session"]["bridge_lease"]["nonce"]


def test_single_session_orders_input_and_output(tmp_path):
    adapter = Adapter()
    bus, nonce = _bus(tmp_path, adapter)

    events = bus.submit_input(
        "hola", modality="voice", origin="architect",
        session_id="chat-1", lease_nonce=nonce,
    )

    assert [event.sequence for event in events] == [1, 2]
    assert [event.direction for event in events] == ["input", "output"]
    assert adapter.inputs[0].conversation_session_id == "chat-1"
    assert bus.status()["session"]["active_agent_id"] == "alfred"


def test_same_owner_attach_is_idempotent(tmp_path):
    bus = SessionBus(event_log=CanonicalEventLog(tmp_path / "events.jsonl"))
    bus.register_current_session(
        conversation_session_id="chat-1", parent_arqx_session_id="E-1",
        active_agent_id="alfred", project="ARQUX", scope="CYCLE-12",
        adapter=Adapter(),
    )
    first = bus.attach_voice("chat-1", "voice")
    second = bus.attach_voice("chat-1", "voice")

    assert first["session"]["bridge_lease"] == second["session"]["bridge_lease"]


def test_conflicting_session_and_missing_adapter_fail_closed(tmp_path):
    bus = SessionBus(event_log=CanonicalEventLog(tmp_path / "events.jsonl"))
    bus.register_current_session(
        conversation_session_id="chat-1", parent_arqx_session_id="E-1",
        active_agent_id="alfred", project="ARQUX", scope="CYCLE-12",
    )
    with pytest.raises(SessionMismatch):
        bus.register_current_session(
            conversation_session_id="chat-2", parent_arqx_session_id="E-2",
            active_agent_id="alfred", project="ARQUX", scope="CYCLE-12",
        )
    state = bus.attach_voice("chat-1", "voice")
    with pytest.raises(BridgeUnavailable):
        bus.submit_input(
            "hola", modality="voice", origin="architect",
            session_id="chat-1",
            lease_nonce=state["session"]["bridge_lease"]["nonce"],
        )


def test_expired_lease_is_rejected(tmp_path):
    now = [100.0]
    bus = SessionBus(
        event_log=CanonicalEventLog(tmp_path / "events.jsonl"),
        clock=lambda: now[0],
    )
    bus.register_current_session(
        conversation_session_id="chat-1", parent_arqx_session_id="E-1",
        active_agent_id="alfred", project="ARQUX", scope="CYCLE-12",
        adapter=Adapter(),
    )
    state = bus.attach_voice("chat-1", "voice")
    nonce = state["session"]["bridge_lease"]["nonce"]
    now[0] = 131.0
    with pytest.raises(LeaseExpired):
        bus.submit_input(
            "hola", modality="voice", origin="architect",
            session_id="chat-1", lease_nonce=nonce,
        )


def test_persistent_event_log_replays_after_reopen(tmp_path):
    adapter = Adapter()
    bus, nonce = _bus(tmp_path, adapter)
    bus.submit_input(
        "uno", modality="voice", origin="architect",
        session_id="chat-1", lease_nonce=nonce,
    )

    reopened = CanonicalEventLog(tmp_path / "events.jsonl")
    assert [event.sequence for event in reopened.events("chat-1")] == [1, 2]


def test_recovered_bus_continues_sequence_and_deduplicates_retry(tmp_path):
    path = tmp_path / "events.jsonl"
    first = SessionBus(event_log=CanonicalEventLog(path))
    adapter = Adapter()
    first.register_current_session(
        conversation_session_id="chat-1", parent_arqx_session_id="E-1",
        active_agent_id="alfred", project="ARQUX", scope="CYCLE-12",
        adapter=adapter,
    )
    nonce = first.attach_voice("chat-1", "voice")["session"]["bridge_lease"]["nonce"]
    first.submit_input(
        "uno", modality="voice", origin="architect", session_id="chat-1",
        lease_nonce=nonce, metadata={"idempotency_key": "turn-1"},
    )

    second = SessionBus(event_log=CanonicalEventLog(path))
    second.register_current_session(
        conversation_session_id="chat-1", parent_arqx_session_id="E-1",
        active_agent_id="alfred", project="ARQUX", scope="CYCLE-12",
        adapter=adapter,
    )
    nonce = second.attach_voice("chat-1", "voice")["session"]["bridge_lease"]["nonce"]
    retried = second.submit_input(
        "uno", modality="voice", origin="architect", session_id="chat-1",
        lease_nonce=nonce, metadata={"idempotency_key": "turn-1"},
    )
    next_events = second.submit_input(
        "dos", modality="voice", origin="architect", session_id="chat-1",
        lease_nonce=nonce,
    )

    assert [event.sequence for event in retried] == [1, 2]
    assert [event.sequence for event in next_events] == [3, 4]


def test_turn_lock_serializes_concurrent_inputs(tmp_path):
    adapter = Adapter()
    bus, nonce = _bus(tmp_path, adapter)
    results: list[list[ConversationEvent]] = []

    def send(text: str):
        results.append(bus.submit_input(
            text, modality="voice", origin="architect",
            session_id="chat-1", lease_nonce=nonce,
        ))

    threads = [threading.Thread(target=send, args=(str(i),)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sequences = sorted(event.sequence for result in results for event in result)
    assert sequences == list(range(1, 9))
