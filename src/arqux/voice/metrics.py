"""Bounded, content-free latency instrumentation for the voice runtime."""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping


class LatencyRecorder:
    """Record monotonic stage timestamps without retaining audio or text."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id
        self._events: dict[str, float] = {}
        self._lock = threading.Lock()

    def mark(self, name: str, at: float | None = None) -> float:
        """Store a stage timestamp and return it."""
        timestamp = time.monotonic() if at is None else at
        with self._lock:
            self._events[name] = timestamp
        return timestamp

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._events)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def durations(self) -> dict[str, float]:
        """Return selected stage durations in milliseconds."""
        events = self.snapshot()
        pairs = {
            "turn_to_first_audio_ms": ("speech_end", "first_audio"),
            "llm_ms": ("llm_start", "first_token"),
            "tts_ms": ("first_token", "first_tts"),
            "playback_ms": ("first_tts", "first_audio"),
        }
        result: dict[str, float] = {}
        for name, (start, end) in pairs.items():
            if start in events and end in events and events[end] >= events[start]:
                result[name] = round((events[end] - events[start]) * 1000, 2)
        return result

    def summary(self) -> dict[str, object]:
        """Return safe metrics suitable for logs or a transcript footer."""
        return {
            "session_id": self.session_id,
            "events": self.snapshot(),
            "durations": self.durations(),
        }


def merge_metrics(*records: Mapping[str, object]) -> dict[str, object]:
    """Merge stage metrics without copying content-bearing fields."""
    merged: dict[str, object] = {}
    for record in records:
        for key in ("session_id", "events", "durations"):
            if key in record:
                merged[key] = record[key]
    return merged
