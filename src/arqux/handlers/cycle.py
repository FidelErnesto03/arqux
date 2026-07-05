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
    write_cortex_pair,
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
    (cdir / TASKS_DIR).mkdir(exist_ok=True)
    # No pulse.jsonl — pulse events live in the project brain's # PULSE section.

    fm = {
        "id": cycle_id,
        "name": name or cycle_id,
        "description": description or "",
        "status": CYCLE_OPEN,
        "created": _now_iso(),
        "closed": None,
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
    """Close a cycle (no new tasks can be added)."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cdir = cycle_dir(root, cycle_id)
    if not cdir.exists():
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")

    fm = {
        "id": cycle_id,
        "status": CYCLE_CLOSED,
        "closed": _now_iso(),
        "summary": summary or "",
    }
    body = f"# CYCLE {cycle_id} (closed)\n\n{summary or ''}\n"
    write_cortex_pair(cdir, "cycle", fm, body)

    return CortexOUT.work(
        f"cycle.close ok id={cycle_id}",
        cycle_id=cycle_id,
        status=CYCLE_CLOSED,
    )


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
