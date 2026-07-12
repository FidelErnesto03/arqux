"""Blueprint read and list handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...constants import (
    BLUEPRINTS_DIR,
    CYCLES_DIR,
)
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext

from ._helpers import _find_blueprint, _resolve_root, _read_blueprint


# ---------------------------------------------------------------------------
# blueprint.read
# ---------------------------------------------------------------------------


def read_blueprint(
    bp_id: str,
    format: str = "hcortex",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read a full Blueprint."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
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
) -> CortexOUT:
    """List Blueprints with optional filters."""
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
            bp_status = fm.get("status", "")
            if status and bp_status != status:
                continue
            all_bps.append({
                "id": fm.get("blueprint_id", bp_file.stem),
                "title": fm.get("title", bp_file.stem),
                "cycle": fm.get("cycle", cdir.name),
                "status": bp_status,
                "governor": fm.get("governor", ""),
                "executor": fm.get("executor", ""),
                "verification_loop": fm.get("verification_loop", 0),
            })

    return CortexOUT.work(
        f"blueprints: {len(all_bps)}",
        count=len(all_bps),
        blueprints=all_bps,
    )
