"""Socket client for the host-owned current ArqUX session.

The socket is a transport for the host adapter contract only.  It never
selects or starts a model.  A missing socket is a hard bridge failure.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from ..session_models import BridgeUnavailable, ConversationEvent


class SocketCurrentAgentAdapter:
    """Call a host session adapter over a restricted Unix socket."""

    adapter_id = "host-unix-socket"

    def __init__(self, path: str | Path, timeout_s: float = 90.0):
        self.path = Path(path)
        self.timeout_s = timeout_s

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.path.exists():
            raise BridgeUnavailable(f"host session bridge not found: {self.path}")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout_s)
        try:
            sock.connect(str(self.path))
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode())
            raw = b""
            while not raw.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                raw += chunk
            if not raw:
                raise BridgeUnavailable("host session bridge closed the connection")
            response = json.loads(raw.decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BridgeUnavailable(f"host session bridge unavailable: {exc}") from exc
        finally:
            sock.close()
        if not response.get("ok", False):
            raise BridgeUnavailable(str(response.get("error", "host bridge rejected request")))
        return response.get("result", {})

    def submit_input(self, event: ConversationEvent) -> list[str]:
        result = self._request({"op": "submit_input", "event": event.to_dict()})
        chunks = result.get("chunks")
        if not isinstance(chunks, list):
            raise BridgeUnavailable("host bridge response has no response chunks")
        return [str(chunk) for chunk in chunks if str(chunk)]

    def status(self) -> dict[str, Any]:
        try:
            result = self._request({"op": "status"})
        except BridgeUnavailable as exc:
            return {
                "adapter_id": self.adapter_id,
                "available": False,
                "error": str(exc),
            }
        return {"adapter_id": self.adapter_id, "available": True, **result}
