"""Tests for the daemon-owned autonomous conversation loop."""

from __future__ import annotations

import queue
import time
from types import SimpleNamespace

from arqux.voice.agent_backend import BackendConfig, CodexBackend
from arqux.voice.supervisor import ConversationSupervisor


class _Transcript:
    def __init__(self):
        self.entries = []

    def append(self, channel, text):
        item = {"channel": channel, "text": text}
        self.entries.append(item)
        return item

    def tail(self, n=20, since_ts=None):
        del since_ts
        return self.entries[-n:]


class _Stt:
    lang = "es"


class _Meeting:
    agent = "alfred"
    stt = _Stt()

    def __init__(self):
        self.tx = _Transcript()
        self.incoming = queue.Queue()
        self.fragments = []
        self.responses = []
        self.session_id = "voice-test-session"
        self.arqx_context = {}

    def bind_conversation_session(self, session_id, arqx_context=None):
        assert session_id == self.session_id
        self.arqx_context.update(arqx_context or {})
        return {"session_id": session_id, "arqx_context": self.arqx_context}

    def listen(self, timeout=1.0):
        try:
            return self.incoming.get(timeout=timeout)
        except queue.Empty:
            return {"timeout": True}

    def transcript(self, tail_n=12):
        return self.tx.tail(tail_n)

    def say_incremental(self, fragment):
        self.fragments.append(fragment)
        return {"spoken": bool(fragment["text"])}

    def record_agent_response(self, text):
        self.responses.append(text)
        return self.tx.append("agent", text)

    def say(self, text, interrupt=False):
        del interrupt
        return {"spoken": True, "text": text}


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_supervisor_requires_explicit_start_and_answers_with_echo():
    meeting = _Meeting()
    supervisor = ConversationSupervisor(meeting)

    assert supervisor.status()["active"] is False
    started = supervisor.start(backend="echo")
    assert started["active"] is True
    assert supervisor.start(backend="echo")["session_id"] == "voice-test-session"

    meeting.incoming.put({"text": "hola Alfred"})
    assert _wait_for(lambda: len(meeting.responses) == 1)
    assert meeting.responses == ["Te escuché decir: hola Alfred"]
    assert supervisor.status()["turns"] == 1
    assert any(fragment["final"] for fragment in meeting.fragments)

    stopped = supervisor.stop()
    assert stopped["active"] is False
    assert stopped["state"] == "stopped"


def test_supervisor_does_not_start_without_backend():
    meeting = _Meeting()
    supervisor = ConversationSupervisor(meeting)

    try:
        supervisor.start(backend="none")
    except RuntimeError as exc:
        assert "no hay backend" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("backend none must reject activation")
    assert supervisor.status()["state"] == "error"


def test_codex_backend_reuses_one_thread_id(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        thread_id = "thread-1"
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=(
                f'{{"type":"thread.started","thread_id":"{thread_id}"}}\n'
                '{"type":"item.completed","item":{"type":"agent_message",'
                '"text":"respuesta"}}\n'
            ),
        )

    import arqux.voice.agent_backend as backend_mod
    monkeypatch.setattr(backend_mod.shutil, "which", lambda name: "/bin/codex")
    monkeypatch.setattr(backend_mod.subprocess, "run", fake_run)
    backend = CodexBackend(BackendConfig(name="codex", command=()))

    assert list(backend.stream("uno", [])) == ["respuesta"]
    assert list(backend.stream("dos", [])) == ["respuesta"]
    assert calls[0][1:3] == ["exec", "--json"]
    assert calls[1][1:4] == ["exec", "resume", "thread-1"]
