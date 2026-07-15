"""blueprint.synthesize handler (BLP-007).

Writes a Blueprint's content sections in a single call from a CORTEX
content payload. Uses ``parse_blp_template()`` (BLP-013) to validate
section IDs against ``BLP_TEMPLATE.md``.

Creates the BLP ``.md`` file if it doesn't exist (status=draft). Does
NOT change BLP status — only writes content. Writes atomically (temp
file + rename).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...blueprint.template import parse_blp_template
from ...constants import BLUEPRINTS_DIR, CYCLES_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root
from ._synthesize_common import parse_content_sections
from .manage import update_blueprint

# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------


def synthesize_blueprint(
    bp_id: str,
    content: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Write a Blueprint's content sections in one call.

    Args:
        bp_id: Blueprint ID (e.g. ``"BLP-007"``). If the BLP file does
            not exist, it is created with status=draft.
        content: CORTEX content payload. Two forms accepted:

            - **Per-section form:** ``$1:{body1}\n$2:{body2}\n...``
            - **Single-body form:** ``$0:{1: "body1", 2: "body2", ...}``

            In the per-section form, the section ID is the part after
            ``$`` and before ``:``. The body is everything between
            ``{`` and the matching ``}``.

        path: Starting path for resolving the project root.
        ctx: Permission context.

    Returns ``OUT-WORK`` with:

    - ``blueprint_id`` (str)
    - ``path`` (str) — path to the written BLP file
    - ``sections_written`` (list[str])
    - ``sections_skipped`` (list[str]) — IDs in content but not in template
    - ``bytes_written`` (int)
    - ``created`` (bool) — true if the BLP was created (vs. updated)
    """
    if not bp_id or not isinstance(bp_id, str):
        return CortexOUT.error("bp_id is required", code="INVALID_ARGS")
    if not re.match(r"^BLP-\d{3}$", bp_id):
        return CortexOUT.error(
            f"invalid bp_id={bp_id!r} (must match BLP-NNN)",
            code="INVALID_ARGS",
        )
    if not content or not isinstance(content, str):
        return CortexOUT.error("content is required", code="INVALID_ARGS")

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Validate section IDs against template.
    tmpl_result = parse_blp_template(path=path)
    if tmpl_result.profile != "OUT-WORK":
        return CortexOUT.error(
            f"cannot validate sections: {tmpl_result.message}",
            code="TEMPLATE_MISSING",
        )
    valid_ids = set(tmpl_result.fields.get("markers", {}))

    # Parse content into section_id -> body.
    sections = parse_content_sections(content)
    if not sections:
        return CortexOUT.error(
            "no sections parsed from content",
            code="INVALID_ARGS",
        )

    sections_skipped = [sid for sid in sections if f"BLP:{sid}" not in valid_ids]
    sections_to_write = {sid: body for sid, body in sections.items()
                         if f"BLP:{sid}" in valid_ids}
    if not sections_to_write:
        return CortexOUT.error(
            f"no valid sections to write. Skipped: {sections_skipped}",
            code="INVALID_ARGS",
            skipped=sections_skipped,
            valid_ids=sorted(valid_ids),
        )

    # Find or create the BLP file.
    bp_path, fm, body, created = _find_or_create_blueprint(root, bp_id, ctx, path_hint=path)

    # Delegate each section to blueprint.update (reuses _replace_section).
    sections_written: list[str] = []
    sections_errors: list[dict] = []
    for sid, section_content in sections_to_write.items():
        result = update_blueprint(bp_id, section=sid, content=section_content, path=path, ctx=ctx)
        if result.profile == "OUT-WORK":
            sections_written.append(sid)
        else:
            sections_errors.append({"id": sid, "error": result.message})

    _record_pulse(root, ctx, bp_id=bp_id, action="synthesize",
                  sections_written=sections_written)

    msg = (f"blueprint.synthesize ok id={bp_id} sections={len(sections_written)} "
           f"errors={len(sections_errors)} created={created}")
    if sections_errors:
        msg += f" failed={sections_errors}"

    return CortexOUT.work(
        msg,
        blueprint_id=bp_id,
        path=str(bp_path),
        sections_written=sections_written,
        sections_errors=sections_errors if sections_errors else None,
        sections_skipped=sections_skipped,
        created=created,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_or_create_blueprint(
    root: Path,
    bp_id: str,
    ctx: PermissionContext | None,
    *,
    path_hint: str | None = None,
) -> tuple[Path, dict[str, Any], str, bool]:
    """Find the BLP file across cycles, or create a new draft.

    Returns ``(bp_path, frontmatter, body, created)``.
    """
    cycles_base = root / CYCLES_DIR

    # 1. Explicit path_hint
    if path_hint:
        from ._helpers import _resolve_blueprint_path
        resolved = _resolve_blueprint_path(root, bp_id, path_hint=path_hint)
        if resolved and resolved.exists():
            text = resolved.read_text(encoding="utf-8")
            fm, body = _parse_md(text)
            return resolved, fm, body, False

    # 2. Search across cycles (most recent first)
    if cycles_base.exists():
        for cdir in sorted(cycles_base.iterdir(), reverse=True):
            bp_path = cdir / BLUEPRINTS_DIR / f"{bp_id}.md"
            if bp_path.exists():
                text = bp_path.read_text(encoding="utf-8")
                fm, body = _parse_md(text)
                return bp_path, fm, body, False

    # Not found — create in the latest cycle.
    if cycles_base.exists():
        open_cycles = sorted([d.name for d in cycles_base.iterdir() if d.is_dir()])
        cycle_id = open_cycles[-1] if open_cycles else "CYCLE-01"
    else:
        cycle_id = "CYCLE-01"
        cycles_base.mkdir(parents=True, exist_ok=True)

    bp_dir = cycles_base / cycle_id / BLUEPRINTS_DIR
    bp_dir.mkdir(parents=True, exist_ok=True)
    bp_path = bp_dir / f"{bp_id}.md"

    # Use the template as the starting body.
    from ...blueprint.template import _resolve_template
    template_path = _resolve_template(path=str(root.parent))
    if template_path and template_path.exists():
        body = template_path.read_text(encoding="utf-8")
        body = body.replace("blueprint_id: \"\"", f'blueprint_id: "{bp_id}"')
        body = body.replace("# BLP-NNN: Título", f"# {bp_id}: Synthesized")
    else:
        body = f"---\nblueprint_id: \"{bp_id}\"\nstatus: \"draft\"\n---\n\n# {bp_id}: Synthesized\n"

    fm, body = _parse_md(body)
    fm["blueprint_id"] = bp_id
    fm["status"] = "draft"
    fm["governor"] = (ctx or PermissionContext.from_env(project_root=root)).agent_id

    return bp_path, fm, body, True


def _parse_md(text: str) -> tuple[dict[str, Any], str]:
    """Parse a BLP .md file into (frontmatter, body)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw = parts[1].strip()
    body = parts[2].strip()
    fm: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip().rstrip("@")
        v = v.strip().strip('"').strip("'")
        if v == "true":
            v = True
        elif v == "false":
            v = False
        fm[k] = v
    return fm, body


def _record_pulse(
    root: Path,
    ctx: PermissionContext | None,
    *,
    bp_id: str,
    action: str,
    sections_written: list[str],
) -> None:
    """Append a PULSE event for the synthesize call (best-effort)."""
    try:
        agent = (ctx or PermissionContext.from_env(project_root=root)).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id=bp_id,
            kind="blueprint_lifecycle",
            agent=agent,
            payload=f"[{action}] sections={','.join(sections_written)}",
        )
    except Exception:  # noqa: BLE001
        pass
