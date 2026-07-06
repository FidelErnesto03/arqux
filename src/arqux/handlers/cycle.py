"""`cycle` module — work-cycle governance.

Handlers:
    cycle.create   — open a new cycle in the active project
    cycle.list     — list cycles in the active project
    cycle.current  — get the currently active cycle
    cycle.close    — close a cycle (no new tasks can be added)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import (
    ARQUX_DIR,
    CYCLES_DIR,
    CYCLE_CLOSED,
    CYCLE_OPEN,
    OUT_WORK,
    TASKS_DIR,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import (
    cycle_dir,
    find_project_root,
    next_cycle_id,
    parse_cortex_file as _parse_cortex_file,
    write_cortex_pair,
)
from ..constants import (
    CYCLES_DIR,
    CYCLE_CLOSED,
    CYCLE_OPEN,
    OUT_WORK,
    TASKS_DIR,
    TASK_BLOCKED,
    TASK_CANCELLED,
    TASK_DONE,
    TASK_DRAFT,
    TASK_IN_PROGRESS,
    TASK_OPEN,
    TASK_REVIEW,
)


def create_cycle(
    name: str | None = None,
    description: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Open a new cycle in the active project."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycle_id = next_cycle_id(root)
    cdir = cycle_dir(root, cycle_id)
    cdir.mkdir(parents=True, exist_ok=True)

    # Use CYCLE_MANIFEST_TEMPLATE.md from package templates (always available after install).
    template_path = Path(__file__).resolve().parent.parent / "templates" / "CYCLE_MANIFEST_TEMPLATE.md"

    if template_path and template_path.exists():
        raw = template_path.read_text(encoding="utf-8")
        raw = raw.replace('cycle_id: ""', f'cycle_id: "{cycle_id}"')
        raw = raw.replace('name: ""', f'name: "{name or cycle_id}"')
        raw = raw.replace('governor: ""', f'governor: "{(ctx or PermissionContext.from_env()).agent_id}"')
        raw = raw.replace('created_at: ""', f'created_at: "{_now_iso()}"')
        (cdir / "MANIFEST.md").write_text(raw, encoding="utf-8")

    # Also create the legacy cycle.cortex for backward compat
    fm = {
        "id": cycle_id,
        "name": name or cycle_id,
        "description": description or "",
        "status": CYCLE_OPEN,
        "created": _now_iso(),
    }
    body = f"# CYCLE {cycle_id}\n\n{description or ''}\n"
    write_cortex_pair(cdir, "cycle", fm, body)

    return CortexOUT.work(
        f"cycle.create ok id={cycle_id}",
        cycle_id=cycle_id,
        path=str(cdir),
    )


def list_cycles(
    status: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List cycles in the active project."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.work("no cycles yet", count=0)

    cycles: list[str] = []
    for cdir in sorted(cycles_base.iterdir()):
        if not cdir.is_dir():
            continue
        cycles.append(cdir.name)

    return CortexOUT.work(
        f"cycles={len(cycles)}",
        cycles=cycles,
    )


def current_cycle(path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """Get the currently active (most recent open) cycle."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles", code="NOT_FOUND")

    open_cycles = []
    for cdir in sorted(cycles_base.iterdir()):
        if cdir.is_dir():
            open_cycles.append(cdir.name)

    if not open_cycles:
        return CortexOUT.error("no cycles", code="NOT_FOUND")

    return CortexOUT.work(
        f"current={open_cycles[-1]}",
        cycle=open_cycles[-1],
    )


