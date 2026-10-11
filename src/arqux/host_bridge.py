"""Host-owned broker for the canonical ArqUX conversation.

The broker is intentionally model-free.  The active ArqUX host registers its
current session and polls input requests; the voice daemon submits events and
waits for the host to return the current agent response.  This keeps the
audio process independent while preserving one semantic conversation.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socketserver
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from .session_models import (
    BridgeUnavailable,
    ConversationEvent,
    SessionMismatch,
    opaque_id,
)


def host_bridge_socket_path() -> Path:
    configured = os.environ.get("ARQUX_HOST_BRIDGE_SOCKET")
    if configured:
        return Path(configured)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "arqux-session-bridge.sock"
    return Path.home() / ".cache" / "arqux" / "session-bridge.sock"


class HostSessionBridge:
    """Thread-safe request broker for one active ArqUX session."""

    def __init__(self, *, request_timeout_s: float = 90.0):
        self.request_timeout_s = request_timeout_s
        self._session: dict[str, Any] | None = None
        self._queue: deque[str] = deque()
        self._requests: dict[str, dict[str, Any]] = {}
        self._condition = threading.Condition(threading.RLock())

    def register_session(self, metadata: dict[str, Any]) -> dict[str, Any]:
        required = (
            "conversation_session_id", "parent_arqx_session_id",
            "active_agent_id", "project", "scope",
        )
        missing = [key for key in required if not metadata.get(key)]
        if missing:
            raise ValueError(f"missing host session fields: {', '.join(missing)}")
        clean = {key: str(metadata[key]) for key in required}
        with self._condition:
            if self._session is not None:
                current = {key: self._session[key] for key in required}
                if current != clean:
                    raise SessionMismatch("a different host session is already registered")
            else:
                self._session = clean
            self._condition.notify_all()
            return self.status()

    def detach(self, session_id: str) -> dict[str, Any]:
        with self._condition:
            self._require_session(session_id)
            for request in self._requests.values():
                if request["state"] in {"queued", "claimed"}:
                    request["state"] = "cancelled"
                    request["error"] = "host session detached"
                    request["condition"].notify_all()
            self._queue.clear()
            self._session = None
            self._condition.notify_all()
            return self.status()

    def submit_input(self, event: ConversationEvent,
                     timeout_s: float | None = None) -> list[str]:
        timeout = self.request_timeout_s if timeout_s is None else timeout_s
        with self._condition:
            self._require_session(event.conversation_session_id)
            request_id = opaque_id("host-request")
            request = {
                "request_id": request_id,
                "event": event.to_dict(),
                "state": "queued",
                "chunks": None,
                "error": None,
                "condition": self._condition,
            }
            self._requests[request_id] = request
            self._queue.append(request_id)
            self._condition.notify_all()
            deadline = time.monotonic() + timeout
            while request["state"] not in {"completed", "cancelled", "failed"}:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    request["state"] = "failed"
                    request["error"] = "host did not complete the current turn"
                    break
                self._condition.wait(remaining)
            if request["state"] != "completed":
                raise BridgeUnavailable(str(request["error"] or "host bridge failed"))
            return list(request["chunks"] or [])

    def poll(self, timeout_s: float = 20.0) -> dict[str, Any] | None:
        deadline = time.monotonic() + max(0.0, timeout_s)
        with self._condition:
            while not self._queue:
                if self._session is None:
                    raise BridgeUnavailable("no host session is registered")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            request_id = self._queue.popleft()
            request = self._requests[request_id]
            request["state"] = "claimed"
            return {
                "request_id": request_id,
                "event": dict(request["event"]),
            }

    def complete(self, request_id: str, chunks: list[str]) -> dict[str, Any]:
        with self._condition:
            request = self._requests.get(request_id)
            if request is None:
                raise KeyError(f"unknown host request: {request_id}")
            if request["state"] != "claimed":
                raise ValueError(f"request is not claimed: {request['state']}")
            request["chunks"] = [str(chunk) for chunk in chunks if str(chunk)]
            request["state"] = "completed"
            self._condition.notify_all()
            return {"request_id": request_id, "state": request["state"]}

    def status(self) -> dict[str, Any]:
        with self._condition:
            return {
                "available": self._session is not None,
                **(dict(self._session) if self._session else {}),
                "pending": sum(
                    1 for request in self._requests.values()
                    if request["state"] in {"queued", "claimed"}
                ),
            }

    def _require_session(self, session_id: str) -> None:
        if self._session is None:
            raise BridgeUnavailable("no host session is registered")
        if self._session["conversation_session_id"] != session_id:
            raise SessionMismatch("event does not belong to the registered host session")


class HostBridgeClient:
    """Client used by the active ArqUX host/handler, not by the voice daemon."""

    def __init__(self, path: str | Path | None = None, timeout_s: float = 30.0):
        self.path = Path(path) if path else host_bridge_socket_path()
        self.timeout_s = timeout_s

    def request(self, op: str, **payload: Any) -> Any:
        if not self.path.exists():
            raise BridgeUnavailable(f"host bridge not found: {self.path}")
        import socket

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.timeout_s)
        try:
            client.connect(str(self.path))
            client.sendall((json.dumps({"op": op, **payload}, ensure_ascii=False) + "\n").encode())
            raw = b""
            while not raw.endswith(b"\n"):
                chunk = client.recv(65536)
                if not chunk:
                    break
                raw += chunk
            if not raw:
                raise BridgeUnavailable("host bridge closed the connection")
            response = json.loads(raw.decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeUnavailable(str(exc)) from exc
        finally:
            client.close()
        if not response.get("ok", False):
            raise BridgeUnavailable(str(response.get("error", "host bridge rejected request")))
        return response.get("result")

    def register_session(self, **metadata: Any) -> dict[str, Any]:
        return self.request("register_session", session=metadata)

    def status(self) -> dict[str, Any]:
        return self.request("status")

    def poll(self, timeout_s: float = 20.0) -> dict[str, Any] | None:
        return self.request("poll", timeout_s=timeout_s)

    def complete(self, request_id: str, chunks: list[str]) -> dict[str, Any]:
        return self.request("complete", request_id=request_id, chunks=chunks)

    def detach(self, conversation_session_id: str) -> dict[str, Any]:
        return self.request("detach", conversation_session_id=conversation_session_id)

    def shutdown(self) -> dict[str, Any]:
        return self.request("shutdown")


class _BridgeServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, path: str, bridge: HostSessionBridge):
        self.bridge = bridge
        self.stop_event = threading.Event()
        super().__init__(path, _BridgeRequestHandler)


class _BridgeRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(1024 * 1024)
        if not raw:
            return
        try:
            request = json.loads(raw.decode("utf-8"))
            result = self._dispatch(request)
            response = {"ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001
            response = {"ok": False, "error": str(exc)}
        self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode())

    def _dispatch(self, request: dict[str, Any]) -> Any:
        bridge: HostSessionBridge = self.server.bridge  # type: ignore[attr-defined]
        op = str(request.get("op", ""))
        if op == "status":
            return bridge.status()
        if op == "register_session":
            return bridge.register_session(dict(request.get("session") or {}))
        if op == "detach":
            return bridge.detach(str(request["conversation_session_id"]))
        if op == "submit_input":
            return {
                "chunks": bridge.submit_input(
                    ConversationEvent(**dict(request["event"])),
                    timeout_s=float(request.get("timeout_s", bridge.request_timeout_s)),
                )
            }
        if op == "poll":
            return bridge.poll(float(request.get("timeout_s", 20)))
        if op == "complete":
            return bridge.complete(str(request["request_id"]), list(request.get("chunks") or []))
        if op == "shutdown":
            self.server.stop_event.set()  # type: ignore[attr-defined]
            return {"stopping": True}
        raise ValueError(f"unknown host bridge operation: {op}")


def serve_host_bridge(path: str | Path, bridge: HostSessionBridge | None = None) -> int:
    """Run the broker in the foreground and remove only its own socket."""
    socket_path = Path(path)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        raise RuntimeError(f"host bridge socket already exists: {socket_path}")
    server = _BridgeServer(str(socket_path), bridge or HostSessionBridge())
    os.chmod(socket_path, 0o600)
    server.timeout = 0.5
    try:
        while not server.stop_event.is_set():
            server.handle_request()
    finally:
        server.server_close()
        with contextlib.suppress(FileNotFoundError):
            socket_path.unlink()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ArqUX canonical host session bridge")
    parser.add_argument("--socket", default=str(host_bridge_socket_path()))
    parser.add_argument("--request-timeout", type=float, default=90.0)
    args = parser.parse_args()
    serve_host_bridge(args.socket, HostSessionBridge(request_timeout_s=args.request_timeout))


if __name__ == "__main__":  # pragma: no cover - process entry point
    main()
