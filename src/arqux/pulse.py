"""Pulse/evidence and handoff operations on brain.cortex.

Pulse entries (AUD) are lightweight evidence records appended to the brain's
PULSE section. Handoff entries (HDL) track agent-to-agent task handovers.

Both are append-only operations on the brain sections dict.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .constants import ARQUX_DIR, BRAIN_CORTEX
from .state import _now_iso, crud_add, crud_read, find_project_root


def _brain_cortex_path(project_root: Path) -> Path:
    root = find_project_root(start=str(project_root))
    if root is None:
        # Never nest: a path already inside .arqux must not get another .arqux
        # (the fallback produced .arqux/.arqux/brain.cortex.lock — BLP-009).
        base = Path(project_root)
        if base.name == ARQUX_DIR:
            return base / BRAIN_CORTEX
        return project_root / ".arqux" / "brain.cortex"
    return root / "brain.cortex"


# --- Pulse operations --------------------------------------------------------


_PULSE_ID_RE = re.compile(r"^(E-|SES-|OBS-|HDL-)\d+$")


def _is_valid_pulse_id(event_id: str) -> bool:
    """Validate pulse event ID format (BLP-008 GOV-001 P4.1)."""
    return bool(_PULSE_ID_RE.match(event_id))


def _brain_lock(project_root: Path):
    """Brain-wide write lock; see ``session_identity.brain_lock``."""
    from .session_identity import brain_lock

    return brain_lock(project_root)


def next_pulse_event_id(project_root: Path) -> str:
    """Return the next sequential event ID (E-XXXX).

    Canonical format uses hyphen (BLP-008 GOV-001 P3.1).
    Scans existing entries for both hyphen and underscore prefixes
    for backward compatibility. Implements sanity check: if the
    generated ID already exists, keep incrementing (P3.3).
    """
    events = read_pulse_from_brain(project_root, limit=None)
    existing_ids = set()
    if not events:
        return "E-0001"
    max_num = 0
    for ev in events:
        eid = ev.get("id", "")
        existing_ids.add(eid)
        # Accept both hyphen and underscore for backward compat
        if eid.startswith("E-") or eid.startswith("E_"):
            try:
                num = int(eid[2:])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue

    # P3.3: Sanity check — if generated ID already exists, keep incrementing
    candidate = max_num + 1
    while True:
        candidate_id = f"E-{candidate:04d}"
        if candidate_id not in existing_ids:
            return candidate_id
        candidate += 1


def record_pulse(
    project_root: Path,
    *,
    task_id: str | None,
    kind: str,
    agent: str,
    payload: str,
    cycle: str | None = None,
    ses_ref: str | None = None,
) -> str:
    """Allocate an event id and append the pulse under a single brain lock.

    Allocating and writing in two separate critical sections lets two
    processes read the same maximum id and produce the same ``E-XXXX``, with the
    second write silently overwriting the first (and its ``ses_ref``).
    """
    with _brain_lock(project_root):
        event_id = next_pulse_event_id(project_root)
        append_pulse_to_brain(
            project_root,
            event_id=event_id,
            task_id=task_id,
            kind=kind,
            agent=agent,
            payload=payload,
            cycle=cycle,
            ses_ref=ses_ref,
        )
    return event_id


def append_pulse_to_brain(
    project_root: Path,
    *,
    event_id: str,
    task_id: str | None,
    kind: str,
    agent: str,
    payload: str,
    cycle: str | None = None,
    ses_ref: str | None = None,
) -> str:
    """Append a pulse entry to the brain's PULSE section.

    Validates naming conventions (BLP-008 GOV-001 P4.1):
    - event_id must start with E- or SES- or OBS-
    - kind must be a known pulse kind

    Returns pulse summary line.

    Note: event_id uses hyphen (E-0004) for API consistency.
    Internally, CRUD stores with underscore (E_0004) because
    the CODEC-CORTEX parser uses hyphen as a selector separator.
    """
    # P4.1: Validate naming conventions
    if not _is_valid_pulse_id(event_id):
        raise ValueError(
            f"invalid pulse event_id={event_id!r}: must start with "
            f"E-, SES-, OBS-, or HDL-"
        )
    if not kind or not isinstance(kind, str):
        raise ValueError(f"kind is required (got {kind!r})")
    ts = _now_iso()
    brain_path = _brain_cortex_path(project_root)
    # AUD requires non-empty evidence/result (E034). An empty payload records
    # nothing — synthesize the event's identity so the evidence field always
    # says *something* (HD-01 audit finding).
    payload = payload or f"{kind} on {task_id or '-'}"
    value = {"date": ts, "event": event_id, "task": task_id or "-", "kind": kind, "agent": agent, "result": payload, "evidence": payload}
    if cycle:
        value["cycle"] = cycle
    # CYCLE-14 / BLP-001: membership. A pulse that does not say which session
    # produced it cannot be compacted later without guessing.
    if ses_ref:
        value["ses_ref"] = ses_ref
    with _brain_lock(project_root):
        # Last line of defence: a caller that pre-allocated its id outside the
        # lock may hand us one that another process just took. Renaming here is
        # what keeps two processes from silently overwriting each other's
        # evidence (and its membership).
        if event_id in _existing_ids(brain_path):
            event_id = next_pulse_event_id(project_root)
            value["event"] = event_id
        crud_add(
            brain_path, "$6", "AUD", event_id.replace("-", "_"),
            value,
            create_section=True, force=True,
        )
    return f"- [{ts}] id={event_id} task={task_id or '-'} kind={kind} agent={agent} :: {payload}"


def _existing_ids(brain_path: Path) -> set[str]:
    """Ids already present in PULSE, both API and storage spelling."""
    try:
        result = crud_read(brain_path, "$6/AUD:*")
    except Exception:
        return set()
    ids = set()
    for entry in result.get("entries", []):
        value = entry.get("value")
        value = value if isinstance(value, dict) else {}
        ids.add(value.get("event", entry.get("name", "")))
    return ids


def read_pulse_from_brain(
    project_root: Path,
    *,
    task_id: str | None = None,
    cycle: str | None = None,
    since: str | None = None,
    ses_ref: str | None = None,
    limit: int | None = 100,
    offset: int = 0,
) -> list[dict[str, str]]:
    """Read pulse entries from the brain's PULSE section via crud_read.

    Each entry is returned as dict with fields:
        {ts, id, task, kind, cycle, agent, payload}

    ``limit=None`` reads all matching entries; ``offset`` skips the
    first N matching entries.
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
            "ses_ref": val.get("ses_ref", ""),
        }
        if task_id and ev["task"] != task_id:
            continue
        if cycle and ev.get("cycle") != cycle:
            continue
        if ses_ref and ev.get("ses_ref") != ses_ref:
            continue
        if since and ev["ts"] < since:
            continue
        entries.append(ev)
        if limit is not None and len(entries) >= offset + limit:
            break
    return entries[offset:]


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


