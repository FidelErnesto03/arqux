"""Tests for the `cycle` module."""

from __future__ import annotations

import os
from pathlib import Path

from arqux.handlers import cycle, project, workspace


def _setup_project(workspace_root: Path, governor_ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))
    return project_dir


def test_cycle_create_assigns_sequential_id(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        r1 = cycle.create_cycle(name="First cycle")
        r2 = cycle.create_cycle(name="Second cycle")
        assert "id=CYCLE-01" in r1.to_text()
        assert "id=CYCLE-02" in r2.to_text()
    finally:
        os.chdir(cwd)


def test_cycle_list_returns_all(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="A")
        cycle.create_cycle(name="B")
        result = cycle.list_cycles()
        text = result.to_text()
        assert "CYCLE-01" in text
        assert "CYCLE-02" in text
        assert "cycles=2" in text
    finally:
        os.chdir(cwd)


def test_cycle_current_returns_latest(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="A")
        cycle.create_cycle(name="B")
        result = cycle.current_cycle()
        assert "open_cycles=" in result.to_text()
        assert "CYCLE-02" in result.to_text()
        assert "CYCLE-01" in result.to_text()
        assert "count=2" in result.to_text()
        assert "latest=CYCLE-02" in result.to_text()
    finally:
        os.chdir(cwd)


def test_cycle_close_changes_status(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="A")
        result = cycle.close_cycle(cycle_id="CYCLE-01", summary="done")
        text = result.to_text()
        assert "status=closed" in text
        assert "learning_scan=" in text
        assert "learning_candidates=" in text
    finally:
        os.chdir(cwd)
