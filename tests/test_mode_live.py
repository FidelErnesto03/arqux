"""Tests for blueprint.mature mode='live'."""

from __future__ import annotations

import os
import re
from pathlib import Path

from arqux.handlers import blueprint, cycle, project, workspace


def _setup_blueprint(workspace_root: Path, ctx) -> tuple[Path, str]:
    workspace.init_workspace(path=str(workspace_root), ctx=ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir), ctx=ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="TestCycle", ctx=ctx)
        manifest = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "MANIFEST.md"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace('status: "draft"', 'status: "ready"', 1),
            encoding="utf-8",
        )
        result = blueprint.create_blueprint(obj="Mode live test", ctx=ctx)
        bp_id = result.fields["blueprint_id"]
    finally:
        os.chdir(cwd)

    return project_dir, bp_id


def _set_status(path: Path, status: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'status:\s*"[^"]*"', f'status: "{status}"', text, count=1)
    path.write_text(text, encoding="utf-8")


def _run_in_project(project_dir: Path, fn, *args, **kwargs):
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        return fn(*args, **kwargs)
    finally:
        os.chdir(cwd)


def test_mature_mode_live_accepted(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "draft")
    result = _run_in_project(
        project_dir,
        blueprint.mature_blueprint,
        bp_id=bp_id,
        mode="live",
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("mode") == "live"


def test_mature_mode_async_default(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "draft")
    result = _run_in_project(
        project_dir,
        blueprint.mature_blueprint,
        bp_id=bp_id,
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("mode") == "async"


def test_mature_invalid_mode_rejected(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "draft")
    result = _run_in_project(
        project_dir,
        blueprint.mature_blueprint,
        bp_id=bp_id,
        mode="invalid",
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-ERROR"
    assert "invalid" in result.message


def test_mature_live_transitions(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "draft")
    _run_in_project(
        project_dir,
        blueprint.mature_blueprint,
        bp_id=bp_id,
        mode="live",
        ctx=governor_ctx,
    )
    assert bp_path.read_text(encoding="utf-8").count("maturing") > 0
