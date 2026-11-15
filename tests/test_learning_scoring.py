"""Scoring tests for the native learning engine (BLP-003)."""
from __future__ import annotations

from arqux.core.learning.algorithms.scoring import score_candidate


def test_score_candidate_weights():
    # 3*decisions + 2*blocked + hints + evidence - age_penalty(age>1)
    assert score_candidate(decisions=1, blocked=0, hints=0, evidence=0) == 3
    assert score_candidate(decisions=0, blocked=1, hints=0, evidence=0) == 2
    assert score_candidate(decisions=2, blocked=1, hints=1, evidence=1, age_in_sessions=1) == 10


def test_score_candidate_age_penalty_and_floor():
    # age_in_sessions<=1 => no penalty; older sessions decay
    assert score_candidate(decisions=1, blocked=0, hints=0, evidence=0, age_in_sessions=1) == 3
    assert score_candidate(decisions=1, blocked=0, hints=0, evidence=0, age_in_sessions=3) == 1
    assert score_candidate(decisions=0, blocked=0, hints=0, evidence=0, age_in_sessions=5) == -4


def test_score_candidate_deterministic():
    kwargs = {"decisions": 2, "blocked": 1, "hints": 0, "evidence": 1, "age_in_sessions": 2}
    assert score_candidate(**kwargs) == score_candidate(**kwargs) == 8
