"""Degradation tests (BLP-002 T-2.11).

Pinning the contract: when the engine cannot operate, callers get a
*typed* cause — never a silently-empty result.
"""
from __future__ import annotations

from pathlib import Path

from arqux.core import learning
from arqux.core.learning import _common


def test_available_returns_tuple():
    ok, cause = _common.learning_engine_available()
    assert ok is True
    assert cause is None


def test_scan_brain_with_memory_brain_available(tmp_path: Path):
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()
    # Brain missing entirely => engine still reports the unavailable state.
    brain = arqux_dir / "brain.cortex"
    brain.write_text("$0\n\n$1: IDENTITY\nWRK:fake{}\n", encoding="utf-8")
    result = learning.scan_brain(tmp_path, verbose=False)
    assert result.get("engine") in {"available", "unavailable"}
    if result.get("engine") == "unavailable":
        assert "error" in result or "cause" in result


def test_elevation_without_brain_returns_typed_error(tmp_path: Path):
    result = learning.elevate_candidate(tmp_path, "candidate:never", dry_run=True)
    # Either a real candidate id from an empty-context scan (not possible) or an explicit error.
    assert "error" in result
