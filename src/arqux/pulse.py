"""Pulse/evidence and handoff operations on brain.cortex.

Pulse entries (AUD) are lightweight evidence records appended to the brain's
PULSE section. Handoff entries (HDL) track agent-to-agent task handovers.

Both are append-only operations on the brain sections dict.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .constants import BRAIN_SECTION_HANDOFFS, BRAIN_SECTION_PULSE
from .state import (
    _bump_concurrency,
    _now_iso,
    append_to_brain_section,
    read_brain,
    write_brain_sections,
)


# --- Pulse operations --------------------------------------------------------


def next_pulse_event_id(project_root: Path) -> str:
    """Return the next sequential event ID (E-XXXX)."""
    events = read_pulse_from_brain(project_root)
    if not events:
        return "E-0001"
    max_num = 0
    for ev in events:
        eid = ev.get("id", "")
        if eid.startswith("E-"):
            try:
                num = int(eid[2:])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
    return f"E-{max_num + 1:04d}"


def append_pulse_to_brain(
    project_root: Path,
    *,
    event_id: str,
    task_id: str | None,
    kind: str,
    agent: str,
    payload: str,
    cycle: str | None = None,
) -> str:
    """Append a pulse entry to the brain's PULSE section.

    Returns the rendered pulse line.
    """
    fm, sections, _ = read_brain(project_root)
    ts = _now_iso()
    cycle_part = f" cycle={cycle}" if cycle else ""
    line = (
        f"- [{ts}] id={event_id} task={task_id or '-'} kind={kind}{cycle_part} "
        f"agent={agent} :: {payload}"
    )
    append_to_brain_section(sections, BRAIN_SECTION_PULSE, line)
    _bump_concurrency(fm, agent)
    write_brain_sections(project_root, fm, sections)
    return line


def read_pulse_from_brain(
    project_root: Path,
    *,
    task_id: str | None = None,
    cycle: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Read pulse entries from the brain's PULSE section.

    Each entry is returned as a dict with parsed fields:
        {ts, id, task, kind, cycle, agent, payload}
    """
    _, sections, _ = read_brain(project_root)
    raw = sections.get(BRAIN_SECTION_PULSE, "")
    entries: list[dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        entry = _parse_pulse_line(line)
        if not entry:
            continue
        if task_id and entry.get("task") != task_id:
            continue
        if cycle and entry.get("cycle") != cycle:
            continue
        if since and entry.get("ts", "") < since:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries


def _parse_pulse_line(line: str) -> dict[str, str] | None:
    """Parse a single pulse line: '- [ts] id=... task=... kind=... ... :: payload'."""
    m = re.match(
        r"^- \[(?P<ts>[^\]]+)\] id=(?P<id>\S+) task=(?P<task>\S+) kind=(?P<kind>\S+)"
        r"(?: cycle=(?P<cycle>\S+))? agent=(?P<agent>\S+) :: (?P<payload>.*)$",
        line,
    )
    if not m:
        return None
    entry: dict[str, str] = {
        "ts": m.group("ts"),
        "id": m.group("id"),
        "task": m.group("task"),
        "kind": m.group("kind"),
        "agent": m.group("agent"),
        "payload": m.group("payload"),
    }
    if m.group("cycle"):
        entry["cycle"] = m.group("cycle")
    return entry


# --- Handoff operations ------------------------------------------------------


def read_handoffs(
    project_root: Path,
    *,
    agent: str | None = None,
    task_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Read handoff entries from the brain's HANDOFFS section."""
    _, sections, _ = read_brain(project_root)
    raw = sections.get(BRAIN_SECTION_HANDOFFS, "")
    entries: list[dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        m = re.match(
            r"^- \[(?P<ts>[^\]]+)\] (?P<from>\S+) -> (?P<to>\S+) task=(?P<task>\S+) :: (?P<note>.*)$",
            line,
        )
        if not m:
            continue
        entry = {
            "ts": m.group("ts"),
            "from": m.group("from"),
            "to": m.group("to"),
            "task": m.group("task"),
            "note": m.group("note"),
        }
        if agent and agent not in (entry["from"], entry["to"]):
            continue
        if task_id and entry["task"] != task_id:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries
