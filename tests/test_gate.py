"""Tests for blueprint.gate handler."""

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
        result = blueprint.create_blueprint(obj="Gate test", ctx=ctx)
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


def test_gate_approve_single(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "maturing")
    _run_in_project(
        project_dir,
        blueprint.gate_blueprint,
        bp_id=bp_id,
        gate="has_clear_objective",
        ctx=governor_ctx,
    )
    text = bp_path.read_text(encoding="utf-8")
    assert "has_clear_objective: true" in text


def test_gate_invalid_state(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "ready")
    result = _run_in_project(
        project_dir,
        blueprint.gate_blueprint,
        bp_id=bp_id,
        gate="has_clear_objective",
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-ERROR"
    assert "must be maturing" in result.message


def test_gate_all_approved(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "maturing")
    result = _run_in_project(
        project_dir,
        blueprint.gate_blueprint,
        bp_id=bp_id,
        gate="all",
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-WORK" or "learning" in result.message


def test_gate_unknown_gate_rejected(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_id = _setup_blueprint(workspace_root, governor_ctx)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    _set_status(bp_path, "maturing")
    result = _run_in_project(
        project_dir,
        blueprint.gate_blueprint,
        bp_id=bp_id,
        gate="nonexistent_gate",
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-ERROR"
    assert "unknown" in result.message


def test_gate_invalid_bp_id(workspace_root: Path, governor_ctx) -> None:
    project_dir, _ = _setup_blueprint(workspace_root, governor_ctx)
    result = _run_in_project(
        project_dir,
        blueprint.gate_blueprint,
        bp_id="BLP-999",
        gate="has_clear_objective",
        ctx=governor_ctx,
    )
    assert result.profile == "OUT-ERROR"
