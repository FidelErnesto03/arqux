"""Blueprint lifecycle handlers.

Simplified lifecycle: create → ready → claim → complete (BLP-004)
"""

from __future__ import annotations

from pathlib import Path

from ...constants import CYCLE_CLOSED, CYCLES_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...sync import reconcile_cycle, sync_brain
from ._helpers import (
    BLUEPRINT_TEMPLATE,
    BP_DRAFT,
    BP_IN_PROGRESS,
    BP_READY,
    _blueprints_dir,
    _find_blueprint,
    _find_workspace_template,
    _now_iso,
    _prefill_from_context,
    _read_blueprint,
    _resolve_root,
    _transition,
    _write_blueprint,
    next_blueprint_id_safe,
    scan_markers,
)

# ---------------------------------------------------------------------------
# blueprint.create
# ---------------------------------------------------------------------------


def create_blueprint(
    obj: str,
    cycle: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Create a new Blueprint from BLP_TEMPLATE.md."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Find cycle
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")

    if cycle:
        cycle_id = cycle
    else:
        open_cycles = sorted([d.name for d in cycles_base.iterdir() if d.is_dir() and (d / "MANIFEST.md").exists()])
        if not open_cycles:
            open_cycles = sorted([d.name for d in cycles_base.iterdir() if d.is_dir()])
        if not open_cycles:
            return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")
        cycle_id = open_cycles[-1]

    # Check cycle is in draft (not closed) and validate no placeholders in manifest
    cycle_mf = cycles_base / cycle_id / "MANIFEST.md"
    if cycle_mf.exists():
        mf_text = cycle_mf.read_text(encoding="utf-8")
        mf_fm, _ = _read_blueprint(cycle_mf)
        cycle_status = mf_fm.get("status", "") if mf_fm else ""
        if cycle_status == CYCLE_CLOSED:
            return CortexOUT.error(
                f"cycle {cycle_id} is closed. Cannot create blueprints in a closed cycle.",
                code="INVALID_STATE",
            )
        # BLP-003: validate no placeholders in cycle manifest
        from ..cycle import _manifest_body_has_placeholders
        placeholders = _manifest_body_has_placeholders(mf_text)
        if placeholders:
            return CortexOUT.error(
                f"cycle {cycle_id} MANIFEST.md still has template placeholders. "
                f"Complete the conversational design first via cycle.synthesize(). "
                f"Found: {placeholders}",
                code="INVALID_STATE",
            )

    bp_dir = _blueprints_dir(root, cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    bp_id = next_blueprint_id_safe(bp_dir)

    # Try workspace templates first, fallback to package templates.
    template_src = _find_workspace_template(root, BLUEPRINT_TEMPLATE)
    if template_src is None:
        template_src = Path(__file__).resolve().parent.parent / "templates" / BLUEPRINT_TEMPLATE

    if not template_src.exists():
        return CortexOUT.error(f"template {BLUEPRINT_TEMPLATE} not found. Reinstall arqux.", code="NOT_FOUND")

    template_text = template_src.read_text(encoding="utf-8")
    # Replace placeholders
    _ctx = ctx or PermissionContext.from_env(project_root=root)
    gov = _ctx.agent_id
    body = template_text.replace('blueprint_id: ""', f'blueprint_id: "{bp_id}"')
    body = body.replace('title: ""', f'title: "{obj}"')
    body = body.replace('cycle: ""', f'cycle: "{cycle_id}"')
    body = body.replace('governor: ""', f'governor: "{gov}"')
    body = body.replace('created_at: ""', f'created_at: "{_now_iso()}"')
    body = body.replace("# BLP-NNN: Título", f"# {bp_id}: {obj}")

    # Pre-fill context from brain.cortex and cycle manifest
    body = _prefill_from_context(body, root, cycle_id)

    # Scan markers and store map in frontmatter
    markers = scan_markers(body)
    if markers:
        markers_json = ", ".join(f'"{m}"' for m in markers)
        body = body.replace(
            "_template_ref:",
            f"blp_markers@: [{markers_json}]\n_template_ref:",
            1,
        )

    bp_path = bp_dir / f"{bp_id}.md"
    bp_path.write_text(body, encoding="utf-8")

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.create",
        focus=f"Definir {bp_id}",
        detail=f"{bp_id} created in {cycle_id}",
    )

    reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.create ok id={bp_id} cycle={cycle_id}",
        blueprint_id=bp_id,
        cycle=cycle_id,
        status=BP_DRAFT,
        path=str(bp_path),
        markers=markers,
        instruction=(
            f"Blueprint {bp_id} created with {len(markers)} markers. "
            "Use blueprint.update(section=N, content=...) to fill sections."
        ),
    )


# ---------------------------------------------------------------------------
# blueprint.ready
# ---------------------------------------------------------------------------


def ready_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Architect declares Blueprint ready for execution. State → ready (draft→ready directly)."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_READY)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    fm["status"] = BP_READY
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.ready",
        focus=f"Blueprint {bp_id} listo para ejecutar",
        detail=f"{bp_id} {BP_READY}",
    )

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.ready ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_READY,
        instruction="Blueprint is ready for execution. Call blueprint.claim() to start.",
    )


# ---------------------------------------------------------------------------
# blueprint.claim
# ---------------------------------------------------------------------------


def claim_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Executor claims the Blueprint. State → in_progress. Assigns executor implicitly."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_IN_PROGRESS)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    caller = (ctx or PermissionContext.from_env(project_root=root)).agent_id
    fm["status"] = BP_IN_PROGRESS
    fm["executor"] = caller
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.claim ok id={bp_id} executor={caller}",
        blueprint_id=bp_id,
        status=BP_IN_PROGRESS,
        executor=caller,
    )
