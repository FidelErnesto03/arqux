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
from ..sync import reconcile_cycle, sync_brain
from .execution import ExecutionError, execute_action


def create_task(
    obj: str = "",
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
    cycle: str | None = None,
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
    content_ignored: list[str] = []
    if content:
        from ..cortex.parse_content import parse_content_entry, unused_content_keys
        parsed = parse_content_entry(content)
        if parsed:
            # Merge rule: content wins if key exists, else individual param.
            obj = parsed.get("obj", obj)
            assignee = parsed.get("assignee", assignee or "")
            complexity = parsed.get("complexity", complexity)
            priority = parsed.get("priority", priority)
            # Lists — content wins; a scalar coerces to a single-item list
            # instead of being silently dropped.
            if "pre" in parsed:
                pre = parsed["pre"] if isinstance(parsed["pre"], list) else [str(parsed["pre"])]
            if "proc" in parsed:
                proc = parsed["proc"] if isinstance(parsed["proc"], list) else [str(parsed["proc"])]
            if "ac" in parsed:
                ac = parsed["ac"] if isinstance(parsed["ac"], list) else [str(parsed["ac"])]
            if "blk" in parsed:
                blk = parsed["blk"] if isinstance(parsed["blk"], list) else [str(parsed["blk"])]
            content_ignored = unused_content_keys(
                parsed,
                {"obj", "assignee", "complexity", "priority", "pre", "proc", "ac", "blk"},
                raw=content,
            )
        else:
            content_ignored = ["<content did not parse>"]

    pre = [p for p in (pre or []) if str(p).strip()]
    proc = [p for p in (proc or []) if str(p).strip()]
    ac = [a for a in (ac or []) if str(a).strip()]
    blk = [b for b in (blk or []) if str(b).strip()]

    if not obj:
        return CortexOUT.error(
            "obj is required (pass obj or content with an obj key)",
            code="INVALID_ARGS",
        )

    # Find the target cycle: explicit > active/open cycle > last OPEN directory.
    # FIX (T-037): before, `_cc.data` (a CortexOUT has `.fields`, not `.data`)
    # was always missing, so the fallback silently picked the last directory by
    # name — which could be a CLOSED cycle (E-1816 pattern, task.create).
    from ..timelog_capture import cycle_is_closed, require_open_cycle

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")
    cycle_dirs = [p.name for p in sorted(cycles_base.iterdir()) if p.is_dir()]
    if not cycle_dirs:
        return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")

    cycle_id = (cycle or "").strip()
    if cycle_id and cycle_id not in cycle_dirs:
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")
    if not cycle_id:
        from .cycle import current_cycle as _current_cycle

        _cc = _current_cycle(path=path)
        _open = _cc.fields.get("open_cycles", []) if hasattr(_cc, "fields") else []
        cycle_id = _open[-1] if _open else ""
    if not cycle_id:
        open_names = [n for n in cycle_dirs if not cycle_is_closed(root, n)]
        cycle_id = open_names[-1] if open_names else cycle_dirs[-1]

    rejection = require_open_cycle(root, cycle_id, action="task.create")
    if rejection:
        return CortexOUT.error(
            rejection["message"], code=rejection["code"],
            remediation=rejection["remediation"],
        )

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

    reconcile_cycle(root, cycle_id)

    fields: dict[str, Any] = {
        "task_id": task_id,
        "cycle": cycle_id,
        "status": fm["status"],
    }
    if content_ignored:
        fields["content_ignored"] = content_ignored
    return CortexOUT.work(f"task.create ok id={task_id}", **fields)


def claim_task(task_id: str, path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """An executor claims a task → status: in_progress."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    path, fm, body = _load_task(root, task_id, cycle=_cycle_from_path(path), path=path)
    if path is None:
        return _task_lookup_error(task_id, fm)

    # BLP-022 invariante A: reject before mutating when this project has session
    # identity but none is bound to this execution (E-1805).
    from ..timelog_capture import require_bound_session

    rejection = require_bound_session(root, ctx, action="task.claim")
    if rejection:
        return CortexOUT.error(
            rejection["message"], code=rejection["code"],
            remediation=rejection["remediation"],
        )

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

    from ..timelog_capture import observe, unbound_warning

    lifecycle = observe(root, ctx, event="open",
                        operation_ref=f"task:{task_id}", activity=f"task:{task_id}")

    return CortexOUT.work(
        f"task.claim ok id={task_id} agent={caller}",
        task_id=task_id,
        status=TASK_IN_PROGRESS,
        assignee=caller,
        lifecycle=lifecycle,
        warnings=[w for w in (unbound_warning(lifecycle, action="task.claim"),) if w],
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

    path, fm, body = _load_task(root, task_id, cycle=_cycle_from_path(path), path=path)
    if path is None:
        return _task_lookup_error(task_id, fm)

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

    path, fm, body = _load_task(root, task_id, cycle=_cycle_from_path(path), path=path)
    if path is None:
        return _task_lookup_error(task_id, fm)

    # BLP-022 invariante A: same pre-write gate as task.claim (E-1805).
    from ..timelog_capture import require_bound_session

    rejection = require_bound_session(root, ctx, action="task.complete")
    if rejection:
        return CortexOUT.error(
            rejection["message"], code=rejection["code"],
            remediation=rejection["remediation"],
        )

    if fm.get("status") == TASK_DONE:
        return CortexOUT.error("task already done", code="INVALID_STATE")

    fm["status"] = TASK_DONE
    fm["updated"] = _now_iso()
    new_body = body.rstrip() + f"\n\n# EVIDENCE\n{evidence}\n" if evidence else body
    write_cortex_pair(path.parent, task_id, fm, new_body)

    # Record in the brain's PULSE section (not a separate file).
    from ..pulse import record_pulse
    agent = (ctx or PermissionContext.from_env()).agent_id
    event_id = record_pulse(
        root,
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

    from ..timelog_capture import observe, unbound_warning

    lifecycle = observe(root, ctx, event="close",
                        operation_ref=f"task:{task_id}", activity=f"task:{task_id}")

    return CortexOUT.work(
        f"task.complete ok id={task_id} (evidence in brain PULSE as {event_id})",
        task_id=task_id,
        status=TASK_DONE,
        pulse_event_id=event_id,
        lifecycle=lifecycle,
        warnings=[w for w in (unbound_warning(lifecycle, action="task.complete"),) if w],
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

    path, fm, body = _load_task(root, task_id, cycle=_cycle_from_path(path), path=path)
    if path is None:
        return _task_lookup_error(task_id, fm)

    fm["status"] = TASK_BLOCKED
    fm["updated"] = _now_iso()
    new_body = body.rstrip() + f"\n\n# BLOCK ({_now_iso()})\n{reason}\n"
    write_cortex_pair(path.parent, task_id, fm, new_body)

    from ..pulse import record_pulse
    agent = (ctx or PermissionContext.from_env()).agent_id
    event_id = record_pulse(
        root,
        task_id=task_id,
        kind="task_block",
        agent=agent,
        payload=reason,
        cycle=fm.get("cycle", ""),
    )

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    from ..timelog_capture import observe, unbound_warning

    lifecycle = observe(root, ctx, event="close",
                        operation_ref=f"task:{task_id}", activity=f"task:{task_id}")

    return CortexOUT.work(
        f"task.fail ok id={task_id} reason={reason!r} (recorded in brain PULSE as {event_id})",
        task_id=task_id,
        status=TASK_BLOCKED,
        pulse_event_id=event_id,
        lifecycle=lifecycle,
        warnings=[w for w in (unbound_warning(lifecycle, action="task.fail"),) if w],
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

    # BLP-fix (G-7): restringir la busqueda al ciclo derivado del path;
    # BLP-006: sin ciclo derivable el ciclo actual del proyecto gana y
    # multiples coincidencias fuera de el devuelven TASK_AMBIGUOUS.
    _cycle = _cycle_from_path(path)
    target, matches = _resolve_task_file(root, task_id, _cycle, _current_cycle_id(root, path))
    if target is None:
        if len(matches) > 1:
            cycles = sorted({m.parent.parent.name for m in matches})
            return CortexOUT.error(
                f"task {task_id} is ambiguous — exists in cycles "
                f"{', '.join(cycles)}; pass a cycle-scoped path",
                code="TASK_AMBIGUOUS",
            )
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
    limit: int | None = None,
    offset: int = 0,
) -> CortexOUT:
    """List tasks with filters.

    Paginated when ``limit`` is given: fields total, returned, offset
    and next_offset report the pagination state.
    """
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

    try:
        offset_i = int(offset)
        limit_i = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        return CortexOUT.error("limit and offset must be integers", code="INVALID_ARGS")
    if limit_i is not None and (limit_i < 1 or offset_i < 0):
        return CortexOUT.error("limit must be >= 1 and offset must be >= 0", code="INVALID_ARGS")
    if offset_i < 0:
        return CortexOUT.error("offset must be >= 0", code="INVALID_ARGS")

    total = len(tasks)
    page = tasks[offset_i:] if limit_i is None else tasks[offset_i : offset_i + limit_i]
    next_offset = (
        offset_i + limit_i
        if limit_i is not None and offset_i + limit_i < total
        else None
    )

    return CortexOUT.work(
        f"tasks={len(page)}",
        tasks=page,
        total=total,
        returned=len(page),
        offset=offset_i,
        next_offset=next_offset,
    )


# --- Internal helpers ------------------------------------------------------

def _cycle_from_path(path: str | None) -> str | None:
    """Derive the cycle ID from a path if it points inside a cycle dir.

    BLP-fix (G-7): when a handler receives a path that resolves to
    ``.../cycles/CYCLE-XX``, return ``CYCLE-XX`` so task lookups are
    scoped to that cycle instead of scanning all cycles.
    """
    if not path:
        return None
    p = Path(path)
    # Walk up looking for a 'cycles' parent.
    for parent in [p, *p.parents]:
        if parent.name == "cycles" and parent.parent.is_dir():
            # path is the cycles dir itself -> use current cycle fallback
            return None
        if parent.parent.name == "cycles":
            return parent.name
    return None


def _current_cycle_id(root: Path, path: str | None = None) -> str | None:
    """Return the project's most recent non-closed cycle.

    Same precedence rule as ``create_task``: ``current_cycle()`` open
    cycles, last entry. Falls back to the last cycle directory by name.
    """
    try:
        from .cycle import current_cycle as _current_cycle

        _cc = _current_cycle(path=path or str(root))
        _open = _cc.data.get("open_cycles", []) if hasattr(_cc, "data") else []
        if _open:
            return _open[-1]
    except Exception:
        pass
    cycles_base = root / CYCLES_DIR
    if cycles_base.exists():
        names = [c.name for c in sorted(cycles_base.iterdir()) if c.is_dir()]
        if names:
            return names[-1]
    return None


def _resolve_task_file(
    root: Path,
    task_id: str,
    cycle: str | None = None,
    current_cycle_id: str | None = None,
) -> tuple[Path | None, list[Path]]:
    """Resolve a task file with deterministic cycle precedence (BLP-006).

    Returns ``(chosen, matches)``:

    - explicit ``cycle``: search only that cycle directory.
    - no cycle: the project's current cycle wins if the task exists there.
    - otherwise all cycles are scanned: a single match becomes ``chosen``;
      multiple matches leave ``chosen=None`` and ``matches`` lists every
      candidate so the caller can report TASK_AMBIGUOUS instead of
      silently returning the first alphabetical cycle.
    """
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return None, []

    def _in(cdir: Path) -> Path | None:
        for ext in (".cortex", ".md"):
            candidate = cdir / TASKS_DIR / f"{task_id}{ext}"
            if candidate.exists():
                return candidate
        return None

    cdirs = [c for c in sorted(cycles_base.iterdir()) if c.is_dir()]

    if cycle:
        for cdir in cdirs:
            if cdir.name != cycle:
                continue
            hit = _in(cdir)
            return (hit, [hit]) if hit else (None, [])
        return None, []

    if current_cycle_id:
        for cdir in cdirs:
            if cdir.name == current_cycle_id:
                hit = _in(cdir)
                if hit:
                    return hit, [hit]
                break

    matches = [hit for cdir in cdirs if (hit := _in(cdir)) is not None]
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def _task_lookup_error(task_id: str, fm: dict[str, Any]) -> CortexOUT:
    """Build the lookup error for ``_load_task`` callers (BLP-006)."""
    ambiguous = fm.get("_ambiguous_cycles") if isinstance(fm, dict) else None
    if ambiguous:
        return CortexOUT.error(
            f"task {task_id} is ambiguous — exists in cycles "
            f"{', '.join(ambiguous)}; pass a cycle-scoped path",
            code="TASK_AMBIGUOUS",
        )
    return CortexOUT.error(f"task {task_id} not found", code="NOT_FOUND")


def _load_task(
    root: Path,
    task_id: str,
    cycle: str | None = None,
    path: str | None = None,
) -> tuple[Path | None, dict[str, Any], str]:
    """Find and parse a task by ID.

    BLP-fix (G-5/G-7): if ``cycle`` is provided, restrict the search to
    that cycle only instead of scanning all cycles (which caused task_id
    collisions across cycles).

    BLP-006: without ``cycle``, the project's current cycle wins; a single
    match elsewhere is returned; multiple matches make the lookup
    ambiguous and ``fm`` carries ``_ambiguous_cycles`` so callers report
    TASK_AMBIGUOUS instead of silently picking the first one.
    """
    chosen, matches = _resolve_task_file(root, task_id, cycle, _current_cycle_id(root, path))
    if chosen is not None:
        fm, body = _parse_cortex_file(chosen)
        return chosen, fm, body
    if len(matches) > 1:
        return None, {"_ambiguous_cycles": sorted({m.parent.parent.name for m in matches})}, ""
    return None, {}, ""


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# task.run (BLP-010)
# ---------------------------------------------------------------------------


def _step_execution_spec(step: str) -> tuple[str, dict[str, Any]] | None:
    """Extract ``(action, params)`` from a procedure step.

    Same marker as blueprint.execute::

        - [ ] hacer algo [exec:write_file path=out.txt content=hola]

    Returns ``None`` when the step declares no action, so the caller can
    report it as unavailable instead of pretending it ran (BLP-005).
    """
    import re as _re

    match = _re.search(r"\[exec:(\w+)((?:\s+[^\s\]]+=[^\]]*)?)\s*\]\s*$", step)
    if not match:
        return None
    params: dict[str, Any] = {}
    for key, value in _re.findall(r"(\w+)=([^\s\]]*)", match.group(2) or ""):
        params[key] = value
    return match.group(1), params


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

    arqux_root = find_project_root(start=path)
    if arqux_root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # find_project_root returns the ``.arqux/`` directory, which the rest of
    # this handler expects (it searches cycles/ beneath it). Execution is
    # separately confined to the project directory above it, so that a task
    # step cannot write outside the project (BLP-005 CA-18).
    root = arqux_root
    exec_root = arqux_root.parent

    # Find the task file (BLP-006: same deterministic resolution as
    # _load_task/read_task — no arbitrary first-match across cycles).
    task_path, matches = _resolve_task_file(
        root, task_id, _cycle_from_path(path), _current_cycle_id(root, path)
    )
    if task_path is None:
        if len(matches) > 1:
            cycles = sorted({m.parent.parent.name for m in matches})
            return CortexOUT.error(
                f"task {task_id} is ambiguous — exists in cycles "
                f"{', '.join(cycles)}; pass a cycle-scoped path",
                code="TASK_AMBIGUOUS",
            )
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

    if dry_run:
        # A dry run reports the plan and touches nothing.
        preconditions_report: list[dict[str, Any]] = [
            {"precondition": p, "status": "parsed"} for p in preconditions
        ]
        execution_report: list[dict[str, Any]] = [
            {"step": i + 1, "description": step, "status": "parsed"}
            for i, step in enumerate(procedure_steps)
        ]
        return CortexOUT.work(
            f"task.run dry_run task_id={task_id} steps={len(procedure_steps)}",
            task_id=task_id,
            dry_run=True,
            outcome="dry_run",
            preconditions=preconditions_report,
            execution=execution_report,
            evidence="dry run: no state was modified",
        )

    # BLP-005: preconditions are reported as unchecked. They are not
    # machine-verifiable, so claiming them "verified" was a lie.
    preconditions_report = [
        {"precondition": p, "status": "unchecked"} for p in preconditions
    ]

    # Run each procedure step through the real execution mechanism. A step
    # is executable only when it declares an action, using the same
    # ``[exec:action k=v ...]`` marker as blueprint.execute.
    execution_report: list[dict[str, Any]] = []
    failure_reason = ""
    for i, step in enumerate(procedure_steps, start=1):
        spec = _step_execution_spec(step)
        if spec is None:
            execution_report.append(
                {"step": i, "description": step, "status": "unavailable",
                 "reason": "no_execution_spec"}
            )
            failure_reason = failure_reason or f"paso {i}: sin especificación de ejecución"
            break
        action, params = spec
        try:
            result = execute_action(action, params, ctx=ctx, root=exec_root)
        except ExecutionError as exc:
            execution_report.append(
                {"step": i, "description": step, "status": "failed",
                 "reason": exc.message, "code": exc.code}
            )
            failure_reason = failure_reason or f"paso {i}: {exc.message}"
            break
        if not result.ok:
            execution_report.append(
                {"step": i, "description": step, "status": "failed",
                 "reason": result.reason}
            )
            failure_reason = failure_reason or f"paso {i}: {result.reason}"
            break
        execution_report.append(
            {
                "step": i,
                "description": step,
                "status": "executed",
                "action": action,
                "evidence_ref": result.evidence_ref,
                "actor": result.actor,
                "role": result.role,
            }
        )

    steps_ok = bool(execution_report) and all(
        s["status"] == "executed" for s in execution_report
    )

    # BLP-005 CA-11: the outcome follows the execution. It is no longer
    # "complete" by default, and a run with no executable steps cannot
    # claim success.
    if fail_reason_override:
        outcome = "fail"
        evidence = fail_reason_override
    elif failure_reason:
        outcome = "fail"
        evidence = failure_reason
    elif steps_ok:
        outcome = "complete"
        refs = [s.get("evidence_ref") for s in execution_report if s.get("evidence_ref")]
        evidence = evidence_override or (
            f"Task {task_id} executed {len(execution_report)} steps; "
            f"evidence={refs[0] if refs else 'none'}"
        )
    else:
        outcome = "fail"
        evidence = f"Task {task_id}: no executable steps produced evidence."

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
    """Parse a task file into sections.

    Two formats are in the wild. ``create_task`` writes canonical
    CODEC-CORTEX (``$3: PROCEDURE`` holding ``STP:stepN`` entries), while
    older files use legacy markdown (``# PROC`` with a numbered list).
    Only the legacy form was understood, so a freshly created task parsed
    as having no procedure at all — and BLP-005's executor then had nothing
    to run. Both are read here.
    """
    import re
    out: dict[str, Any] = {
        "obj": "",
        "pre": [],
        "proc": [],
        "ac": [],
        "blk": [],
    }

    # -- Canonical CORTEX -------------------------------------------------
    cortex_obj = re.search(r'^OBJ:objective\{text:"(.*)"\}\s*$', text, re.MULTILINE)
    if cortex_obj:
        out["obj"] = cortex_obj.group(1)
    for step in re.finditer(r'^STP:step\w*\{action:"(.*)"\}\s*$', text, re.MULTILINE):
        out["proc"].append(step.group(1))
    for sigil, key in (("PRE", "pre"), ("AC", "ac"), ("BLK", "blk")):
        section = re.search(
            rf'^\$\d+:\s*{sigil}\b(.*?)(?=^\$\d+:|\Z)', text, re.MULTILINE | re.DOTALL
        )
        if not section:
            continue
        for entry in re.finditer(r'^(\w+):\w+\{(.*)\}\s*$', section.group(1), re.MULTILINE):
            attrs = entry.group(2)
            match = re.search(r'(?:text|desc|value):"(.*?)"', attrs)
            out[key].append(match.group(1) if match else attrs)

    if out["obj"] or out["proc"]:
        return out

    # -- Legacy markdown --------------------------------------------------
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
        from ..pulse import record_pulse
        agent = (ctx or PermissionContext.from_env()).agent_id
        record_pulse(
            root,
            task_id=task_id,
            kind="task_run",
            agent=agent,
            payload=f"[task.run] outcome={outcome}",
        )
    except Exception:  # noqa: BLE001
        pass


handler_schemas = [
    {"name": "task.create", "fn": create_task, "description": "Create a governed task in the current cycle. Accepts a 'content' CORTEX entry string (BLP-009) with keys obj, pre[], proc[], ac[], blk[], assignee, complexity, priority — parsed values override individual params (merge rule: content wins; scalar list values coerce to single-item lists). obj is optional when content carries an obj key; INVALID_ARGS otherwise.", "input_schema": {"type": "object", "properties": {"obj": {"type": "string", "description": "Objective text. Optional when content carries an obj key."}, "pre": {"type": "array", "items": {"type": "string"}}, "proc": {"type": "array", "items": {"type": "string"}}, "ac": {"type": "array", "items": {"type": "string"}}, "blk": {"type": "array", "items": {"type": "string"}}, "assignee": {"type": "string"}, "complexity": {"type": "string", "enum": ["simple", "standard", "complex"]}, "priority": {"type": "string", "enum": ["low", "medium", "high"]}, "content": {"type": "string", "description": "CORTEX entry string with keys obj,pre[],proc[],ac[],blk[],assignee,complexity,priority. Lists as key:[v1,v2,v3] (a scalar value coerces to a single-item list). Parsed values override individual params (BLP-009: content wins)."}, "cycle": {"type": "string", "description": "Target cycle ID (e.g. CYCLE-07). If omitted, uses the current cycle."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "task.claim", "fn": claim_task, "description": "An executor claims a task → status: in_progress.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id"]}},
    {"name": "task.update", "fn": update_task, "description": "Update task progress, optionally change status.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "note": {"type": "string"}, "status": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id", "note"]}},
    {"name": "task.complete", "fn": complete_task, "description": "Mark a task done and record evidence.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "evidence": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id"]}},
    {"name": "task.fail", "fn": fail_task, "description": "Mark a task blocked and record the cause.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "reason": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id", "reason"]}},
    {"name": "task.read", "fn": read_task, "description": "Read a task (CORTEX or HCORTEX format).", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "format": {"type": "string", "enum": ["cortex", "hcortex"], "default": "cortex"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["task_id"]}},
    {"name": "task.list", "fn": list_tasks, "description": "List tasks with filters. Paginated: limit + offset; fields total, returned, offset, next_offset report the pagination state.", "input_schema": {"type": "object", "properties": {"status": {"type": "string"}, "assignee": {"type": "string"}, "cycle": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}, "limit": {"type": "integer", "description": "Max tasks per page (default: all)."}, "offset": {"type": "integer", "default": 0, "description": "Tasks to skip before the page."}}}},
    {"name": "task.run", "fn": run_task, "description": "Run a governed task: verify preconditions, execute procedure steps, mark complete or fail (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "content": {"type": "string", "description": "CORTEX content with keys task_id, evidence, fail_reason."}, "dry_run": {"type": "boolean", "default": False, "description": "If true, report what would happen without modifying state."}, "path": {"type": "string"}}, "required": ["task_id"]}},
]
