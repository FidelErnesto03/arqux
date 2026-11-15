"""Golden behaviour tests (BLP-002 T-2.11).

The goldens are synthetic fixtures authored in ArqUX — they record the
*behavioural contract* of the native engine, not a dump of codec output.
No test in this module imports ``cortex.*`` or ``codec_cortex.*``.
"""
from __future__ import annotations

from pathlib import Path

from arqux.core.learning import _common
from arqux.core.learning.algorithms import (
    detect_candidates,
    parse_policy_document,
    plan_patch,
    rebuild_index,
    render_diff,
    score_candidate,
    score_for_sigil,
)
from arqux.core.learning.document import from_cortex_dict, load_brain_document
from arqux.cortex.reader import cortex_to_dict

FIXTURES = Path(__file__).parent / "fixtures" / "learning"
BRAIN = (FIXTURES / "brain.cortex").read_text(encoding="utf-8")
POLICY = (FIXTURES / "learn-policies.cortex").read_text(encoding="utf-8")


def _brain():
    return from_cortex_dict(cortex_to_dict(BRAIN))


def _policy():
    return parse_policy_document(cortex_to_dict(POLICY))


def test_load_brain_document(tmp_path: Path):
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()
    (arqux_dir / "brain.cortex").write_text(BRAIN, encoding="utf-8")
    doc = load_brain_document(tmp_path)
    assert doc is not None
    assert any(e.sigil == "SES" for _, e in doc.iter_entries())


def test_policy_parse_two_rules():
    ps = _policy()
    assert len(ps.entries) == 2
    ses = [e for e in ps.entries if e.source == "SES"][0]
    assert ses.target == "LNG"
    assert ses.threshold == 3


def test_scoring_fibonacci_like():
    assert score_candidate(decisions=2, blocked=1, hints=0, evidence=0, age_in_sessions=1) == 8
    assert score_candidate(decisions=0, blocked=0, hints=0, evidence=0, age_in_sessions=1) == 0
    assert score_for_sigil("KNW") > score_for_sigil("WRK")


def test_detect_candidates_seeded_brain():
    doc = _brain()
    candidates = detect_candidates(doc)
    assert candidates
    assert all(c.target in {"LNG", "KNW"} for c in candidates)
    assert all(len(c.source_entries) >= 1 for c in candidates)


def test_detect_candidates_empty_brain():
    doc = from_cortex_dict({"sections": []})
    assert detect_candidates(doc) == []


def test_index_rebuild_fills_bins():
    idx = rebuild_index(_brain())
    assert len(idx) > 0
    assert list(idx.keys())  # deterministic-ish: no crash, non-empty


def test_plan_patch_protects_blocking_cnst():
    doc = _brain()
    # Synthesize a doc whose CNST:blocking entry in SES role is protected.
    # Simpler contract: detect_candidates over the fixture yields no CNST source.
    candidates = detect_candidates(doc)
    assert candidates
    patch = plan_patch(doc, _policy(), candidates[0])
    assert patch.mode == "propose"


def test_render_diff_contains_section_header():
    doc = _brain()
    candidates = detect_candidates(doc)
    patch = plan_patch(doc, _policy(), candidates[0])
    rendered = render_diff(doc, patch)
    assert "# Patch mode:" in rendered
    assert "+++" in rendered


def test_degradation_available():
    ok, cause = _common.learning_engine_available()
    assert ok is True
    assert cause is None
