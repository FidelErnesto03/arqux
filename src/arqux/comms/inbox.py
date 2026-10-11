"""Thread-safe inbox of incoming comms messages."""

from __future__ import annotations

import collections
import threading
import time


class Inbox:
    """Deduplicated, thread-safe queue with a long-poll ``listen``."""

    def __init__(self) -> None:
        self._dq: collections.deque = collections.deque()
        self._cv = threading.Condition()
        self._seen: set = set()

    def put(self, msg: dict) -> bool:
        """Enqueue ``msg``; return False when it is a duplicate."""
        mid = msg.get("id")
        with self._cv:
            if mid is not None:
                if mid in self._seen:
                    return False
                self._seen.add(mid)
            self._dq.append(msg)
            self._cv.notify()
            return True

    def unread(self) -> list[dict]:
        with self._cv:
            return list(self._dq)

    def listen(self, timeout: float = 20.0) -> dict | None:
        """Pop the next message or None on timeout (cap 120 s)."""
        deadline = time.monotonic() + max(0.1, min(float(timeout or 20), 120))
        with self._cv:
            while not self._dq:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cv.wait(remaining)
            return self._dq.popleft()
