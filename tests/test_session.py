"""Tests for session handlers: close, resume, status."""

from __future__ import annotations

import os
from pathlib import Path

from arqux.handlers import project, session, workspace


def _setup_project(workspace_root: Path, ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir), ctx=ctx)
    return project_dir


def _run_in_project(project_dir: Path, fn, *args, **kwargs):
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        return fn(*args, **kwargs)
    finally:
        os.chdir(cwd)


def test_session_close_creates_ses(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    result = _run_in_project(
        project_dir,
        session.close,
        summary="Test session",
        blps="BLP-001,BLP-002",
        tasks="T-001",
        decisions="Use pytest",
        gaps="Missing docs",
    )
    assert result.profile == "OUT-WORK"
    assert result.fields["event_id"] is not None
    assert result.fields["size_bytes"] < 2048


def test_session_resume_reads_ses(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    _run_in_project(
        project_dir,
        session.close,
        summary="Resume test",
        blps="BLP-003",
    )
    result = _run_in_project(project_dir, session.resume)
    assert result.profile == "OUT-WORK"
    assert result.fields["summary"] == "Resume test"
    assert "BLP-003" in result.fields.get("blps", [])


def test_session_status_metadata(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    _run_in_project(
        project_dir,
        session.close,
        summary="Status test",
        blps="BLP-001",
        tasks="T-001,T-002",
    )
    result = _run_in_project(project_dir, session.status)
    assert result.profile == "OUT-WORK"
    assert result.fields["blp_count"] == 1
    assert result.fields["task_count"] == 2


def test_session_ses_under_2kb(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    result = _run_in_project(
        project_dir,
        session.close,
        summary="A" * 2000,
    )
    assert result.profile == "OUT-ERROR"
    assert "2KB" in result.message


def test_session_close_no_blps(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    result = _run_in_project(
        project_dir,
        session.close,
        summary="Minimal session",
    )
    assert result.profile == "OUT-WORK"
    assert result.fields["event_id"] is not None


def test_session_resume_no_prior_ses(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    result = _run_in_project(project_dir, session.resume)
    assert result.profile == "OUT-ERROR"
    assert "no previous session" in result.message


def test_session_close_no_project(workspace_root: Path, governor_ctx) -> None:
    result = session.close(summary="orphan", path=str(workspace_root))
    assert result.profile == "OUT-ERROR"


def test_session_status_no_project(workspace_root: Path, governor_ctx) -> None:
    result = session.status(path=str(workspace_root))
    assert result.profile == "OUT-ERROR"
