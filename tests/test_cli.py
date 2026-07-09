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
    lines = [l.strip() for l in result.output.strip().split("\n") if l.strip()]
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
    """arqux call with unknown handler returns error message."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["call", "nonexistent.handler"])
    assert result.exit_code == 0  # click doesn't raise, but output contains ERROR
    assert "ERROR" in result.output or "unknown handler" in result.output.lower()


def test_call_workspace_status() -> None:
    """arqux call workspace.status returns status output."""
    from arqux.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["call", "workspace.status"])
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
