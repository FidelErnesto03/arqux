"""context.full handler (BLP-006).

Returns the full project context: project name, available cycles,
current cycle, agents bound, skills available.

Reads ``.arqux/`` files directly — no MCP handler calls.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ...constants import (
    CYCLES_DIR,
)
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root, find_workspace_root, read_brain


def full_handler(
    path: str | None = None,
    *,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Return the full project context.

    Aggregates:

    - ``project`` — name (from brain.cortex $1:IDENTITY) and root path
    - ``cycles`` — list of cycle IDs, with the current cycle marked
    - ``agents`` — list of agent IDs bound to the project (from brain
      SESSIONS section)
    - ``skills`` — list of skill names available in ``.arqux/skills/``
    - ``workspace`` — workspace root if available

    Args:
        path: Starting path. Defaults to cwd.
        ctx: Permission context.
    """
    start = Path(path or os.getcwd()).resolve()

    project_arqux = find_project_root(start=start)
    workspace_arqux = find_workspace_root(start=start)

    if project_arqux is None:
        return CortexOUT.error(
            "no .arqux/ project root found — call context.detect first",
            code="NOT_FOUND",
            start=str(start),
        )

    # Read brain.cortex for project name and bound agents.
    project_root_parent = project_arqux.parent
    fm, sections, raw = read_brain(project_root_parent)
    project_name = fm.get("project", "") or project_root_parent.name
    governor = fm.get("governor", "")

    # Parse bound agents from SESSIONS section (best-effort).
    agents: list[dict[str, str]] = []
    sessions_text = sections.get("SESSIONS", "")
    for line in sessions_text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        m = re.search(r"agent=([^\s]+)", line)
        if m:
            agents.append({"agent_id": m.group(1), "raw": line})

    # List cycles.
    cycles_base = project_arqux / CYCLES_DIR
    cycles: list[dict[str, Any]] = []
    current_cycle_id: str | None = None
    if cycles_base.exists():
        for cdir in sorted(cycles_base.iterdir()):
            if not cdir.is_dir():
                continue
            manifest = cdir / "MANIFEST.md"
            cycle_status = ""
            if manifest.exists():
                try:
                    mf_text = manifest.read_text(encoding="utf-8")
                    status_match = re.search(r"status:\s*[\"']?(\w+)", mf_text)
                    if status_match:
                        cycle_status = status_match.group(1)
                except OSError:
                    pass
            cycles.append({
                "id": cdir.name,
                "status": cycle_status,
            })
            # Heuristic: "active" or "ready" cycle is current.
            if cycle_status in ("active", "ready") and current_cycle_id is None:
                current_cycle_id = cdir.name

    if current_cycle_id is None and cycles:
        current_cycle_id = cycles[-1]["id"]

    # List skills.
    skills_dir = project_arqux / "skills"
    skills: list[str] = []
    if skills_dir.exists():
        for f in sorted(skills_dir.iterdir()):
            if f.is_file() and f.name.endswith(".skill.md"):
                skills.append(f.stem.removesuffix(".skill"))

    # Pulse.
    _record_pulse(project_arqux, ctx, project=project_name)

    return CortexOUT.work(
        f"context.full ok project={project_name} cycles={len(cycles)} "
        f"agents={len(agents)} skills={len(skills)}",
        project=project_name,
        project_path=str(project_root_parent),
        arqux_path=str(project_arqux),
        governor=governor,
        cycles=cycles,
        current_cycle=current_cycle_id,
        agents=agents,
        skills=skills,
        workspace_path=str(workspace_arqux.parent) if workspace_arqux else None,
    )


def _record_pulse(
    project_arqux: Path,
    ctx: PermissionContext | None,
    *,
    project: str,
) -> None:
    """Append a PULSE event for the full call (best-effort)."""
    try:
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(project_arqux)
        append_pulse_to_brain(
            project_arqux,
            event_id=event_id,
            task_id="-",
            kind="handler_call",
            agent=agent,
            payload=f"[context.full] project={project}",
        )
    except Exception:  # noqa: BLE001
        pass
