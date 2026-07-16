"""blueprint.synthesize handler — pure sequencer for guided BLP creation.

GUIDE MODE:
  1. Create or find the BLP in the active cycle
  2. Scan the body with ``Sequencer("BLP").scan()``
  3. Return the first pending section (lowest ID with unfilled markers)
  4. Agent writes directly via ``blueprint.update()``

synthesize does NOT write files.
Agent calls ``blueprint.update()`` directly for every section.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from ...blueprint.template import parse_blp_template
from ...constants import BLUEPRINTS_DIR, CYCLES_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root
from ._helpers import _write_blueprint

# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------


def synthesize_blueprint(
    bp_id: str,
    content: str | None = None,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Write a Blueprint's content sections via guided orchestration.

    Args:
        bp_id: Blueprint ID (e.g. ``"BLP-007"``). Created if not exists.
        content: CORTEX content payload. Per-section form:
            ``$1:{full section body}``.
            Omit for GUIDE MODE.
        path: Starting path for resolving the project root.
        ctx: Permission context.

    Returns ``OUT-WORK`` with:
        - ``blueprint_id`` (str)
        - ``path`` (str) — path to the written BLP file
        - ``sections_written`` (list[str])
        - ``next_section`` (dict | None) — next section to fill
        - ``frontmatter_prompt`` (dict | None) — YAML fields after §18
    """
    if not bp_id or not isinstance(bp_id, str):
        return CortexOUT.error("bp_id is required", code="INVALID_ARGS")
    if not re.match(r"^BLP-\d{3}$", bp_id):
        return CortexOUT.error(
            f"invalid bp_id={bp_id!r} (must match BLP-NNN)",
            code="INVALID_ARGS",
        )
    if content is not None and not isinstance(content, str):
        return CortexOUT.error("invalid content type", code="INVALID_ARGS")

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

    # Find or create the BLP file.
    bp_path, fm, body, created = _find_or_create_blueprint(root, bp_id, ctx, path_hint=path)

    # Persist the template body to disk immediately if freshly created.
    if created:
        _write_blueprint(bp_path, fm, body)

    # GUIDE MODE: scan BLP with Sequencer and return next pending section.
    from ...core.sequencer import Sequencer
    seq = Sequencer("BLP")
    pending_segments = seq.scan(body).pending
    if not pending_segments:
        # All sections filled — prompt for YAML frontmatter.
        return _prompt_yaml(created, bp_path, bp_id)
    next_seg = pending_segments[0]
    return CortexOUT.work(
        f"blueprint.synthesize guide id={bp_id}",
        blueprint_id=bp_id,
        path=str(bp_path),
        next_section={
            "section_id": next_seg.id,
            "template": next_seg.template,
            "markers": next_seg.pending_markers if not next_seg.has_content else [],
        },
        sections_pending={s.id: s.pending_markers for s in pending_segments},
        created=created,
    )


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------


def _prompt_yaml(created: bool, bp_path: Path, bp_id: str) -> CortexOUT:
    """Return YAML frontmatter prompt when all sections are filled."""
    return CortexOUT.work(
        f"blueprint.synthesize complete id={bp_id}",
        blueprint_id=bp_id,
        path=str(bp_path),
        next_section=None,
        frontmatter_prompt={
            "title": "string",
            "priority": "low|medium|high",
            "complexity": "simple|standard|complex",
            "has_clear_objective": "true|false",
            "has_verifiable_preconditions": "true|false",
            "has_scope_and_exclusions": "true|false",
            "has_acceptance_criteria": "true|false",
            "has_work_procedure": "true|false",
            "has_required_validations": "true|false",
            "has_learning_recorded": "true|false",
        },
        created=created,
    )


# ---------------------------------------------------------------------------
# BLP file find-or-create
# ---------------------------------------------------------------------------


def _find_or_create_blueprint(
    root: Path,
    bp_id: str,
    ctx: PermissionContext | None,
    *,
    path_hint: str | None = None,
) -> tuple[Path, dict[str, Any], str, bool]:
    """Find the BLP file in the active cycle, or create a new draft.

    synthesize only searches the ACTIVE cycle — BLP numbers reset per cycle
    and the synthesizer must respect session context.

    Returns ``(bp_path, frontmatter, body, created)``.
    """
    cycles_base = root / CYCLES_DIR

    # Determine active cycle from session context
    from ...state import crud_read
    cycle_id = ""
    try:
        brain_path = root / ".arqux" / "brain.cortex"
        if brain_path.exists():
            cur = crud_read(brain_path, "$1/FCS:current")
            fcs = cur.get("entries", [{}])[0].get("value", {}) if cur.get("entries") else {}
            cycle_id = fcs.get("cycle", "")
    except Exception:
        pass

    # 1. Active cycle lookup (scope: only the active cycle)
    if cycle_id and cycles_base.exists():
        bp_path = cycles_base / cycle_id / BLUEPRINTS_DIR / f"{bp_id}.md"
        if bp_path.exists():
            text = bp_path.read_text(encoding="utf-8")
            fm, body = _parse_md(text)
            return bp_path, fm, body, False

    # Fallback: search for last open (non-closed) cycle
    if not cycle_id and cycles_base.exists():
        active_cycles: list[str] = []
        for cdir in sorted(cycles_base.iterdir()):
            if not cdir.is_dir():
                continue
            manifest_path = cdir / "MANIFEST.md"
            if manifest_path.exists():
                manifest_text = manifest_path.read_text(encoding="utf-8")
                if "status: closed" not in manifest_text:
                    active_cycles.append(cdir.name)
        cycle_id = active_cycles[-1] if active_cycles else None
        if cycle_id:
            bp_path = cycles_base / cycle_id / BLUEPRINTS_DIR / f"{bp_id}.md"
            if bp_path.exists():
                text = bp_path.read_text(encoding="utf-8")
                fm, body = _parse_md(text)
                return bp_path, fm, body, False

    if not cycle_id:
        cycle_id = "CYCLE-01"

    # Not found — create fresh in the target cycle.
    bp_dir = cycles_base / cycle_id / BLUEPRINTS_DIR
    bp_dir.mkdir(parents=True, exist_ok=True)
    bp_path = bp_dir / f"{bp_id}.md"

    from ...blueprint.template import _resolve_template
    template_path = _resolve_template(path=str(root.parent))
    if template_path and template_path.exists():
        body = template_path.read_text(encoding="utf-8")
        body = body.replace('blueprint_id: ""', f'blueprint_id: "{bp_id}"')
        body = body.replace("# BLP-NNN: Título", f"# {bp_id}: Synthesized")
    else:
        body = (
            "---\n"
            f'blueprint_id: "{bp_id}"\n'
            'status: "draft"\n'
            "---\n\n"
            f"# {bp_id}: Synthesized\n"
        )

    fm, body = _parse_md(body)
    fm["blueprint_id"] = bp_id
    fm["status"] = "draft"
    fm["governor"] = (ctx or PermissionContext.from_env(project_root=root)).agent_id

    return bp_path, fm, body, True


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


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
