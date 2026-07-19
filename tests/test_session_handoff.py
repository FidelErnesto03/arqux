"""Tests for session.handoff identity preservation (BLP-fix T-004).

Validates AC-1 (handoff preserves the emitter's agent_id without
falling back to the default 'alfred'), AC-2 (coherence between
context.set and handoff identity), and that an explicit ctx agent is
respected end-to-end.
"""

from __future__ import annotations

import os
from pathlib import Path

from arqux.handlers import project, session, workspace
from arqux.permissions import PermissionContext, ROLE_GOVERNOR, ROLE_EXECUTOR


def _handoff_text(project_dir: Path, target_agent: str) -> str:
    """Read the serialized handoff file written by session.handoff."""
    p = project_dir / ".arqux" / "handoffs" / f"{target_agent}.cortex"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _setup_project(workspace_root: Path, ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir(parents=True, exist_ok=True)
    project.init_project(name="my-app", path=str(project_dir), ctx=ctx)
    return project_dir


def _run_in_project(project_dir: Path, fn, *args, **kwargs):
    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        return fn(*args, **kwargs)
    finally:
        os.chdir(cwd)


def _ctx(agent_id: str):
    return PermissionContext(agent_id=agent_id, role=ROLE_GOVERNOR)


def test_handoff_preserves_explicit_agent_id(workspace_root: Path, governor_ctx) -> None:
    """AC-1: handoff respects ctx.agent_id, never masks it as 'alfred'."""
    project_dir = _setup_project(workspace_root, governor_ctx)
    heimdall = _ctx("heimdall")

    result = _run_in_project(
        project_dir,
        session.handoff,
        target_agent="jarvis",
        content='target_agent:"jarvis", summary:"handoff test", blps:"", tasks:""',
        path=str(project_dir),
        ctx=heimdall,
    )
    assert result.profile == "OUT-WORK"
    # The serialized handoff must carry the emitter identity, not the default.
    handoff_text = _handoff_text(project_dir, "jarvis")
    assert 'from:"heimdall"' in handoff_text, handoff_text
    assert 'from:"alfred"' not in handoff_text, "identity masked as alfred"


def test_handoff_coherence_with_context_set(workspace_root: Path, governor_ctx) -> None:
    """AC-2: context.set and handoff agree on the active agent identity."""
    project_dir = _setup_project(workspace_root, governor_ctx)
    heimdall = _ctx("heimdall")

    # Set the session context as heimdall.
    cset = _run_in_project(
        project_dir,
        session.context_set,
        project="my-app",
        scope="WATCH",
        path=str(project_dir),
        ctx=heimdall,
    )
    assert cset.fields.get("agent") == "heimdall", cset.fields

    # Handoff from the same identity must preserve it.
    hoff = _run_in_project(
        project_dir,
        session.handoff,
        target_agent="jarvis",
        content='target_agent:"jarvis", summary:"x", blps:"", tasks:""',
        path=str(project_dir),
        ctx=heimdall,
    )
    assert 'from:"heimdall"' in _handoff_text(project_dir, "jarvis")


def test_handoff_executor_identity_preserved(workspace_root: Path, governor_ctx) -> None:
    """AC-1b: a non-default agent (executor) is preserved, not alfred."""
    project_dir = _setup_project(workspace_root, governor_ctx)
    jarvis = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR)

    result = _run_in_project(
        project_dir,
        session.handoff,
        target_agent="heimdall",
        content='target_agent:"heimdall", summary:"y", blps:"", tasks:""',
        path=str(project_dir),
        ctx=jarvis,
    )
    assert 'from:"jarvis"' in _handoff_text(project_dir, "heimdall"), result.fields
