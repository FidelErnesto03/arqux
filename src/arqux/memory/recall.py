"""BLP-003: deterministic recall with abstention.

Recall returns *context and provenance*, never permissions (§7.1, L-SEC-04).
It never mutates the canonical CORTEX (CA-06). The ranking is deterministic:
same query, same corpus, same feedback state, same order (CA-02). When no
memory is relevant or confidence is insufficient the service abstains and
declares why (CA-04) — abstention is a valid result, not a failure (§7.10).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .events import TRUST_DATA, RecallResult

_TOKEN_RE = re.compile(r"[a-z0-9_]+")

# L-SEC-01: text that imitates an instruction is reported as such but is
# still only data. Detection is a *report*, never a trigger for action.
_INSTRUCTION_MARKERS = (
    "ignore",
    "override",
    "you must",
    "system:",
    "as the architect",
    "authorize",
    "grant",
    "execute",
    "bypass",
    "skip the",
)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def looks_like_instruction(text: str) -> bool:
    """True when text reads like an order rather than a memory."""
    low = text.lower()
    return any(marker in low for marker in _INSTRUCTION_MARKERS)


class RecallService:
    """Rank memory records lexically and temporally, with abstention."""

    MIN_CONFIDENCE_DEFAULT = 0.5

    def __init__(
        self,
        store: Any,
        *,
        min_confidence: float | None = None,
        policy: Any = None,
    ) -> None:
        self.store = store
        self.min_confidence = (
            self.MIN_CONFIDENCE_DEFAULT if min_confidence is None else float(min_confidence)
        )
        self.policy = policy

    def recall(
        self, query: str, *, limit: int = 5, now_epoch: float | None = None
    ) -> list[RecallResult]:
        records: Iterable = self.store.query(now_epoch=now_epoch)
        records = tuple(records)
        query_tokens = _tokens(query)
        max_epoch = max((r.created_epoch for r in records), default=0.0)

        candidates: list[RecallResult] = []
        for record in records:
            text = " ".join(str(v) for v in record.payload.values())
            haystack = f"{record.kind} {record.origin.name} {text}"
            overlap = query_tokens & _tokens(haystack)
            if query_tokens and not overlap:
                continue
            lexical = (len(overlap) / len(query_tokens)) if query_tokens else 0.0
            recency = (record.created_epoch / max_epoch) if max_epoch else 0.0
            bonus = self.policy.bonus(record.address) if self.policy is not None else 0.0
            score = 0.7 * lexical + 0.3 * recency + bonus
            candidates.append(
                RecallResult(
                    query=query,
                    record=record,
                    score=round(score, 6),
                    ranking_reason=(
                        f"lexical={len(overlap)}/{len(query_tokens)} "
                        f"recency={recency:.3f} feedback={bonus:+.3f}"
                    ),
                    confidence=record.confidence,
                    trust=TRUST_DATA,
                    instruction_like=looks_like_instruction(text),
                )
            )

        if not candidates:
            return [self._abstain(query, "sin coincidencia léxica")]

        eligible = [c for c in candidates if c.confidence >= self.min_confidence]
        if not eligible:
            return [
                self._abstain(
                    query, f"confianza insuficiente (< {self.min_confidence:.2f})"
                )
            ]

        # Deterministic order: score desc, then address asc as the tiebreaker.
        eligible.sort(key=lambda c: (-c.score, c.address))
        return eligible[:limit]

    def _abstain(self, query: str, reason: str) -> RecallResult:
        return RecallResult(
            query=query,
            record=None,
            score=0.0,
            ranking_reason="",
            confidence=0.0,
            abstained=True,
            abstention_reason=reason,
        )
