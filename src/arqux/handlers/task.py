"""`task` module — governed tasks.

Handlers:
    task.create    — create a governed task in the current cycle
    task.claim     — an executor claims a task → status: in_progress
    task.update    — update task progress, optionally change status
    task.complete  — mark task done, record evidence
    task.fail      — mark task blocked, record cause
    task.read      — read a task (CORTEX or HCORTEX format)
    task.list      — list tasks with filters
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import (
    CYCLES_DIR,
    OUT_WORK,
    TASKS_DIR,
    TASK_BLOCKED,
    TASK_CANCELLED,
    TASK_DONE,
    TASK_DRAFT,
    TASK_IN_PROGRESS,
    TASK_OPEN,
    TASK_REVIEW,
    TASK_TRANSITIONS,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import (
    cycle_dir,
    find_project_root,
    next_task_id,
    parse_cortex_file as _parse_cortex_file,
    task_path,
    write_cortex_pair,
)
from ..sync import sync_brain


def create_task(
    obj: str,
    pre: list[str] | None = None,
    proc: list[str] | None = None,
    ac: list[str] | None = None,
    blk: list[str] | None = None,
    assignee: str | None = None,
    complexity: str = "standard",
    priority: str = "medium",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Create a governed task in the current cycle."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Find the current cycle.
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")
    open_cycles = [p.name for p in sorted(cycles_base.iterdir()) if p.is_dir()]
    if not open_cycles:
        return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")
    cycle_id = open_cycles[-1]

    task_id = next_task_id(root, cycle_id)
    fm = {
        "id": task_id,
        "status": TASK_OPEN if assignee else TASK_DRAFT,
        "governor": (ctx or PermissionContext.from_env()).agent_id,
        "assignee": assignee or "",
        "priority": priority,
        "complexity": complexity,
        "cycle": cycle_id,
        "created": _now_iso(),
        "updated": _now_iso(),
    }

    body_parts = [f"# OBJ\n{obj}\n"]
    if pre:
        body_parts.append("# PRE\n" + "\n".join(f"- {p}" for p in pre) + "\n")
    if proc:
        body_parts.append("# PROC\n" + "\n".join(f"{i+1}. {p}" for i, p in enumerate(proc)) + "\n")
    if ac:
        body_parts.append("# AC\n" + "\n".join(f"- {a}" for a in ac) + "\n")
    if blk:
        body_parts.append("# BLK\n" + "\n".join(f"- {b}" for b in blk) + "\n")

    body = "\n".join(body_parts)
    write_cortex_pair(
        cycle_dir(root, cycle_id) / TASKS_DIR,
        task_id,
        fm,
        body,
    )

    sync_brain(
        root,
        "task.create",
        metrics={"tasks_active": 1},
        detail=f"task {task_id} created in {cycle_id}",
    )

    return CortexOUT.work(
        f"task.create ok id={task_id}",
        task_id=task_id,
        cycle=cycle_id,
        status=fm["status"],
    )


def claim_task(task_id: str, path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """An executor claims a task → status: in_progress."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    path, fm, body = _load_task(root, task_id)
    if path is None:
        return CortexOUT.error(f"task {task_id} not found", code="NOT_FOUND")

    if fm.get("status") not in (TASK_OPEN, TASK_DRAFT):
        return CortexOUT.error(
            f"task is {fm.get('status')} — cannot claim",
            code="INVALID_STATE",
        )

    caller = (ctx or PermissionContext.from_env()).agent_id
    fm["status"] = TASK_IN_PROGRESS
    fm["assignee"] = caller
    fm["updated"] = _now_iso()
    write_cortex_pair(path.parent, task_id, fm, body)

    return CortexOUT.work(
        f"task.claim ok id={task_id} agent={caller}",
        task_id=task_id,
        status=TASK_IN_PROGRESS,
        assignee=caller,
    )


