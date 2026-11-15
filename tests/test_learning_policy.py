"""Policy parsing tests (BLP-003)."""
from __future__ import annotations

from arqux.core.learning.algorithms.policy import (
    CoolingPolicy,
    DetectionPolicy,
    FeedbackPolicy,
    FibonacciThresholds,
    ProtectedPatterns,
    Thresholds,
    parse_policy_document,
)
from arqux.cortex.reader import cortex_to_dict


def test_thresholds_fibonacci_defaults():
    t = Thresholds()
    assert (t.observed, t.repeated, t.pattern, t.candidate, t.ask_user, t.strong_candidate, t.critical) == (
        1, 2, 3, 5, 8, 13, 21
    )


def test_protected_targets_default():
    doc = cortex_to_dict("$0\n\n$5: LEARNING POLICY\nPOL:ses_to_lng{from:\"SES\", to:\"LNG\", tier:\"1\", threshold:\"3\"}\n")
    ps = parse_policy_document(doc)
    assert ps.protected_targets.sigils == ["IDN", "AXM", "CNST:blocking", "CLAIM", "LIM"]


def test_parse_policy_blocks():
    text = """$0

$5: LEARNING POLICY
THR:thresholds{observed:"1", repeated:"2", pattern:"3", candidate:"5", ask_user:"8", strong_candidate:"13", critical:"21"}
PRT:targets{sigils:"IDN,AXM"}
POL:ses_to_lng{from:"SES", to:"LNG", tier:"1", threshold:"3"}
POL:fibonacci_thresholds{series:"1,1,2,3,5,8,13,21"}
POL:cooling{enabled:"true", sessions:"3"}
POL:detection{min_cluster_size:"2", max_candidates:"10"}
POL:feedback{record:"true"}
POL:protected_patterns{patterns:"CNST:blocking"}
"""
    ps = parse_policy_document(cortex_to_dict(text))
    assert isinstance(ps.fibonacci_thresholds, FibonacciThresholds)
    assert ps.fibonacci_thresholds.series == [1, 1, 2, 3, 5, 8, 13, 21]
    assert isinstance(ps.cooling, CoolingPolicy) and ps.cooling.sessions == 3
    assert isinstance(ps.detection, DetectionPolicy) and ps.detection.max_candidates == 10
    assert isinstance(ps.feedback, FeedbackPolicy) and ps.feedback.record is True
    assert isinstance(ps.protected_patterns, ProtectedPatterns)
    assert "CNST:blocking" in ps.protected_patterns.patterns
    assert ps.protected_targets.sigils == ["IDN", "AXM"]
    assert len([e for e in ps.entries if e.source == "SES"]) == 1
