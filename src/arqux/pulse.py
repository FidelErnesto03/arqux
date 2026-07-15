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
        if eid.startswith("E-") or eid.startswith("E_"):
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


# --- Pulse compaction (BLP-013) ----------------------------------------------


def _prune_pulse_entries(
    brain_path: Path,
    entry_ids: list[str],
    *,
    dry_run: bool = False,
) -> dict:
    """Remove specific pulse entries from the brain's PULSE section."""
    if not brain_path.exists():
        return {"pruned": 0, "errors": 0, "dry_run": dry_run}
    text = brain_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    pruned = 0
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (stripped.startswith("AUD:") or stripped.startswith("- [")) and any(
            eid in stripped for eid in entry_ids
        ):
            pruned += 1
            continue
        kept.append(line)
    if not dry_run:
        brain_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    result: dict = {"pruned": pruned, "errors": 0, "dry_run": dry_run}
    if dry_run:
        result["would_prune"] = pruned
    return result


def compact_session_pulse(
    project_root: Path,
    *,
    session_id: str,
    agent_id: str = "system",
    dry_run: bool = False,
) -> dict:
    """Compact pulse entries for a completed session.

    Reads all pulse entries, prunes non-SES entries between this SES
    and the previous SES, writes a consolidated LNG lesson, and records
    a meta-event AUD.
    """
    brain_path = _brain_cortex_path(project_root)
    if not brain_path.exists():
        return {"error": "brain not found", "compacted": False}

    all_entries = read_pulse_from_brain(project_root, limit=10000)

    ses_entry = None
    for e in all_entries:
        if e["id"] == session_id and e.get("kind") == "session":
            ses_entry = e
            break
    if ses_entry is None:
        return {"error": f"SES {session_id} not found", "compacted": False}

    prev_ses_idx = -1
    ses_entries = [e for e in all_entries if e.get("kind") == "session"]
    for i, e in enumerate(ses_entries):
        if e["id"] == session_id and i > 0:
            prev_id = ses_entries[i - 1]["id"]
            for j, ae in enumerate(all_entries):
                if ae["id"] == prev_id:
                    prev_ses_idx = j
                    break
            break

    ses_idx = next((j for j, ae in enumerate(all_entries) if ae["id"] == session_id), len(all_entries) - 1)
    entries_to_compact = [
        all_entries[j] for j in range(prev_ses_idx + 1, ses_idx)
        if all_entries[j].get("kind") != "session"
    ]
    entry_count = len(entries_to_compact)

    # Idempotency check BEFORE entry count — already compacted sessions
    # may have 0 entries because all were pruned
    lng_name = f"session_{session_id.replace('-', '_')}"
    try:
        existing = crud_read(brain_path, f"$7/LNG:{lng_name}")
        if existing.get("entries"):
            return {"skip": True, "reason": f"already compacted (LNG:{lng_name} exists)", "lng_name": lng_name, "entry_count": entry_count, "compacted": False}
    except Exception:
        pass

    if entry_count < 5:
        return {"skip": True, "reason": f"only {entry_count} entries (< 5)", "entry_count": entry_count, "compacted": False}

    kind_counts: dict[str, int] = {}
    for e in entries_to_compact:
        k = e.get("kind", "unknown")
        kind_counts[k] = kind_counts.get(k, 0) + 1
    summary = ",".join(f"{k}:{v}" for k, v in sorted(kind_counts.items()))

    entry_ids = [e["id"] for e in entries_to_compact]

    if dry_run:
        return {"dry_run": True, "entry_count": entry_count, "ses_preserved": True, "entries_to_prune": entry_ids, "lng_name": lng_name, "summary": summary, "compacted": False}

    # Write LNG — ensure $0 has LNG sigil, then use crud_add
    text = brain_path.read_text(encoding="utf-8")
    if "$0" not in text[:200]:
        # No $0 glossary — add minimal one
        glossary = "$0\n# -- $0: MINIMAL LOCAL GLOSSARY --\n# LNG | lesson | attrs | M | Episodic | Behavioral lessons\n"
        text = glossary + "\n" + text
        brain_path.write_text(text, encoding="utf-8")
    elif "LNG " not in text[:text.find("\n\n")] if "\n\n" in text else "LNG " not in text[:500]:
        # $0 exists but no LNG — prepend LNG declaration
        idx = text.find("\n", text.find("$0"))
        if idx > 0:
            text = text[:idx] + "\n# LNG | lesson | attrs | M | Episodic | Behavioral lessons" + text[idx:]
            brain_path.write_text(text, encoding="utf-8")

    crud_add(
        brain_path, "$7", "LNG", lng_name,
        {"type": "session", "entry_count": entry_count, "summary": summary,
         "session_id": session_id, "agent": agent_id, "date": _now_iso()},
        create_section=True, force=True,
    )

    prune_result = _prune_pulse_entries(brain_path, entry_ids)

    meta_id = next_pulse_event_id(project_root)
    append_pulse_to_brain(project_root, event_id=meta_id, task_id="-", kind="pulse_compact", agent=agent_id, payload=f"pulse.compact ok session={session_id} pruned={prune_result['pruned']} lng={lng_name} summary={summary}")

    return {"compacted": True, "pruned": prune_result["pruned"], "entry_count": entry_count, "ses_preserved": True, "meta_event": meta_id, "lng_name": lng_name, "summary": summary}
