"""
PATCH: src/arqux/handlers/cycle.py
==================================

This file REPLACES the existing cycle.py to add:
    - ALTO-1 fix: `cycle.mature` handler for draft → ready transition.

CHANGES vs original:
    1. New handler `mature_cycle()` that transitions a cycle from
       status="draft" to status="ready".
    2. `create_cycle()` now writes status="draft" explicitly (was implicit
       via template), and returns an instruction to call cycle.mature.
    3. `close_cycle()` unchanged except for also updating MANIFEST.md.

The new handler is registered in handlers/__init__.py as "cycle.mature".
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..constants import (
    ARQUX_DIR,
    CYCLE_CLOSED,
    CYCLE_OPEN,
    CYCLES_DIR,
    TASK_BLOCKED,
    TASK_CANCELLED,
    TASK_DONE,
    TASK_DRAFT,
    TASK_IN_PROGRESS,
    TASK_OPEN,
    TASK_REVIEW,
    TASKS_DIR,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext, enforce_ctx
from ..state import (
    cycle_dir,
    find_project_root,
    next_cycle_id,
    write_cortex_pair,
)
from ..state import (
    parse_cortex_file as _parse_cortex_file,
)
from ..sync import reconcile_cycle, sync_brain
from .blueprint._synthesize_common import parse_content_sections

# --- Cycle states (NEW in v0.4.0) -----------------------------------------
# Previously cycles only had "open" and "closed" states. The MANIFEST.md
# template writes status="draft" but blueprint.create validates
# status in ("ready", "active"). This was the ALTO-1 bug.
# v0.4.0 introduces explicit cycle state machine:
#     draft → ready → active → closed
# The "open" state is kept as alias for backward compat (mapped to "ready").

CYCLE_DRAFT = "draft"
CYCLE_READY = "ready"
CYCLE_ACTIVE = "active"

CYCLE_TRANSITIONS_V040: dict[str, tuple[str, ...]] = {
    CYCLE_DRAFT: (CYCLE_READY,),
    CYCLE_READY: (CYCLE_ACTIVE, CYCLE_CLOSED),
    CYCLE_ACTIVE: (CYCLE_CLOSED,),
    CYCLE_CLOSED: (),
    # Backward compat: "open" maps to ready.
    CYCLE_OPEN: (CYCLE_ACTIVE, CYCLE_CLOSED),
}


def _find_workspace_template(root: Path, template_name: str) -> Path | None:
    """Walk up from root to find .arqux/templates/<template_name>."""
    cursor = root
    while True:
        tmpl = cursor / ARQUX_DIR / "templates" / template_name
        if tmpl.exists():
            return tmpl
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


TEMPLATE_PLACEHOLDER_PATTERNS: list[str] = [
    r"_¿[Pp]or\s+qué",
    r"_¿A\s+qué\s+objetivos",
    r"_Ítem\s+\d+",
    r"_Objetivo\s+[—–-]",
    r"_Directriz\s+\d+",
    r"_YYYY[ -]MM[ -]DD",
    r"_Descripción",
    r"_¿Qué\s+debe\s+",
    r"_BLP[ -]NNN",
    r"_Título",
    r"_draft/ready/\.\.\.",
    r"_CP[ -]NN",
    r"_Regla\s+\d+",
    r"_critical/high/medium/low",
    r"_CYC[ -]OBJ[ -]N",
    r"_agente",
    r"_¿Qué\s+debe\s+validarse",
]


def _manifest_body_has_placeholders(text: str) -> list[str]:
    """Check if the manifest body contains template placeholders.

    Returns a list of matched placeholder patterns (empty = clean).
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    body = parts[2]
    found: list[str] = []
    for pattern in TEMPLATE_PLACEHOLDER_PATTERNS:
        if re.search(pattern, body):
            found.append(pattern)
    return found


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_cycle_manifest(cdir: Path) -> dict[str, Any] | None:
    """Read the cycle's MANIFEST.md frontmatter."""
    mf = cdir / "MANIFEST.md"
    if not mf.exists():
        return None
    text = mf.read_text(encoding="utf-8")
    # Parse frontmatter (between --- markers).
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    fm_raw = parts[1].strip()
    fm: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        if line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        fm[key.strip()] = value
    return fm


