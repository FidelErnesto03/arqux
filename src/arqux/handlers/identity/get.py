"""identity.get handler (BLP-006).

Returns agent identity data from ``.arqux/identities/<agent>.cortex`` or
the global workspace identities shipped with the package.

Default agent_id is ``"alfred"``.
"""

from __future__ import annotations

import os
from pathlib import Path

from ...constants import IDENTITIES_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import find_project_root, find_workspace_root

DEFAULT_AGENT = "alfred"


def get_handler(
    agent_id: str | None = None,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Return agent identity data.

    Looks for the identity file in this order:

    1. ``<project>/.arqux/identities/<agent>.cortex``
    2. ``<workspace>/.arqux/identities/<agent>.cortex``
    3. The packaged identities shipped with arqux
       (``arqux/identities/<agent>.cortex``)

    Args:
        agent_id: Agent identifier. Defaults to ``"alfred"``.
        path: Starting path for resolving the project/workspace root.
        ctx: Permission context.

    Returns ``OUT-WORK`` with:

    - ``agent_id`` (str)
    - ``path`` (str) — path to the identity file
    - ``content`` (str) — raw CORTEX source of the identity
    - ``source`` (str) — ``"project"`` | ``"workspace"`` | ``"package"``
    """
    if agent_id is None or not agent_id:
        agent_id = DEFAULT_AGENT
    canonical_agent_id = agent_id.casefold()

    start = Path(path or os.getcwd()).resolve()

    # 1. Project identities.
    project_arqux = find_project_root(start=start)
    if project_arqux is not None:
        candidate = project_arqux / "identities" / f"{canonical_agent_id}.cortex"
        if candidate.exists():
            return _emit(
                agent_id,
                candidate,
                source="project",
            )

    # 2. Workspace identities.
    workspace_arqux = find_workspace_root(start=start)
    if workspace_arqux is not None:
        candidate = workspace_arqux / "identities" / f"{canonical_agent_id}.cortex"
        if candidate.exists():
            return _emit(
                agent_id,
                candidate,
                source="workspace",
            )

    # 3. Packaged identities.
    candidate = IDENTITIES_DIR / f"{canonical_agent_id}.cortex"
    if candidate.exists():
        return _emit(
            agent_id,
            candidate,
            source="package",
        )

    return CortexOUT.error(
        f"identity not found for agent_id={agent_id!r}",
        code="NOT_FOUND",
        agent_id=agent_id,
        searched=[
            str(project_arqux / "identities" / f"{agent_id}.cortex")
            if project_arqux
            else None,
            str(workspace_arqux / "identities" / f"{agent_id}.cortex")
            if workspace_arqux
            else None,
            str(candidate),
        ],
    )


def _emit(
    agent_id: str,
    identity_path: Path,
    *,
    source: str,
) -> CortexOUT:
    """Read the identity file and return OUT-WORK."""
    try:
        content = identity_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    return CortexOUT.work(
        f"identity.get ok agent_id={agent_id} source={source}",
        agent_id=agent_id,
        path=str(identity_path),
        source=source,
        content=content,
        size_bytes=len(content),
    )
