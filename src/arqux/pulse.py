"""Pulse/evidence and handoff operations on brain.cortex.

Pulse entries (AUD) are lightweight evidence records appended to the brain's
PULSE section. Handoff entries (HDL) track agent-to-agent task handovers.

Both are append-only operations on the brain sections dict.
"""

from __future__ import annotations

import re
from pathlib import Path

from .state import _now_iso, crud_add, crud_read, find_project_root


def _brain_cortex_path(project_root: Path) -> Path:
    root = find_project_root(start=str(project_root))
    if root is None:
        return project_root / ".arqux" / "brain.cortex"
    return root / "brain.cortex"


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

    Returns pulse summary line.
    """
    ts = _now_iso()
    brain_path = _brain_cortex_path(project_root)
    value = {"date": ts, "event": event_id, "task": task_id or "-", "kind": kind, "agent": agent, "result": payload, "evidence": payload}
    if cycle:
        value["cycle"] = cycle
    crud_add(
        brain_path, "$6", "AUD", event_id.replace("-", "_"),
        value,
        create_section=True, force=True,
    )
    return f"- [{ts}] id={event_id} task={task_id or '-'} kind={kind} agent={agent} :: {payload}"


def read_pulse_from_brain(
    project_root: Path,
    *,
    task_id: str | None = None,
    cycle: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Read pulse entries from the brain's PULSE section via crud_read.

    Each entry is returned as dict with fields:
        {ts, id, task, kind, cycle, agent, payload}
    """
    brain_path = _brain_cortex_path(project_root)
    if not brain_path.exists():
        return []
    try:
        result = crud_read(brain_path, "$6/AUD:*")
    except Exception:
        return []
    entries: list[dict[str, str]] = []
    for entry in result.get("entries", []):
        val = entry.get("value", {})
        if not isinstance(val, dict):
            continue
        ev = {
            "ts": val.get("date", ""),
            "id": val.get("event", entry.get("name", "")),
            "task": val.get("task", "-"),
            "kind": val.get("kind", ""),
            "agent": val.get("agent", ""),
            "payload": val.get("evidence", val.get("result", "")),
            "cycle": val.get("cycle", ""),
        }
        if task_id and ev["task"] != task_id:
            continue
        if cycle and ev.get("cycle") != cycle:
            continue
        if since and ev["ts"] < since:
            continue
        entries.append(ev)
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
    """Read handoff entries from the brain via crud_read."""
    brain_path = _brain_cortex_path(project_root)
    if not brain_path.exists():
        return []
    try:
        result = crud_read(brain_path, "$5/HDL:*")
    except Exception:
        return []
    entries: list[dict[str, str]] = []
    for entry in result.get("entries", []):
        val = entry.get("value", {})
        if not isinstance(val, dict):
            continue
        ev = {
            "ts": val.get("date", ""),
            "from": val.get("from", ""),
            "to": val.get("to", ""),
            "task": val.get("task", ""),
            "note": val.get("note", ""),
        }
        if agent and agent not in (ev["from"], ev["to"]):
            continue
        if task_id and ev["task"] != task_id:
            continue
        entries.append(ev)
        if len(entries) >= limit:
            break
    return entries
