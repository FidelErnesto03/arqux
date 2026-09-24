"""Blueprint read and list handlers."""

from __future__ import annotations

from ...constants import (
    BLUEPRINTS_DIR,
    CYCLES_DIR,
)
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ._helpers import (
    _effective_status,
    _find_blueprint,
    _read_blueprint,
    _resolve_root,
)

# ---------------------------------------------------------------------------
# blueprint.read
# ---------------------------------------------------------------------------


def read_blueprint(
    bp_id: str,
    format: str = "hcortex",
    path: str | None = None,
    cycle: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read a full Blueprint."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id, cycle=cycle)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if format == "cortex":
        cortex_body = f"BLP:{bp_id}{{status:{fm.get('status','')}, cycle:{fm.get('cycle','')}, governor:{fm.get('governor','')}"
        return CortexOUT.work(cortex_body, **fm)
    else:
        return CortexOUT.work(body, **fm)


# ---------------------------------------------------------------------------
# blueprint.list
# ---------------------------------------------------------------------------


def list_blueprints(
    cycle: str | None = None,
    status: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> CortexOUT:
    """List Blueprints with optional filters.

    Paginated when ``limit`` is given: fields total, returned, offset
    and next_offset report the pagination state.
    """
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.work("no blueprints yet", blueprints=[])

    all_bps = []
    for cdir in sorted(cycles_base.iterdir()):
        if not cdir.is_dir():
            continue
        if cycle and cdir.name != cycle:
            continue
        bp_dir = cdir / BLUEPRINTS_DIR
        if not bp_dir.exists():
            continue
        for bp_file in sorted(bp_dir.glob("*.md")):
            if bp_file.name == "BLP_TEMPLATE.md":
                continue
            fm, _ = _read_blueprint(bp_file)
            if fm is None:
                continue
            bp_status = _effective_status(fm)
            if status and bp_status != status:
                continue
            entry = {
                "id": fm.get("blueprint_id", bp_file.stem),
                "title": fm.get("title", bp_file.stem),
                "cycle": fm.get("cycle", cdir.name),
                "status": bp_status,
                "governor": fm.get("governor", ""),
                "executor": fm.get("executor", ""),
                "verification_loop": fm.get("verification_loop", 0),
            }
            raw_status = str(fm.get("status", "")).strip().lower()
            if raw_status != bp_status:
                entry["raw_status"] = raw_status
            all_bps.append(entry)

    try:
        offset_i = int(offset)
        limit_i = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        return CortexOUT.error("limit and offset must be integers", code="INVALID_ARGS")
    if limit_i is not None and (limit_i < 1 or offset_i < 0):
        return CortexOUT.error("limit must be >= 1 and offset must be >= 0", code="INVALID_ARGS")
    if offset_i < 0:
        return CortexOUT.error("offset must be >= 0", code="INVALID_ARGS")

    total = len(all_bps)
    page = all_bps[offset_i:] if limit_i is None else all_bps[offset_i : offset_i + limit_i]
    next_offset = (
        offset_i + limit_i
        if limit_i is not None and offset_i + limit_i < total
        else None
    )

    return CortexOUT.work(
        f"blueprints: {len(page)}",
        count=len(page),
        blueprints=page,
        total=total,
        returned=len(page),
        offset=offset_i,
        next_offset=next_offset,
    )
