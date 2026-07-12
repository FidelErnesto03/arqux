"""Tests for context.detect, context.full, identity.get (BLP-006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers.context import detect_handler, full_handler
from arqux.handlers.identity import get_handler
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")


# ---------------------------------------------------------------------------
# Helpers — bootstrap a minimal project + workspace
# ---------------------------------------------------------------------------


def _bootstrap_project(tmp_path: Path) -> Path:
    """Create a minimal .arqux/ project structure and return its root.

    The project is nested INSIDE the workspace (matching the conftest.py
    fixture pattern) so template resolution walks up correctly.
    """
    from arqux.handlers.project import init_project
    from arqux.handlers.workspace import init_workspace

    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()

    ctx = PermissionContext(agent_id="test-governor", role="governor")
    init_workspace(path=str(ws_root), ctx=ctx)
    init_project(name="test-proj", path=str(proj_root), ctx=ctx)
    return proj_root


# ---------------------------------------------------------------------------
# context.detect
# ---------------------------------------------------------------------------


def test_detect_finds_project(tmp_path: Path) -> None:
    proj_root = _bootstrap_project(tmp_path)
    # Detect from inside the project.
    result = detect_handler(path=str(proj_root), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("found") is True
    assert result.fields.get("path") is not None
    # Path should end with .arqux
    assert result.fields["path"].endswith(".arqux")


def test_detect_not_found(tmp_path: Path) -> None:
    # tmp_path has no .arqux/ structure.
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    result = detect_handler(path=str(deep), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("found") is False
    assert result.fields.get("path") is None


def test_detect_default_path_uses_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When path=None, the handler should use cwd."""
    proj_root = _bootstrap_project(tmp_path)
    monkeypatch.chdir(str(proj_root))
    result = detect_handler(ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("found") is True


# ---------------------------------------------------------------------------
# context.full
# ---------------------------------------------------------------------------


def test_full_returns_context(tmp_path: Path) -> None:
    proj_root = _bootstrap_project(tmp_path)
    result = full_handler(path=str(proj_root), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert "project" in result.fields
    assert "cycles" in result.fields
    assert "agents" in result.fields
    assert "skills" in result.fields
    assert result.fields.get("arqux_path", "").endswith(".arqux")


def test_full_not_found(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    result = full_handler(path=str(deep), ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# identity.get
# ---------------------------------------------------------------------------


def test_identity_get_default_alfred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default agent_id is alfred — packaged identity is shipped.

    Uses tmp_path as cwd to avoid picking up a workspace .arqux/ that
    may exist in the developer's environment.
    """
    monkeypatch.chdir(str(tmp_path))
    result = get_handler(ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("agent_id") == "alfred"
    assert "content" in result.fields
    assert "IDN:alfred" in result.fields["content"]
    assert result.fields.get("source") == "package"


def test_identity_get_governor() -> None:
    result = get_handler("governor", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("agent_id") == "governor"
    assert "IDN:governor" in result.fields["content"]


def test_identity_get_not_found() -> None:
    result = get_handler("nonexistent_agent", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"
    assert "searched" in result.fields


def test_identity_get_from_project(tmp_path: Path) -> None:
    """When project has its own identity file, source='project'."""
    proj_root = _bootstrap_project(tmp_path)
    arqux_dir = proj_root / ".arqux"
    identities_dir = arqux_dir / "identities"
    identities_dir.mkdir(parents=True, exist_ok=True)
    custom = identities_dir / "custom.cortex"
    custom.write_text(
        '$0\n\n$1: IDENTITY\n\nIDN:custom{name:"Custom", role:"test", status:"current"}\n',
        encoding="utf-8",
    )

    result = get_handler("custom", path=str(proj_root), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("source") == "project"
    assert "IDN:custom" in result.fields["content"]
