"""Tests for the `project` module.

Project sessions now live INSIDE the project brain's SESSIONS section,
not in a separate `bindings.cortex` file. These tests verify that.
"""

from __future__ import annotations

import os
from pathlib import Path

from arqux.constants import ARQUX_DIR, BRAIN_CORTEX
from arqux.handlers import project, workspace


def test_project_init_creates_local_governance(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)

    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    result = project.init_project(name="my-app", path=str(project_dir))

    gov = project_dir / ARQUX_DIR
    assert (gov / BRAIN_CORTEX).exists()
    assert "project.init ok" in result.to_text()


def test_project_bind_writes_session_to_brain(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = project.bind(agent_id="ex-1", role="executor")
        # The session should be in brain.cortex, NOT in bindings.cortex.
        brain_text = (project_dir / ARQUX_DIR / BRAIN_CORTEX).read_text(encoding="utf-8")
        assert "$4: SESSIONS" in brain_text
        assert "agent=ex-1" in brain_text or "SES:ex_1" in brain_text
        assert "role=executor" in brain_text or "executor" in brain_text
        # No bindings.cortex file should exist.
        assert not (project_dir / ARQUX_DIR / "bindings.cortex").exists()
        assert "brain" in result.to_text()
    finally:
        os.chdir(cwd)


def test_project_unbind_marks_session_released_in_brain(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        project.bind(agent_id="ex-1", role="executor")
        project.bind(agent_id="ex-2", role="executor")
        project.unbind(agent_id="ex-1")
        brain_text = (project_dir / ARQUX_DIR / BRAIN_CORTEX).read_text(encoding="utf-8")
        # ex-1 should be marked as released (history preserved).
        assert "SES:ex_1" in brain_text or "agent=ex-1" in brain_text
        assert "released" in brain_text
        # ex-2 should still be active.
        assert "SES:ex_2" in brain_text or "agent=ex-2" in brain_text
        assert "active" in brain_text
    finally:
        os.chdir(cwd)


def test_project_status_reports_brain_version(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        project.bind(agent_id="ex-1", role="executor")
        result = project.status()
        text = result.to_text()
        # After one bind, brain_version should be 1 (one mutation).
        assert "brain_version=1" in text
        assert "active_agents=1" in text
    finally:
        os.chdir(cwd)


def test_project_lessons_returns_contextual_kind(workspace_root: Path, governor_ctx) -> None:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = project.lessons()
        text = result.to_text()
        assert "contextual" in text
        # Behavioral lessons live in identity .cortex, not here.
        assert "behavioral" in text
    finally:
        os.chdir(cwd)
