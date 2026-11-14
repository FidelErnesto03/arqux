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

from ..constants import (
    PRODUCT_NAME_UPPER,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import find_workspace_root


def _agents_section_id(doc: dict) -> str | None:
    """Return the section that holds agent entries, preferring ``$1``."""
    ids = {str(s.get("id", "")) for s in doc.get("sections", []) if isinstance(s, dict)}
    for candidate in ("$1", "$19"):
        if candidate in ids:
            return candidate
    for section in doc.get("sections", []):
        if isinstance(section, dict):
            for entry in section.get("entries", []):
                if isinstance(entry, dict) and entry.get("sigil") == "IDN":
                    return str(section.get("id", ""))
    return next((str(s.get("id", "")) for s in doc.get("sections", [])
                 if isinstance(s, dict)), None)


def _register_agent(agents_path: Path, agent_id: str, role: str) -> None:
    """Record an agent in ``agents.cortex`` as a CORTEX entry (upsert).

    The registry is a governed artifact, so it is written through the CORTEX
    model — never as appended plain text. Appending ``- agent=X role=Y`` produced
    a file that no longer parsed (S003_INVALID_IDEA_HEAD) and grew one junk line
    per ``identity.switch``: 85 accumulated in a single session (T-001).

    Idempotent: re-adopting the same agent updates its ``role`` instead of
    adding a second entry.
    """
    from ..cortex import crud
    from ..cortex.atomic import atomic_write_json
    from ..cortex.reader import cortex_to_dict

    if agents_path.exists():
        doc = cortex_to_dict(agents_path.read_text(encoding="utf-8"))
    else:
        doc = {"glossary": {"header": "$0", "comments": [], "symbols": []}, "sections": []}

    section_id = _agents_section_id(doc)
    if section_id is None:
        raise ValueError("agents.cortex has no section to hold the registry")

    try:
        crud.update_entry(doc, f"{section_id}/IDN:{agent_id}",
                          set_={"role": role, "status": "current", "adopted": _now_iso()})
    except ValueError:
        crud.add_entry(doc, section_id, "IDN", agent_id,
                       {"role": role, "status": "current", "adopted": _now_iso()},
                       create_section=False)

    atomic_write_json(doc, str(agents_path), strict=False)


def _unregister_agent(agents_path: Path, agent_id: str) -> None:
    """Remove an agent's entry from ``agents.cortex``, preserving the rest.

    The previous implementation filtered lines containing ``agent=<id>``, a shape
    that does not exist in a CORTEX registry — so ``release`` silently matched
    nothing while the registry kept accumulating plain-text lines.
    """
    from ..cortex import crud
    from ..cortex.atomic import atomic_write_json
    from ..cortex.reader import cortex_to_dict

    if not agents_path.exists():
        return

    doc = cortex_to_dict(agents_path.read_text(encoding="utf-8"))
    section_id = _agents_section_id(doc)
    if section_id is None:
        return

    try:
        crud.delete_entry(doc, f"{section_id}/IDN:{agent_id}")
    except ValueError:
        return  # nothing to remove: release is idempotent

    atomic_write_json(doc, str(agents_path), strict=False)


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
        _register_agent(root / "agents.cortex", agent_id, role)

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
        _unregister_agent(agents_path, agent_id)

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

