"""Bounded, owner-checked incremental speech sessions."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Mapping


class StreamRejected(ValueError):
    """An incremental fragment violated the SpeechSession contract."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SpeechSession:
    """Accept ordered text fragments without retaining audio or open buffers."""

    def __init__(self, session_id: str, owner: str, *, ttl_s: float = 30.0,
                 max_fragments: int = 64, max_bytes: int = 32_000):
        if not session_id or not owner:
            raise ValueError("session_id and owner are required")
        self.session_id = session_id
        self.owner = owner
        self.ttl_s = max(0.1, ttl_s)
        self.max_fragments = max(1, max_fragments)
        self.max_bytes = max(1, max_bytes)
        self.stream_id: str | None = None
        self._next_sequence = 1
        self._bytes = 0
        self._fragments: deque[str] = deque()
        self._last_activity = time.monotonic()
        self._closed = False
        self._interrupted = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def expired(self) -> bool:
        return time.monotonic() - self._last_activity > self.ttl_s

    def _reject(self, code: str, message: str) -> None:
        raise StreamRejected(code, message)

    def accept(self, fragment: Mapping[str, object], *, owner: str) -> dict:
        """Validate and enqueue one text fragment.

        The caller owns draining the bounded text queue into TTS. Audio is
        deliberately absent from this object and is never persisted here.
        """
        if owner != self.owner:
            self._reject("owner_mismatch", "stream owner does not match")
        if self.expired:
            self._closed = True
            self._reject("expired", "stream TTL expired")
        if str(fragment.get("session_id", "")) != self.session_id:
            self._reject("session_mismatch", "session_id does not match")
        stream_id = str(fragment.get("stream_id", ""))
        if not stream_id:
            self._reject("missing_stream", "stream_id is required")
        if self.stream_id is None:
            self.stream_id = stream_id
        elif stream_id != self.stream_id:
            self._reject("stream_mismatch", "stream_id does not match")
        if bool(fragment.get("interrupt", False)):
            self.cancel()
            return {"accepted": False, "interrupted": True,
                    "session_id": self.session_id, "stream_id": stream_id}
        if self._closed:
            self._reject("closed", "stream is already closed")
        try:
            sequence = int(fragment["sequence"])
        except (KeyError, TypeError, ValueError):
            self._reject("invalid_sequence", "sequence is required")
        if sequence != self._next_sequence:
            self._reject("out_of_order", f"expected sequence {self._next_sequence}")
        text = fragment.get("text", "")
        if not isinstance(text, str):
            self._reject("invalid_text", "text must be a string")
        encoded = len(text.encode("utf-8"))
        if (len(self._fragments) >= self.max_fragments
                or self._bytes + encoded > self.max_bytes):
            self._reject("buffer_limit", "stream buffer limit exceeded")
        self._fragments.append(text)
        self._bytes += encoded
        self._next_sequence += 1
        self._last_activity = time.monotonic()
        if bool(fragment.get("final", False)):
            self._closed = True
        return {"accepted": True, "final": self._closed,
                "sequence": sequence, "session_id": self.session_id,
                "stream_id": stream_id}

    def drain(self) -> str:
        """Return buffered text and release it immediately."""
        text = "".join(self._fragments)
        self._fragments.clear()
        self._bytes = 0
        return text

    def cancel(self) -> None:
        self._fragments.clear()
        self._bytes = 0
        self._closed = True
        self._interrupted = True

    def status(self) -> dict[str, object]:
        return {"session_id": self.session_id, "stream_id": self.stream_id,
                "next_sequence": self._next_sequence,
                "buffered_fragments": len(self._fragments),
                "buffered_bytes": self._bytes, "closed": self._closed,
                "interrupted": self._interrupted, "expired": self.expired}
