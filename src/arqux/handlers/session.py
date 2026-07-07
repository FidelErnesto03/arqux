"""`session` module — session handoff between agents.

Handlers:
    session.close   — generate a portable SES entry in brain PULSE
    session.resume  — read the last SES and restore context
    session.status  — read SES metadata without restoring full context

SES entries are stored in the brain's PULSE section as evidence-like
entries with kind="session". Each SES is self-contained and < 2KB.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..pulse import append_pulse_to_brain, next_pulse_event_id, read_pulse_from_brain
from ..state import find_project_root


def close(
    summary: str,
    blps: str | None = None,
    tasks: str | None = None,
    decisions: str | None = None,
    gaps: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Close the current session and write a portable SES entry to brain PULSE.

    Args:
        summary: Short human-readable summary of what was accomplished.
        blps: Comma-separated list of active blueprint IDs (e.g. "BLP-006,BLP-007").
        tasks: Comma-separated list of pending task IDs (e.g. "T-002,T-003").
        decisions: Comma-separated list of key decisions made.
        gaps: Comma-separated list of detected gaps or pending items.
        path: Path to project root. Defaults to cwd.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    agent = (ctx or PermissionContext.from_env()).agent_id

    blps_list = _parse_csv(blps)
    tasks_list = _parse_csv(tasks)
    decisions_list = _parse_csv(decisions)
    gaps_list = _parse_csv(gaps)

    ses_payload = _build_ses(
        summary=summary,
        blps=blps_list,
        tasks=tasks_list,
        decisions=decisions_list,
        gaps=gaps_list,
    )

    if len(ses_payload) > 2048:
        return CortexOUT.error(
            f"SES exceeds 2KB ({len(ses_payload)} bytes). Prioritize critical info.",
            code="SES_TOO_LARGE",
        )

    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root,
        event_id=event_id,
        task_id="-",
        kind="session",
        agent=agent,
        payload=ses_payload,
    )

    return CortexOUT.work(
        "session.close ok",
        event_id=event_id,
        agent=agent,
        size_bytes=len(ses_payload),
        summary=summary,
    )


def resume(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read the last SES entry from brain PULSE and return the context."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    events = read_pulse_from_brain(root, limit=10_000)
    ses_entries = [e for e in events if e.get("kind") == "session"]

    if not ses_entries:
        return CortexOUT.error("no previous session found", code="NOT_FOUND")

    last_ses = ses_entries[-1]
    payload = last_ses.get("payload", "")

    parsed = _parse_ses(payload)

    return CortexOUT.work(
        "session.resume ok",
        event_id=last_ses.get("id", "?"),
        ts=last_ses.get("ts", ""),
        agent=last_ses.get("agent", ""),
        summary=parsed.get("summary", ""),
        blps=parsed.get("blps", []),
        tasks=parsed.get("tasks", []),
        decisions=parsed.get("decisions", []),
        gaps=parsed.get("gaps", []),
        lng_count=parsed.get("lng_count", 0),
    )


def status(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read SES metadata without restoring full context."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    events = read_pulse_from_brain(root, limit=10_000)
    ses_entries = [e for e in events if e.get("kind") == "session"]

    if not ses_entries:
        return CortexOUT.error("no previous session found", code="NOT_FOUND")

    last_ses = ses_entries[-1]
    payload = last_ses.get("payload", "")
    parsed = _parse_ses(payload)

    return CortexOUT.work(
        "session.status ok",
        event_id=last_ses.get("id", "?"),
        ts=last_ses.get("ts", ""),
        agent=last_ses.get("agent", ""),
        summary=parsed.get("summary", ""),
        blp_count=len(parsed.get("blps", [])),
        task_count=len(parsed.get("tasks", [])),
        decision_count=len(parsed.get("decisions", [])),
        gap_count=len(parsed.get("gaps", [])),
        lng_count=parsed.get("lng_count", 0),
    )


# --- SES format helpers -----------------------------------------------------

SES_TEMPLATE = (
    "SES:{ts} agent={agent} "
    'summary="{summary}" '
    "blps=[{blps}] "
    "tasks=[{tasks}] "
    "decisions=[{decisions}] "
    "gaps=[{gaps}] "
    "lng_count={lng_count}"
)


def _build_ses(
    summary: str,
    blps: list[str],
    tasks: list[str],
    decisions: list[str],
    gaps: list[str],
    agent: str = "",
) -> str:
    """Build a compact SES string (< 2KB)."""
    import time

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return SES_TEMPLATE.format(
        ts=ts,
        agent=agent,
        summary=_escape_ses_value(summary),
        blps=",".join(blps) if blps else "-",
        tasks=",".join(tasks) if tasks else "-",
        decisions=",".join(decisions) if decisions else "-",
        gaps=",".join(gaps) if gaps else "-",
        lng_count=len(blps) + len(tasks) + len(decisions) + len(gaps),
    )


def _parse_ses(payload: str) -> dict[str, Any]:
    """Parse a SES string back into structured data."""
    result: dict[str, Any] = {
        "summary": "",
        "blps": [],
        "tasks": [],
        "decisions": [],
        "gaps": [],
        "lng_count": 0,
    }

    m = re.search(r'summary="([^"]*)"', payload)
    if m:
        result["summary"] = m.group(1)

    for field in ("blps", "tasks", "decisions", "gaps"):
        m = re.search(rf"{field}=\[([^\]]*)\]", payload)
        if m:
            raw = m.group(1)
            result[field] = [x.strip() for x in raw.split(",") if x.strip() and x.strip() != "-"]

    m = re.search(r"lng_count=(\d+)", payload)
    if m:
        result["lng_count"] = int(m.group(1))

    return result


def _parse_csv(value: str | None) -> list[str]:
    """Parse a comma-separated string into a list."""
    if not value or not value.strip():
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _escape_ses_value(value: str) -> str:
    """Escape a value for safe embedding in a SES string."""
    return value.replace('"', "'").replace("\n", " ")
