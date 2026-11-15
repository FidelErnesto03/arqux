"""Scoring for learning candidates (BLP-003, native).

Semantics follow the documented CLE behavioural contract (ADR 0001):
    score = 3 * #decisions + 2 * #blocked + #hints + #evidence - age_penalty

No codec source text is reused. Deterministic, no clock access.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

_WEIGHTS = {
    "decision": 3,
    "blocked": 2,
    "hint": 1,
    "evidence": 1,
    "age_penalty": 1,
}


@dataclass
class SignalSet:
    decisions: int = 0
    blocked: int = 0
    hints: int = 0
    evidence: int = 0
    age_in_sessions: int = 0


@dataclass
class ScoreRecord:
    hotness: int = 0
    promotion: int = 0
    risk: int = 1
    priority: str = "P4"
    action: str = "review"
    last_accessed: str | None = None
    signals: dict[str, int] = field(default_factory=dict)


def score_hotness(*, decisions: int, blocked: int, hints: int, evidence: int, age_in_sessions: int = 0) -> int:
    return max(0, score_candidate(decisions=decisions, blocked=blocked, hints=hints, evidence=evidence, age_in_sessions=age_in_sessions))


def score_promotion(*, decisions: int, blocked: int, hints: int, evidence: int, age_in_sessions: int = 0) -> int:
    return score_candidate(decisions=decisions, blocked=blocked, hints=hints, evidence=evidence, age_in_sessions=age_in_sessions)


def score_risk(*, blocked: int = 0, decisions: int = 0) -> int:
    # Conservative risk floor: blocked/decision pressure raises risk weight.
    return 1 + (1 if blocked else 0) + (1 if decisions >= 2 else 0)


def derive_read_priority(score: int) -> str:
    if score >= 8:
        return "P0"
    if score >= 5:
        return "P1"
    if score >= 3:
        return "P2"
    if score >= 1:
        return "P3"
    if score >= 0:
        return "P4"
    return "P5"


def suggest_action(target: str, score: int) -> str:
    if target == "KNW":
        return "promote_to_knowledge"
    if target == "LNG":
        return "record_lesson"
    return "review" if score < 3 else "candidate"


def detect_signals(entries: list[Any]) -> SignalSet:
    decisions = blocked = hints = evidence = 0
    for e in entries:
        value = e.value if hasattr(e, "value") and isinstance(e.value, dict) else {}
        for key, value_item in value.items():
            k = str(key).lower()
            if k == "blocked_outcome" and str(value_item).lower() in {"true", "1", "yes"}:
                blocked += 1
            elif k in {"outcome", "decision", "fail"} or "decision" in k or "block" in k:
                decisions += 1
            elif k == "hint":
                hints += 1
            elif k == "user_validated" and bool(value_item):
                evidence += 1
    return SignalSet(decisions=decisions, blocked=blocked, hints=hints, evidence=evidence, age_in_sessions=len(entries))


def score_candidate(
    *,
    decisions: int,
    blocked: int,
    hints: int,
    evidence: int,
    age_in_sessions: int = 0,
) -> int:
    """Compute the integer score of a learning candidate."""
    decision_part = decisions * _WEIGHTS["decision"]
    blocked_part = blocked * _WEIGHTS["blocked"]
    hint_part = hints * _WEIGHTS["hint"]
    evidence_part = evidence * _WEIGHTS["evidence"]
    age = max(0, age_in_sessions - 1) * _WEIGHTS["age_penalty"]
    return int(math.trunc(decision_part + blocked_part + hint_part + evidence_part - age))


__all__ = [
    "SignalSet",
    "ScoreRecord",
    "detect_signals",
    "derive_read_priority",
    "score_candidate",
    "score_hotness",
    "score_promotion",
    "score_risk",
    "suggest_action",
]
