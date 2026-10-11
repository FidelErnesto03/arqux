"""Tests for the persistent voice daemon IPC boundary."""

import json
import socketserver
import threading

import pytest

pytest.importorskip("faster_whisper")
pytest.importorskip("onnxruntime")
pytest.importorskip("piper")


def test_daemon_client_roundtrip(tmp_path):
    from arqux.voice.daemon_client import VoiceDaemonClient

    path = tmp_path / "voice.sock"

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            request = json.loads(self.rfile.readline())
            response = {"ok": True, "result": {
                "op": request["op"], "args": request["args"]}}
            self.wfile.write((json.dumps(response) + "\n").encode())

    class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True

    server = Server(str(path), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = VoiceDaemonClient(path).request(
            "meeting_listen", timeout_s=1)
        assert result == {"op": "meeting_listen", "args": {"timeout_s": 1}}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_daemon_dispatch_routes_to_persistent_meeting(tmp_path, monkeypatch):
    import arqux.voice.daemon as daemon_mod
    import arqux.voice.transcript as transcript_mod

    monkeypatch.setattr(transcript_mod, "meetings_dir", lambda: tmp_path)

    class FakeMeeting:
        gate = type("Gate", (), {"mode": "always"})()

        def status(self):
            return {"listening": "on"}

        def listen(self, timeout):
            return {"text": "hola", "timeout": timeout}

        def say(self, text, interrupt=False):
            return {"text": text, "interrupt": interrupt}

        def say_incremental(self, args):
            return {"incremental": args["sequence"]}

        def transcript(self, tail_n, since_ts):
            return [{"tail_n": tail_n, "since_ts": since_ts}]

        def note(self, text, kind):
            return {"text": text, "kind": kind}

        def stop(self):
            return {"entries": 1}

        def set_mic(self, mic):
            return {"device": mic}

    state = daemon_mod.VoiceDaemon()
    state.meeting = FakeMeeting()
    assert state.dispatch({"op": "status"})["meeting"] == {
        "listening": "on"}
    assert state.dispatch({"op": "meeting_listen",
                           "args": {"timeout_s": 2}})["text"] == "hola"
    assert state.dispatch({"op": "meeting_say",
                           "args": {"text": "hola"}})["text"] == "hola"
    assert state.dispatch({"op": "meeting_say", "args": {
        "session_id": "s", "sequence": 2}})["incremental"] == 2


def test_daemon_conversation_requires_canonical_bridge():
    import arqux.voice.daemon as daemon_mod

    class FakeMeeting:
        agent = "alfred"
        stt = type("Stt", (), {"lang": "es"})()

        def status(self):
            return {"listening": "on"}

        def stop(self):
            return {"entries": 1}

    state = daemon_mod.VoiceDaemon()
    state.meeting = FakeMeeting()

    assert state.dispatch({"op": "conversation_status"})["active"] is False
    with pytest.raises(RuntimeError, match="BRIDGE_UNAVAILABLE"):
        state.dispatch({"op": "conversation_start", "args": {
            "backend": "echo"}})
