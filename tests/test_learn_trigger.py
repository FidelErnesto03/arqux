"""Tests for cortex.learn auto-trigger on identity.record."""

from __future__ import annotations

import os
from pathlib import Path

from arqux.handlers import cortex, project, workspace


def _setup_project(workspace_root: Path, ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir), ctx=ctx)
    # Create identity file for the test agent so record_lesson_handler can find it
    identity_dir = workspace_root / ".arqux" / "identities"
    identity_dir.mkdir(parents=True, exist_ok=True)
    identity_file = identity_dir / f"{ctx.agent_id}.cortex"
    identity_file.write_text(
        "$0\n"
        "# -- $0: IDENTITY GLOSSARY --\n"
        "# IDN   | identity   | attrs      | B | Semantic | Agent identity\n"
        "# LNG   | lesson     | attrs      | M | Episodic | Behavioral lessons\n"
        "\n"
        "$1: IDENTITY\n"
        "IDN:test_governor{name:\"test-governor\", role:\"governor\"}\n"
        "\n"
        "$5: BEHAVIORAL LESSONS\n",
        encoding="utf-8",
    )
    return project_dir


def _run_in_project(project_dir: Path, fn, *args, **kwargs):
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        return fn(*args, **kwargs)
    finally:
        os.chdir(cwd)


def test_learn_auto_trigger_on_record(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    result = _run_in_project(
        project_dir,
        cortex.record_lesson_handler,
        lesson="Auto-trigger test lesson",
        kind="behavioral",
        agent_id="test-governor",
        ctx=governor_ctx,
        path=str(project_dir),
    )
    assert result.profile == "OUT-WORK"
    assert "learning_candidates" in result.fields or "hint" in result.fields


def test_learn_scan_detects_patterns(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    for i in range(3):
        _run_in_project(
            project_dir,
            cortex.record_lesson_handler,
            lesson=f"Pattern lesson {i}",
            kind="behavioral",
            agent_id="test-governor",
            path=str(project_dir),
        )
    result = _run_in_project(
        project_dir,
        cortex.learn_scan_handler,
        scope="project",
        path=str(project_dir),
    )
    assert result.profile == "OUT-WORK"
    candidates = result.fields.get("candidates", [])
    assert isinstance(candidates, list)


def test_learn_elevate_writes_knw(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    for i in range(3):
        _run_in_project(
            project_dir,
            cortex.record_lesson_handler,
            lesson=f"Elevate test {i}",
            kind="behavioral",
            agent_id="test-governor",
            path=str(project_dir),
        )
    scan = _run_in_project(
        project_dir,
        cortex.learn_scan_handler,
        scope="project",
        path=str(project_dir),
    )
    candidates = scan.fields.get("candidates", [])
    if candidates:
        cid = candidates[0]["id"]
        dry = _run_in_project(
            project_dir,
            cortex.learn_elevate_handler,
            candidate_id=cid,
            path=str(project_dir),
            apply=False,
        )
        assert dry.profile == "OUT-WORK"
        assert dry.fields.get("mode") == "dry_run"
        assert dry.fields.get("preview_hash")


def test_learn_no_pattern_silent(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    _run_in_project(
        project_dir,
            cortex.record_lesson_handler,
            lesson="Single lesson",
            kind="behavioral",
            agent_id="test-governor",
        path=str(project_dir),
    )
    scan = _run_in_project(
        project_dir,
        cortex.learn_scan_handler,
        scope="project",
        path=str(project_dir),
    )
    assert scan.profile == "OUT-WORK"
