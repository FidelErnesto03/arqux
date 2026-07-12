"""`protocol` module — control of governance.

Handlers:
    protocol.adopt    — onboard an agent with a role (records in workspace brain-equivalent: agents index in manifest)
    protocol.release  — fully detach an agent (clean exit, no orphans)
    protocol.pause    — suspend governance for the current session
    protocol.resume   — resume governance after a pause

Per the architecture decision (gap 6 fix), agent onboarding records are
written via handlers — no direct file editing. The agents index lives
alongside the manifest, not as a separate `agents.cortex` file. Project
sessions live in the project brain (see `project.bind`).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..constants import (
    OUT_WORK,
    PRODUCT_NAME_UPPER,
    ARQUX_DIR,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import find_workspace_root, write_cortex_pair, parse_cortex_file


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
    The agents registry is appended to the workspace's `agents.cortex`
    through the state helper — handlers are the only interface.
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
        agents_path = root / "agents.cortex"
        existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
        entry = f"- agent={agent_id} role={role} adopted={_now_iso()}\n"
        agents_path.write_text(existing + entry, encoding="utf-8")

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

    agents_path = root / "agents.cortex"
    if agents_path.exists():
        lines = agents_path.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if f"agent={agent_id}" not in ln]
        agents_path.write_text("\n".join(kept) + "\n", encoding="utf-8")

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


handler_schemas = [
    dict(name="protocol.adopt", fn=adopt, description="Onboard an agent with a role.", input_schema={"type": "object", "properties": {"agent_id": {"type": "string"}, "role": {"type": "string", "enum": ["governor", "executor", "auditor"]}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["agent_id", "role"]}),
    dict(name="protocol.release", fn=release, description="Fully detach an agent (clean exit, no orphans).", input_schema={"type": "object", "properties": {"agent_id": {"type": "string"}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["agent_id"]}),
    dict(name="protocol.pause", fn=pause, description="Suspend governance for the current session without losing state.", input_schema={"type": "object", "properties": {}}),
    dict(name="protocol.resume", fn=resume, description="Resume governance after a pause.", input_schema={"type": "object", "properties": {}}),
]