def _normalize_id(event_id: str) -> str:
    """Compare ids regardless of the storage spelling (E-0005 / E_0005)."""
    return (event_id or "").replace("_", "-").strip()


def _line_entry_id(line: str) -> str:
    """The id a PULSE line actually declares, or '' when the line has none.

    Handles both the stored ``AUD:E_0005{...}`` form and the legacy
    ``- [ts] id=E-0005 task=...`` form.
    """
    stripped = line.strip()
    if stripped.startswith("AUD:"):
        rest = stripped[len("AUD:"):]
        name = re.split(r"[{\s]", rest, maxsplit=1)[0]
        return _normalize_id(name)
    if stripped.startswith("- ["):
        m = re.search(r"\bid=(\S+)", stripped)
        return _normalize_id(m.group(1)) if m else ""
    return ""


def _atomic_write_text(path: Path, text: str) -> None:
    """Replace *path* through a temporary file (caller holds the brain lock)."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


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
    # Compare the entry's OWN id, never a substring. An id appearing inside a
    # payload (e.g. "E-0005" quoted in another entry's evidence) must not take
    # that other entry down with it.
    wanted = {_normalize_id(eid) for eid in entry_ids}
    pruned = 0
    kept: list[str] = []
    for line in lines:
        if _line_entry_id(line) in wanted:
            pruned += 1
            continue
        kept.append(line)
    if not dry_run:
        _atomic_write_text(brain_path, "\n".join(kept) + "\n")
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
    ses_ref: str | None = None,
) -> dict:
    """Compact pulse entries for a completed session.

    With ``ses_ref`` (CYCLE-14 / BLP-001) selection is by *membership*: only
    pulses whose ``ses_ref`` is exactly this session are compacted. Concurrent
    sessions interleave in PULSE, and legacy pulses carry no membership at all
    — neither may be silently reassigned or pruned by position.

    Without ``ses_ref`` the legacy positional rule applies unchanged (everything
    between this SES and the previous one), so brains written before real
    session identity keep their previous behaviour.
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
    if ses_ref:
        owner = ses_entry.get("ses_ref") or ""
        if owner != ses_ref:
            # Including an unlabelled close: compacting by membership requires
            # proving the close belongs to the session being compacted. Without
            # that proof the event could belong to anyone.
            return {
                "error": (
                    f"session event {session_id} belongs to "
                    f"{owner or 'no recorded session'}, not to {ses_ref}"
                ),
                "compacted": False,
            }
        entries_to_compact = [
            e for e in all_entries
            if e.get("kind") != "session"
            and e.get("ses_ref") == ses_ref
            and e["id"] != session_id
        ]
    else:
        entries_to_compact = [
            all_entries[j] for j in range(prev_ses_idx + 1, ses_idx)
            if all_entries[j].get("kind") != "session"
        ]
    entry_count = len(entries_to_compact)

    lng_name = f"session_{(ses_ref or session_id).replace('-', '_')}"
    kind_counts: dict[str, int] = {}
    for e in entries_to_compact:
        k = e.get("kind", "unknown")
        kind_counts[k] = kind_counts.get(k, 0) + 1
    summary = ",".join(f"{k}:{v}" for k, v in sorted(kind_counts.items()))

    # The compactor rewrites the whole PULSE section twice (lesson + prune), so
    # its mutations belong to the same exclusion as every other brain writer.
    # The idempotency check must live in that same critical section: checking
    # here and writing there is a TOCTOU gap where every concurrent compactor
    # observes "not yet compacted" and writes its own lesson.
    with _brain_lock(project_root):
        return _compact_locked(
            brain_path, project_root, session_id, ses_ref, agent_id, entry_count,
            entries_to_compact, lng_name, summary, dry_run,
        )


