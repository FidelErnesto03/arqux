"""Client for the optional persistent arqux-voice daemon.

The daemon owns PipeWire capture independently from an MCP stdio process.
This module is deliberately stdlib-only so the MCP server can fall back to
its in-process runtime when no daemon has been started.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any


class DaemonUnavailable(RuntimeError):
    """The persistent voice daemon is not reachable."""


class DaemonRequestError(RuntimeError):
    """The daemon received a request but could not execute it."""


def _runtime_dir() -> Path:
    configured = os.environ.get("XDG_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return Path.home() / ".cache" / "arqux" / "voice"


def socket_path() -> Path:
    configured = os.environ.get("ARQUX_VOICE_DAEMON_SOCKET")
    return Path(configured) if configured else _runtime_dir() / "arqux-voice.sock"


def pid_path() -> Path:
    configured = os.environ.get("ARQUX_VOICE_DAEMON_PID")
    return Path(configured) if configured else _runtime_dir() / "arqux-voice.pid"


def log_path() -> Path:
    configured = os.environ.get("ARQUX_VOICE_DAEMON_LOG")
    return Path(configured) if configured else _runtime_dir() / "arqux-voice.log"


class VoiceDaemonClient:
    """Small one-request-per-connection JSONL client."""

    def __init__(self, path: Path | None = None,
                 connect_timeout: float = 0.35):
        self.path = path or socket_path()
        self.connect_timeout = connect_timeout

    def request(self, op: str, timeout: float | None = None,
                **args: Any) -> Any:
        if not self.path.exists():
            raise DaemonUnavailable(f"socket not found: {self.path}")
        request = json.dumps({"op": op, "args": args}, ensure_ascii=False)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        read_timeout = timeout if timeout is not None else self.connect_timeout
        if op in {"meeting_listen", "voice_listen"}:
            read_timeout = max(read_timeout, float(args.get("timeout_s", 20)) + 5)
        elif op in {"meeting_say", "voice_say"}:
            # Piper/Kokoro synthesis and playback are synchronous at the
            # current MCP boundary; do not mistake a normal voice turn for a
            # dead daemon just because the health probe is short.
            read_timeout = max(read_timeout, 150.0)
        try:
            sock.settimeout(read_timeout)
            sock.connect(str(self.path))
            sock.sendall((request + "\n").encode("utf-8"))
            raw = b""
            while not raw.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                raw += chunk
            if not raw:
                raise DaemonUnavailable("daemon closed the connection")
            response = json.loads(raw.decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DaemonUnavailable(str(exc)) from exc
        finally:
            sock.close()
        if not response.get("ok", False):
            raise DaemonRequestError(str(response.get("error", "unknown error")))
        return response.get("result")

    def available(self) -> bool:
        try:
            self.request("status")
        except (DaemonUnavailable, DaemonRequestError):
            return False
        return True


def daemon_mode() -> str:
    """Return ``auto``, ``required`` or ``off`` for MCP routing."""
    value = (os.environ.get("ARQUX_VOICE_DAEMON") or "auto").strip().lower()
    return value if value in {"auto", "required", "off"} else "auto"
