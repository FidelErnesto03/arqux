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
from ...pulse import append_pulse_to_brain, next_pulse_event_id
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

    start = Path(path or os.getcwd()).resolve()

    # 1. Project identities.
    project_arqux = find_project_root(start=start)
    if project_arqux is not None:
        candidate = project_arqux / "identities" / f"{agent_id}.cortex"
        if candidate.exists():
            return _emit(
                agent_id,
                candidate,
                source="project",
                ctx=ctx,
                project_arqux=project_arqux,
            )

    # 2. Workspace identities.
    workspace_arqux = find_workspace_root(start=start)
    if workspace_arqux is not None:
        candidate = workspace_arqux / "identities" / f"{agent_id}.cortex"
        if candidate.exists():
            return _emit(
                agent_id,
                candidate,
                source="workspace",
                ctx=ctx,
                project_arqux=project_arqux,
            )

    # 3. Packaged identities.
    candidate = IDENTITIES_DIR / f"{agent_id}.cortex"
    if candidate.exists():
        return _emit(
            agent_id,
            candidate,
            source="package",
            ctx=ctx,
            project_arqux=project_arqux,
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
    ctx: PermissionContext | None,
    project_arqux: Path | None,
) -> CortexOUT:
    """Read the identity file and return OUT-WORK."""
    try:
        content = identity_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    _record_pulse(project_arqux, ctx, agent_id=agent_id, source=source)

    return CortexOUT.work(
        f"identity.get ok agent_id={agent_id} source={source}",
        agent_id=agent_id,
        path=str(identity_path),
        source=source,
        content=content,
        size_bytes=len(content),
    )


def _record_pulse(
    project_arqux: Path | None,
    ctx: PermissionContext | None,
    *,
    agent_id: str,
    source: str,
) -> None:
    """Append a PULSE event for the get call (best-effort)."""
    try:
        if project_arqux is None:
            return
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(project_arqux)
        append_pulse_to_brain(
            project_arqux,
            event_id=event_id,
            task_id="-",
            kind="handler_call",
            agent=agent,
            payload=f"[identity.get] agent_id={agent_id} source={source}",
        )
    except Exception:  # noqa: BLE001
        pass
