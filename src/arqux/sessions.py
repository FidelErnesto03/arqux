"""Session management operations on brain.cortex.

Tracks agent-to-project binding through SESSIONS and HANDOFFS sections
in the project brain.
"""

from __future__ import annotations

from pathlib import Path

from .constants import BRAIN_SECTION_HANDOFFS, BRAIN_SECTION_SESSIONS
from .state import (
    _bump_concurrency,
    _now_iso,
    append_to_brain_section,
    read_brain,
    write_brain_sections,
)


def add_session_to_brain(
    project_root: Path,
    agent_id: str,
    role: str,
) -> str:
    """Add a session entry to the brain's SESSIONS section.

    Returns the rendered session line.
    """
    ts = _now_iso()
    line = f"- [{ts}] agent={agent_id} role={role} status=active"
    fm, sections, _ = read_brain(project_root)
    append_to_brain_section(sections, BRAIN_SECTION_SESSIONS, line)
    _bump_concurrency(fm, agent_id)
    write_brain_sections(project_root, fm, sections)
    return line


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

    Returns the rendered handoff line.
    """
    ts = _now_iso()
    line = f"- [{ts}] {from_agent} -> {to_agent} task={task_id} :: {note}"
    fm, sections, _ = read_brain(project_root)
    append_to_brain_section(sections, BRAIN_SECTION_HANDOFFS, line)
    _bump_concurrency(fm, from_agent)
    write_brain_sections(project_root, fm, sections)
    return line