def _compact_locked(
    brain_path, project_root, session_id, ses_ref, agent_id, entry_count,
    entries_to_compact, lng_name, summary, dry_run,
) -> dict:
    if dry_run:
        return {"dry_run": True, "selection": "membership" if ses_ref else "positional", "entry_count": entry_count, "ses_preserved": True, "entries_to_prune": [e["id"] for e in entries_to_compact], "lng_name": lng_name, "summary": summary, "compacted": False}

    # Idempotency check BEFORE entry count — already compacted sessions may have
    # 0 entries because all were pruned. It shares this critical section with
    # the write that follows it, which is what makes the guard atomic.
    try:
        existing = crud_read(brain_path, f"$7/LNG:{lng_name}")
        if existing.get("entries"):
            return {"skip": True,
                    "reason": f"already compacted (LNG:{lng_name} exists)",
                    "lng_name": lng_name, "entry_count": entry_count,
                    "compacted": False}
    except Exception:
        pass

    if entry_count < 5:
        return {"skip": True, "reason": f"only {entry_count} entries (< 5)",
                "entry_count": entry_count, "compacted": False}

    entry_ids = [e["id"] for e in entries_to_compact]
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
         "session_id": session_id, "ses_ref": ses_ref or "", "agent": agent_id,
         "date": _now_iso()},
        create_section=True, force=True,
    )

    prune_result = _prune_pulse_entries(brain_path, entry_ids)

    meta_id = next_pulse_event_id(project_root)
    append_pulse_to_brain(
        project_root, event_id=meta_id, task_id="-", kind="pulse_compact",
        agent=agent_id, ses_ref=ses_ref or None,
        payload=(f"pulse.compact ok session={session_id} ses_ref={ses_ref or '-'} "
                 f"pruned={prune_result['pruned']} lng={lng_name} summary={summary}"),
    )

    return {"compacted": True, "selection": "membership" if ses_ref else "positional", "pruned": prune_result["pruned"], "entry_count": entry_count, "ses_preserved": True, "meta_event": meta_id, "lng_name": lng_name, "summary": summary}
