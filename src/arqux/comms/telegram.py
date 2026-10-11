"""Telegram Bot API channel: outbound send + inbound long-poll.

Local-first: reception uses ``getUpdates`` long-polling (no public webhook).
Fail-closed: sending requires egress enabled AND the destination chat in the
allowlist.
"""

from __future__ import annotations

import contextlib
import threading
import time

from .config import allowlist as _allowlist
from .config import egress_enabled, redact, state_dir

_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramChannel:
    def __init__(self, token: str, inbox, allowlist: set[str] | None = None):
        self.token = token
        self.inbox = inbox
        self.allowlist = allowlist if allowlist is not None else _allowlist()
        self._offset = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None
        self.sent = 0
        self.received = 0
        self._load_offset()

    # -- offset persistence ------------------------------------------------
    def _offset_file(self):
        return state_dir() / "telegram_offset"

    def _load_offset(self) -> None:
        try:
            self._offset = int(self._offset_file().read_text().strip())
        except Exception:  # noqa: BLE001
            self._offset = 0

    def _store_offset(self) -> None:
        with contextlib.suppress(Exception):
            self._offset_file().write_text(str(self._offset))

    # -- outbound ----------------------------------------------------------
    def send(self, chat_id, text: str) -> dict:
        import httpx

        if not egress_enabled():
            return {"error": "egress_disabled",
                    "hint": "set ARQUX_COMMS_EGRESS=on"}
        if not self.allowlist or str(chat_id) not in self.allowlist:
            return {"error": "destination_not_allowed", "to": str(chat_id)}
        url = _API.format(token=self.token, method="sendMessage")
        try:
            r = httpx.post(url, json={"chat_id": chat_id, "text": text},
                           timeout=15)
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": "transport", "detail": redact(repr(exc))}
        if not data.get("ok"):
            return {"error": "telegram",
                    "detail": redact(str(data.get("description", r.status_code)))}
        self.sent += 1
        return {"ok": True, "id": data["result"].get("message_id"),
                "to": str(chat_id)}

    # -- inbound -----------------------------------------------------------
    def _poll_once(self) -> None:
        import httpx

        url = _API.format(token=self.token, method="getUpdates")
        r = httpx.get(url, params={"offset": self._offset, "timeout": 20},
                      timeout=30)
        data = r.json()
        if not data.get("ok"):
            self.last_error = redact(str(data.get("description")))
            return
        for upd in data.get("result", []):
            try:
                self._offset = max(self._offset,
                                   int(upd.get("update_id", 0)) + 1)
            except (TypeError, ValueError):
                continue
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            cid = str(chat.get("id", ""))
            text = msg.get("text", "")
            if not cid or not text:
                continue
            if self.allowlist and cid not in self.allowlist:
                continue  # untrusted sender: drop silently
            if self.inbox.put({"id": upd.get("update_id"), "from": cid,
                               "channel": "telegram", "text": text,
                               "ts": time.time()}):
                self.received += 1
        self._store_offset()

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001
                self.last_error = redact(repr(exc))
                time.sleep(3)

    def start(self) -> None:
        if self._thread:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
