"""Per-turn latency measurements for the canonical multimodal session."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

DEFAULT_BUDGETS_MS = {
    "speech_end_to_bus_submit": 300.0,
    "speech_end_to_agent_first_token": 1500.0,
    "speech_end_to_tts_first_audio": 2000.0,
    "barge_in_cancel": 200.0,
}


@dataclass
class TurnLatency:
    turn_id: str
    marks: dict[str, float] = field(default_factory=dict)

    def mark(self, name: str, at: float | None = None) -> float:
        value = at if at is not None else time.monotonic()
        self.marks.setdefault(name, value)
        return value

    def duration_ms(self, start: str, end: str) -> float | None:
        if start not in self.marks or end not in self.marks:
            return None
        return round((self.marks[end] - self.marks[start]) * 1000, 2)

    def report(self, budgets_ms: dict[str, float] | None = None) -> dict[str, Any]:
        budgets = budgets_ms or DEFAULT_BUDGETS_MS
        durations = {
            "speech_end_to_bus_submit": self.duration_ms("speech_end", "bus_submit"),
            "speech_end_to_agent_first_token": self.duration_ms(
                "speech_end", "agent_first_token"),
            "speech_end_to_tts_first_audio": self.duration_ms(
                "speech_end", "tts_first_audio"),
            "barge_in_cancel": self.duration_ms("barge_in", "cancelled"),
        }
        violations = [
            name for name, value in durations.items()
            if value is not None and name in budgets and value > budgets[name]
        ]
        return {
            "turn_id": self.turn_id,
            "marks": dict(self.marks),
            "durations_ms": durations,
            "budgets_ms": dict(budgets),
            "violations": violations,
        }


class SessionLatencyRecorder:
    def __init__(self, budgets_ms: dict[str, float] | None = None):
        self.budgets_ms = dict(budgets_ms or DEFAULT_BUDGETS_MS)
        self._turns: dict[str, TurnLatency] = {}
        self._lock = threading.RLock()

    def turn(self, turn_id: str) -> TurnLatency:
        with self._lock:
            return self._turns.setdefault(turn_id, TurnLatency(turn_id))

    def mark(self, turn_id: str, name: str, at: float | None = None) -> float:
        return self.turn(turn_id).mark(name, at)

    def report(self, turn_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            if turn_id is not None:
                return self.turn(turn_id).report(self.budgets_ms)
            return {
                "turns": [turn.report(self.budgets_ms)
                          for turn in self._turns.values()],
                "budgets_ms": dict(self.budgets_ms),
            }
