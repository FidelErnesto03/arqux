"""Shared pytest fixtures.

Every test runs in a fresh tmp_path with no inherited governance state.
Permission contexts are constructed explicitly so tests do not depend
on the host's environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from arqux.constants import (
    PRODUCT_NAME_UPPER,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)
from arqux.permissions import PermissionContext


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A clean workspace root directory."""
    return tmp_path


@pytest.fixture
def governor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-governor", role=ROLE_GOVERNOR)


@pytest.fixture
def executor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-executor", role=ROLE_EXECUTOR)


@pytest.fixture
def auditor_ctx() -> PermissionContext:
    return PermissionContext(agent_id="test-auditor", role=ROLE_AUDITOR)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any ARQUX_* env vars set by previous tests."""
    for key in list(os.environ.keys()):
        if key.startswith(f"{PRODUCT_NAME_UPPER}_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def arqux_env(request, tmp_path, monkeypatch):
    """Create a fully initialized ArqUX workspace in tmp_path.

    Returns a helper object with:
    - .ws_root: Path to workspace root
    - .proj_root: Path to project root
    - .gov_ctx: Governor PermissionContext
    - .exec_ctx: Executor PermissionContext
    - .cycle_id: str
    - .bp_id: str
    """
    from dataclasses import dataclass

    from arqux.handlers.blueprint.lifecycle import create_blueprint
    from arqux.handlers.cycle import create_cycle, synthesize_cycle
    from arqux.handlers.project import init_project
    from arqux.handlers.workspace import init_workspace

    for key in list(os.environ.keys()):
        if key.startswith(f"{PRODUCT_NAME_UPPER}_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ARQUX_AGENT", "test-governor")
    monkeypatch.setenv("ARQUX_ROLE", "governor")

    ws_root = Path(tmp_path)
    proj_root = ws_root / "test-proj"
    proj_root.mkdir()

    gov_ctx = PermissionContext(agent_id="test-governor", role=ROLE_GOVERNOR)
    exec_ctx = PermissionContext(agent_id="test-executor", role=ROLE_EXECUTOR)

    init_workspace(path=str(ws_root), ctx=gov_ctx)
    init_project(name="test-proj", path=str(proj_root), ctx=gov_ctx)

    result = create_cycle(name="CYCLE-TEST", path=str(proj_root), ctx=gov_ctx)
    cycle_id = result.fields["cycle_id"]

    synthesize_cycle(cycle_id=cycle_id, content="$1:{Test purpose}$2:{Test scope: inside, outside}$3:{CYC-OBJ-1: Test objective}$4:{Test guideline}$5:{Test checkpoint}$6:{BLP index}$7:{Metrics: 0}$8:{Test rule}$9:{Gates}", path=str(proj_root), ctx=gov_ctx)

    # BLP-003: mature_cycle removed. Cycles stay in draft (normal active state).
    result = create_blueprint(obj="test BLP", path=str(proj_root), ctx=gov_ctx)
    bp_id = result.fields["blueprint_id"]

    @dataclass
    class ArqUXEnv:
        ws_root: Path
        proj_root: Path
        gov_ctx: PermissionContext
        exec_ctx: PermissionContext
        cycle_id: str
        bp_id: str

    yield ArqUXEnv(
        ws_root=ws_root,
        proj_root=proj_root,
        gov_ctx=gov_ctx,
        exec_ctx=exec_ctx,
        cycle_id=cycle_id,
        bp_id=bp_id,
    )
