"""Tests for Blueprint learning reminders and gates."""

from __future__ import annotations

import os
import re
from pathlib import Path

from arqux.handlers import blueprint, cycle, project, workspace


def _setup_blueprint(workspace_root: Path, governor_ctx) -> tuple[Path, Path]:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir), ctx=governor_ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="A", ctx=governor_ctx)
        manifest = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "MANIFEST.md"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace('status: "draft"', 'status: "ready"', 1),
            encoding="utf-8",
        )
        result = blueprint.create_blueprint(obj="Learning test", ctx=governor_ctx)
    finally:
        os.chdir(cwd)

    return project_dir, Path(result.fields["path"])


def _set_frontmatter_status(path: Path, status: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace('status: "draft"', f'status: "{status}"', 1)
    path.write_text(text, encoding="utf-8")


def _set_all_quality_gates(path: Path, value: bool) -> None:
    text = path.read_text(encoding="utf-8")
    replacement = "true," if value else "false,"
    for gate in [
        "has_clear_objective",
        "has_verifiable_preconditions",
        "has_scope_and_exclusions",
        "has_acceptance_criteria",
        "has_work_procedure",
        "has_required_validations",
        "has_learning_recorded",
    ]:
        text = re.sub(
            rf"({gate}:\s*)(true|false),",
            rf"\1{replacement}",
            text,
            count=1,
        )
    path.write_text(text, encoding="utf-8")


def _mark_all_acceptance_criteria(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"- \[ \] \*\*(AC-\d+):\*\*", r"- [x] **\1:**", text)
    path.write_text(text, encoding="utf-8")


def test_blueprint_task_completed_returns_learning_instruction(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "in_progress")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.task_blueprint("BLP-001", "T-1.1", "completed", evidence="done")
    finally:
        os.chdir(cwd)

    assert "instruction=" in result.to_text()
    assert "identity.record" in result.to_text()


def test_blueprint_ac_failed_returns_learning_instruction(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "in_progress")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.ac_blueprint("BLP-001", "AC-01", "failed", reason="not enough evidence")
    finally:
        os.chdir(cwd)

    assert "instruction=" in result.to_text()
    assert "identity.record" in result.to_text()


def test_blueprint_update_section_returns_learning_instruction(workspace_root: Path, governor_ctx) -> None:
    project_dir, _ = _setup_blueprint(workspace_root, governor_ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.update_blueprint("BLP-001", section="§3", content="Updated preconditions")
    finally:
        os.chdir(cwd)

    assert "instruction=" in result.to_text()
    assert "identity.record" in result.to_text()


def test_blueprint_ready_blocks_when_learning_gate_false(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "maturing")
    _set_all_quality_gates(bp_path, True)
    text = bp_path.read_text(encoding="utf-8").replace("has_learning_recorded: true,", "has_learning_recorded: false,", 1)
    bp_path.write_text(text, encoding="utf-8")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.ready_blueprint("BLP-001")
    finally:
        os.chdir(cwd)

    assert "code=LEARNING_NOT_RECORDED" in result.to_text()
    assert "identity.record" in result.to_text()


def test_blueprint_gate_approves_maturation_gates(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "maturing")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.gate_blueprint("BLP-001", gate="all")
        ready = blueprint.ready_blueprint("BLP-001")
    finally:
        os.chdir(cwd)

    assert "blueprint.gate ok" in result.to_text()
    assert "code=LEARNING_NOT_RECORDED" in ready.to_text()
    text = bp_path.read_text(encoding="utf-8")
    assert "has_clear_objective: true" in text
    assert "has_learning_recorded" in text


def test_blueprint_gate_blocks_learning_without_recorded_evidence(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "maturing")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.gate_blueprint("BLP-001", gate="has_learning_recorded")
    finally:
        os.chdir(cwd)

    assert "code=LEARNING_NOT_RECORDED" in result.to_text()


def test_blueprint_ready_accepts_recorded_learning_for_legacy_gate(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "maturing")
    _set_all_quality_gates(bp_path, True)
    text = bp_path.read_text(encoding="utf-8").replace("has_learning_recorded: true,", "has_learning_recorded: false,", 1)
    bp_path.write_text(text, encoding="utf-8")

    identity = workspace_root / ".arqux" / "identities" / "alfred.cortex"
    identity.write_text(
        identity.read_text(encoding="utf-8")
        + '\nLNG:blp_001{type:"process", cause:"BLP-001 test", lesson:"BLP-001 learning recorded"}\n',
        encoding="utf-8",
    )

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.ready_blueprint("BLP-001")
    finally:
        os.chdir(cwd)

    assert "blueprint.ready ok" in result.to_text()


def test_blueprint_complete_blocks_pending_tasks(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "in_progress")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.complete_blueprint("BLP-001", evidence="tests passed")
    finally:
        os.chdir(cwd)

    assert "code=EXECUTION_INCOMPLETE" in result.to_text()
    assert "missing_tasks=" in result.to_text()


def test_blueprint_approve_blocks_unverified_acceptance_criteria(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "review")
    _set_all_quality_gates(bp_path, True)

    identity = workspace_root / ".arqux" / "identities" / "alfred.cortex"
    identity.write_text(
        identity.read_text(encoding="utf-8")
        + '\nLNG:blp_001{type:"process", cause:"BLP-001 test", lesson:"BLP-001 learning recorded"}\n',
        encoding="utf-8",
    )

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.approve_blueprint("BLP-001")
    finally:
        os.chdir(cwd)

    assert "code=APPROVAL_INCOMPLETE" in result.to_text()
    assert "missing_acceptance_criteria=" in result.to_text()


def test_blueprint_approve_requires_learning_gate_and_returns_instruction(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "review")
    _set_all_quality_gates(bp_path, True)
    _mark_all_acceptance_criteria(bp_path)
    identity = workspace_root / ".arqux" / "identities" / "alfred.cortex"
    identity.write_text(
        identity.read_text(encoding="utf-8")
        + '\nLNG:blp_001{type:"process", cause:"BLP-001 approval", lesson:"BLP-001 learning recorded"}\n',
        encoding="utf-8",
    )

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.approve_blueprint("BLP-001")
    finally:
        os.chdir(cwd)

    assert "blueprint.approve ok" in result.to_text()
    assert "identity.record" in result.to_text()


def test_blueprint_template_contains_learning_gate() -> None:
    template = Path("src/arqux/templates/BLP_TEMPLATE.md").read_text(encoding="utf-8")
    assert "has_learning_recorded: false" in template
    assert "| has_learning_recorded |" in template


def test_blueprint_create_replaces_visible_title(workspace_root: Path, governor_ctx) -> None:
    _, bp_path = _setup_blueprint(workspace_root, governor_ctx)

    text = bp_path.read_text(encoding="utf-8")

    assert "# BLP-001: Learning test" in text
    assert "# BLP-NNN: Title" not in text


def test_blueprint_update_preserves_section_title(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        blueprint.update_blueprint("BLP-001", section="§1", content="Updated problem")
    finally:
        os.chdir(cwd)

    text = bp_path.read_text(encoding="utf-8")
    assert "## §1: Problem Statement" in text
    assert "## §1:\n\nUpdated problem" not in text


def test_blueprint_update_no_header_duplication(workspace_root: Path, governor_ctx) -> None:
    """Multiple updates to the same section must not create duplicate headers."""
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        blueprint.update_blueprint("BLP-001", section="§1", content="First update")
        blueprint.update_blueprint("BLP-001", section="§1", content="Second update")
    finally:
        os.chdir(cwd)

    text = bp_path.read_text(encoding="utf-8")
    # The header must appear exactly once
    assert text.count("## §1: Problem Statement") == 1
    assert "Second update" in text
    # Verify no raw header remnants
    assert text.count("## §1:\n") == 0
