"""`evidence` module — append-only trace inside the project brain.

Handlers:
    evidence.record  — append an evidence entry to the brain's PULSE section
    evidence.list    — query the evidence trail (reads from brain PULSE)
    evidence.read    — read a single evidence event by ID

Per the architecture decision (gap 1+6 fix), pulse entries NO LONGER live
in a separate `pulse.jsonl` file. They live inside the project brain's
PULSE section. This keeps the project mind in one place and makes the
brain the single source of truth for every agent working concurrently.
"""

from __future__ import annotations

from ..constants import CYCLES_DIR
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..pulse import append_pulse_to_brain, next_pulse_event_id, read_pulse_from_brain
from ..state import find_project_root


def record_evidence(
    task_id: str,
    kind: str,
    payload: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Append an evidence entry to the brain's PULSE section."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Find which cycle owns this task (search across cycles).
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles", code="NOT_FOUND")

    cycle_id: str | None = None
    for cdir in cycles_base.iterdir():
        if (cdir / "tasks" / f"{task_id}.cortex").exists():
            cycle_id = cdir.name
            break
    if cycle_id is None:
        return CortexOUT.error(f"task {task_id} not found in any cycle", code="NOT_FOUND")

    agent = (ctx or PermissionContext.from_env()).agent_id
    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root,
        event_id=event_id,
        task_id=task_id,
        kind=kind,
        agent=agent,
        payload=payload,
        cycle=cycle_id,
    )

    return CortexOUT.work(
        f"evidence.record ok task={task_id} kind={kind} (in brain PULSE)",
        event_id=event_id,
        task_id=task_id,
        cycle=cycle_id,
        storage="brain.pulse",
    )


def list_evidence(
    task_id: str | None = None,
    cycle: str | None = None,
    since: str | None = None,
    limit: int = 100,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Query the evidence trail (reads from the brain's PULSE section)."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    events = read_pulse_from_brain(
        root,
        task_id=task_id,
        cycle=cycle,
        since=since,
        limit=limit,
    )
    return CortexOUT.work(
        f"events={len(events)} (from brain PULSE)",
        events=[e.get("id", "?") for e in events],
        storage="brain.pulse",
    )


def read_evidence(
    event_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read a single evidence event by ID (from the brain's PULSE section)."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    events = read_pulse_from_brain(root, limit=10_000)
    for event in events:
        if event.get("id") == event_id:
            return CortexOUT.work(
                f"event={event_id} (from brain PULSE)",
                event=event,
                storage="brain.pulse",
            )
    return CortexOUT.error(f"event {event_id} not found", code="NOT_FOUND")


handler_schemas = [
    {"name": "evidence.record", "fn": record_evidence, "description": "Append an evidence entry to pulse.jsonl.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "kind": {"type": "string", "enum": ["note", "artifact", "decision", "metric", "blocker"]}, "payload": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id", "kind", "payload"]}},
    {"name": "evidence.list", "fn": list_evidence, "description": "Query the evidence trail.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "cycle": {"type": "string"}, "since": {"type": "string"}, "limit": {"type": "integer", "default": 100}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "evidence.read", "fn": read_evidence, "description": "Read a single evidence event by ID.", "input_schema": {"type": "object", "properties": {"event_id": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["event_id"]}},
]
