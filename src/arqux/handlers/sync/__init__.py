"""sync.run — manually sync a project brain.cortex to meta-brain."""

from __future__ import annotations

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import find_project_root
from ...sync import sync_brain


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
]
