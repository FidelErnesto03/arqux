"""
PATCH: src/arqux/handlers/cycle.py
==================================

This file REPLACES the existing cycle.py.
The obsolete `mature` handler was removed in BLP-003 — cycle state machine
simplified to draft → closed. Maturation is conversational, not a handler.

CHANGES vs original:
    1. `create_cycle()` now writes status="draft" explicitly (was implicit
       via template).
    2. `close_cycle()` unchanged except for also updating MANIFEST.md.
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
    find_workspace_root,
    next_cycle_id,
    write_cortex_pair,
)
from ..state import (
    parse_cortex_file as _parse_cortex_file,
)
from ..sync import reconcile_cycle, sync_brain
from .blueprint._synthesize_common import parse_content_sections

# --- Cycle states (BLP-003 simplification) --------------------------------
# Simplified to 2 states: draft (open/designing) and closed (finished).
# The "open" alias is kept for backward compatibility (mapped to closed).

CYCLE_DRAFT = "draft"

CYCLE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    CYCLE_DRAFT: (CYCLE_CLOSED,),
    CYCLE_CLOSED: (),
    # Backward compat: "open" maps to closed.
    CYCLE_OPEN: (CYCLE_CLOSED,),
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


# ---------------------------------------------------------------------------
# Template-based marker system (BLP-001)
# ---------------------------------------------------------------------------

MARKER_PATTERN = re.compile(r"(?<!\w)_([\w¿¡][\w\s\-/.,;:¿?!¡()]*?)_(?!\w)")


def parse_cycle_template(
    template_path: str | Path | None = None,
) -> dict[int, list[str]]:
    """Parse CYCLE_MANIFEST_TEMPLATE.md and return markers by section.

    Returns ``{section_num: [marker_text, ...]}`` where each marker_text
    is the full placeholder string (e.g. ``"_Ítem 1_"``).

    The parser discovers markers dynamically — no hardcoded list.
    Uses ``<!-- CYCLE:N -->`` markers as canonical delimiters (like BLPs),
    with ``## §N:`` headers as fallback.
    """
    if template_path is None:
        root = Path.cwd()
        template_path = _find_workspace_template(root, "CYCLE_MANIFEST_TEMPLATE.md")
        if template_path is None:
            template_path = Path(__file__).resolve().parent.parent / "templates" / "CYCLE_MANIFEST_TEMPLATE.md"

    p = Path(template_path)
    if not p.exists():
        return {}

    text = p.read_text(encoding="utf-8")
    sections: dict[int, list[str]] = {}

    # Split body after frontmatter
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text

    # Try CYCLE:N markers first (more precise)
    cycle_markers = list(re.finditer(r"<!--\s*CYCLE:(\d+)\s*-->(.*?)<!--\s*/CYCLE:\1\s*-->", body, re.DOTALL))

    if cycle_markers:
        # Use CYCLE:N markers as delimiters
        for m in cycle_markers:
            snum = int(m.group(1))
            section_text = m.group(2)
            markers = []
            for marker_m in MARKER_PATTERN.finditer(section_text):
                marker_text = f"_{marker_m.group(1)}_"
                if marker_text not in markers:
                    markers.append(marker_text)
            sections[snum] = markers
    else:
        # Fallback: split by ## §N: headers
        section_headers = list(re.finditer(r"^## §(\d+):", body, re.MULTILINE))
        for i, header in enumerate(section_headers):
            snum = int(header.group(1))
            start = header.end()
            end = section_headers[i + 1].start() if i + 1 < len(section_headers) else len(body)
            section_text = body[start:end]
            markers = []
            for m in MARKER_PATTERN.finditer(section_text):
                marker_text = f"_{m.group(1)}_"
                if marker_text not in markers:
                    markers.append(marker_text)
            sections[snum] = markers

    return sections


def _read_allowed_placeholders(mf_text: str) -> list[str]:
    """Read ``allowed_placeholders@`` from MANIFEST.md frontmatter.

    Returns a list of placeholder strings that should be ignored during
    maturity validation.
    """
    parts = mf_text.split("---", 2)
    if len(parts) < 2:
        return []
    fm_text = parts[1]
    m = re.search(r"allowed_placeholders@:\s*\[(.*?)\]", fm_text, re.DOTALL)
    if not m:
        return []
    raw = m.group(1)
    # Parse comma-separated quoted strings
    allowed: list[str] = []
    for item in re.findall(r'"([^"]*)"', raw):
        allowed.append(item)
    return allowed


def _find_template_markers_in_body(body: str, tmpl_markers: dict[int, list[str]]) -> list[str]:
    """Find markers from the template that remain in the manifest body.

    Returns a list of unmatched marker strings found in the body.
    """
    found: list[str] = []
    for _snum, markers in tmpl_markers.items():
        for marker in markers:
            if marker in body and marker not in found:
                found.append(marker)
    return found


def _replace_markers_in_section(
    manifest_text: str,
    section_num: int,
    markers: dict[str, str],
) -> str:
    """Replace specific markers in a section of the manifest.

    ``markers`` is a dict mapping the original marker (e.g. ``"_Ítem 1_"``)
    to its replacement value.

    Only replaces markers that exist in the template section.
    """
    marker = f"## §{section_num}:"
    # Find the section boundaries
    pattern = re.compile(
        rf"^{re.escape(marker)}.*?(?=^## §\d+:|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    section_match = pattern.search(manifest_text)
    if not section_match:
        return manifest_text

    section_content = section_match.group(0)
    for orig_marker, replacement in markers.items():
        section_content = section_content.replace(orig_marker, replacement)

    return pattern.sub(section_content, manifest_text, count=1)


def _has_known_markers(content_body: str, tmpl_markers: dict[int, list[str]]) -> bool:
    """Check if content_body contains any markers from the template."""
    for _snum, markers in tmpl_markers.items():
        for marker in markers:
            if marker in content_body:
                return True
    return False


def _manifest_body_has_placeholders(text: str) -> list[str]:
    """Check if the manifest body contains template placeholders.

    Returns a list of matched placeholder full text (empty = clean).
    Uses dynamic markers from the template file.
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []
    body = parts[2]

    # Get allowed placeholders from frontmatter
    allowed = _read_allowed_placeholders(text)

    # Find markers from the template that remain in the body
    tmpl_markers = parse_cycle_template()
    found = _find_template_markers_in_body(body, tmpl_markers)

    # Filter out allowed placeholders
    filtered = [m for m in found if m not in allowed]

    return filtered


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

    v0.4.0 change: cycle starts in status="draft". Already active on creation.
    """
    ctx = enforce_ctx(ctx, "cycle.create")
    root = _resolve_project_root(path)
    if root[0] is None:
        return CortexOUT.error(root[1], code="NOT_FOUND")
    root = root[0]

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
            "Use cycle.synthesize() to fill the manifest, then create blueprints with blueprint.create()."
        ),
    )


# mature_cycle() removed in BLP-003 — cycle state machine simplified to
# draft → closed. Maturation is conversational, not a handler.


def list_cycles(
    status: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List cycles in the active project."""
    root = _resolve_project_root(path)
    if root[0] is None:
        return CortexOUT.error(root[1], code="NOT_FOUND")
    root = root[0]

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
    root = _resolve_project_root(path)
    if root[0] is None:
        return CortexOUT.error(root[1], code="NOT_FOUND")
    root = root[0]

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
    root = _resolve_cycle_root(cycle_id, path)
    if root[0] is None:
        return CortexOUT.error(root[1], code="NOT_FOUND")
    root = root[0]

    cdir = cycle_dir(root, cycle_id)
    if not cdir.exists():
        return CortexOUT.error(f"cycle {cycle_id} not found", code="NOT_FOUND")

    # BLP-003: If cycle is in draft, validate no placeholders in manifest
    mf_path = cdir / "MANIFEST.md"
    if mf_path.exists():
        mf_text = mf_path.read_text(encoding="utf-8")
        mf_fm = _read_cycle_manifest(cdir)
        if mf_fm and mf_fm.get("status", "") == CYCLE_DRAFT:
            placeholders = _manifest_body_has_placeholders(mf_text)
            if placeholders:
                return CortexOUT.error(
                    f"cycle {cycle_id} is in draft and MANIFEST.md still has template placeholders. "
                    f"Complete the conversational design first via cycle.synthesize(). "
                    f"Found: {placeholders}",
                    code="INVALID_STATE",
                )

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



