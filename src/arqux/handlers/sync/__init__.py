"""sync handlers — run (manual), reconcile (auto after mutations)."""

from __future__ import annotations

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import find_project_root
from ...sync import reconcile_brain, reconcile_cycle, sync_brain


def sync_run_handler(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Sync a project brain.cortex to meta-brain.

    Calls sync_brain with metrics to trigger meta-brain DOM:arqux sync.
    _sync_meta_brain internally counts blueprints and tests.

    Args:
        path: Path to project root. Defaults to auto-detection from cwd.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    project_root = root.parent if root.name == ".arqux" else root

    try:
        sync_brain(
            project_root,
            "sync.run",
            focus="sync.run manual trigger",
            metrics={"sync_run": 1},
            detail="sync.run manual trigger — full sync to meta-brain",
        )
    except Exception as exc:
        return CortexOUT.error(f"sync failed: {exc}", code="SYNC_FAILED")

    return CortexOUT.work(
        f"sync.run ok project={project_root}",
        project=str(project_root),
    )


def reconcile_handler(
    path: str | None = None,
    cycle_id: str | None = None,
    level: str = "auto",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Reconcile brain.cortex persistent state with filesystem reality.

    Scans all cycles and blueprints, counts by status, and updates:
    - brain.cortex §3 (OBJ): goal with accurate counts
    - meta-brain.cortex $2/DOM:arqux: counts if meta-brain exists

    When ``cycle_id`` is provided, only reconciles that cycle's MANIFEST.md.
    When ``level`` is ``project`` (or ``auto`` at project root), reconciles
    brain.cortex. When ``level`` is ``workspace``, reconciles meta-brain.

    This is the automated reconciliation that runs after every mutation.

    Args:
        path: Path to project root. Auto-detected from cwd if omitted.
        cycle_id: If set, reconcile only this cycle's MANIFEST.md.
        level: Scope level — ``cycle``, ``project``, ``workspace``, or ``auto``.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    project_root = root.parent if root.name == ".arqux" else root

    # Cycle-level reconcile (when cycle_id provided or level=cycle)
    if cycle_id or level == "cycle":
        target_cycle = cycle_id
        if not target_cycle:
            return CortexOUT.error("level=cycle requires cycle_id", code="NO_CYCLE")
        try:
            result = reconcile_cycle(project_root, target_cycle)
            if result["reconciled"]:
                metrics = result["metrics"]
                return CortexOUT.work(
                    f"reconcile.cycle.ok cycle={cycle_id} "
                    f"blueprints={metrics.get('total_blueprints', 0)}",
                    project=str(project_root),
                    cycle_id=cycle_id,
                    metrics=metrics,
                )
            else:
                return CortexOUT.error(
                    f"reconcile.cycle.failed for {cycle_id}: {result.get('errors', [])}",
                    code="RECONCILE_CYCLE_FAILED",
                )
        except Exception as exc:
            return CortexOUT.error(f"reconcile.cycle error: {exc}", code="RECONCILE_CYCLE_ERROR")

    # Project-level reconcile (default)
    try:
        # Check if we're at workspace root (workspace context) vs project root
        from arqux.state import find_workspace_root
        ws_root = find_workspace_root(start=project_root)
        is_workspace_context = (ws_root is not None and
                                ws_root.parent == project_root)

        if is_workspace_context:
            # Workspace context: reconcile meta-brain directly
            result = reconcile_brain(project_root)
            # Override reconciled flag since we're in workspace context
            result["reconciled"] = True
            result["is_workspace"] = True
        else:
            result = reconcile_brain(project_root)

        if result["reconciled"]:
            metrics = result["metrics"]
            return CortexOUT.work(
                f"reconcile.ok blueprints={metrics.get('total_blueprints', 0)} "
                f"open_cycles={metrics.get('open_cycles', 0)} "
                f"closed_cycles={metrics.get('closed_cycles', 0)} "
                f"workspace={'true' if result.get('is_workspace', False) else 'false'}",
                project=str(project_root),
                metrics=metrics,
                meta_synced=result.get("meta_synced", False),
            )
        else:
            return CortexOUT.error(
                f"reconcile.failed: {result.get('errors', [])}",
                code="RECONCILE_FAILED",
                errors=result.get("errors", []),
            )
    except Exception as exc:
        return CortexOUT.error(f"reconcile error: {exc}", code="RECONCILE_ERROR")


handler_schemas = [
    {
        "name": "sync.run",
        "fn": sync_run_handler,
        "description": "Manually sync a project brain.cortex to meta-brain with full metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to project root. Auto-detected from cwd if omitted.",
                },
            },
        },
    },
    {
        "name": "sync.reconcile",
        "fn": reconcile_handler,
        "description": "Reconcile brain.cortex with filesystem reality. Supports cycle-level (cycle_id) or project-level reconcile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to project root. Auto-detected from cwd if omitted.",
                },
                "cycle_id": {
                    "type": "string",
                    "description": "If set, reconcile only this cycle's MANIFEST.md (BLP table + metrics).",
                },
                "level": {
                    "type": "string",
                    "enum": ["auto", "cycle", "project", "workspace"],
                    "description": "Reconciliation scope level. Default: auto.",
                },
            },
        },
    },
]
