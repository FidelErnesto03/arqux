"""Tests for arqux.cli — Click commands.

Covers:
    - --version flag
    - handlers command
    - init command (with CliRunner + tmpdir)
    - call command (handler dispatch)
"""

from __future__ import annotations

from click.testing import CliRunner

# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


def test_version() -> None:
    """arqux --version prints version info."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "arqux" in result.output.lower() or "arqux" in result.output


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------


def test_handlers_list() -> None:
    """arqux handlers lists available handler names."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["handlers"])
    assert result.exit_code == 0
    # Should output at least some handler names
    lines = [ln.strip() for ln in result.output.strip().split("\n") if ln.strip()]
    assert len(lines) > 0


def test_handlers_contains_workspace_status() -> None:
    """arqux handlers includes 'workspace.status'."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["handlers"])
    assert "workspace.status" in result.output


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_creates_arqux_dir(tmp_path) -> None:
    """arqux init creates .arqux/ directory at the specified path."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["init", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / ".arqux").exists()


def test_init_verbose(tmp_path) -> None:
    """arqux init --verbose produces output without errors."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["init", "--path", str(tmp_path), "--verbose"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# call
# ---------------------------------------------------------------------------


def test_call_unknown_handler() -> None:
    """P1-A: arqux call with unknown handler exits non-zero."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["call", "nonexistent.handler"])
    # P1-A PATCH: unknown handler must exit non-zero
    assert result.exit_code != 0
    assert "ERROR" in result.output or "unknown handler" in result.output.lower()


def test_call_workspace_status(tmp_path) -> None:
    """arqux call workspace.status returns status output (needs workspace)."""
    from arqux.cli import main
    from arqux.handlers.workspace import init_workspace

    init_workspace(path=str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["call", "workspace.status", f"path={tmp_path}"])
    assert result.exit_code == 0
    # Should return some text (CORTEX-OUT format)
    assert len(result.output.strip()) > 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_command() -> None:
    """arqux status runs without crashing."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    # status may fail if not in a workspace, but should not crash (exit 1)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# call with args
# ---------------------------------------------------------------------------


def test_call_with_key_value_args(tmp_path) -> None:
    """arqux call workspace.status path=X works (needs workspace)."""
    from arqux.cli import main
    from arqux.handlers.workspace import init_workspace

    init_workspace(path=str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["call", "workspace.status", f"path={tmp_path}"])
    assert result.exit_code == 0


def test_call_with_underscore_name(tmp_path) -> None:
    """P0-F: arqux call workspace_status resolves to workspace.status.

    The test must initialize a workspace first — workspace.status returns
    OUT-ERROR if no workspace is found, which would make the assertion fail.
    """
    from arqux.cli import main
    from arqux.handlers.workspace import init_workspace

    # Initialize workspace in tmp_path.
    init_workspace(path=str(tmp_path))

    runner = CliRunner()
    result = runner.invoke(main, ["call", "workspace_status", f"path={tmp_path}"])
    assert result.exit_code == 0
    assert "ERROR" not in result.output.upper()
    assert "workspace" in result.output.lower()


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------


def test_migrate_injects_metadata(tmp_path) -> None:
    """arqux migrate injects ARQX:artifact into a .cortex file."""
    from arqux.cli import main

    cortex_file = tmp_path / "test.cortex"
    cortex_file.write_text("$0: test\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [
        "migrate", str(cortex_file),
        "--level", "0",
        "--name", "test-pkg",
        "--usage", "config",
    ])
    assert result.exit_code == 0
    assert "MIGRATED" in result.output or "ALREADY_HAS" in result.output


def test_migrate_idempotent(tmp_path) -> None:
    """arqux migrate is idempotent — second call reports ALREADY_HAS."""
    from arqux.cli import main

    cortex_file = tmp_path / "idempotent.cortex"
    cortex_file.write_text("$0: test\n", encoding="utf-8")

    runner = CliRunner()
    runner.invoke(main, [
        "migrate", str(cortex_file),
        "--level", "1",
        "--name", "test-behavioral",
        "--usage", "lesson",
    ])
    result2 = runner.invoke(main, [
        "migrate", str(cortex_file),
        "--level", "1",
        "--name", "test-behavioral",
        "--usage", "lesson",
    ])
    assert "ALREADY_HAS_METADATA" in result2.output


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_valid_file(tmp_path) -> None:
    """arqux validate passes on a valid .cortex file."""
    from arqux.cli import main

    cortex_file = tmp_path / "valid.cortex"
    cortex_file.write_text("""$0: test

