"""Regression tests for sync_brain (P0-A).

Validates that:
- sync_brain with metrics does NOT emit NotFoundError for $2/DOM:arqux
- meta-brain.cortex copied from template contains $2/DOM:arqux entry
- write_meta_brain does NOT overwrite template-rich meta-brain
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from arqux.handlers.workspace import init_workspace
from arqux.handlers.project import init_project
from arqux.sync import sync_brain


@pytest.fixture
def fresh_workspace(tmp_path: Path) -> Path:
    """Initialize a fresh workspace and return its .arqux path."""
    init_workspace(path=str(tmp_path))
    return tmp_path / ".arqux"


@pytest.fixture
def workspace_with_project(tmp_path: Path) -> Path:
    """Initialize a workspace AND a project (so brain.cortex exists)."""
    init_workspace(path=str(tmp_path))
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    init_project(name="myproject", path=str(project_dir))
    return project_dir / ".arqux"


class TestSyncBrainRegression:
    """P0-A: sync_brain must not fail with NotFoundError for $2/DOM:arqux."""

    def test_meta_brain_template_contains_dom_arqux(self, fresh_workspace: Path) -> None:
        """After init, meta-brain.cortex must contain $2/DOM:arqux entry."""
        meta_brain = fresh_workspace / "meta-brain.cortex"
        assert meta_brain.exists(), "meta-brain.cortex not created"
        content = meta_brain.read_text(encoding="utf-8")
        assert "DOM:arqux" in content, (
            "meta-brain.cortex does not contain $2/DOM:arqux entry. "
            "write_meta_brain likely overwrote the template."
        )

    def test_sync_brain_with_metrics_does_not_warn(
        self,
        workspace_with_project: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """sync_brain with metrics must not emit ERROR for $2/DOM:arqux."""
        with caplog.at_level(logging.ERROR, logger="arqux.sync"):
            sync_brain(
                workspace_with_project,
                "test.event",
                focus="testing",
                metrics={"tasks_done": 1, "handlers": 73, "cycles_closed": 0},
            )
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        dom_errors = [r for r in errors if "DOM:arqux" in r.getMessage()]
        assert not dom_errors, (
            f"sync_brain emitted DOM:arqux error: {[r.getMessage() for r in dom_errors]}"
        )

    def test_sync_brain_updates_dom_arqux_metrics(
        self,
        workspace_with_project: Path,
    ) -> None:
        """sync_brain should successfully update $2/DOM:arqux with metrics."""
        sync_brain(
            workspace_with_project,
            "test.event",
            focus="testing",
            metrics={"handlers": 73, "tasks_done": 5, "cycles_closed": 1},
        )
        # sync_brain updates the meta-brain at the workspace level, which is
        # the parent of workspace_with_project (which is project-level .arqux).
        # Find meta-brain: walk up from workspace_with_project.
        meta_brain = None
        for p in [workspace_with_project.parent.parent, workspace_with_project.parent]:
            candidate = p / ".arqux" / "meta-brain.cortex"
            if candidate.exists():
                meta_brain = candidate
                break
        if meta_brain is None:
            # Try direct path
            meta_brain = workspace_with_project.parent.parent / ".arqux" / "meta-brain.cortex"
        assert meta_brain.exists(), f"meta-brain not found at {meta_brain}"
        content = meta_brain.read_text(encoding="utf-8")
        # sync_brain should have updated the DOM:arqux entry — the "73" handlers
        # count should appear in the meta-brain.
        # Note: if sync_brain silently failed (pre-P0-A fix), this would not be present.
        assert "73" in content, (
            "handlers count 73 not synced to meta-brain — sync_brain may have failed silently"
        )

    def test_sync_brain_idempotent_across_calls(
        self,
        workspace_with_project: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Multiple sync_brain calls should not produce errors."""
        with caplog.at_level(logging.ERROR, logger="arqux.sync"):
            for i in range(3):
                sync_brain(
                    workspace_with_project,
                    f"event.{i}",
                    focus=f"iteration-{i}",
                    metrics={"handlers": 73, "tasks_done": i},
                )
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert not errors, f"sync_brain emitted errors on iteration: {[r.getMessage() for r in errors]}"

    def test_init_workspace_preserves_template_richness(self, tmp_path: Path) -> None:
        """Fresh workspace meta-brain should preserve template sections."""
        init_workspace(path=str(tmp_path))
        meta_brain = tmp_path / ".arqux" / "meta-brain.cortex"
        content = meta_brain.read_text(encoding="utf-8")
        # Template contains these sections — write_meta_brain's minimal version omits them.
        assert "$0" in content, "glossary section missing"
        assert "$1" in content or "$1:" in content, "META-BRAIN section missing"
        assert "$2" in content or "$2:" in content, "PROJECTS section missing"
        assert "DOM:arqux" in content, "DOM:arqux entry missing"
