"""`protocol` module — control of governance.

Handlers:
    protocol.adopt    — onboard an agent with a role (records in workspace brain-equivalent: agents index in manifest)
    protocol.release  — fully detach an agent (clean exit, no orphans)
    protocol.pause    — suspend governance for the current session
    protocol.resume   — resume governance after a pause

Per the architecture decision (gap 6 fix), agent onboarding records are
written via handlers — no direct file editing. The agents index lives in
the workspace meta-brain ``REGISTRY`` (GRADIENT-12); the standalone
`agents.cortex` file is retired. Project sessions live in the project
brain (see `project.bind`).
"""

from __future__ import annotations

import os
from pathlib import Path

from ..constants import (
    PRODUCT_NAME_UPPER,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import find_workspace_root


def _meta_registry_sec(meta_brain_path: Path) -> str:
    """Resolve the meta-brain section holding agent/project records."""
    from ..core.state._crud import crud_section_id_for_title
    for title in ("REGISTRY", "AGENTS", "PROJECTS"):
        sec = crud_section_id_for_title(meta_brain_path, title)
        if sec:
            return sec
    return "$10"


def _register_agent(meta_brain_path: Path, agent_id: str, role: str) -> None:
    """Record an agent in the meta-brain REGISTRY as an ``IDN:`` entry.

    Canon (GRADIENT-12 / G-8): the workspace agent registry lives in
    ``meta-brain.cortex`` ``$10 REGISTRY`` — the standalone
    ``agents.cortex`` index is retired and must never be recreated.
    Idempotent: re-adopting the same agent updates its ``role``.
    """
    from ..state import crud_add, crud_read, crud_update

    if not meta_brain_path.exists():
        return

    reg_sec = _meta_registry_sec(meta_brain_path)
    attrs = {"name": agent_id, "role": role, "status": "current",
             "adopted": _now_iso()}
    try:
        existing = crud_read(meta_brain_path, f"{reg_sec}/IDN:{agent_id}")
    except Exception:
        existing = {"entries": []}
    if existing.get("entries"):
        crud_update(meta_brain_path, f"{reg_sec}/IDN:{agent_id}",
                    set_=attrs, force=True)
    else:
        crud_add(meta_brain_path, reg_sec, "IDN", agent_id, attrs,
                 create_section=False, force=True)


def _unregister_agent(meta_brain_path: Path, agent_id: str) -> None:
    """Remove an agent's ``IDN:`` entry from the meta-brain REGISTRY."""
    from ..state import crud_delete

    if not meta_brain_path.exists():
        return
    reg_sec = _meta_registry_sec(meta_brain_path)
    try:
        crud_delete(meta_brain_path, f"{reg_sec}/IDN:{agent_id}", force=True)
    except Exception:
        return  # nothing to remove: release is idempotent


def adopt(
    agent_id: str,
    role: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Onboard an agent with a role.

    Sets environment variables for the current session:
        ARQUX_AGENT_ID=<agent_id>
        ARQUX_AGENT_ROLE=<role>

    And records the onboarding via the handlers (no direct file editing).
    The agents registry lives in the workspace meta-brain ``REGISTRY``
    (GRADIENT-12); entries are upserted through the state helpers.
    """
    if role not in ("governor", "executor", "auditor"):
        return CortexOUT.error(
            f"invalid role: {role}",
            code="INVALID_ARGUMENT",
        )

    os.environ[f"{PRODUCT_NAME_UPPER}_AGENT_ID"] = agent_id
    os.environ[f"{PRODUCT_NAME_UPPER}_AGENT_ROLE"] = role

    root = find_workspace_root(start=path)
    if root is not None:
        _register_agent(root / "meta-brain.cortex", agent_id, role)

    return CortexOUT.work(
        f"protocol.adopt ok agent={agent_id} role={role}",
        agent_id=agent_id,
        role=role,
    )


def release(agent_id: str, path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """Fully detach an agent (clean exit, no orphans).

    Removes the agent from the workspace's agents index via the handler.
    Other agents continue operating. Does NOT mutate any project state —
    project sessions are released via `project.unbind`.

    BC-7 fix: ALWAYS clear ARQUX_AGENT_ID/ARQUX_AGENT_ROLE env vars on
    release, regardless of whether the workspace is found or whether
    the env var matched agent_id. The release semantic is "no agent is
    active after release", so unconditionally pop.
    """
    # BC-7 fix: clear env vars FIRST, before any early return.
    os.environ.pop(f"{PRODUCT_NAME_UPPER}_AGENT_ID", None)
    os.environ.pop(f"{PRODUCT_NAME_UPPER}_AGENT_ROLE", None)

    root = find_workspace_root(start=path)
    if root is None:
        # Still allow release if the workspace was never initialized.
        return CortexOUT.work(f"protocol.release ok agent={agent_id} (no workspace)", agent_id=agent_id)

    meta_brain_path = root / "meta-brain.cortex"
    if meta_brain_path.exists():
        _unregister_agent(meta_brain_path, agent_id)

    return CortexOUT.work(
        f"protocol.release ok agent={agent_id}",
        agent_id=agent_id,
    )


def pause(ctx: PermissionContext | None = None) -> CortexOUT:
    """Suspend governance for the current session without losing state.

    Sets ARQUX_SUSPENDED=1. Handlers that mutate state
    should check this flag and refuse.
    """
    os.environ[f"{PRODUCT_NAME_UPPER}_SUSPENDED"] = "1"
    return CortexOUT.work(
        "protocol.pause ok — governance suspended",
        suspended=True,
    )


def resume(ctx: PermissionContext | None = None) -> CortexOUT:
    """Resume governance after a pause."""
    os.environ.pop(f"{PRODUCT_NAME_UPPER}_SUSPENDED", None)
    return CortexOUT.work(
        "protocol.resume ok — governance resumed",
        suspended=False,
    )


def is_suspended() -> bool:
    """Check whether governance is currently paused."""
    return os.environ.get(f"{PRODUCT_NAME_UPPER}_SUSPENDED") == "1"


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())



def onboard(
    agent_id: str,
    role: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Onboard an agent — alias of protocol.adopt."""
    return adopt(agent_id=agent_id, role=role, path=path, ctx=ctx)

handler_schemas = [
    {"name": "protocol.adopt", "fn": adopt, "description": "Onboard an agent with a role.", "input_schema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "role": {"type": "string", "enum": ["governor", "executor", "auditor"]}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["agent_id", "role"]}},
    {"name": "protocol.release", "fn": release, "description": "Fully detach an agent (clean exit, no orphans).", "input_schema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["agent_id"]}},
    {"name": "protocol.pause", "fn": pause, "description": "Suspend governance for the current session without losing state.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "protocol.resume", "fn": resume, "description": "Resume governance after a pause.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "protocol.onboard", "fn": onboard, "description": "Onboard an agent with a role. Alias of protocol.adopt for w06 workflow compatibility.", "input_schema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "role": {"type": "string", "enum": ["governor", "executor", "auditor"]}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["agent_id", "role"]}},
]

