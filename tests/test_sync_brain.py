"""Tests for ``sync_brain()`` helper — automatic brain.cortex updates.

See BLP-017 for full design.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brain_path(tmp_path: Path) -> Path:
    """Create a minimal brain.cortex and return its path."""
    brain_dir = tmp_path / ".arqux"
    brain_dir.mkdir(parents=True)
    brain = brain_dir / "brain.cortex"
    content = """$0
# Glossary
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# WRK   | work       | attrs      | B | Working        | Current execution
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# OBJ   | objective  | attrs      | H | Working        | Active goal

$2: FOCUS
FCS:current{what:"Initial focus", priority:"medium", status:"current", survive:"work"}

$3: OBJECTIVES
OBJ:main{goal:"Test objective", status:"current", success:"done", survive:"work"}

$8: ACTIVE_CONTEXT
WRK:current{phase:"active", current:"initial state", blocked:"no", survive:"work"}
"""
    brain.write_text(content, encoding="utf-8")
    return brain


@pytest.fixture
def brain_project(tmp_path: Path, brain_path: Path) -> Path:
    """Return project_root for a project with a brain at .arqux/brain.cortex."""
    return brain_path.parent.parent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_sync_brain_updates_wrk(brain_project: Path) -> None:
    """sync_brain() updates WRK:current with the event."""
    from arqux.sync import sync_brain

    sync_brain(
        brain_project,
        "test.event",
        detail="test detail",
    )

    # Re-read brain to verify
    from arqux.state import cortex_read

    result = cortex_read(str(brain_project / ".arqux" / "brain.cortex"))
    wrk_entries = [
        e for s in result["sections"]
        for e in s["entries"]
        if e["sigil"] == "WRK" and e["name"] == "current"
    ]
    assert len(wrk_entries) == 1
    val = wrk_entries[0]["value"]
    assert val["event"] == "test.event"
    assert val["current"] == "test.event: test detail"
    assert val["phase"] == "current"  # BC-2 fix: canonical status


def test_sync_brain_updates_fcs(brain_project: Path) -> None:
    """sync_brain() updates FCS:current when focus= is provided."""
    from arqux.sync import sync_brain

    sync_brain(
        brain_project,
        "blueprint.approve",
        focus="Próximo BLP o cierre de ciclo",
    )

    from arqux.state import cortex_read

    result = cortex_read(str(brain_project / ".arqux" / "brain.cortex"))
    fcs_entries = [
        e for s in result["sections"]
        for e in s["entries"]
        if e["sigil"] == "FCS" and e["name"] == "current"
    ]
    assert len(fcs_entries) == 1
    val = fcs_entries[0]["value"]
    assert val["what"] == "Próximo BLP o cierre de ciclo"
    assert val["event"] == "blueprint.approve"


def test_sync_brain_fail_silent_missing_brain(brain_project: Path) -> None:
    """sync_brain() does not raise when brain.cortex is missing."""
    from arqux.sync import sync_brain

    # Remove brain
    brain = brain_project / ".arqux" / "brain.cortex"
    brain.unlink()

    # Should not raise
    sync_brain(brain_project, "test.event")  # no error


def test_sync_brain_fail_silent_none_path() -> None:
    """sync_brain() does not raise when project_root is None."""
    from arqux.sync import sync_brain

    sync_brain(None, "test.event")  # no error


def test_sync_brain_does_not_change_read_only_handlers() -> None:
    """Verify that handlers that only read do NOT import sync_brain.

    We grep the handler source files for 'from ..sync import' to ensure
    only the intended mutating handlers import it.
    """
    import os

    handler_dir = Path(__file__).resolve().parent.parent / "src" / "arqux" / "handlers"
    read_only_modules = {
        "cortex",  # some cortex handlers are read-write, skip for now
        "session",
        "evidence",  # evidence.read/list are read-only
    }

    for fpath in sorted(handler_dir.glob("*.py")):
        stem = fpath.stem
        if stem.startswith("_"):
            continue
        content = fpath.read_text(encoding="utf-8")
        if "sync_brain" in content:
            # Allow only mutating handlers
            assert stem in {
                "blueprint",
                "project",
                "cycle",
                "task",
                "skill",
                "identity",
                "cortex",
            }, f"{stem}.py imports sync_brain but is not in the approved list"


# ---------------------------------------------------------------------------
# BLP-027: meta-brain template consistency tests
# ---------------------------------------------------------------------------


def test_meta_brain_template_has_dom_arqux() -> None:
    """Template meta-brain.cortex includes $2/DOM:arqux entry (BLP-027)."""
    template_path = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "arqux"
        / "templates"
        / "meta-brain.cortex"
    )
    content = template_path.read_text(encoding="utf-8")
    assert "DOM:arqux" in content, (
        "Template meta-brain.cortex missing DOM:arqux entry required by sync.py"
    )
    assert "$2" in content, (
        "Template meta-brain.cortex missing $2 section required by sync.py"
    )


def test_sync_meta_brain_no_warning(tmp_path: Path, caplog) -> None:
    """_sync_meta_brain() does not produce NotFoundError for DOM:arqux (BLP-027)."""
    import logging

    # Create workspace with meta-brain.cortex from template
    ws_root = tmp_path
    meta_brain = ws_root / "meta-brain.cortex"
    template_path = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "arqux"
        / "templates"
        / "meta-brain.cortex"
    )
    meta_brain.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Create project with brain.cortex
    project_root = ws_root / "test_project"
    arqux_dir = project_root / ".arqux"
    arqux_dir.mkdir(parents=True)
    brain = arqux_dir / "brain.cortex"
    brain.write_text("""$0
# Glossary
# WRK   | work       | attrs      | B | Working        | Current execution
# FCS   | focus      | attrs      | H | Working        | Active attention anchor

$2: FOCUS
FCS:current{what:"Test", priority:"medium", status:"current", survive:"work"}

$8: ACTIVE_CONTEXT
WRK:current{phase:"active", current:"test", blocked:"no", survive:"work"}
""", encoding="utf-8")

    from arqux.sync import _sync_meta_brain

    with caplog.at_level(logging.WARNING):
        _sync_meta_brain(project_root, {"handlers": 10}, "test.event", "2026-01-01T00:00:00Z")

    # Verify no NotFoundError in logs
    not_found_errors = [r for r in caplog.records if "NotFoundError" in r.message]
    assert len(not_found_errors) == 0, (
        f"_sync_meta_brain produced NotFoundError: {not_found_errors}"
    )
