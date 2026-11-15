"""Native learning algorithms for the ArqUX learning engine (BLP-003).

This package provides native learning algorithms for ArqUX. It is
plain Python over the learning document protocol (see ``protocol.py``);
it is a self-contained native package.

The implementation follows documented semantics (ADR 0001): candidate
detection (SES -> LNG -> KNW, weighted by evidence), scoring with
documented weights, and Fibonacci thresholds 1..21.
"""
from __future__ import annotations

from . import candidates, elevation, index, policy, scoring
from .candidates import Candidate, detect_candidates
from .elevation import Patch, plan_patch, render_diff
from .index import Bin, LearnIndex, rebuild_index, remove_from_index
from .policy import LearningPolicySet, PolicyEntry, parse_policy_document, score_for_sigil
from .scoring import score_candidate

__all__ = [
    "Bin",
    "Candidate",
    "LearnIndex",
    "LearningPolicySet",
    "Patch",
    "PolicyEntry",
    "candidates",
    "detect_candidates",
    "elevation",
    "index",
    "parse_policy_document",
    "plan_patch",
    "policy",
    "rebuild_index",
    "remove_from_index",
    "render_diff",
    "score_candidate",
    "score_for_sigil",
    "scoring",
]
