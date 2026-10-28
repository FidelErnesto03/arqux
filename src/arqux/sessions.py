"""Session management operations on brain.cortex.

Tracks agent-to-project binding through SESSIONS and HANDOFFS sections
in the project brain.
"""

from __future__ import annotations

from pathlib import Path

from .state import (
    _now_iso,
    crud_add,
    crud_list,
    crud_update,
    find_project_root,
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

    The entry is updated where it lives (CYCLE-12 / BLP-024). Reading the
    brain as a legacy ``sections`` dict and rewriting the whole file
    degraded every canonical entry the legacy model did not understand:
    lessons lost their cause and prevention and risks collapsed into
    identical placeholders.
    """
    brain_path = _brain_cortex_path(project_root)
    sessions = crud_list(brain_path, section="$4", sigil="SES").get("entries", [])
    updated_line = ""
    for entry in sessions:
        value = entry.get("value") or {}
        if value.get("agent") != agent_id or value.get("status") != "active":
            continue
        ts = _now_iso()
        crud_update(
            brain_path, f"$4/SES:{entry['name']}",
            set_={
                "date": ts,
                "status": "released",
                "outcome": "released",
                "output": "session released",
            },
            force=True,
        )
        updated_line = f"- [{ts}] agent={agent_id} role={value.get('role', '')} status=released"
    if not updated_line:
        return ""
    _bump_brain_concurrency(brain_path, agent_id)
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
