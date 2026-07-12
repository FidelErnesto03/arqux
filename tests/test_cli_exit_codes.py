"""Tests for CLI exit codes (P1-A, P1-B).

Validates:
- arqux call unknown.handler returns exit 1 (P1-A)
- arqux call with handler that returns OUT-ERROR returns exit 1 (P1-B)
- arqux call with valid handler returns exit 0
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    """Initialize a workspace in tmp_path and chdir to it."""
    from arqux.handlers.workspace import init_workspace
    init_workspace(path=str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestExitCodes:
    """P1-A / P1-B: exit codes for arqux call."""

    def test_unknown_handler_exits_nonzero(self, workspace: Path) -> None:
        """P1-A: arqux call unknown.handler should exit 1."""
        from arqux.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["call", "totally.unknown.handler"])
        assert result.exit_code != 0, (
            f"Expected non-zero exit code for unknown handler, got {result.exit_code}"
        )

    def test_known_handler_exits_zero(self, workspace: Path) -> None:
        """Valid handler should exit 0."""
        from arqux.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["call", "workspace.status"])
        # workspace.status on initialized workspace should return OK
        assert result.exit_code == 0, (
            f"Expected exit 0 for valid handler, got {result.exit_code}. Output: {result.output}"
        )

    def test_handler_error_exits_nonzero(self, tmp_path: Path, monkeypatch) -> None:
        """P1-B: arqux call workspace.status (no workspace) should exit 1."""
        from arqux.cli import main
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["call", "workspace.status"])
        # No workspace initialized → OUT-ERROR → exit 1
        assert result.exit_code != 0, (
            f"Expected non-zero exit code when handler returns ERROR, got {result.exit_code}"
        )

    def test_underscore_handler_resolution(self, workspace: Path) -> None:
        """workspace_status should resolve to workspace.status."""
        from arqux.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["call", "workspace_status"])
        assert result.exit_code == 0
        assert "ERROR" not in result.output.upper()