def _resolve_project_root(path: str | None = None) -> tuple[Path | None, str]:
    """Resolve project root from path or by scanning workspace projects.

    Returns (root, error_msg) where error_msg is empty-string on success.
    """
    root = find_project_root(start=path)
    if root is not None:
        return root, ""

    if path is not None:
        return None, "no project initialized"

    # Try known workspace locations
    for wdir in [Path.cwd(), Path.home() / "workspace", Path.home() / "proyectos"]:
        ws_root = find_workspace_root(start=str(wdir))
        if ws_root is None:
            continue
        # Use the first project with .arqux/brain.cortex
        for entry in sorted(ws_root.parent.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            pa = entry / ".arqux"
            if (pa / "brain.cortex").exists():
                return pa, ""
    return None, (
        "no project initialized. "
        "Provide 'path' or run session.context.set first."
    )


def _resolve_cycle_root(cycle_id: str, path: str | None = None) -> tuple[Path | None, str]:
    """Resolve project root from path or by scanning workspace for a cycle.

    Returns (root, error_msg) where error_msg is empty-string on success.
    """
    root = find_project_root(start=path)
    if root is not None:
        return root, ""

    # Fallback: scan workspace when path is not provided
    if path is not None:
        return None, "no project initialized"

    # Try known workspace locations
    for wdir in [Path.cwd(), Path.home() / "workspace", Path.home() / "proyectos"]:
        ws_root = find_workspace_root(start=str(wdir))
        if ws_root is None:
            continue
        # Check ws-level cycles first
        if (ws_root / "cycles" / cycle_id).is_dir():
            return ws_root.parent, ""
        # Search projects
        for entry in sorted(ws_root.parent.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            pa = entry / ".arqux"
            if not (pa / "brain.cortex").exists():
                continue
            if (pa / "cycles" / cycle_id).is_dir():
                return pa, ""
    return None, (
        f"cycle {cycle_id} not found in any workspace project. "
        "Provide 'path' or run session.context.set first."
    )


def synthesize_cycle(
    cycle_id: str,
    content: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Populate a cycle MANIFEST.md from CORTEX content (§1-§9).

    Two modes (auto-detected per section):

    1. **Marker replacement** — Content body contains known template
       markers (``_marker_``). Each marker in the content is matched to
       the template, and the *following text* (after ``→``) replaces the
       original marker in the manifest.

       Example::

           $4:{_Ítem 1_→Refinar pipeline de gobernanza}

       This replaces only ``_Ítem 1_`` in §4 with
       ``Refinar pipeline de gobernanza``, leaving the rest of §4 intact.

    2. **Section replacement** (backward compat) — Content body has NO
       template markers. The entire section block ``## §N:...`` is
       replaced by the provided content.

       Example::

           $4:{Contenido completamente nuevo para §4}

    Parses CYCLE_MANIFEST_TEMPLATE.md dynamically — no hardcoded
    structure knowledge.
    """
    root = _resolve_cycle_root(cycle_id, path)
    if root[0] is None:
        return CortexOUT.error(root[1], code="NOT_FOUND")
    root = root[0]
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

    # Parse template markers once for marker-based replacement
    tmpl_markers = parse_cycle_template()

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

        # Check if content contains known markers → marker-level replacement
        known_markers = tmpl_markers.get(snum, [])
        marker_map: dict[str, str] = {}
        for marker in known_markers:
            if marker in section_body:
                # Extract value after "→" or after the marker itself
                after_marker = section_body.split(marker, 1)[1].strip()
                # Remove leading → or : if present
                if after_marker.startswith("→") or after_marker.startswith(":"):
                    after_marker = after_marker[1:].strip()
                # If there's a quoted value, extract it
                if after_marker and after_marker[0] in ('"', "'"):
                    end_quote = after_marker.find(after_marker[0], 1)
                    if end_quote > 1:
                        after_marker = after_marker[1:end_quote]
                marker_map[marker] = after_marker

        if marker_map:
            # Marker-level replacement: replace each marker in the manifest
            body = _replace_markers_in_section(body, snum, marker_map)
            sections_written.append(f"{sid}(markers)")
        else:
            # No known markers — replace entire section (backward compat)
            body = _replace_manifest_section(body, snum, section_body.strip())
            sections_written.append(sid)

    new_text = f"---{fm_text}---\n{body}"
    mf.write_text(new_text, encoding="utf-8")

    reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"cycle.synthesize ok id={cycle_id} sections={len(sections_written)}",
        cycle_id=cycle_id,
        sections_written=sections_written,
        path=str(mf),
    )


def _replace_manifest_section(manifest_text: str, section_num: int, new_content: str) -> str:
    """Replace a section (SN) in manifest text. Returns original if section not found.
    Preserves CYCLE:N comment markers if present.
    """
    # Try to find CYCLE:N markers first (more precise)
    cycle_pat = re.compile(
        rf"(<!--\s*CYCLE:{section_num}\s*-->).*?(<!--\s*/CYCLE:{section_num}\s*-->)",
        re.DOTALL,
    )
    cycle_match = cycle_pat.search(manifest_text)
    if cycle_match:
        open_tag = cycle_match.group(1)
        close_tag = cycle_match.group(2)
        replacement = f"{open_tag}\n{new_content}\n{close_tag}"
        return cycle_pat.sub(replacement, manifest_text, count=1)

    # Fallback: split by ## §N: headers (backward compat)
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
    {"name": "cycle.close", "fn": close_cycle, "description": "Close a cycle (no new tasks can be added).", "input_schema": {"type": "object", "properties": {"cycle_id": {"type": "string"}, "summary": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["cycle_id"]}},
    {"name": "cycle.synthesize", "fn": synthesize_cycle, "description": "Populate a cycle's MANIFEST.md sections in a single call.", "input_schema": {"type": "object", "properties": {"cycle_id": {"type": "string"}, "content": {"type": "string"}, "path": {"type": "string"}}, "required": ["cycle_id", "content"]}},
]

