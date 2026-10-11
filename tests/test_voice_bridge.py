from __future__ import annotations

import pytest

from arqux.session_bus import CanonicalEventLog, SessionBus
from arqux.session_models import BridgeUnavailable, ConversationEvent
from arqux.voice.session_bridge import VoiceSessionBridge


class Adapter:
    adapter_id = "current-session"

    def submit_input(self, event: ConversationEvent) -> list[str]:
        return [f"respuesta actual: {event.text}"]

    def status(self) -> dict:
        return {"adapter_id": self.adapter_id, "available": True}


def make_bridge(tmp_path, adapter=None):
    bus = SessionBus(event_log=CanonicalEventLog(tmp_path / "events.jsonl"))
    bus.register_current_session(
        conversation_session_id="chat-1", parent_arqx_session_id="E-1",
        active_agent_id="heimdall", project="ARQUX", scope="CYCLE-12",
        blp="BLP-019", adapter=adapter,
    )
    bridge = VoiceSessionBridge(bus)
    bridge.attach("chat-1")
    return bridge, bus


def test_voice_is_a_projection_of_current_agent_output(tmp_path):
    bridge, bus = make_bridge(tmp_path, Adapter())
    spoken: list[ConversationEvent] = []
    bridge.set_tts_projection(spoken.append)

    events = bridge.submit_voice("buen día")

    assert events[0].modality == "voice"
    assert events[1].direction == "output"
    assert events[1].origin == "heimdall"
    assert spoken[0].event_id == events[1].event_id
    assert bus.event_log.events("chat-1") == events


def test_bridge_without_host_adapter_fails_closed(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    with pytest.raises(BridgeUnavailable):
        bridge.submit_voice("no backend")
