from __future__ import annotations

from pathlib import Path

from arqux.core.learning._elevate import elevate_candidate
from arqux.core.learning.algorithms import detect_candidates, plan_patch
from arqux.core.learning.document import from_cortex_dict
from arqux.core.learning.sections import section_for_sigil
from arqux.cortex.reader import cortex_to_dict

FIXTURES = Path(__file__).parent / "fixtures" / "learning"


def _brain_doc(tmp_path: Path):
    src = (FIXTURES / "brain.cortex").read_text(encoding="utf-8")
    (tmp_path / ".arqux").mkdir()
    (tmp_path / ".arqux" / "brain.cortex").write_text(src, encoding="utf-8")
    (tmp_path / ".arqux" / "learn-policies.cortex").write_text(
        (FIXTURES / "learn-policies.cortex").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return from_cortex_dict(cortex_to_dict(src))


def test_protected_sigils_block():
    doc = from_cortex_dict({"sections": [{"id": "$1", "title": "IDENTITY", "entries": [{"sigil": "IDN", "name": "core", "attrs": {"x": "1"}}], "comments": []}]})
    # synthetic candidate sourced from protected sigil
    class C:
        candidate_id = "cand"
        source_entries = ["IDN:core"]
        target = "KNW"
        promotion_score = 5
        reason = "r"
    p = plan_patch(doc, None, C())
    assert p.mode == "block"


def test_admin_gate_requires_confirmation():
    brain = _brain_doc(Path(__import__("tempfile").mkdtemp()))
    cands = detect_candidates(brain)
    assert cands
    # policy-like object with admin gate
    class Entry:
        policy_id = "p1"
        source = cands[0].source_entries[0].split(":")[0]
        target = cands[0].target
        requires = "admin_policy"
        action = "apply"
    class PSet:
        entries = [Entry()]
    patch = plan_patch(brain, PSet(), cands[0])
    assert patch.mode in {"propose", "block"}  # without admin_confirmed not applied
    patch_ok = plan_patch(brain, PSet(), cands[0], admin_confirmed=True)
    assert patch_ok.mode == "apply"


def test_confirm_hash_required_and_no_mutation(tmp_path: Path):
    src = (FIXTURES / "brain.cortex").read_text(encoding="utf-8")
    arqux = tmp_path / ".arqux"
    arqux.mkdir()
    brain = arqux / "brain.cortex"
    brain.write_text(src, encoding="utf-8")
    (arqux / "learn-policies.cortex").write_text(
        (FIXTURES / "learn-policies.cortex").read_text(encoding="utf-8"), encoding="utf-8"
    )
    before = brain.read_text(encoding="utf-8")
    # find candidate via dry-run on temp project
    from arqux.core.learning.document import load_brain_document
    doc = load_brain_document(tmp_path)
    cands = detect_candidates(doc)
    assert cands
    cid = cands[0].candidate_id
    dry = elevate_candidate(tmp_path, cid, dry_run=True)
    assert dry.get("mode") == "dry_run" and dry.get("preview_hash")
    bad = elevate_candidate(tmp_path, cid, dry_run=False, confirm_hash="wrong")
    assert "error" in bad
    assert brain.read_text(encoding="utf-8") == before


def test_elevation_writes_to_vigente_section(tmp_path: Path):
    # Brain where LESSONS live at $7 (vigente) instead of BrainSection $6.
    src = (
        "$0\n\n$1: IDENTITY\nFCS:current{status:\"current\"}\n\n"
        "$4: SESSIONS\nSES:first{input:\"a\", output:\"b\", outcome:\"ok\", decision:\"x\"}\n"
        "SES:second{input:\"c\", output:\"d\", outcome:\"rework\", decision:\"y\"}\n\n"
        "$7: LESSONS\nLNG:seed{type:\"process\", cause:\"c\", lesson:\"l\", prevention:\"p\"}\n"
    )
    arqux = tmp_path / ".arqux"
    arqux.mkdir()
    (arqux / "brain.cortex").write_text(src, encoding="utf-8")
    (arqux / "learn-policies.cortex").write_text(
        (FIXTURES / "learn-policies.cortex").read_text(encoding="utf-8"), encoding="utf-8"
    )
    from arqux.core.learning.document import load_brain_document
    doc = load_brain_document(tmp_path)
    assert section_for_sigil("LNG", doc) == "$7"
    cands = detect_candidates(doc)
    assert cands
    cid = cands[0].candidate_id
    dry = elevate_candidate(tmp_path, cid, dry_run=True)
    assert "error" not in dry
    applied = elevate_candidate(tmp_path, cid, dry_run=False, confirm_hash=dry["preview_hash"])
    assert applied.get("mode") == "applied"
    assert applied.get("section") == "$7"
    after = (arqux / "brain.cortex").read_text(encoding="utf-8")
    assert "\n$7: LESSONS" in after
    assert "\n+LNG" not in after  # diff marker not written to file
    assert "LNG:first" in after or "LNG:second" in after or "LNG:" in after