def _write_cycle_manifest(cdir: Path, fm: dict[str, Any]) -> None:
    """Write the cycle's MANIFEST.md with updated frontmatter."""
    mf = cdir / "MANIFEST.md"
    text = mf.read_text(encoding="utf-8") if mf.exists() else ""
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else ""

    new_fm_lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, str):
            new_fm_lines.append(f'{k}: "{v}"')
        elif isinstance(v, bool):
            new_fm_lines.append(f'{k}: {str(v).lower()}')
        else:
            new_fm_lines.append(f"{k}: {v}")
    new_fm_lines.append("---")

    new_text = "\n".join(new_fm_lines) + "\n" + body
    mf.write_text(new_text, encoding="utf-8")


def create_cycle(
    name: str | None = None,
    description: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Open a new cycle in the active project.

    v0.4.0 change: cycle starts in status="draft". Call `cycle.mature`
    to transition to "ready" before creating blueprints.
    """
    ctx = enforce_ctx(ctx, "cycle.create")
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycle_id = next_cycle_id(root)
    cdir = cycle_dir(root, cycle_id)
    cdir.mkdir(parents=True, exist_ok=True)

    template_path = _find_workspace_template(root, "CYCLE_MANIFEST_TEMPLATE.md")
    if template_path is None:
        template_path = Path(__file__).resolve().parent.parent / "templates" / "CYCLE_MANIFEST_TEMPLATE.md"

    if template_path and template_path.exists():
        raw = template_path.read_text(encoding="utf-8")
        raw = raw.replace('cycle_id: ""', f'cycle_id: "{cycle_id}"')
        raw = raw.replace('name: ""', f'name: "{name or cycle_id}"')
        raw = raw.replace('governor: ""', f'governor: "{ctx.agent_id}"')
        raw = raw.replace('created_at: ""', f'created_at: "{_now_iso()}"')
        # v0.4.0: explicit draft status.
        raw = raw.replace('status: "open"', 'status: "draft"')
        (cdir / "MANIFEST.md").write_text(raw, encoding="utf-8")

    fm = {
        "id": cycle_id,
        "name": name or cycle_id,
        "description": description or "",
        "status": CYCLE_DRAFT,
        "created": _now_iso(),
    }
    body = f"# CYCLE {cycle_id}\n\n{description or ''}\n"
    write_cortex_pair(cdir, "cycle", fm, body)

    sync_brain(root, "cycle.create", focus=f"Ciclo {cycle_id} iniciado", detail=f"cycle {cycle_id} created")

    reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"cycle.create ok id={cycle_id} status=draft",
        cycle_id=cycle_id,
        path=str(cdir),
        status=CYCLE_DRAFT,
        instruction=(
            f"Cycle {cycle_id} is in draft state. "
            "Call cycle.mature to transition to ready before creating blueprints."
        ),
    )


def mature_cycle(
    cycle_id: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Mature a cycle from draft → ready.

    NEW handler in v0.4.0. Fixes ALTO-1 (workflow incompleto).

    A cycle in "ready" state allows blueprint creation. The maturation
    step is intentional: it forces the governor to explicitly declare
    the cycle ready for work, providing a natural checkpoint for review.

    Args:
        cycle_id: Cycle to mature. If None, uses the most recent cycle.
        path: Path to project root.
        ctx: Permission context (requires GOVERNOR role in strict mode).

    Returns:
        CortexOUT with cycle_id and new status.
    """
    ctx = enforce_ctx(ctx, "cycle.mature")
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles", code="NOT_FOUND")

    if cycle_id is None:
        all_cycles = sorted(
            d.name for d in cycles_base.iterdir() if d.is_dir()
        )
        if not all_cycles:
            return CortexOUT.error("no cycles", code="NOT_FOUND")
        cycle_id = all_cycles[-1]

    cdir = cycle_dir(root, cycle_id)
    if not cdir.exists():
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")

    fm = _read_cycle_manifest(cdir)
    if fm is None:
        return CortexOUT.error(
            f"cycle {cycle_id} has no MANIFEST.md", code="INVALID_STATE"
        )

    current_status = fm.get("status", "draft")

    if current_status == CYCLE_READY:
        return CortexOUT.work(
            f"cycle {cycle_id} already in ready state",
            cycle_id=cycle_id,
            status=CYCLE_READY,
            no_op=True,
        )
    if current_status == CYCLE_ACTIVE:
        return CortexOUT.work(
            f"cycle {cycle_id} is active (already matured)",
            cycle_id=cycle_id,
            status=CYCLE_ACTIVE,
            no_op=True,
        )
    if current_status == CYCLE_CLOSED:
        return CortexOUT.error(
            f"cycle {cycle_id} is closed; cannot mature",
            code="INVALID_STATE",
        )
    if current_status not in (CYCLE_DRAFT, CYCLE_OPEN):
        return CortexOUT.error(
            f"cycle {cycle_id} has unexpected status {current_status!r}; "
            f"expected draft or open",
            code="INVALID_STATE",
        )

    # Validate manifest content: reject template placeholders.
    mf_path = cdir / "MANIFEST.md"
    if mf_path.exists():
        mf_text = mf_path.read_text(encoding="utf-8")
        placeholders = _manifest_body_has_placeholders(mf_text)
        if placeholders:
            return CortexOUT.error(
                f"cycle {cycle_id} MANIFEST.md still contains template placeholders; "
                f"run cycle.synthesize() first. Found: {placeholders}",
                code="INVALID_STATE",
            )

    fm["status"] = CYCLE_READY
    fm["matured_at"] = _now_iso()
    fm["matured_by"] = ctx.agent_id
    _write_cycle_manifest(cdir, fm)

    cortex_path = cdir / "cycle.cortex"
    if cortex_path.exists():
        try:
            cfm, body = _parse_cortex_file(cortex_path)
            if cfm:
                cfm["status"] = CYCLE_READY
                cfm["matured_at"] = _now_iso()
                write_cortex_pair(cdir, "cycle", cfm, body)
        except Exception:
            pass

    sync_brain(
        root,
        "cycle.mature",
        focus=f"Ciclo {cycle_id} madurado",
        detail=f"cycle {cycle_id} transitioned draft -> ready by {ctx.agent_id}",
    )

    reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"cycle.mature ok id={cycle_id} status=ready",
        cycle_id=cycle_id,
        status=CYCLE_READY,
        matured_by=ctx.agent_id,
        instruction=(
            f"Cycle {cycle_id} is now ready. "
            "You can create blueprints with blueprint.create."
        ),
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
    """Get all currently active cycles (non-closed).

    Returns ALL cycles whose status is NOT 'closed'.
    The list is sorted by name (highest number = most recent).

    For projects with legacy cycles (no MANIFEST.md), they are
    treated as open for backward compatibility.

    Returns:
        CortexOUT with:
        - open_cycles: list of all non-closed cycle IDs
        - count: number of open cycles
        - latest: the most recent cycle (highest ID)
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles", code="NOT_FOUND")

    open_cycles = []
    for cdir in sorted(cycles_base.iterdir(), reverse=True):
        if not cdir.is_dir():
            continue
        # Read manifest to verify cycle is not closed.
        fm = _read_cycle_manifest(cdir)
        if fm is None:
            # No manifest — treat as open for backward compat.
            open_cycles.append(cdir.name)
            continue
        status = fm.get("status", "")
        if status != CYCLE_CLOSED:
            open_cycles.append(cdir.name)

    # Reverse to get ascending order, so open_cycles[-1] is the most recent.
    open_cycles.reverse()

    if not open_cycles:
        return CortexOUT.work(
            "no open cycles",
            open_cycles=[],
            count=0,
            latest=None,
        )

    return CortexOUT.work(
        f"open_cycles={len(open_cycles)}",
        open_cycles=open_cycles,
        count=len(open_cycles),
        latest=open_cycles[-1],  # Most recent (highest ID)
    )


def close_cycle(
    cycle_id: str,
    summary: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Close a cycle with automatic lesson generation."""
    ctx = enforce_ctx(ctx, "cycle.close")
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cdir = cycle_dir(root, cycle_id)
    if not cdir.exists():
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")

    tasks_dir = cdir / TASKS_DIR
    now = _now_iso()

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

    if open_tasks and not summary:
        return CortexOUT.work(
            f"cycle {cycle_id} has {len(open_tasks)} open tasks: {', '.join(open_tasks)}. "
            f"Close or complete them first, or provide a summary to force close.",
            cycle_id=cycle_id,
            open_tasks=open_tasks,
            hint="Provide a summary to force-close with open tasks.",
        )

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

    if lessons:
        try:
            from ..state import read_brain, write_brain_sections
            project_dir = root.parent
            fm, sections, _ = read_brain(project_dir)
            existing = sections.get("LESSONS", "").strip()
            new_lessons = "\n".join(
                f"- [{now}] {l}" for l in lessons
            )
            sections["LESSONS"] = (existing + "\n" + new_lessons).strip() if existing else new_lessons
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

    learning_scan: dict[str, Any] = {
        "status": "not_run",
        "candidates": [],
    }
    try:
        from ..learning import list_candidates, scan_brain

        project_dir = root.parent
        scan = scan_brain(project_dir, verbose=True)
        if scan.get("engine") == "unavailable":
            learning_scan = {
                "status": "unavailable",
                "error": "learning engine unavailable",
                "candidates": [],
            }
        elif "error" in scan:
            learning_scan = {
                "status": "error",
                "error": scan["error"],
                "candidates": [],
            }
        else:
            candidates = scan.get("candidates", []) or list_candidates(root)
            learning_scan = {
                "status": "ok",
                "total": scan.get("count", 0),
                "candidates": candidates,
            }
    except Exception as exc:  # noqa: BLE001
        learning_scan = {
            "status": "error",
            "error": str(exc),
            "candidates": [],
        }

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
        "learning_scan": learning_scan["status"],
        "learning_candidates": len(learning_scan.get("candidates", [])),
    }
    body = (
        f"# CYCLE {cycle_id} (closed)\n\n"
        f"## Summary\n{summary or 'Cycle closed'}\n\n"
        f"## Metrics\n"
        f"- Tasks completed: {len(completed)}\n"
        f"- Tasks failed: {len(failed)}\n"
        f"- Tasks open on close: {len(open_tasks)}\n"
        f"- Lessons auto-generated: {len(lessons)}\n"
        f"- Learning scan: {learning_scan['status']}\n"
        f"- Elevation candidates proposed: {len(learning_scan.get('candidates', []))}\n"
    )
    write_cortex_pair(cdir, "cycle", fm, body)

    manifest_fm = _read_cycle_manifest(cdir)
    if manifest_fm is not None:
        manifest_fm["status"] = CYCLE_CLOSED
        manifest_fm["closed_at"] = now
        _write_cycle_manifest(cdir, manifest_fm)

    sync_brain(root, "cycle.close", focus="Ciclo cerrado", metrics={"cycles_closed": 1}, detail=f"cycle {cycle_id} closed")

    reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"cycle.close ok id={cycle_id} completed={len(completed)} "
        f"failed={len(failed)} lessons={len(lessons)} "
        f"learning_scan={learning_scan['status']} "
        f"candidates={len(learning_scan.get('candidates', []))}",
        cycle_id=cycle_id,
        status=CYCLE_CLOSED,
        tasks_completed=len(completed),
        tasks_failed=len(failed),
        lessons_generated=len(lessons),
        learning_scan=learning_scan["status"],
        learning_candidates=len(learning_scan.get("candidates", [])),
    instruction="Review cortex.learn candidates; apply elevations only with Architect approval.",
        )



