"""BLP-003: contracts for recall, outcomes and feedback.

Retrieved content is DATA, never INSTRUCTION (L-SEC-01). Every artifact that
carries recall, an outcome or a metric declares its provenance (L-SEC-03).
Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import MemoryRecord

# L-SEC-01: recalled content is delivered marked as untrusted data.
TRUST_DATA = "untrusted_data"


class Feedback(str, Enum):
    """The four feedback states (BLP-003 §3)."""

    USEFUL = "useful"
    IRRELEVANT = "irrelevant"
    INCORRECT = "incorrect"
    UNEVALUATED = "unevaluated"


@dataclass(frozen=True)
class RecallResult:
    """One recalled memory, or an explicit abstention (CA-01, CA-03, CA-04)."""

    query: str
    record: MemoryRecord | None
    score: float
    ranking_reason: str
    confidence: float
    trust: str = TRUST_DATA
    instruction_like: bool = False
    abstained: bool = False
    abstention_reason: str = ""

    @property
    def content(self) -> dict[str, Any]:
        """The recalled payload — always a data blob, never executable policy."""
        return dict(self.record.payload) if self.record else {}

    @property
    def provenance(self) -> str:
        """Canonical CORTEX address the memory came from (L-SEC-03)."""
        return self.record.provenance.derived_from if self.record else ""

    @property
    def address(self) -> str:
        return self.record.address if self.record else ""


@dataclass(frozen=True)
class OutcomeEvent:
    """The result of a governed decision (BLP-003 §7.2, L-SEC-03)."""

    decision_id: str
    result: str
    success: bool
    date: str
    provenance: str
    outcome_id: str = ""


@dataclass(frozen=True)
class FeedbackEvent:
    """Explicit feedback tying a decision and its result to a memory (§7.2)."""

    decision_id: str
    outcome_id: str
    recall_address: str
    feedback: Feedback
    date: str
    provenance: str