def close_cycle(
    cycle_id: str,
    summary: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Close a cycle with automatic lesson generation.

    1. Checks for open tasks.
    2. Scans completed and failed tasks for patterns.
    3. Auto-generates LESSONS in the project brain.
    4. Records cycle closure evidence in brain PULSE.
    5. Writes cycle summary with metrics.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cdir = cycle_dir(root, cycle_id)
    if not cdir.exists():
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")

    tasks_dir = cdir / TASKS_DIR
    now = _now_iso()

    # 1. Scan all tasks in the cycle
    open_tasks = []
    completed = []
    failed = []
    task_list = sorted(tasks_dir.iterdir()) if tasks_dir.exists() else []

    for tfile in task_list:
        if tfile.suffix not in (".cortex",):
            continue
        try:
            tfm, _ = _parse_cortex_file(tfile)
            ts = tfm.get("status", "")
            tid = tfm.get("id", tfile.stem)
            if ts in (TASK_OPEN, TASK_DRAFT, TASK_IN_PROGRESS, TASK_REVIEW):
                open_tasks.append(tid)
            elif ts == TASK_DONE:
                completed.append(tid)
            elif ts in (TASK_BLOCKED, TASK_CANCELLED):
                failed.append(tid)
        except Exception:
            continue

    # 2. Block if there are open tasks (unless forced via a full summary)
    if open_tasks and not summary:
        return CortexOUT.work(
            f"cycle {cycle_id} has {len(open_tasks)} open tasks: {', '.join(open_tasks)}. "
            f"Close or complete them first, or provide a summary to force close.",
            cycle_id=cycle_id,
            open_tasks=open_tasks,
            hint="Provide a summary to force-close with open tasks.",
        )

    # 3. Auto-generate lessons from completed/failed tasks
    lessons = []
    if failed:
        lessons.append(
            f"LNG:{cycle_id.lower()}_blockers{{type:\"process\", "
            f"cause:\"{len(failed)} task(s) blocked in {cycle_id}\", "
            f"lesson:\"Identify blockers early to avoid cycle delays\"}}"
        )
    if completed:
        lessons.append(
            f"LNG:{cycle_id.lower()}_completion{{type:\"process\", "
            f"cause:\"{len(completed)} task(s) completed in {cycle_id}\", "
            f"lesson:\"Completed tasks show effective cycle planning\"}}"
        )

    # 4. Update brain with lessons and closure evidence
    if lessons:
        try:
            from ..state import read_brain, write_brain_sections
            # find_project_root returns .arqux/ path; read_brain/write_brain_sections
            # expect the project root (parent of .arqux/).
            project_dir = root.parent
            fm, sections, _ = read_brain(project_dir)
            existing = sections.get("LESSONS", "").strip()
            new_lessons = "\n".join(
                f"- [{now}] {l}" for l in lessons
            )
            sections["LESSONS"] = (existing + "\n" + new_lessons).strip() if existing else new_lessons
            # Also add to PULSE
            pulse = sections.get("PULSE", "").strip()
            closure_entry = (
                f"- [{now}] AUD:{cycle_id}_close{{kind:\"cycle\", "
                f"summary:{summary or ''!r}, completed:{len(completed)}, "
                f"failed:{len(failed)}, lessons:{len(lessons)}}}"
            )
            sections["PULSE"] = (pulse + "\n" + closure_entry).strip() if pulse else closure_entry
            write_brain_sections(project_dir, fm, sections)
        except Exception:
            pass

    # 5. Write cycle.cortex with metrics
    fm = {
        "id": cycle_id,
        "status": CYCLE_CLOSED,
        "closed": now,
        "summary": summary or "",
        "tasks_total": len(task_list),
        "tasks_completed": len(completed),
        "tasks_failed": len(failed),
        "tasks_open": len(open_tasks),
        "lessons_generated": len(lessons),
    }
    body = (
        f"# CYCLE {cycle_id} (closed)\n\n"
        f"## Summary\n{summary or 'Cycle closed'}\n\n"
        f"## Metrics\n"
        f"- Tasks completed: {len(completed)}\n"
        f"- Tasks failed: {len(failed)}\n"
        f"- Tasks open on close: {len(open_tasks)}\n"
        f"- Lessons auto-generated: {len(lessons)}\n"
    )
    write_cortex_pair(cdir, "cycle", fm, body)

    return CortexOUT.work(
        f"cycle.close ok id={cycle_id} completed={len(completed)} "
        f"failed={len(failed)} lessons={len(lessons)}",
        cycle_id=cycle_id,
        status=CYCLE_CLOSED,
        tasks_completed=len(completed),
        tasks_failed=len(failed),
        lessons_generated=len(lessons),
    )


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
