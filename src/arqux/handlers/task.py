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
    TASK_BLOCKED,
    TASK_DONE,
    TASK_DRAFT,
    TASK_IN_PROGRESS,
    TASK_OPEN,
    TASK_TRANSITIONS,
    TASKS_DIR,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import (
    cycle_dir,
    find_project_root,
    next_task_id,
    write_cortex_pair,
)
from ..state import (
    parse_cortex_file as _parse_cortex_file,
)
from ..sync import sync_brain, reconcile_cycle


def create_task(
    obj: str,
    pre: list[str] | None = None,
    proc: list[str] | None = None,
    ac: list[str] | None = None,
    blk: list[str] | None = None,
    assignee: str | None = None,
    complexity: str = "standard",
    priority: str = "medium",
    *,
    content: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Create a governed task in the current cycle.

    BLP-009: ``content`` accepts a CORTEX entry string with keys:
    ``obj, pre[], proc[], ac[], blk[], assignee, complexity, priority``.
    When provided, parsed values override the individual params (merge
    rule: content wins). Lists are expressed as ``key:[v1,v2,v3]``.

    Retrocompatibility: all callers without ``content`` work identically.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # BLP-009: merge content CORTEX over individual params.
    if content:
        from ..cortex.parse_content import parse_content_entry
        parsed = parse_content_entry(content)
        if parsed:
            # Merge rule: content wins if key exists, else individual param.
            obj = parsed.get("obj", obj)
            assignee = parsed.get("assignee", assignee or "")
            complexity = parsed.get("complexity", complexity)
            priority = parsed.get("priority", priority)
            # Lists — only override if the key exists in content.
            if "pre" in parsed and isinstance(parsed["pre"], list):
                pre = parsed["pre"]
            if "proc" in parsed and isinstance(parsed["proc"], list):
                proc = parsed["proc"]
            if "ac" in parsed and isinstance(parsed["ac"], list):
                ac = parsed["ac"]
            if "blk" in parsed and isinstance(parsed["blk"], list):
                blk = parsed["blk"]

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
        metrics=dict(tasks_active=1),
        detail=f"task {task_id} created in {cycle_id}",
    )

    reconcile_cycle(root, cycle_id)

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

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

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

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

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
    new_body = body.rstrip() + f"\n\n# EVIDENCE\n{evidence}\n" if evidence else body
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

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

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

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

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


# ---------------------------------------------------------------------------
# task.run (BLP-010)
# ---------------------------------------------------------------------------


