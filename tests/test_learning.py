"""Tests for the learning adapter."""

from __future__ import annotations

from pathlib import Path

from arqux.constants import ARQUX_DIR
from arqux.handlers import cortex
from arqux.learning import (
    POLICY_FILENAME,
    _preview_hash,
    _resolve_policy_path,
    _validate_elevation_payload,
)


def test_learning_policy_falls_back_to_packaged_default(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    gov_dir = project_root / ARQUX_DIR
    gov_dir.mkdir(parents=True)
    (gov_dir / "brain.cortex").write_text("$0\n", encoding="utf-8")

    policy_path = _resolve_policy_path(project_root)

    assert policy_path.name == POLICY_FILENAME
    assert policy_path.exists()
    assert policy_path != project_root / ARQUX_DIR / POLICY_FILENAME


def test_learning_policy_prefers_project_local_file(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    gov_dir = project_root / ARQUX_DIR
    gov_dir.mkdir(parents=True)
    local_policy = gov_dir / POLICY_FILENAME
    local_policy.write_text("$0\n", encoding="utf-8")

    assert _resolve_policy_path(project_root) == local_policy


def test_learning_preview_hash_is_stable() -> None:
    diff = "--- before\n+++ after\n+session summary"

    assert _preview_hash(diff) == _preview_hash(diff)
    assert _preview_hash(diff) != _preview_hash(diff + "\nchanged")


def test_learning_validation_blocks_empty_or_placeholder_payload() -> None:
    problems = _validate_elevation_payload(
        "SES",
        {"input": "", "output": "", "outcome": "elevated_outcome"},
        '+SES:current{input:"", output:"", outcome:"elevated_outcome", date:""}',
    )

    assert "proposed elevation contains empty fields" in problems
    assert "proposed elevation contains generic or placeholder content" in problems


def test_learn_elevate_handler_passes_confirm_hash(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    gov_dir = project_root / ARQUX_DIR
    gov_dir.mkdir(parents=True)
    (gov_dir / "brain.cortex").write_text("$0\n", encoding="utf-8")
    seen = {}

    def fake_elevate_candidate(root, candidate_id, *, dry_run=True, confirm_hash=None):
        seen["root"] = root
        seen["candidate_id"] = candidate_id
        seen["dry_run"] = dry_run
        seen["confirm_hash"] = confirm_hash
        return {
            "mode": "applied",
            "diff": "+approved",
            "candidate": candidate_id,
            "preview_hash": "abc123",
        }

    monkeypatch.setattr("arqux.learning.elevate_candidate", fake_elevate_candidate)

    result = cortex.learn_elevate_handler(
        "cand_001",
        path=str(project_root),
        apply=True,
        confirm_hash="abc123",
    )

    assert "learn.elevate applied" in result.to_text()
    assert seen == {
        "root": project_root,
        "candidate_id": "cand_001",
        "dry_run": False,
        "confirm_hash": "abc123",
    }
