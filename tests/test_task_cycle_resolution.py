"""Regression tests for task cycle resolution (BLP-006).

Issue 2026-07-19-task-cycle-resolution: task.create ignored the requested
cycle and task.read returned the first alphabetical match across ALL
cycles. The remaining defect: without a derivable cycle, lookups must
prefer the project's current cycle and report TASK_AMBIGUOUS when the
task_id exists in several other cycles — never silently pick one.
"""

from __future__ import annotations

import os
from pathlib import Path

from arqux.constants import ARQUX_DIR
from arqux.handlers import cycle, project, task, workspace


def _setup_project(workspace_root: Path, governor_ctx, cycles: int = 1) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))
    cwd = os.getcwd()
    os.chdir(project_dir)
    for i in range(cycles):
        cycle.create_cycle(name=f"Test cycle {i + 1}")
    os.chdir(cwd)
    return project_dir


def _tasks_dir(project_dir: Path, cycle_id: str) -> Path:
    return project_dir / ARQUX_DIR / "cycles" / cycle_id / "tasks"


def test_create_task_respects_explicit_cycle(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx, cycles=2)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = task.create_task(obj="In first cycle", cycle="CYCLE-01", ctx=governor_ctx)
        assert "cycle=CYCLE-01" in result.to_text()
        assert (_tasks_dir(project_dir, "CYCLE-01") / "T-001.cortex").exists()
        assert not (_tasks_dir(project_dir, "CYCLE-02") / "T-001.cortex").exists()
    finally:
        os.chdir(cwd)


def test_read_scoped_by_cycle_path(workspace_root: Path, governor_ctx) -> None:
    """A cycle-scoped path resolves the task in that cycle even with
    duplicate task_ids elsewhere (fix G-7, preserved)."""
    project_dir = _setup_project(workspace_root, governor_ctx, cycles=2)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Task in cycle one", cycle="CYCLE-01", ctx=governor_ctx)
        task.create_task(obj="Task in cycle two", cycle="CYCLE-02", ctx=governor_ctx)
        result = task.read_task(
            task_id="T-001",
            path=str(project_dir / ARQUX_DIR / "cycles" / "CYCLE-01"),
        )
        assert "Task in cycle one" in result.fields["content"]
    finally:
        os.chdir(cwd)


def test_read_prefers_current_cycle_without_cycle_path(workspace_root: Path, governor_ctx) -> None:
    """BLP-006: no derivable cycle -> the project's current cycle wins,
    not the first alphabetical one."""
    project_dir = _setup_project(workspace_root, governor_ctx, cycles=2)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Task in cycle one", cycle="CYCLE-01", ctx=governor_ctx)
        task.create_task(obj="Task in cycle two", cycle="CYCLE-02", ctx=governor_ctx)
        result = task.read_task(task_id="T-001", path=str(project_dir))
        assert "Task in cycle two" in result.fields["content"]
    finally:
        os.chdir(cwd)


def test_read_ambiguous_returns_task_ambiguous(workspace_root: Path, governor_ctx) -> None:
    """BLP-006: task_id in several NON-current cycles -> explicit
    TASK_AMBIGUOUS error listing the candidate cycles."""
    project_dir = _setup_project(workspace_root, governor_ctx, cycles=3)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Dup in cycle one", cycle="CYCLE-01", ctx=governor_ctx)
        task.create_task(obj="Dup in cycle two", cycle="CYCLE-02", ctx=governor_ctx)
        # Current cycle is CYCLE-03 (empty); T-001 lives in two other cycles.
        result = task.read_task(task_id="T-001", path=str(project_dir))
        text = result.to_text()
        assert "TASK_AMBIGUOUS" in text
        assert "CYCLE-01" in text and "CYCLE-02" in text
    finally:
        os.chdir(cwd)


def test_update_ambiguous_returns_task_ambiguous(workspace_root: Path, governor_ctx) -> None:
    """The mutation path (_load_task) reports the same ambiguity instead
    of silently updating the wrong cycle's task."""
    project_dir = _setup_project(workspace_root, governor_ctx, cycles=3)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Dup in cycle one", cycle="CYCLE-01", ctx=governor_ctx)
        task.create_task(obj="Dup in cycle two", cycle="CYCLE-02", ctx=governor_ctx)
        result = task.update_task(task_id="T-001", note="x", ctx=governor_ctx)
        assert "TASK_AMBIGUOUS" in result.to_text()
    finally:
        os.chdir(cwd)


def test_read_single_match_outside_current_resolves(workspace_root: Path, governor_ctx) -> None:
    """A single match in a non-current cycle is still returned."""
    project_dir = _setup_project(workspace_root, governor_ctx, cycles=2)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Only in old cycle", cycle="CYCLE-01", ctx=governor_ctx)
        result = task.read_task(task_id="T-001", path=str(project_dir))
        assert "Only in old cycle" in result.fields["content"]
    finally:
        os.chdir(cwd)
