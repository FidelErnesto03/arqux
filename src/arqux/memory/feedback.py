"""BLP-003: outcome and feedback recording, in the derived store only.

Feedback never mutates the canonical CORTEX (R-12, §7.3): it writes only to
the derived index, adjusting ranking. An artifact without provenance is not
persisted (L-SEC-03). Reading a memory never makes it valid knowledge (§4).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .events import Feedback, FeedbackEvent, OutcomeEvent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FeedbackPolicy:
    """Derived ranking adjustment derived from explicit feedback only."""

    BONUS = {
        Feedback.USEFUL: 0.2,
        Feedback.IRRELEVANT: -0.1,
        Feedback.INCORRECT: -0.3,
        Feedback.UNEVALUATED: 0.0,
    }

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._events: list[FeedbackEvent] = []
        if self.path is not None and self.path.is_file():
            self._load()

    def bonus(self, address: str) -> float:
        total = 0.0
        for event in self._events:
            if event.recall_address == address:
                total += self.BONUS.get(event.feedback, 0.0)
        return round(total, 6)

    def record(self, event: FeedbackEvent) -> None:
        if not event.provenance:
            raise ValueError("feedback sin procedencia no se persiste (L-SEC-03)")
        self._events.append(event)
        self._persist()

    def events(self) -> tuple[FeedbackEvent, ...]:
        return tuple(self._events)

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "decision_id": e.decision_id,
                "outcome_id": e.outcome_id,
                "recall_address": e.recall_address,
                "feedback": e.feedback.value,
                "date": e.date,
                "provenance": e.provenance,
            }
            for e in self._events
        ]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load(self) -> None:
        for row in json.loads(self.path.read_text(encoding="utf-8")):
            self._events.append(
                FeedbackEvent(
                    decision_id=row["decision_id"],
                    outcome_id=row["outcome_id"],
                    recall_address=row["recall_address"],
                    feedback=Feedback(row["feedback"]),
                    date=row["date"],
                    provenance=row["provenance"],
                )
            )


class OutcomeRecorder:
    """Records governed decision results; never touches CORTEX."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._outcomes: list[OutcomeEvent] = []
        if self.path is not None and self.path.is_file():
            self._load()

    def record(self, event: OutcomeEvent) -> None:
        if not event.provenance:
            raise ValueError("outcome sin procedencia no se persiste (L-SEC-03)")
        self._outcomes.append(event)
        self._persist()

    def outcomes(self) -> tuple[OutcomeEvent, ...]:
        return tuple(self._outcomes)

    def _persist(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "decision_id": e.decision_id,
                "result": e.result,
                "success": e.success,
                "date": e.date,
                "provenance": e.provenance,
                "outcome_id": e.outcome_id,
            }
            for e in self._outcomes
        ]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load(self) -> None:
        for row in json.loads(self.path.read_text(encoding="utf-8")):
            self._outcomes.append(
                OutcomeEvent(
                    decision_id=row["decision_id"],
                    result=row["result"],
                    success=bool(row["success"]),
                    date=row["date"],
                    provenance=row["provenance"],
                    outcome_id=row.get("outcome_id", ""),
                )
            )