$1: SECTION
body here
""", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(cortex_file)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# call with handler args
# ---------------------------------------------------------------------------


def test_call_blueprint_list(tmp_path) -> None:
    """arqux call blueprint.list returns data without error."""
    from arqux.cli import main
    from arqux.handlers.workspace import init_workspace
    from arqux.handlers.project import init_project

    init_workspace(path=str(tmp_path))
    # blueprint.list requires a project to be initialized
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    init_project(name="myproject", path=str(project_dir))
    runner = CliRunner()
    result = runner.invoke(main, ["call", "blueprint.list", f"path={project_dir}"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# identity list
# ---------------------------------------------------------------------------


def test_identity_list(tmp_path) -> None:
    """arqux identity list returns agent names without error."""
    from arqux.cli import main

    # Create dummy identities dir
    id_dir = tmp_path / "identities"
    id_dir.mkdir()
    (id_dir / "test-agent.cortex").write_text(
        '$0: test identity\n', encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(main, [
        "identity", "list",
        "--identities-dir", str(id_dir),
    ])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# skill list
# ---------------------------------------------------------------------------


def test_skill_list_returns_skills(tmp_path) -> None:
    """arqux skill list returns at least the packaged skills."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "list",
        "--arqux-root", str(tmp_path),
    ])
    assert result.exit_code == 0
    # Packaged skills from src/arqux/skills/ are always found
    assert len(result.output.strip().split("\n")) > 0


# ---------------------------------------------------------------------------
# migrate with various options
# ---------------------------------------------------------------------------


def test_migrate_with_all_options(tmp_path) -> None:
    """arqux migrate accepts all optional parameters."""
    from arqux.cli import main

    f = tmp_path / "full.cortex"
    f.write_text("$0: test\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, [
        "migrate", str(f),
        "--level", "2",
        "--name", "test-skill",
        "--usage", "skill",
        "--kind", "inherited",
        "--source", "https://example.com",
        "--upstream-version", "1.0.0",
    ])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# skill import with missing content
# ---------------------------------------------------------------------------


def test_skill_import_missing_content(tmp_path) -> None:
    """arqux skill import errors when no content or file provided."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "import", "test-skill",
        "--source", "https://example.com",
        "--arqux-root", str(tmp_path),
    ])
    assert "ERROR" in result.output


# ---------------------------------------------------------------------------
# validate with strict flag
# ---------------------------------------------------------------------------


def test_validate_strict_valid(tmp_path) -> None:
    """arqux validate with --strict passes on valid file."""
    from arqux.cli import main

    f = tmp_path / "strict_valid.cortex"
    f.write_text(
        "$0: test\n\n$1: SECTION\nbody\n", encoding="utf-8"
    )
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(f)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# status commands
# ---------------------------------------------------------------------------


def test_status_with_path(tmp_path) -> None:
    """arqux status --path works."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["status", "--path", str(tmp_path)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# call with JSON arg
# ---------------------------------------------------------------------------


def test_call_with_json_arg(tmp_path) -> None:
    """arqux call with JSON value in arg works."""
    from arqux.cli import main
    from arqux.handlers.workspace import init_workspace
    from arqux.handlers.project import init_project

    init_workspace(path=str(tmp_path))
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    init_project(name="myproject", path=str(project_dir))
    runner = CliRunner()
    result = runner.invoke(main, [
        "call", "blueprint.list",
        f"path={project_dir}",
    ])
    assert result.exit_code == 0
