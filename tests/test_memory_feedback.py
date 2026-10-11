"""BLP-003: feedback and outcome events, and CA-08 (L-SEC-07).

Feedback requires a decision and a result and carries provenance (L-SEC-03);
it writes only to the derived index (R-12). CA-08: provenance does not attest
truth — confidence is judged by the record, never by its origin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.memory import (
    Feedback,
    FeedbackEvent,
    FeedbackPolicy,
    LocalStore,
    OutcomeEvent,
    OutcomeRecorder,
    RecallService,
)

SAMPLE = """$0
$0:format{cortex:0.1,encoding:UTF-8}
KNW:knowledge{type:attrs,weight:B,fields:"topic:text|content:text|status:text|confidence:dec",focus:content,desc:"Knowledge"}
$1:KNOW
KNW:cortex{topic:"CORTEX",content:"lineal sigil codec",status:"current",confidence:0.9}
KNW:falsy{topic:"cortex",content:"cortex but false",status:"current",confidence:0.1}
"""


def _store(tmp_path: Path) -> LocalStore:
    source = tmp_path / "brain.cortex"
    source.write_text(SAMPLE, encoding="utf-8")
    return LocalStore(tmp_path / "index.json", [source])


def _feedback(address: str, feedback: Feedback) -> FeedbackEvent:
    return FeedbackEvent(
        decision_id="D-1",
        outcome_id="O-1",
        recall_address=address,
        feedback=feedback,
        date="2026-10-10",
        provenance="session#SES:1",
    )


def test_feedback_requires_provenance() -> None:
    policy = FeedbackPolicy()
    with pytest.raises(ValueError):
        policy.record(
            FeedbackEvent(
                decision_id="D-1",
                outcome_id="O-1",
                recall_address="a",
                feedback=Feedback.USEFUL,
                date="2026-10-10",
                provenance="",
            )
        )


def test_outcome_requires_provenance() -> None:
    with pytest.raises(ValueError):
        OutcomeRecorder().record(
            OutcomeEvent(
                decision_id="D-1", result="ok", success=True, date="2026-10-10", provenance=""
            )
        )


def test_useful_feedback_raises_the_ranking(tmp_path: Path) -> None:
    store = _store(tmp_path)
    address = store.query(kind="knowledge")[0].address
    policy = FeedbackPolicy()
    base = RecallService(store, policy=policy).recall("cortex")[0].score
    policy.record(_feedback(address, Feedback.USEFUL))
    boosted = RecallService(store, policy=policy).recall("cortex")[0].score
    assert boosted > base


def test_feedback_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "feedback.json"
    policy = FeedbackPolicy(path)
    policy.record(_feedback("addr-1", Feedback.USEFUL))
    reloaded = FeedbackPolicy(path)
    assert reloaded.bonus("addr-1") == policy.bonus("addr-1") == 0.2


def test_confidence_is_judged_by_the_record_not_the_origin(tmp_path: Path) -> None:
    """CA-08 / L-SEC-07: an authorized source does not make content true.

    ``KNW:falsy`` lives in the same canonical file but carries confidence 0.1,
    so it does not cross a 0.5 threshold by its origin alone.
    """
    store = _store(tmp_path)
    results = RecallService(store, min_confidence=0.5).recall("cortex")
    addresses = [r.address for r in results if not r.abstained]
    assert addresses, "expected at least the high-confidence record"
    assert all("falsy" not in a for a in addresses)
