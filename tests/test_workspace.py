"""Tests for the `workspace` module."""

from __future__ import annotations

from pathlib import Path

from arqux.constants import ARQUX_DIR
from arqux.handlers import workspace


def test_workspace_init_creates_governance_directory(workspace_root: Path, governor_ctx) -> None:
    result = workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    gov_dir = workspace_root / ARQUX_DIR
    assert gov_dir.exists()
    assert (gov_dir / "meta-brain.cortex").exists()
    assert (gov_dir / "meta-brain.cortex").exists()
    assert (gov_dir / "projects.cortex").exists()
    assert "workspace.init ok" in result.to_text()


def test_workspace_status_returns_not_found_when_uninitialized(workspace_root: Path) -> None:
    import os
    cwd = os.getcwd()
    try:
        os.chdir(workspace_root)
        result = workspace.status()
        assert "NOT_FOUND" in result.to_text()
    finally:
        os.chdir(cwd)


def test_workspace_status_returns_ok_after_init(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    import os
    cwd = os.getcwd()
    try:
        os.chdir(workspace_root)
        result = workspace.status()
        assert "meta_brain=true" in result.to_text()
    finally:
        os.chdir(cwd)


def test_workspace_lessons_returns_not_found_when_uninitialized(workspace_root: Path) -> None:
    import os
    cwd = os.getcwd()
    try:
        os.chdir(workspace_root)
        result = workspace.lessons()
        assert "NOT_FOUND" in result.to_text()
    finally:
        os.chdir(cwd)
