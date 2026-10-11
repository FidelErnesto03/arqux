from __future__ import annotations

import json
import socketserver
import threading

from arqux.session_models import ConversationEvent
from arqux.voice.host_adapter import SocketCurrentAgentAdapter


def test_socket_current_agent_adapter_forwards_canonical_event(tmp_path):
    path = tmp_path / "host.sock"
    received = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            request = json.loads(self.rfile.readline())
            received.append(request)
            if request["op"] == "status":
                result = {"session_id": "chat-1"}
            else:
                result = {"chunks": ["respuesta del agente actual"]}
            self.wfile.write((json.dumps({"ok": True, "result": result}) + "\n").encode())

    class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True

    server = Server(str(path), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        adapter = SocketCurrentAgentAdapter(path)
        event = ConversationEvent.create(
            session_id="chat-1", turn_id="turn-1", sequence=1,
            direction="input", modality="voice", origin="architect",
            text="hola",
        )
        assert adapter.submit_input(event) == ["respuesta del agente actual"]
        assert adapter.status()["session_id"] == "chat-1"
        assert received[0]["op"] == "submit_input"
        assert received[0]["event"]["conversation_session_id"] == "chat-1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