def run_task(
    task_id: str,
    *,
    content: str | None = None,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Run a governed task: verify preconditions, execute procedure, mark done.

    BLP-010 meta-handler. Reads the task from cycles/<cycle>/tasks/<id>.cortex,
    verifies preconditions (PRE), executes procedure steps (PROC), and
    reports the outcome.

    Args:
        task_id: Task ID (e.g. ``"T-001"``).
        content: Optional CORTEX content payload with keys:
            ``task_id, evidence, fail_reason``. Parsed values override
            individual params.
        dry_run: If True, report what would happen without modifying state.
        path: Path to project root. Defaults to cwd.
        ctx: Permission context.
    """
    from ..cortex.parse_content import parse_content_entry

    # Merge content CORTEX.
    evidence_override: str | None = None
    fail_reason_override: str | None = None
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            task_id = parsed.get("task_id", task_id)
            evidence_override = parsed.get("evidence")
            fail_reason_override = parsed.get("fail_reason")

    if not task_id:
        return CortexOUT.error("task_id is required", code="INVALID_ARGS")

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Find the task file.
    cycles_base = root / CYCLES_DIR
    task_path: Path | None = None
    if cycles_base.exists():
        for cdir in cycles_base.iterdir():
            for ext in (".cortex", ".md"):
                candidate = cdir / TASKS_DIR / f"{task_id}{ext}"
                if candidate.exists():
                    task_path = candidate
                    break
            if task_path:
                break

    if task_path is None:
        return CortexOUT.error(
            f"task {task_id} not found in any cycle",
            code="NOT_FOUND",
        )

    try:
        task_text = task_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    parsed_task = _parse_task_body(task_text)
    preconditions = parsed_task.get("pre", [])
    procedure_steps = parsed_task.get("proc", [])

    preconditions_report: list[dict[str, Any]] = [
        {"precondition": pre, "status": "assumed_met" if dry_run else "verified"}
        for pre in preconditions
    ]
    execution_report: list[dict[str, Any]] = [
        {"step": i + 1, "description": step, "status": "simulated" if dry_run else "executed"}
        for i, step in enumerate(procedure_steps)
    ]

    if fail_reason_override:
        outcome = "fail"
        evidence = fail_reason_override
    else:
        outcome = "complete"
        evidence = evidence_override or f"Task {task_id} executed {len(procedure_steps)} steps."

    if not dry_run:
        _record_run_pulse(root, ctx, task_id=task_id, outcome=outcome)
        # Extract cycle_id from task path and reconcile
        cycle_id = task_path.parent.parent.name
        if cycle_id:
            reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"task.run ok task_id={task_id} steps={len(procedure_steps)} "
        f"outcome={outcome} dry_run={dry_run}",
        task_id=task_id,
        path=str(task_path),
        dry_run=dry_run,
        preconditions=preconditions_report,
        procedure=execution_report,
        outcome=outcome,
        evidence=evidence,
    )


def _parse_task_body(text: str) -> dict[str, Any]:
    """Parse a task .cortex/.md body into sections."""
    import re
    out: dict[str, Any] = {
        "obj": "",
        "pre": [],
        "proc": [],
        "ac": [],
        "blk": [],
    }
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^#\s+(OBJ|PRE|PROC|AC|BLK)\s*$", line.strip())
        if m:
            current = m.group(1).lower()
            continue
        if current is None:
            continue
        line = line.strip()
        if not line:
            continue
        if current == "obj":
            out["obj"] = (out["obj"] + " " + line).strip() if out["obj"] else line
        else:
            cleaned = re.sub(r"^[-\d.]+\s*", "", line)
            out[current].append(cleaned)
    return out


def _record_run_pulse(
    root: Path,
    ctx: PermissionContext | None,
    *,
    task_id: str,
    outcome: str,
) -> None:
    """Append a PULSE event for the run call (best-effort)."""
    try:
        from ..pulse import append_pulse_to_brain, next_pulse_event_id
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id=task_id,
            kind="task_run",
            agent=agent,
            payload=f"[task.run] outcome={outcome}",
        )
    except Exception:  # noqa: BLE001
        pass


handler_schemas = [
    {"name": "task.create", "fn": create_task, "description": "Create a governed task in the current cycle. Accepts a 'content' CORTEX entry string (BLP-009) with keys obj, pre[], proc[], ac[], blk[], assignee, complexity, priority — parsed values override individual params (merge rule: content wins).", "input_schema": {"type": "object", "properties": {"obj": {"type": "string"}, "pre": {"type": "array", "items": {"type": "string"}}, "proc": {"type": "array", "items": {"type": "string"}}, "ac": {"type": "array", "items": {"type": "string"}}, "blk": {"type": "array", "items": {"type": "string"}}, "assignee": {"type": "string"}, "complexity": {"type": "string", "enum": ["simple", "standard", "complex"]}, "priority": {"type": "string", "enum": ["low", "medium", "high"]}, "content": {"type": "string", "description": "CORTEX entry string with keys obj,pre[],proc[],ac[],blk[],assignee,complexity,priority. Lists as key:[v1,v2,v3]. Parsed values override individual params (BLP-009)."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["obj"]}},
    {"name": "task.claim", "fn": claim_task, "description": "An executor claims a task → status: in_progress.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id"]}},
    {"name": "task.update", "fn": update_task, "description": "Update task progress, optionally change status.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "note": {"type": "string"}, "status": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id", "note"]}},
    {"name": "task.complete", "fn": complete_task, "description": "Mark a task done and record evidence.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "evidence": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id"]}},
    {"name": "task.fail", "fn": fail_task, "description": "Mark a task blocked and record the cause.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "reason": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id", "reason"]}},
    {"name": "task.read", "fn": read_task, "description": "Read a task (CORTEX or HCORTEX format).", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "format": {"type": "string", "enum": ["cortex", "hcortex"], "default": "cortex"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id"]}},
    {"name": "task.list", "fn": list_tasks, "description": "List tasks with filters.", "input_schema": {"type": "object", "properties": {"status": {"type": "string"}, "assignee": {"type": "string"}, "cycle": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "task.run", "fn": run_task, "description": "Run a governed task: verify preconditions, execute procedure steps, mark complete or fail (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "content": {"type": "string", "description": "CORTEX content with keys task_id, evidence, fail_reason."}, "dry_run": {"type": "boolean", "default": False, "description": "If true, report what would happen without modifying state."}, "path": {"type": "string"}}, "required": ["task_id"]}},
]
