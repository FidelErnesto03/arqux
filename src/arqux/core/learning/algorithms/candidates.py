"""Candidate extraction.

Semantics follow the CLE's documented contract (see ADR 0001):

  ``SES`` -> ``LNG`` -> ``KNW`` promotion, weighted by evidence.
  The implementation is original — it does not reuse codec source text,
  only the behavioural contract (see ADR 0001).

Fields (match the codec's observable shape):

  ``candidate_id``       stable identifier (deterministic from source entries)
  ``source_entries``     selectors "SIGIL:name" for the entries in the cluster
  ``target``             target sigil: SES→LNG, LNG→KNW
  ``promotion_score``    integer; see ``scoring.score_candidate``
  ``hotness_score``      weighted mention frequency
  ``risk_weight``        fixed 1 (no CNST/CLAIM influence)
  ``read_priority``      P0..P5
  ``suggested_action``   "record_lesson" | "promote_to_knowledge" | "review"
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..protocol import LearningEntry
from .scoring import score_candidate

MAX_CANDIDATES = 10
MIN_SESSIONS_FOR_LNG = 2


@dataclass
class Candidate:
    """A proposed elevation candidate."""

    candidate_id: str
    source_entries: list[str]
    target: str
    promotion_score: int
    hotness_score: int
    risk_weight: int
    read_priority: str
    suggested_action: str
    policy_match: str | None = None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "source_entries": list(self.source_entries),
            "target": self.target,
            "promotion_score": self.promotion_score,
            "hotness_score": self.hotness_score,
            "risk_weight": self.risk_weight,
            "read_priority": self.read_priority,
            "suggested_action": self.suggested_action,
            "policy_match": self.policy_match,
            "reason": self.reason,
        }


_TARGET_BY_SOURCE = {"SES": "LNG", "LNG": "KNW"}
_MIN_DECISIONS_FOR_TARGET = {"LNG": 1, "KNW": 2}


def _priority_for(score: int) -> str:
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


def _action_for(target: str) -> str:
    return {"LNG": "record_lesson", "KNW": "promote_to_knowledge"}.get(target, "review")


def _entry_selector(entry: LearningEntry) -> str:
    return f"{entry.sigil}:{entry.name}"


def _count_signals(entries: list[LearningEntry]) -> dict[str, int]:
    decisions = 0
    blocked = 0
    hints = 0
    user_validated = 0
    evidence = 0
    for e in entries:
        for key, value in (e.value or {}).items() if isinstance(e.value, dict) else []:
            k = str(key).lower()
            v = str(value).lower() if not isinstance(value, bool) else value
            if k == "blocked_outcome" and v in {"true", "1", "yes"}:
                blocked += 1
            elif k in {"decision", "blocker", "fail"}:
                decisions += 1
            elif k == "user_validated" and v is True or v == "true":
                user_validated += 1
    return {"decisions": decisions, "blocked": blocked, "hints": hints, "user_validated": user_validated, "evidence": evidence}


def detect_candidates(
    document,
    index=None,
) -> list[Candidate]:
    """Return the candidate list derived from the brain document.

    Clusters entries by source sigil. One candidate per source sigil that
    clears the minimum threshold. ``index`` is accepted for API compatibility
    with the pre-existing call sites; it is not used for scoring in this
    release.
    """
    by_sigil: dict[str, list[LearningEntry]] = {}
    for _section, entry in document.iter_entries():
        by_sigil.setdefault(entry.sigil, []).append(entry)

    candidates: list[Candidate] = []
    for source, target in _TARGET_BY_SOURCE.items():
        source_entries = by_sigil.get(source, [])
        if not source_entries:
            continue
        decision_count = 0
        blocked_count = 0
        evidence_count = 0
        for e in source_entries:
            value = e.value if isinstance(e.value, dict) else {}
            for key, value_item in value.items():
                k = str(key).lower()
                if k == "blocked_outcome" and str(value_item).lower() in {"true", "1", "yes"}:
                    blocked_count += 1
                elif k in {"outcome", "decision", "fail"} or "decision" in k or "block" in k:
                    decision_count += 1
                elif k == "user_validated" and bool(value_item):
                    evidence_count += 1
        # A single LNG with lesson content is a learning signal only when it
        # carries strong evidence (e.g. user_validated). A lone, unvalidated
        # lesson should not create a "pattern" — it stays silent until there
        # is corroborating signal or a cluster of entries.
        if source == "LNG" and evidence_count == 0 and decision_count == 0 and blocked_count == 0:
            if len(source_entries) < 2:
                continue
            decision_count = min(3, len(source_entries))

        # Minimum substantive signal for the target level: a cluster of
        # entries with zero decisions/blocked/evidence is activity, not a
        # learnable pattern. Without this gate, sheer entry count inflates
        # promotion_score via age_in_sessions (e.g. N boilerplate SES rows
        # producing a P0 "lesson").
        if decision_count + blocked_count + evidence_count < _MIN_DECISIONS_FOR_TARGET.get(target, 1):
            continue

        score = score_candidate(
            decisions=decision_count,
            blocked=blocked_count,
            hints=0,
            evidence=evidence_count,
            age_in_sessions=len(source_entries),
        )
        if score < 1:
            continue

        candidates.append(
            Candidate(
                candidate_id=f"cand_{source.lower()}_{hashlib.sha256(' '.join(sorted(e.name for e in source_entries)).encode()).hexdigest()[:12]}",
                source_entries=[_entry_selector(e) for e in source_entries],
                target=target,
                promotion_score=score,
                hotness_score=len(source_entries),
                risk_weight=1,
                read_priority=_priority_for(score),
                suggested_action=_action_for(target),
            )
        )
        if len(candidates) >= MAX_CANDIDATES:
            break

    return candidates


__all__ = ["Candidate", "detect_candidates"]
