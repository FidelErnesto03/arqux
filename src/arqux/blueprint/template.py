"""BLP-013: Shared BLP template parser.

``parse_blp_template(path?)`` reads ``BLP_TEMPLATE.md`` and extracts the
``<!-- BLP:N -->`` markers, returning ``{section_id: marker_text}``.

The parser discovers markers dynamically — it does NOT hardcode the
section IDs. This means it works with any future template that adds or
removes sections.

The template is searched for in this order:

1. ``<project>/.arqux/templates/BLP_TEMPLATE.md`` (project override)
2. ``<workspace>/.arqux/templates/BLP_TEMPLATE.md`` (workspace override)
3. The packaged template shipped with arqux
   (``arqux/templates/BLP_TEMPLATE.md``)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from ..constants import TEMPLATES_DIR
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..pulse import append_pulse_to_brain, next_pulse_event_id
from ..state import find_project_root, find_workspace_root


TEMPLATE_NAME = "BLP_TEMPLATE.md"


def parse_blp_template(
    path: str | None = None,
    *,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Parse BLP_TEMPLATE.md and return ``{section_id: marker_text}``.

    Args:
        path: Starting path for resolving project/workspace root.
            If ``None``, falls back to cwd. If ``path`` points directly
            to a ``BLP_TEMPLATE.md`` file, that file is used as-is.
        ctx: Permission context.

    Returns ``OUT-WORK`` with:

    - ``markers`` (dict[str, str]) — ``{"BLP:1": "<!-- BLP:1 -->...", ...}``
    - ``template_path`` (str) — path to the template file used
    - ``count`` (int) — number of markers found
    """
    template_path = _resolve_template(path)
    if template_path is None:
        return CortexOUT.error(
            f"template {TEMPLATE_NAME} not found",
            code="NOT_FOUND",
        )

    try:
        text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    markers = _extract_markers(text)

    _record_pulse(path, ctx, count=len(markers), template_path=str(template_path))

    return CortexOUT.work(
        f"parse_blp_template ok markers={len(markers)} path={template_path}",
        markers=markers,
        template_path=str(template_path),
        count=len(markers),
    )


def _resolve_template(path: str | None) -> Path | None:
    """Resolve the BLP_TEMPLATE.md path.

    Order:

    1. If ``path`` points directly to a BLP_TEMPLATE.md file, use it.
    2. <project>/.arqux/templates/BLP_TEMPLATE.md
    3. <workspace>/.arqux/templates/BLP_TEMPLATE.md
    4. Packaged arqux/templates/BLP_TEMPLATE.md
    """
    if path:
        p = Path(path)
        if p.is_file() and p.name == TEMPLATE_NAME:
            return p
        # If path is a directory, look inside it.
        candidate = p / TEMPLATE_NAME
        if candidate.is_file():
            return candidate

    start = Path(path or os.getcwd()).resolve()

    project_arqux = find_project_root(start=start)
    if project_arqux is not None:
        candidate = project_arqux / "templates" / TEMPLATE_NAME
        if candidate.is_file():
            return candidate

    workspace_arqux = find_workspace_root(start=start)
    if workspace_arqux is not None:
        candidate = workspace_arqux / "templates" / TEMPLATE_NAME
        if candidate.is_file():
            return candidate

    packaged = TEMPLATES_DIR / TEMPLATE_NAME
    if packaged.is_file():
        return packaged

    return None


def _extract_markers(text: str) -> dict[str, str]:
    """Discover all ``<!-- BLP:N -->`` markers in the template text.

    Returns a dict mapping marker ID (e.g. ``"BLP:1"``) to the full
    marker text (e.g. ``"<!-- BLP:1 -->"``).

    Closing markers (``<!-- /BLP:N -->``) are NOT included — only
    opening markers.

    The IDs are discovered dynamically — no hardcoded list.
    """
    markers: dict[str, str] = {}
    # Match opening markers: <!-- BLP:N -->  or  <!-- BLP:N.M -->
    # The ID can contain letters, digits, dots, underscores.
    pattern = re.compile(r"<!--\s+(BLP:[\w.]+)\s+-->")
    for match in pattern.finditer(text):
        marker_id = match.group(1)
        # Skip closing markers (they start with /).
        # The regex above already excludes them because we require no '/'.
        # But double-check just in case.
        if marker_id.startswith("/"):
            continue
        if marker_id not in markers:
            markers[marker_id] = match.group(0)
    return markers


def list_template_sections(
    path: str | None = None,
    *,
    ctx: PermissionContext | None = None,
) -> list[str]:
    """Return a sorted list of section IDs from the template.

    Convenience wrapper around ``parse_blp_template`` that returns just
    the IDs as a list.
    """
    result = parse_blp_template(path, ctx=ctx)
    if result.profile != "OUT-WORK":
        return []
    return sorted(result.fields.get("markers", {}).keys())


def _record_pulse(
    path: str | None,
    ctx: PermissionContext | None,
    *,
    count: int,
    template_path: str,
) -> None:
    """Append a PULSE event for the parse call (best-effort)."""
    try:
        root = find_project_root(start=path)
        if root is None:
            return
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id="-",
            kind="handler_call",
            agent=agent,
            payload=f"[parse_blp_template] count={count} path={template_path}",
        )
    except Exception:  # noqa: BLE001
        pass
