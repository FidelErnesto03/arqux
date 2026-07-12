"""Tests for learning-related behavior in the blueprint lifecycle."""

from __future__ import annotations

import os
from pathlib import Path

from arqux.handlers import blueprint, cycle, project, workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_blueprint(workspace_root: Path, ctx) -> tuple[Path, Path]:
    workspace.init_workspace(path=str(workspace_root), ctx=ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir), ctx=ctx)
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="TestCycle", ctx=ctx)
        manifest = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "MANIFEST.md"
        if manifest.exists():
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace('status: "draft"', 'status: "ready"', 1),
                encoding="utf-8",
            )
        result = blueprint.create_blueprint(obj="Learning test", ctx=ctx)
        bp_id = result.fields["blueprint_id"]
    finally:
        os.chdir(cwd)
    bp_path = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / f"{bp_id}.md"
    # Add ACs to §12 so ac_blueprint can find them
    text = bp_path.read_text(encoding="utf-8")
    ac_block = (
        "<!-- BLP:12 -->\n"
        "## §12: Acceptance Criteria\n\n"
        "- [ ] **AC-01:** Test acceptance criterion\n"
        "- [ ] **AC-02:** Second test criterion\n"
        "<!-- /BLP:12 -->"
    )
    import re
    text = re.sub(
        r"<!-- BLP:12 -->.*?<!-- /BLP:12 -->",
        ac_block,
        text,
        flags=re.DOTALL,
    )
    bp_path.write_text(text, encoding="utf-8")
    return project_dir, bp_path


def _set_frontmatter_status(bp_path: Path, status: str) -> None:
    text = bp_path.read_text(encoding="utf-8")
    text = text.replace('status: "draft"', f'status: "{status}"')
    bp_path.write_text(text, encoding="utf-8")


def _set_all_quality_gates(bp_path: Path, value: bool) -> None:
    text = bp_path.read_text(encoding="utf-8")
    v = "true" if value else "false"
    for gate in (
        "has_clear_objective",
        "has_verifiable_preconditions",
        "has_scope_and_exclusions",
        "has_acceptance_criteria",
        "has_work_procedure",
        "has_required_validations",
        "has_learning_recorded",
    ):
        text = text.replace(f"{gate}: false", f"{gate}: {v}")
        text = text.replace(f"{gate}: true", f"{gate}: {v}")
    bp_path.write_text(text, encoding="utf-8")


def _mark_all_acceptance_criteria(bp_path: Path) -> None:
    text = bp_path.read_text(encoding="utf-8")
    text = text.replace("- [ ] ", "- [x] ")
    bp_path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


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


def test_blueprint_ac_verified_returns_message(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "in_progress")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.ac_blueprint("BLP-001", "AC-01", "verified")
    finally:
        os.chdir(cwd)

    assert result.profile == "OUT-WORK"
    assert "blueprint.ac ok" in result.to_text()


def test_blueprint_approve_blocks_failed_acceptance_criteria(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "review")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.ac_blueprint("BLP-001", "AC-01", "verified")
        assert result.profile == "OUT-WORK"

        result2 = blueprint.approve_blueprint("BLP-001")
        assert "APPROVAL_INCOMPLETE" in result2.to_text()
    finally:
        os.chdir(cwd)


def test_blueprint_approve_blocks_unverified_acceptance_criteria(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "review")

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        result = blueprint.approve_blueprint("BLP-001")
    finally:
        os.chdir(cwd)

    assert "APPROVAL_INCOMPLETE" in result.to_text()
    # Approve blocks when ACs are unchecked OR learning/validations are missing
    assert (
        "missing_acceptance_criteria=" in result.to_text()
        or "missing_learning=" in result.to_text()
        or "missing_validations=" in result.to_text()
    )


def test_blueprint_approve_requires_learning_gate_and_returns_instruction(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)
    _set_frontmatter_status(bp_path, "in_progress")
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
        # Complete blueprint to set evidence in frontmatter
        result_complete = blueprint.complete_blueprint("BLP-001", evidence="All ACs verified and tasks done")
        assert result_complete.profile == "OUT-WORK", str(result_complete.fields)
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
    assert "# BLP-NNN: Título" not in text


def test_blueprint_update_preserves_section_title(workspace_root: Path, governor_ctx) -> None:
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        blueprint.update_blueprint("BLP-001", section="1", content="Updated problem")
    finally:
        os.chdir(cwd)

    text = bp_path.read_text(encoding="utf-8")
    assert "## 1: Planteamiento del Problema" not in text
    assert "## 1:Updated problem" not in text


def test_blueprint_update_no_header_duplication(workspace_root: Path, governor_ctx) -> None:
    """Multiple updates to the same section must not create duplicate headers."""
    project_dir, bp_path = _setup_blueprint(workspace_root, governor_ctx)

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        blueprint.update_blueprint("BLP-001", section="1", content="First update")
        blueprint.update_blueprint("BLP-001", section="1", content="Second update")
    finally:
        os.chdir(cwd)

    text = bp_path.read_text(encoding="utf-8")
    # The header must appear exactly once
    assert text.count("## §1: Planteamiento del Problema") == 1
    assert "Second update" in text
    # Verify no raw header remnants
    assert text.count("## 1:n") == 0
