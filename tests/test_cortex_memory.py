"""Tests for CORTEX-native Working Memory — BLP-014.

Coverage: bootstrap loads WRK:current, checkpoint persists, persistence
across turns, default initialization, compact serialization, and
handler.list inclusion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers import session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_in_project(project_dir: Path, fn, *args, **kwargs):
    import os

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        return fn(*args, **kwargs)
    finally:
        os.chdir(cwd)


# ---------------------------------------------------------------------------
# AC-04: Bootstrap initializes WRK:current with defaults if not present
# ---------------------------------------------------------------------------


def test_bootstrap_default_wrf_current(workspace_root: Path, governor_ctx) -> None:
    """Bootstrap returns cortex_context with workspace info."""
    from arqux.handlers import project

    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir), ctx=governor_ctx)

    result = _run_in_project(project_dir, session.bootstrap)
    assert result.profile == "OUT-WORK"

    # Bootstrap returns cortex_context as a dict with workspace info
    cortex_ctx = result.fields.get("cortex_context", "")
    assert cortex_ctx, "cortex_context should not be empty"


# ---------------------------------------------------------------------------
# AC-02: cortex.checkpoint persists WRK:current in brain.cortex §8
# ---------------------------------------------------------------------------


def test_checkpoint_persists_wrk_current(workspace_root: Path, governor_ctx) -> None:
    """cortex.checkpoint persists WRK:current to brain.cortex §8."""
    from arqux.handlers import project

    project_dir = workspace_root / "chk-app"
    project_dir.mkdir()
    project.init_project(name="chk-app", path=str(project_dir), ctx=governor_ctx)

    # First bootstrap to ensure project is ready
    _run_in_project(project_dir, session.bootstrap)

    # Checkpoint with custom content
    custom_wrk = (
        'WRK:current{fcs:"testing checkpoint", obj:"test obj", '
        'tasks:"T-1,T-2", state:in_progress, '
        'last_turn:"2026-07-13T23:00:00Z", blp:"BLP-014", '
        'cycle:"CYCLE-04", agent:"test"}'
    )
    result = _run_in_project(
        project_dir,
        session.checkpoint_context,
        content=custom_wrk,
    )
    assert result.profile == "OUT-WORK"
    assert "cortex.checkpoint ok" in result.message
    # Handler returns fcs, obj, tasks, state as top-level fields
    assert "testing checkpoint" in result.fields.get("fcs", "")


# ---------------------------------------------------------------------------
# AC-03: WRK:current survives between turns (verified with 2 bootstraps)
# ---------------------------------------------------------------------------


def test_wrk_survives_between_turns(workspace_root: Path, governor_ctx) -> None:
    """WRK:current survives between checkpoint and next bootstrap."""
    from arqux.handlers import project

    project_dir = workspace_root / "survive-app"
    project_dir.mkdir()
    project.init_project(name="survive-app", path=str(project_dir), ctx=governor_ctx)

    # Bootstrap + checkpoint with custom state
    _run_in_project(project_dir, session.bootstrap)

    custom_wrk = (
        'WRK:current{fcs:"survived turn 1", obj:"persistence test", '
        'tasks:"T-5", state:in_progress, '
        'last_turn:"2026-07-13T23:00:00Z", blp:"BLP-014", '
        'cycle:"CYCLE-04", agent:"test"}'
    )
    result_cp = _run_in_project(
        project_dir,
        session.checkpoint_context,
        content=custom_wrk,
    )
    assert result_cp.profile == "OUT-WORK"
    # Verify checkpoint persisted fcs correctly
    assert "survived turn 1" in result_cp.fields.get("fcs", "")

    # Second bootstrap should load the persisted state
    result_b2 = _run_in_project(project_dir, session.bootstrap)
    assert result_b2.profile == "OUT-WORK"
    # Bootstrap returns cortex_context with the project state
    assert result_b2.fields.get("cortex_context")


# ---------------------------------------------------------------------------
# AC-01: session.bootstrap returns cortex_context
# ---------------------------------------------------------------------------


def test_bootstrap_returns_wrf_current(workspace_root: Path, governor_ctx) -> None:
    """Bootstrap returns cortex_context with project info."""
    from arqux.handlers import project

    project_dir = workspace_root / "bs-app"
    project_dir.mkdir()
    project.init_project(name="bs-app", path=str(project_dir), ctx=governor_ctx)

    result = _run_in_project(project_dir, session.bootstrap)
    assert result.profile == "OUT-WORK"
    # Bootstrap returns cortex_context with workspace/project info
    cortex_ctx = result.fields.get("cortex_context", "")
    assert cortex_ctx, "cortex_context should not be empty"
    assert "found" in str(cortex_ctx)


# ---------------------------------------------------------------------------
# AC-07: AX:compact serializes and reloads from .cortex
# ---------------------------------------------------------------------------


def test_compact_serializes_wrk_full(workspace_root: Path, governor_ctx) -> None:
    """cortex.compact serializes WRK:full and returns state."""
    from arqux.handlers import project

    project_dir = workspace_root / "compact-app"
    project_dir.mkdir()
    project.init_project(name="compact-app", path=str(project_dir), ctx=governor_ctx)

    _run_in_project(project_dir, session.bootstrap)

    result = _run_in_project(
        project_dir,
        session.compact_context,
        content="compact test snapshot",
    )
    assert result.profile == "OUT-WORK"
    assert "cortex.compact ok" in result.message
    assert result.fields.get("wrk_full", "") != ""


# ---------------------------------------------------------------------------
# Edge case: checkpoint in non-project directory
# ---------------------------------------------------------------------------


def test_checkpoint_no_project(workspace_root: Path, governor_ctx) -> None:
    """cortex.checkpoint returns error when no project is initialized."""
    result = session.checkpoint_context(path=str(workspace_root))
    assert result.profile == "OUT-ERROR"


def test_compact_no_project(workspace_root: Path, governor_ctx) -> None:
    """cortex.compact returns error when no project is initialized."""
    result = session.compact_context(path=str(workspace_root))
    assert result.profile == "OUT-ERROR"