def update_task(
    task_id: str,
    note: str,
    status: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update task progress, optionally change status."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    path, fm, body = _load_task(root, task_id)
    if path is None:
        return CortexOUT.error(f"task {task_id} not found", code="NOT_FOUND")

    if status and status != fm.get("status"):
        allowed = TASK_TRANSITIONS.get(fm.get("status", ""), ())
        if status not in allowed:
            return CortexOUT.error(
                f"cannot transition {fm.get('status')} -> {status}",
                code="INVALID_STATE",
            )
        fm["status"] = status

    fm["updated"] = _now_iso()
    new_body = body.rstrip() + f"\n\n# NOTE ({_now_iso()})\n{note}\n"
    write_cortex_pair(path.parent, task_id, fm, new_body)

    return CortexOUT.work(
        f"task.update ok id={task_id} status={fm['status']}",
        task_id=task_id,
        status=fm["status"],
    )


def complete_task(
    task_id: str,
    evidence: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Mark a task done and record evidence in the brain's PULSE section."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    path, fm, body = _load_task(root, task_id)
    if path is None:
        return CortexOUT.error(f"task {task_id} not found", code="NOT_FOUND")

    if fm.get("status") == TASK_DONE:
        return CortexOUT.error("task already done", code="INVALID_STATE")

    fm["status"] = TASK_DONE
    fm["updated"] = _now_iso()
    if evidence:
        new_body = body.rstrip() + f"\n\n# EVIDENCE\n{evidence}\n"
    else:
        new_body = body
    write_cortex_pair(path.parent, task_id, fm, new_body)

    # Record in the brain's PULSE section (not a separate file).
    from ..pulse import append_pulse_to_brain, next_pulse_event_id
    agent = (ctx or PermissionContext.from_env()).agent_id
    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root,
        event_id=event_id,
        task_id=task_id,
        kind="task_complete",
        agent=agent,
        payload=evidence or "",
        cycle=fm.get("cycle", ""),
    )

    sync_brain(
        root,
        "task.complete",
        metrics={"tasks_done": 1},
        detail=f"task {task_id} completed",
    )

    return CortexOUT.work(
        f"task.complete ok id={task_id} (evidence in brain PULSE as {event_id})",
        task_id=task_id,
        status=TASK_DONE,
        pulse_event_id=event_id,
    )


def fail_task(
    task_id: str,
    reason: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Mark a task blocked and record the cause in the brain's PULSE section."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    path, fm, body = _load_task(root, task_id)
    if path is None:
        return CortexOUT.error(f"task {task_id} not found", code="NOT_FOUND")

    fm["status"] = TASK_BLOCKED
    fm["updated"] = _now_iso()
    new_body = body.rstrip() + f"\n\n# BLOCK ({_now_iso()})\n{reason}\n"
    write_cortex_pair(path.parent, task_id, fm, new_body)

    from ..pulse import append_pulse_to_brain, next_pulse_event_id
    agent = (ctx or PermissionContext.from_env()).agent_id
    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root,
        event_id=event_id,
        task_id=task_id,
        kind="task_block",
        agent=agent,
        payload=reason,
        cycle=fm.get("cycle", ""),
    )

    return CortexOUT.work(
        f"task.fail ok id={task_id} reason={reason!r} (recorded in brain PULSE as {event_id})",
        task_id=task_id,
        status=TASK_BLOCKED,
        pulse_event_id=event_id,
    )


def read_task(
    task_id: str,
    format: str = "cortex",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read a task (CORTEX or HCORTEX format)."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles", code="NOT_FOUND")

    target: Path | None = None
    for cdir in cycles_base.iterdir():
        candidate = cdir / TASKS_DIR / f"{task_id}.cortex"
        if candidate.exists():
            target = candidate
            break
        candidate_h = cdir / TASKS_DIR / f"{task_id}.md"
        if candidate_h.exists():
            target = candidate_h
            break

    if target is None:
        return CortexOUT.error(f"task {task_id} not found", code="NOT_FOUND")

    # Pick the requested format.
    if format == "hcortex":
        target = target.with_suffix(".md") if target.suffix == ".md" and "cortex" in target.name else target
        hcortex = target.parent / f"{task_id}.md"
        if hcortex.exists():
            content = hcortex.read_text(encoding="utf-8")
        else:
            content = target.read_text(encoding="utf-8")
    else:
        content = target.read_text(encoding="utf-8")

    return CortexOUT.work(
        f"task.read ok id={task_id} format={format}",
        task_id=task_id,
        format=format,
        path=str(target),
        content=content,
    )


def list_tasks(
    status: str | None = None,
    assignee: str | None = None,
    cycle: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List tasks with filters."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.work("no tasks", count=0)

    tasks: list[dict[str, Any]] = []
    cycle_dirs = [cycles_base / cycle] if cycle else sorted(cycles_base.iterdir())
    for cdir in cycle_dirs:
        if not cdir.is_dir():
            continue
        tasks_dir = cdir / TASKS_DIR
        if not tasks_dir.exists():
            continue
        for tpath in sorted(tasks_dir.glob("T-*.cortex")):
            fm, _ = _parse_cortex_file(tpath)
            if status and fm.get("status") != status:
                continue
            if assignee and fm.get("assignee") != assignee:
                continue
            tasks.append({"id": fm.get("id", tpath.stem), "status": fm.get("status"), "cycle": cdir.name})

    return CortexOUT.work(
        f"tasks={len(tasks)}",
        tasks=tasks,
    )


# --- Internal helpers ------------------------------------------------------

def _load_task(root: Path, task_id: str) -> tuple[Path | None, dict[str, Any], str]:
    """Find and parse a task by ID across all cycles."""
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return None, {}, ""
    for cdir in sorted(cycles_base.iterdir()):
        candidate = cdir / TASKS_DIR / f"{task_id}.cortex"
        if candidate.exists():
            fm, body = _parse_cortex_file(candidate)
            return candidate, fm, body
    return None, {}, ""


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