def synthesize_cycle(
    cycle_id: str,
    content: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Populate a cycle MANIFEST.md from CORTEX content (§1-§9)."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    cdir = cycle_dir(root, cycle_id)
    if not cdir.exists():
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")
    mf = cdir / "MANIFEST.md"
    if not mf.exists():
        return CortexOUT.error("MANIFEST.md not found", code="NOT_FOUND")
    text = mf.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return CortexOUT.error("invalid MANIFEST.md format", code="INVALID_STATE")
    fm_text = parts[1]
    body = parts[2]
    sections = parse_content_sections(content)
    if not sections:
        return CortexOUT.error("no sections parsed from content", code="INVALID_ARGS")
    sections_written = []
    for sid, section_body in sections.items():
        try:
            snum = int(sid)
            if snum < 1 or snum > 9:
                continue
        except ValueError:
            continue
        marker = f"## §{snum}:"
        pattern = re.compile(rf"^{re.escape(marker)}.*?(?=^## §\d+:|\Z)", re.MULTILINE | re.DOTALL)
        new_section = f"{marker}\n\n{section_body.strip()}\n"
        if pattern.search(body):
            body = pattern.sub(new_section, body, count=1)
        else:
            body += f"\n{new_section}"
        sections_written.append(sid)
    new_text = f"---{fm_text}---\n{body}"
    mf.write_text(new_text, encoding="utf-8")

    reconcile_cycle(root, cycle_id)

    return CortexOUT.work(f"cycle.synthesize ok id={cycle_id} sections={len(sections_written)}", cycle_id=cycle_id, sections_written=sections_written, path=str(mf))


def _replace_manifest_section(manifest_text: str, section_num: int, new_content: str) -> str:
    """Replace a section (§N) in manifest text. Returns original if section not found."""
    marker = f"## §{section_num}:"
    pattern = re.compile(rf"^{re.escape(marker)}.*?(?=^## §\d+:|\Z)", re.MULTILINE | re.DOTALL)
    if pattern.search(manifest_text):
        return pattern.sub(f"{marker}\n\n{new_content.strip()}\n", manifest_text, count=1)
    return manifest_text


def _read_quality_gates_from_manifest(manifest_text: str) -> dict[str, bool]:
    """Extract quality gates from MANIFEST.md body. Reads §9 table."""
    gates: dict[str, bool] = {}
    m = re.search(r"## §9:.*?\n((?:\|.*?\n)+)", manifest_text, re.DOTALL)
    if not m:
        return gates
    table = m.group(1)
    for line in table.strip().splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) >= 2:
            name = cells[0].strip()
            val = cells[1].strip()
            gates[name] = val in ("✅", "true", "☑", "☒")
    return gates


handler_schemas = [
    {"name": "cycle.create", "fn": create_cycle, "description": "Open a new cycle in the active project.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "cycle.list", "fn": list_cycles, "description": "List cycles in the active project.", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "closed"]}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "cycle.current", "fn": current_cycle, "description": "Get the currently active cycle.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "cycle.mature", "fn": mature_cycle, "description": "Mature a cycle (draft → ready).", "input_schema": {"type": "object", "properties": {"cycle_id": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "cycle.close", "fn": close_cycle, "description": "Close a cycle (no new tasks can be added).", "input_schema": {"type": "object", "properties": {"cycle_id": {"type": "string"}, "summary": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["cycle_id"]}},
    {"name": "cycle.synthesize", "fn": synthesize_cycle, "description": "Populate a cycle's MANIFEST.md sections in a single call.", "input_schema": {"type": "object", "properties": {"cycle_id": {"type": "string"}, "content": {"type": "string"}, "path": {"type": "string"}}, "required": ["cycle_id", "content"]}},
]

