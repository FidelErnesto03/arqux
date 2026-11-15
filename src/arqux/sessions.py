"""Session management operations on brain.cortex.

Tracks agent-to-project binding through SESSIONS and HANDOFFS sections
in the project brain.
"""

from __future__ import annotations

from pathlib import Path

from .core.state._crud import crud_section_id_for_title
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
        # GRADIENT-12: ERR:concurrency folded into ARQX:artifact attrs in $1
        # (version/revision/last_writer). Legacy brains still carry
        # ERR:concurrency in a CONCURRENCY-titled section — try canon first.
        result = crud_read(str(brain_path), "$1/ARQX:artifact")
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
            crud_update(str(brain_path), "$1/ARQX:artifact", set_=val, force=True)
            return
        # Legacy path: ERR:concurrency in the CONCURRENCY-titled section.
        conc_sec = crud_section_id_for_title(brain_path, "CONCURRENCY", fallback="$12")
        result = crud_read(str(brain_path), f"{conc_sec}/ERR:concurrency")
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
            crud_update(str(brain_path), f"{conc_sec}/ERR:concurrency", set_=val, force=True)
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
    ses_section = crud_section_id_for_title(brain_path, "SESSIONS", fallback="$10")
    crud_add(
        brain_path, ses_section, "SES", agent_id.replace("-", "_"),
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

    Returns the updated session line, or ``"not_found"`` if the agent has no
    active session.

    The entry is updated where it lives (CYCLE-12 / BLP-024). Reading the
    brain as a legacy ``sections`` dict and rewriting the whole file
    degraded every canonical entry the legacy model did not understand:
    lessons lost their cause and prevention and risks collapsed into
    identical placeholders.
    """
    brain_path = _brain_cortex_path(project_root)
    ses_section = crud_section_id_for_title(brain_path, "SESSIONS", fallback="$10")
    sessions = crud_list(brain_path, section=ses_section, sigil="SES").get("entries", [])
    updated_line = ""
    for entry in sessions:
        value = entry.get("value") or {}
        # Legacy entries name the entry after the agent and carry no agent
        # attribute; canonical ones carry both.
        owner = value.get("agent") or ""
        if owner != agent_id and entry.get("name") != agent_id.replace("-", "_"):
            continue
        if value.get("status") != "active":
            continue
        ts = _now_iso()
        crud_update(
            brain_path, f"{ses_section}/SES:{entry['name']}",
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
        return "not_found"
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
    # Canon (GRADIENT-12): pending handoffs live as HND:<to> in ACTIVE_CONTEXT.
    # Legacy tolerance: if the brain still carries a HANDOFFS section (and no
    # ACTIVE_CONTEXT), keep writing HDL there.
    ac_section = crud_section_id_for_title(brain_path, "ACTIVE_CONTEXT")
    if ac_section:
        crud_add(
            brain_path, ac_section, "HND", f"{from_agent}_{to_agent}_{task_id}",
            {"date": ts, "from": from_agent, "to": to_agent, "task": task_id, "note": note},
            create_section=True, force=True,
        )
    else:
        hd_section = crud_section_id_for_title(brain_path, "HANDOFFS", fallback="$6")
        crud_add(
            brain_path, hd_section, "HDL", f"{from_agent}_{to_agent}_{task_id}",
            {"date": ts, "from": from_agent, "to": to_agent, "task": task_id, "note": note},
            create_section=True, force=True,
        )
    return f"- [{ts}] {from_agent} -> {to_agent} task={task_id} :: {note}"
