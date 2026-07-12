"""Tests for the `task` module.

Task completion and failure now record evidence in the project brain's
PULSE section, not in a separate `pulse.jsonl` file.
"""

from __future__ import annotations

import os
from pathlib import Path

from arqux.constants import ARQUX_DIR, BRAIN_CORTEX
from arqux.handlers import cycle, project, task, workspace


def _setup_with_cycle(workspace_root: Path, governor_ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))
    cwd = os.getcwd()
    os.chdir(project_dir)
    cycle.create_cycle(name="Test cycle")
    os.chdir(cwd)
    return project_dir


def test_task_create_assigns_sequential_id(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_with_cycle(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        r1 = task.create_task(obj="First task", ctx=governor_ctx)
        r2 = task.create_task(obj="Second task", ctx=governor_ctx)
        assert "id=T-001" in r1.to_text()
        assert "id=T-002" in r2.to_text()
    finally:
        os.chdir(cwd)


def test_task_claim_transitions_to_in_progress(workspace_root: Path, governor_ctx, executor_ctx) -> None:
    project_dir = _setup_with_cycle(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Do thing", assignee="test-executor", ctx=governor_ctx)
        result = task.claim_task(task_id="T-001", ctx=executor_ctx)
        assert "status=in_progress" in result.to_text()
    finally:
        os.chdir(cwd)


def test_task_complete_records_evidence_in_brain(workspace_root: Path, governor_ctx, executor_ctx) -> None:
    project_dir = _setup_with_cycle(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Do thing", assignee="test-executor", ctx=governor_ctx)
        task.claim_task(task_id="T-001", ctx=executor_ctx)
        result = task.complete_task(task_id="T-001", evidence="tests pass", ctx=executor_ctx)
        assert "status=done" in result.to_text()
        assert "brain PULSE" in result.to_text()
        # The evidence should be in brain.cortex, NOT in pulse.jsonl.
        brain_text = (project_dir / ARQUX_DIR / BRAIN_CORTEX).read_text(encoding="utf-8")
        assert "$6: PULSE" in brain_text
        assert "task_complete" in brain_text
        assert "tests pass" in brain_text
        assert not (project_dir / ARQUX_DIR / "cycles" / "CYCLE-01" / "pulse.jsonl").exists()
    finally:
        os.chdir(cwd)


def test_task_fail_records_cause_in_brain(workspace_root: Path, governor_ctx, executor_ctx) -> None:
    project_dir = _setup_with_cycle(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Do thing", assignee="test-executor", ctx=governor_ctx)
        task.claim_task(task_id="T-001", ctx=executor_ctx)
        result = task.fail_task(task_id="T-001", reason="missing dependency", ctx=executor_ctx)
        assert "status=blocked" in result.to_text()
        assert "brain PULSE" in result.to_text()
        # The cause should be in brain.cortex.
        brain_text = (project_dir / ARQUX_DIR / BRAIN_CORTEX).read_text(encoding="utf-8")
        assert "task_block" in brain_text
        assert "missing dependency" in brain_text
    finally:
        os.chdir(cwd)


def test_task_list_returns_all(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_with_cycle(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="A", ctx=governor_ctx)
        task.create_task(obj="B", ctx=governor_ctx)
        result = task.list_tasks()
        text = result.to_text()
        assert "T-001" in text
        assert "T-002" in text
    finally:
        os.chdir(cwd)


def test_task_read_returns_content(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_with_cycle(workspace_root, governor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        task.create_task(obj="Hello world", ctx=governor_ctx)
        result = task.read_task(task_id="T-001")
        assert "task.read ok" in result.to_text()
    finally:
        os.chdir(cwd)
