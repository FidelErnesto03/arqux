"""`project` module — project-level governance.

Handlers:
    project.init     — initialize .arqux/ in a project, register in workspace
    project.bind     — bind an agent identity to the current project (writes to brain SESSIONS)
    project.unbind   — release an agent binding (marks session as released in brain)
    project.status   — active project status (cycles, tasks, agents, brain version)
    project.lessons  — list lessons local to current project (from brain LESSONS section)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..constants import (
    BRAIN_CORTEX,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_SESSIONS,
    CYCLES_DIR,
    OUT_WORK,
    PROJECTS_CORTEX,
    ARQUX_DIR,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import (
    add_session_to_brain,
    find_project_root,
    find_workspace_root,
    read_brain,
    remove_session_from_brain,
    write_brain,
)


def init_project(
    name: str,
    path: str | None = None,
    verbose: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Initialize `.<product>/` in a project directory and register it in the workspace."""
    target = Path(path or os.getcwd()).resolve()
    gov_dir = target / ARQUX_DIR
    gov_dir.mkdir(parents=True, exist_ok=True)
    (gov_dir / CYCLES_DIR).mkdir(exist_ok=True)

    brain = {
        "level": 2,
        "project": name,
        "path": str(target),
        "brain_version": "0",
        "brain_last_writer": (ctx or PermissionContext.from_env()).agent_id,
        "brain_updated": _now_iso(),
    }
    write_brain(gov_dir, brain)

    # Register in workspace projects index.
    ws_root = find_workspace_root(start=target)
    if ws_root is not None:
        projects_path = ws_root / PROJECTS_CORTEX
        entry = f"- {name} at {target}\n"
        with projects_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    return CortexOUT.work(
        f"project.init ok name={name} path={gov_dir}",
        project=name,
        path=str(gov_dir),
        registered_in_workspace=ws_root is not None,
    )


def bind(
    agent_id: str,
    role: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Bind an agent identity to the current project with a role.

    Writes a session entry to the brain's SESSIONS section. The brain is the
    shared project mind — every agent bound to the project reads the same
    SESSIONS section to know who else is active.
    """
    root = find_project_root()
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    add_session_to_brain(root, agent_id, role)

    return CortexOUT.work(
        f"project.bind ok agent={agent_id} role={role} (session recorded in brain)",
        agent_id=agent_id,
        role=role,
    )


def unbind(agent_id: str, ctx: PermissionContext | None = None) -> CortexOUT:
    """Release an agent binding from the current project.

    Marks the session as released in the brain's SESSIONS section. The entry
    is preserved for history; only the `status=active` flag changes.
    """
    root = find_project_root()
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    result = remove_session_from_brain(root, agent_id)
    if result == "not_found":
        return CortexOUT.work(
            f"project.unbind ok agent={agent_id} (no active session)",
            agent_id=agent_id,
        )

    return CortexOUT.work(
        f"project.unbind ok agent={agent_id} (session released in brain)",
        agent_id=agent_id,
    )


def status(ctx: PermissionContext | None = None) -> CortexOUT:
    """Active project status: cycles, tasks, agents, brain version.

    The brain version is the optimistic-lock counter — every mutation bumps
    it. Agents reading the brain should check the version before writing.
    """
    root = find_project_root()
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_dir = root / CYCLES_DIR
    cycles = sorted(p.name for p in cycles_dir.iterdir()) if cycles_dir.exists() else []

    fm, sections, _ = read_brain(root)
    sessions_raw = sections.get(BRAIN_SECTION_SESSIONS, "")
    active_agents = sum(1 for ln in sessions_raw.splitlines() if "status=active" in ln)
    brain_version = fm.get("brain_version", "0")

    return CortexOUT.profile(
        OUT_WORK,
        f"project={root.parent.name} cycles={len(cycles)} active_agents={active_agents} "
        f"brain_version={brain_version}",
        project=str(root.parent),
        cycles=len(cycles),
        active_agents=active_agents,
        brain_version=brain_version,
        shared_mind=str(root / BRAIN_CORTEX),
    )


def lessons(ctx: PermissionContext | None = None) -> CortexOUT:
    """List lessons local to the current project.

    Reads from the brain's LESSONS section. These are CONTEXTUAL lessons —
    they apply to this project only. Behavioral lessons (how a role should
    act regardless of project) live in the identity's `.cortex`, not here.
    """
    root = find_project_root()
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    fm, sections, _ = read_brain(root)
    lessons_raw = sections.get(BRAIN_SECTION_LESSONS, "").strip()
    lesson_lines = [ln for ln in lessons_raw.splitlines() if ln.strip()]

    return CortexOUT.work(
        f"contextual_lessons={len(lesson_lines)} (behavioral lessons live in identity .cortex)",
        count=len(lesson_lines),
        kind="contextual",
        brain_path=str(root / BRAIN_CORTEX),
    )


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
