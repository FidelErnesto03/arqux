from __future__ import annotations

import json
import socket
import threading
import time

from arqux.host_bridge import HostSessionBridge, serve_host_bridge
from arqux.session_models import ConversationEvent
from arqux.voice.host_adapter import SocketCurrentAgentAdapter


def _request(path, payload):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(path))
        client.sendall((json.dumps(payload) + "\n").encode())
        raw = b""
        while not raw.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk:
                break
            raw += chunk
        return json.loads(raw.decode())
    finally:
        client.close()


def _session():
    return {
        "conversation_session_id": "chat-1",
        "parent_arqx_session_id": "E-1",
        "active_agent_id": "alfred",
        "project": "ARQUX",
        "scope": "CYCLE-12",
    }


def test_host_bridge_brokers_current_session_response(tmp_path):
    path = tmp_path / "host.sock"
    thread = threading.Thread(target=serve_host_bridge, args=(path,), daemon=True)
    thread.start()
    deadline = time.monotonic() + 2
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)

    try:
        registered = _request(path, {"op": "register_session", "session": _session()})
        assert registered["ok"] is True

        adapter = SocketCurrentAgentAdapter(path, timeout_s=2)
        event = ConversationEvent.create(
            session_id="chat-1", turn_id="turn-1", sequence=1,
            direction="input", modality="voice", origin="architect", text="hola",
        )
        result: list[str] = []
        failure: list[Exception] = []

        def submit():
            try:
                result.extend(adapter.submit_input(event))
            except Exception as exc:  # pragma: no cover - diagnostic
                failure.append(exc)

        submit_thread = threading.Thread(target=submit)
        submit_thread.start()
        request = _request(path, {"op": "poll", "timeout_s": 2})
        assert request["ok"] is True
        assert request["result"]["event"]["text"] == "hola"
        _request(path, {
            "op": "complete", "request_id": request["result"]["request_id"],
            "chunks": ["respuesta del agente activo"],
        })
        submit_thread.join(timeout=2)

        assert not failure
        assert result == ["respuesta del agente activo"]
        assert adapter.status()["active_agent_id"] == "alfred"
    finally:
        if path.exists():
            _request(path, {"op": "shutdown"})
        thread.join(timeout=2)


def test_host_bridge_rejects_second_session():
    bridge = HostSessionBridge()
    bridge.register_session(_session())
    other = dict(_session(), conversation_session_id="chat-2")
    try:
        bridge.register_session(other)
    except Exception as exc:
        assert "different host session" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("second host session must be rejected")
