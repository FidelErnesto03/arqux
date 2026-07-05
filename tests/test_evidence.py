"""Tests for the `evidence` module.

Evidence (pulse) entries now live INSIDE the project brain's PULSE section,
not in a separate `pulse.jsonl` file. These tests verify that.
"""

from __future__ import annotations

import os
from pathlib import Path

from arqux.constants import BRAIN_CORTEX, ARQUX_DIR
from arqux.handlers import cycle, evidence, project, task, workspace


def _setup_with_task(workspace_root: Path, governor_ctx, executor_ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))
    cwd = os.getcwd()
    os.chdir(project_dir)
    cycle.create_cycle(name="C")
    task.create_task(obj="Do thing", assignee="test-executor", ctx=governor_ctx)
    task.claim_task(task_id="T-001", ctx=executor_ctx)
    os.chdir(cwd)
    return project_dir


def test_evidence_record_writes_to_brain_pulse(workspace_root: Path, governor_ctx, executor_ctx) -> None:
    project_dir = _setup_with_task(workspace_root, governor_ctx, executor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = evidence.record_evidence(
            task_id="T-001", kind="note", payload="halfway done", ctx=executor_ctx,
        )
        assert "evidence.record ok" in result.to_text()
        # The pulse entry should be in brain.cortex, NOT in pulse.jsonl.
        brain_path = project_dir / ARQUX_DIR / BRAIN_CORTEX
        brain_text = brain_path.read_text(encoding="utf-8")
        assert "$6: PULSE" in brain_text
        assert "halfway done" in brain_text
        # No pulse.jsonl file should exist anymore.
        assert not (project_dir / ARQUX_DIR / "cycles" / "CYCLE-01" / "pulse.jsonl").exists()
    finally:
        os.chdir(cwd)


def test_evidence_list_reads_from_brain(workspace_root: Path, governor_ctx, executor_ctx) -> None:
    project_dir = _setup_with_task(workspace_root, governor_ctx, executor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        evidence.record_evidence(task_id="T-001", kind="note", payload="one", ctx=executor_ctx)
        evidence.record_evidence(task_id="T-001", kind="note", payload="two", ctx=executor_ctx)
        result = evidence.list_evidence(task_id="T-001")
        text = result.to_text()
        assert "events=2" in text
        assert "brain PULSE" in text
    finally:
        os.chdir(cwd)


def test_evidence_read_returns_event(workspace_root: Path, governor_ctx, executor_ctx) -> None:
    project_dir = _setup_with_task(workspace_root, governor_ctx, executor_ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        evidence.record_evidence(task_id="T-001", kind="note", payload="hello", ctx=executor_ctx)
        result = evidence.read_evidence(event_id="E-0001")
        assert "event=E-0001" in result.to_text()
        assert "brain PULSE" in result.to_text()
    finally:
        os.chdir(cwd)
