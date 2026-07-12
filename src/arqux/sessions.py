"""Session management operations on brain.cortex.

Tracks agent-to-project binding through SESSIONS and HANDOFFS sections
in the project brain.
"""

from __future__ import annotations

from pathlib import Path

from .constants import BRAIN_SECTION_SESSIONS
from .state import (
    _bump_concurrency,
    _now_iso,
    crud_add,
    crud_update,
    find_project_root,
    read_brain,
    write_brain_sections,
)


def _brain_cortex_path(project_root: Path) -> Path:
    """Resolve the brain.cortex path for direct crud operations."""
    root = find_project_root(start=str(project_root))
    if root is None:
        return project_root / ".arqux" / "brain.cortex"
    return root / "brain.cortex"


def _bump_brain_concurrency(brain_path: Path, agent_id: str) -> None:
    """Bump the ERR:concurrency version after a mutation."""
    from .state import crud_read
    try:
        result = crud_read(str(brain_path), "$11/ERR:concurrency")
        entries = result.get("entries", [])
        if entries:
            val = dict(entries[0].get("value", {}))
            try:
                cur = int(val.get("version", "0"))
            except (ValueError, TypeError):
                cur = 0
            val["version"] = str(cur + 1)
            val["last_writer"] = agent_id
            val["updated"] = _now_iso()
            crud_update(str(brain_path), "$11/ERR:concurrency", set_=val, force=True)
    except Exception:
        pass


def add_session_to_brain(
    project_root: Path,
    agent_id: str,
    role: str,
) -> str:
    """Add a session entry to the brain's SESSIONS section.

    Returns session summary line.
    """
    ts = _now_iso()
    brain_path = _brain_cortex_path(project_root)
    crud_add(
        brain_path, "$4", "SES", agent_id.replace("-", "_"),
        {"date": ts, "agent": agent_id, "role": role, "status": "active",
         "input": f"session start for {agent_id}", "output": "session active", "outcome": "active"},
        create_section=True, force=True,
    )
    # Bump concurrency version
    _bump_brain_concurrency(brain_path, agent_id)
    return f"- [{ts}] agent={agent_id} role={role} status=active"


def remove_session_from_brain(
    project_root: Path,
    agent_id: str,
) -> str:
    """Mark an agent's session as released in the brain.

    Returns the updated session line, or empty string if not found.
    """
    fm, sections, _ = read_brain(project_root)
    raw = sections.get(BRAIN_SECTION_SESSIONS, "")
    new_lines: list[str] = []
    updated_line = ""
    for line in raw.splitlines():
        if f"agent={agent_id}" in line and "status=active" in line:
            ts = _now_iso()
            # Replace timestamp and status while preserving format.
            new_line = line.replace("status=active", "status=released")
            if line.startswith("- ["):
                old_ts_end = line.index("]")
                new_line = "- [" + ts + "]" + new_line[old_ts_end + 1:]
            updated_line = new_line
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    if not updated_line:
        return ""
    sections[BRAIN_SECTION_SESSIONS] = "\n".join(new_lines)
    _bump_concurrency(fm, agent_id)
    write_brain_sections(project_root, fm, sections)
    return updated_line


def append_handoff(
    project_root: Path,
    from_agent: str,
    to_agent: str,
    task_id: str,
    note: str,
) -> str:
    """Append a handoff entry to the brain's HANDOFFS section.

    Returns handoff summary line.
    """
    ts = _now_iso()
    brain_path = _brain_cortex_path(project_root)
    crud_add(
        brain_path, "$5", "HDL", f"{from_agent}_{to_agent}_{task_id}",
        {"date": ts, "from": from_agent, "to": to_agent, "task": task_id, "note": note},
        create_section=True, force=True,
    )
    return f"- [{ts}] {from_agent} -> {to_agent} task={task_id} :: {note}"
