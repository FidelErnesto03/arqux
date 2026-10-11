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


def _wait_until_connectable(path, timeout_s: float = 5.0) -> None:
    """Block until the bridge accepts connections, or fail loudly.

    Existence of the socket file is NOT readiness. `UnixStreamServer`
    creates the file in `server_bind()` and only starts listening in
    `server_activate()`, so a client that sees the file can still be
    refused with ECONNREFUSED. Spinning on `path.exists()` therefore made
    this test fail intermittently under CPU load — it reproduced roughly
    1 run in 7 with background load — which is exactly the kind of
    non-determinism a release gate must not carry.
    """
    deadline = time.monotonic() + timeout_s
    last: Exception | None = None
    while time.monotonic() < deadline:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(str(path))
            return
        except OSError as exc:
            last = exc
            time.sleep(0.01)
        finally:
            client.close()
    raise AssertionError(f"bridge socket never became connectable: {path} ({last})")


def test_host_bridge_brokers_current_session_response(tmp_path):
    path = tmp_path / "host.sock"
    thread = threading.Thread(target=serve_host_bridge, args=(path,), daemon=True)
    thread.start()
    _wait_until_connectable(path)

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
        # Teardown must not mask a real failure with a teardown error: the
        # server removes its own socket on exit, so `path.exists()` can be
        # true for a socket nobody is listening on any more.
        try:
            if path.exists():
                _request(path, {"op": "shutdown"})
        except OSError:
            pass
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
