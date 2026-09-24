"""context.detect handler (BLP-006).

Scans upward from a starting path looking for a ``.arqux/`` directory.

Returns ``{found: bool, path: str|null, kind: 'project'|'workspace'|null}``.

- A "project" ``.arqux/`` contains a ``brain.cortex`` file.
- A "workspace" ``.arqux/`` contains a ``meta-brain.cortex`` file.

No filesystem scanning libraries are used — only ``os.path.isdir`` /
``Path.exists`` walking up.
"""

from __future__ import annotations

import os
from pathlib import Path

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import find_project_root, find_workspace_root


def detect_handler(
    path: str | None = None,
    *,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Detect the nearest ``.arqux/`` directory walking upward from ``path``.

    Args:
        path: Starting path. Defaults to current working directory.
        ctx: Permission context (unused — read-only handler).

    Returns ``OUT-WORK`` with:

    - ``found`` (bool)
    - ``path`` (str | None) — absolute path to the ``.arqux/`` directory
    - ``kind`` (str | None) — ``"project"`` if it contains ``brain.cortex``,
      ``"workspace"`` if it contains ``meta-brain.cortex``, else ``None``.
    - ``start`` (str) — the resolved start path.
    """
    start = Path(path or os.getcwd()).resolve()

    # Try project first (closest .arqux/ with brain.cortex).
    project_arqux = find_project_root(start=start)
    if project_arqux is not None and project_arqux.exists():
        return CortexOUT.work(
            f"context.detect ok found=project path={project_arqux}",
            found=True,
            kind="project",
            path=str(project_arqux),
            start=str(start),
        )

    # Try workspace (.arqux/ with meta-brain.cortex).
    workspace_arqux = find_workspace_root(start=start)
    if workspace_arqux is not None and workspace_arqux.exists():
        return CortexOUT.work(
            f"context.detect ok found=workspace path={workspace_arqux}",
            found=True,
            kind="workspace",
            path=str(workspace_arqux),
            start=str(start),
        )

    # Not found — walk up manually as a last-resort to detect any
    # .arqux/ directory even without a brain.cortex (might be a fresh
    # workspace in mid-init).
    cursor = start
    arqux_dir_name = ".arqux"
    while True:
        candidate = cursor / arqux_dir_name
        if candidate.is_dir():
            return CortexOUT.work(
                f"context.detect ok found=untyped path={candidate}",
                found=True,
                kind=None,
                path=str(candidate),
                start=str(start),
            )
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    return CortexOUT.work(
        f"context.detect ok found=false start={start}",
        found=False,
        kind=None,
        path=None,
        start=str(start),
    )
