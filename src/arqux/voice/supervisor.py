"""Autonomous conversation loop for the persistent voice daemon."""

from __future__ import annotations

import contextlib
import re
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Any

from .agent_backend import AgentBackend, BackendError, build_backend

_BOUNDARY_RE = re.compile(r"[.!?。！？](?:[\"'»)]*)\s*$")


class ConversationSupervisor:
    """Consume addressed voice turns and speak backend replies autonomously."""

    def __init__(self, meeting: Any):
        self.meeting = meeting
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._backend: AgentBackend | None = None
        self._backend_name = ""
        self._session_id = str(getattr(meeting, "session_id", ""))
        self._arqx_context: dict[str, str] = dict(
            getattr(meeting, "arqx_context", {}) or {})
        self._state = "stopped"
        self._started = 0.0
        self._turns = 0
        self._errors = 0
        self._last_error = ""
        self._last_input = ""
        self._last_output = ""

    def start(self, **options: Any) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            requested_session = str(options.get("session_id") or "")
            if requested_session and requested_session != self._session_id:
                raise BackendError(
                    "la sesión actual de ArqUX ya está vinculada; "
                    "no se permite abrir una sesión de voz paralela"
                )
            self._arqx_context.update({
                key: str(options[key]) for key in (
                    "arqx_session_id", "project", "scope", "blp")
                if options.get(key)
            })
            self.meeting.bind_conversation_session(
                self._session_id, self._arqx_context)
            self._state = "starting"
            self._last_error = ""
            self._stop.clear()
            try:
                self._backend = build_backend(
                    agent=self.meeting.agent, lang=self.meeting.stt.lang, **options)
            except Exception as exc:  # noqa: BLE001
                self._state = "error"
                self._last_error = str(exc)
                raise
            self._backend_name = getattr(self._backend, "name", "backend")
            self._started = time.monotonic()
            self._thread = threading.Thread(
                target=self._run, name="arqux-voice-conversation", daemon=True)
            self._thread.start()
            self._state = "running"
            self.meeting.tx.append(
                "system", f"Supervisor conversacional activado — backend {self._backend_name}.")
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            if not thread or not thread.is_alive():
                self._state = "stopped"
                return self.status()
            self._state = "stopping"
            self._stop.set()
        thread.join(timeout=5)
        with self._lock:
            if thread.is_alive():
                self._state = "stopping"
            else:
                self._state = "stopped"
                self._thread = None
            self.meeting.tx.append("system", "Supervisor conversacional detenido.")
            return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            return {
                "state": self._state,
                "active": bool(thread and thread.is_alive() and self._state == "running"),
                "backend": self._backend_name or None,
                "backend_session_id": getattr(self._backend, "session_id", None),
                "session_id": self._session_id or None,
                "arqx_context": dict(self._arqx_context),
                "uptime_s": round(time.monotonic() - self._started, 1)
                if self._started else 0.0,
                "turns": self._turns,
                "errors": self._errors,
                "last_error": self._last_error or None,
                "last_input": self._last_input or None,
                "last_output": self._last_output or None,
            }

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self.meeting.listen(timeout=1.0)
                if item.get("timeout"):
                    continue
                self._handle_turn(item)
            except Exception as exc:  # noqa: BLE001
                self._record_error(exc)
                self._stop.wait(0.25)
        with self._lock:
            if self._state == "running":
                self._state = "stopped"

    def _handle_turn(self, item: dict[str, Any]) -> None:
        text = str(item.get("text", "")).strip()
        if not text or self._stop.is_set():
            return
        backend = self._backend
        if backend is None:
            raise BackendError("supervisor sin backend")
        history = self.meeting.transcript(tail_n=12)
        with self._lock:
            self._last_input = text
            previous_backend_session = getattr(backend, "session_id", None)
        chunks = backend.stream(text, history)
        output = self._speak_chunks(chunks)
        if not output:
            raise BackendError("el agente devolvió una respuesta vacía")
        self.meeting.record_agent_response(output)
        backend_session = getattr(backend, "session_id", None)
        if backend_session and backend_session != previous_backend_session:
            self.meeting.tx.append(
                "system", f"Backend vinculado a la sesión única: {backend_session}.")
        with self._lock:
            self._turns += 1
            self._last_output = output

    def _speak_chunks(self, chunks: Iterator[str]) -> str:
        session_id = f"voice-{uuid.uuid4().hex}"
        stream_id = session_id
        sequence = 1
        pending = ""
        emitted: list[str] = []

        for raw in chunks:
            if self._stop.is_set():
                break
            pending += str(raw)
            while True:
                cut = self._flush_point(pending)
                if cut <= 0:
                    break
                fragment, pending = pending[:cut].strip(), pending[cut:]
                if fragment:
                    self._say_fragment(session_id, stream_id, sequence, fragment, False)
                    emitted.append(fragment)
                    sequence += 1
        if pending.strip():
            fragment = pending.strip()
            self._say_fragment(session_id, stream_id, sequence, fragment, True)
            emitted.append(fragment)
        elif emitted:
            self._say_fragment(session_id, stream_id, sequence, "", True)
        return " ".join(emitted).strip()

    @staticmethod
    def _flush_point(text: str) -> int:
        if len(text) < 48 and not _BOUNDARY_RE.search(text):
            return 0
        matches = list(re.finditer(r"[.!?。！？](?:[\"'»)]*)\s+", text))
        if matches:
            return matches[-1].end()
        if len(text) >= 96:
            cut = text.rfind(" ", 48, 96)
            return cut + 1 if cut > 0 else 96
        return 0

    def _say_fragment(self, session_id: str, stream_id: str, sequence: int,
                      text: str, final: bool) -> None:
        self.meeting.say_incremental({
            "session_id": session_id, "stream_id": stream_id,
            "sequence": sequence, "text": text, "final": final,
            "_record": False,
        })

    def _record_error(self, exc: Exception) -> None:
        with self._lock:
            self._errors += 1
            self._last_error = str(exc)
        with contextlib.suppress(Exception):
            self.meeting.tx.append("system", f"Supervisor conversacional: {exc}")
            self.meeting.say(
                "No pude procesar ese turno. Revisa el backend de conversación.",
                interrupt=False)
