"""On-demand persistent voice daemon.

``arqux voice-daemon start`` owns the local Meeting and PipeWire capture in a
detached process. MCP stdio processes can restart or disappear without
silencing the microphone; they reconnect through the local JSONL socket.
The audio runtime remains independent from MCP. A canonical conversation
requires an explicit host session bridge; the daemon never invokes an agent
backend itself.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time
from typing import Any

from ..session_bus import CanonicalEventLog, SessionBus
from ..session_models import BridgeUnavailable
from .daemon_client import (
    DaemonRequestError,
    DaemonUnavailable,
    VoiceDaemonClient,
    log_path,
    pid_path,
    socket_path,
)
from .host_adapter import SocketCurrentAgentAdapter
from .meeting import Meeting
from .session_bridge import VoiceSessionBridge
from .session_runtime import VoiceSessionRuntime


class _UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, path: str, state: VoiceDaemon):
        self.state = state
        super().__init__(path, _RequestHandler)


class _RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(1024 * 1024)
        if not raw:
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            result = self.server.state.dispatch(request)  # type: ignore[attr-defined]
            response = {"ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001
            response = {"ok": False, "error": repr(exc)}
        self.wfile.write((json.dumps(response, ensure_ascii=False,
                                     default=str) + "\n").encode("utf-8"))


class VoiceDaemon:
    """Own one persistent Meeting and expose safe local operations."""

    def __init__(self, name: str = "arqux-voice-daemon", mode: str = "solo",
                 agent: str = "alfred", lang: str = "es",
                 mic: str | None = None):
        self.name = name
        self.mode = mode
        self.agent = agent
        self.lang = lang
        self.mic = mic
        self.meeting: Meeting | None = None
        self.session_bus: SessionBus | None = None
        self.voice_bridge: VoiceSessionBridge | None = None
        self.voice_runtime: VoiceSessionRuntime | None = None
        self._lock = threading.RLock()
        self.stop_event = threading.Event()

    def start_meeting(self, **overrides: Any) -> dict[str, Any]:
        with self._lock:
            if self.meeting is not None:
                raise RuntimeError("meeting already active")
            meeting = Meeting(
                name=str(overrides.get("name", self.name)),
                mode=str(overrides.get("mode", self.mode)),
                agent=str(overrides.get("agent", self.agent)),
                lang=str(overrides.get("lang", self.lang)),
                announce=overrides.get("announce"),
                mention_patterns=overrides.get("mention_patterns"),
                whisper_model=str(overrides.get("whisper_model", "auto")),
                voice=overrides.get("voice"),
                mic=overrides.get("mic", self.mic),
                session_id=overrides.get("session_id"),
                arqx_context=overrides.get("arqx_context"),
            )
            self.meeting = meeting
            try:
                return meeting.start()
            except Exception:
                self.meeting = None
                raise

    def stop_meeting(self) -> dict[str, Any]:
        if self.voice_runtime is not None:
            self.voice_runtime.stop()
            self.voice_runtime = None
            self.voice_bridge = None
            self.session_bus = None
        with self._lock:
            meeting = self.meeting
            self.meeting = None
        if meeting is None:
            return {"stopped": False, "reason": "no active meeting"}
        return {"stopped": True, **meeting.stop()}

    def dispatch(self, request: dict[str, Any]) -> Any:
        op = str(request.get("op", ""))
        args = request.get("args") or {}
        if op == "status":
            with self._lock:
                meeting = self.meeting
                runtime = self.voice_runtime
            return {
                "daemon": "running",
                "pid": os.getpid(),
                "socket": str(socket_path()),
                "meeting": meeting.status() if meeting else None,
                "conversation": runtime.status() if runtime else {
                    "state": "stopped", "active": False},
            }
        if op == "meeting_status":
            with self._lock:
                meeting = self.meeting
            if meeting is None:
                raise RuntimeError(
                    "no active meeting — start the daemon meeting first")
            return meeting.status()
        if op == "meeting_start":
            return self.start_meeting(**args)
        if op == "meeting_stop":
            return self.stop_meeting()
        if op == "conversation_start":
            with self._lock:
                meeting = self.meeting
                if meeting is None:
                    raise RuntimeError(
                        "no active meeting — start the daemon meeting first")
                if self.voice_runtime is not None:
                    current = self.voice_runtime.status()
                    if current.get("active"):
                        return current
                    self.voice_runtime = None
                    self.voice_bridge = None
                    self.session_bus = None
            return self._start_canonical_conversation(**args)
        if op == "conversation_stop":
            with self._lock:
                runtime = self.voice_runtime
            if runtime is not None:
                result = runtime.stop()
                with self._lock:
                    self.voice_runtime = None
                    self.voice_bridge = None
                    self.session_bus = None
                return result
            return {"state": "stopped", "active": False}
        if op == "conversation_status":
            with self._lock:
                runtime = self.voice_runtime
            return runtime.status() if runtime else {
                "state": "stopped", "active": False}
        if op == "shutdown":
            self.stop_event.set()
            return {"stopping": True}

        with self._lock:
            meeting = self.meeting
        if meeting is None:
            raise RuntimeError("no active meeting — start the daemon meeting first")
        if op in {"meeting_listen", "voice_listen"}:
            return meeting.listen(float(args.get("timeout_s", 20)))
        if op in {"meeting_say", "voice_say"}:
            if args.get("session_id"):
                return meeting.say_incremental(args)
            return meeting.say(
                str(args["text"]), interrupt=bool(args.get("interrupt", False)))
        if op == "meeting_transcript":
            return meeting.transcript(args.get("tail_n", 20),
                                      args.get("since_ts"))
        if op == "meeting_note":
            return meeting.note(args["text"], args.get("kind", "note"))
        if op == "voice_configure":
            if args.get("mention_patterns"):
                meeting.gate.set_patterns(args["mention_patterns"])
            if args.get("mode"):
                meeting.gate.set_mode(args["mode"])
            out: dict[str, Any] = {"gate_mode": meeting.gate.mode}
            if args.get("mic"):
                out["mic_health"] = meeting.set_mic(args["mic"])
            return out
        raise ValueError(f"unknown daemon operation: {op}")

    def _start_canonical_conversation(self, **args: Any) -> dict[str, Any]:
        """Attach transport to the already active ArqUX session.

        This path intentionally has no model/backend option.  The host bridge
        owns the current agent and is the only component allowed to answer.
        """
        required = (
            "conversation_session_id", "parent_arqx_session_id",
            "project", "scope", "bridge_socket",
        )
        missing = [key for key in required if not args.get(key)]
        if missing:
            raise RuntimeError(
                "BRIDGE_UNAVAILABLE: canonical voice activation requires "
                f"{', '.join(missing)}"
            )
        with self._lock:
            if self.meeting is None:
                raise RuntimeError("no active meeting")
            adapter = SocketCurrentAgentAdapter(
                args["bridge_socket"], timeout_s=float(args.get("timeout_s", 90)))
            host_status = adapter.status()
            if not host_status.get("available"):
                raise BridgeUnavailable(
                    "host bridge status is unavailable; refusing voice attach")
            for key in ("conversation_session_id", "parent_arqx_session_id",
                        "project", "scope"):
                host_value = host_status.get(key)
                if host_value is not None and str(host_value) != str(args[key]):
                    raise RuntimeError(f"SESSION_MISMATCH: host {key} differs")
            agent_id = str(host_status.get("active_agent_id") or "")
            if not agent_id:
                raise BridgeUnavailable(
                    "host bridge did not resolve active_agent_id")
            bus = SessionBus(
                event_log=CanonicalEventLog(args.get("event_log")),
                lease_ttl_s=float(args.get("lease_ttl_s", 30)),
            )
            bus.register_current_session(
                conversation_session_id=str(args["conversation_session_id"]),
                parent_arqx_session_id=str(args["parent_arqx_session_id"]),
                active_agent_id=agent_id,
                project=str(args["project"]),
                scope=str(args["scope"]),
                blp=str(args.get("blp")) if args.get("blp") else None,
                owner_handler=str(args.get("owner_handler", "host-adapter")),
                adapter=adapter,
            )
            bridge = VoiceSessionBridge(bus)
            bridge.attach(str(args["conversation_session_id"]))
            runtime = VoiceSessionRuntime(self.meeting, bus, bridge)
            bridge.set_tts_projection(runtime.speak_output)
            try:
                self.meeting.bind_conversation_session(
                    str(args["conversation_session_id"]),
                    {
                        "arqx_session_id": str(args["parent_arqx_session_id"]),
                        "project": str(args["project"]),
                        "scope": str(args["scope"]),
                        "blp": str(args.get("blp", "")),
                    },
                )
            except Exception:
                bridge.detach()
                raise
            self.session_bus = bus
            self.voice_bridge = bridge
            self.voice_runtime = runtime
        return runtime.start()

    def close(self) -> None:
        self.stop_meeting()


def _write_pid() -> None:
    path = pid_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="ascii")


def run_foreground(name: str = "arqux-voice-daemon", mode: str = "solo",
                   agent: str = "alfred", lang: str = "es",
                   mic: str | None = None) -> int:
    path = socket_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if VoiceDaemonClient(path).available():
            raise RuntimeError(f"voice daemon already running at {path}")
        path.unlink()
    state = VoiceDaemon(name=name, mode=mode, agent=agent, lang=lang, mic=mic)
    server = _UnixServer(str(path), state)
    os.chmod(path, 0o600)
    _write_pid()

    def stop(_signum: int, _frame: Any) -> None:
        state.stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        state.start_meeting()
        server.timeout = 0.5
        while not state.stop_event.is_set():
            server.handle_request()
    finally:
        state.close()
        server.server_close()
        for candidate in (path, pid_path()):
            with contextlib.suppress(FileNotFoundError):
                candidate.unlink()
    return 0


def start_daemon(name: str = "arqux-voice-daemon", mode: str = "solo",
                 agent: str = "alfred", lang: str = "es",
                 mic: str | None = None, foreground: bool = False) -> dict[str, Any]:
    if foreground:
        run_foreground(name=name, mode=mode, agent=agent, lang=lang, mic=mic)
        return {"running": False}
    client = VoiceDaemonClient()
    if client.available():
        return client.request("status")
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "arqux.voice.daemon", "--foreground",
               "--name", name, "--mode", mode, "--agent", agent,
               "--lang", lang]
    if mic:
        command.extend(["--mic", mic])
    with path.open("a", encoding="utf-8") as log:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                         stderr=log, start_new_session=True,
                         close_fds=True)
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if client.available():
            return client.request("status")
        time.sleep(0.1)
    raise RuntimeError(f"voice daemon did not become ready; see {path}")


def stop_daemon() -> dict[str, Any]:
    client = VoiceDaemonClient()
    try:
        result = client.request("shutdown", timeout=2.0)
    except DaemonUnavailable:
        return {"running": False, "stopped": False}
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and client.available():
        time.sleep(0.1)
    return {"running": False, **result}


def daemon_status() -> dict[str, Any]:
    client = VoiceDaemonClient()
    try:
        return client.request("status")
    except (DaemonUnavailable, DaemonRequestError):
        return {"daemon": "stopped", "socket": str(socket_path())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="arqux-voice persistent daemon")
    parser.add_argument("--foreground", action="store_true")
    parser.add_argument("--name", default="arqux-voice-daemon")
    parser.add_argument("--mode", choices=("solo", "meet"), default="solo")
    parser.add_argument("--agent", default="alfred")
    parser.add_argument("--lang", default="es")
    parser.add_argument("--mic", default=None)
    args = parser.parse_args(argv)
    return run_foreground(name=args.name, mode=args.mode, agent=args.agent,
                          lang=args.lang, mic=args.mic)


if __name__ == "__main__":
    raise SystemExit(main())
