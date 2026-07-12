"""Blueprint lifecycle handlers.

create, define, mature, ready, assign, claim
"""

from __future__ import annotations

import re
from pathlib import Path

from ...constants import CYCLES_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...sync import sync_brain
from ._helpers import (
    BLUEPRINT_TEMPLATE,
    BP_BLOCKED,
    BP_DEFINED,
    BP_DRAFT,
    BP_IN_PROGRESS,
    BP_MATURING,
    BP_READY,
    LEARNING_GATE,
    _blueprints_dir,
    _find_blueprint,
    _find_workspace_template,
    _has_learning_recorded,
    _learning_instruction,
    _now_iso,
    _prefill_from_context,
    _read_blueprint,
    _read_quality_gates,
    _resolve_root,
    _transition,
    _write_blueprint,
    next_blueprint_id_safe,
    scan_markers,
)

# ---------------------------------------------------------------------------
# blueprint.create
# ---------------------------------------------------------------------------


def create_blueprint(
    obj: str,
    cycle: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Create a new Blueprint from BLP_TEMPLATE.md."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Find cycle
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")

    if cycle:
        cycle_id = cycle
    else:
        open_cycles = sorted([d.name for d in cycles_base.iterdir() if d.is_dir() and (d / "MANIFEST.md").exists()])
        if not open_cycles:
            open_cycles = sorted([d.name for d in cycles_base.iterdir() if d.is_dir()])
        if not open_cycles:
            return CortexOUT.error("no cycles — call cycle.create first", code="NOT_FOUND")
        cycle_id = open_cycles[-1]

    # Check cycle is in ready or active state
    cycle_mf = cycles_base / cycle_id / "MANIFEST.md"
    if cycle_mf.exists():
        mf_fm, _ = _read_blueprint(cycle_mf)
        cycle_status = mf_fm.get("status", "") if mf_fm else ""
        if cycle_status not in ("ready", "active"):
            return CortexOUT.error(
                f"cycle {cycle_id} is not ready. Current status: {cycle_status}. Mature the cycle first.",
                code="INVALID_STATE",
            )

    bp_dir = _blueprints_dir(root, cycle_id)
    bp_dir.mkdir(parents=True, exist_ok=True)
    bp_id = next_blueprint_id_safe(bp_dir)

    # Try workspace templates first, fallback to package templates.
    template_src = _find_workspace_template(root, BLUEPRINT_TEMPLATE)
    if template_src is None:
        template_src = Path(__file__).resolve().parent.parent / "templates" / BLUEPRINT_TEMPLATE

    if not template_src.exists():
        return CortexOUT.error(f"template {BLUEPRINT_TEMPLATE} not found. Reinstall arqux.", code="NOT_FOUND")

    template_text = template_src.read_text(encoding="utf-8")
    # Replace placeholders
    gov = (ctx or PermissionContext.from_env()).agent_id
    body = template_text.replace("blueprint_id: \"\"", f'blueprint_id: "{bp_id}"')
    body = body.replace("title: \"\"", f'title: "{obj}"')
    body = body.replace("cycle: \"\"", f'cycle: "{cycle_id}"')
    body = body.replace("governor: \"\"", f'governor: "{gov}"')
    body = body.replace("created_at: \"\"", f'created_at: "{_now_iso()}"')
    body = body.replace("# BLP-NNN: Título", f"# {bp_id}: {obj}")

    # Pre-fill context from brain.cortex and cycle manifest
    body = _prefill_from_context(body, root, cycle_id)

    # Scan markers and store map in frontmatter
    markers = scan_markers(body)
    if markers:
        markers_json = ", ".join(f'"{m}"' for m in markers)
        body = body.replace(
            "_template_ref:",
            f"blp_markers@: [{markers_json}]\n_template_ref:",
            1,
        )

    bp_path = bp_dir / f"{bp_id}.md"
    bp_path.write_text(body, encoding="utf-8")

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.create",
        focus=f"Definir {bp_id}",
        detail=f"{bp_id} created in {cycle_id}",
    )

    return CortexOUT.work(
        f"blueprint.create ok id={bp_id} cycle={cycle_id}",
        blueprint_id=bp_id,
        cycle=cycle_id,
        status=BP_DRAFT,
        path=str(bp_path),
        markers=markers,
        instruction=(
            f"Blueprint {bp_id} created with {len(markers)} markers. "
            "Use blueprint.update(section=N, content=...) to fill sections."
        ),
    )


# ---------------------------------------------------------------------------
# blueprint.define
# ---------------------------------------------------------------------------


def define_blueprint(
    bp_id: str,
    pre: list[str] | None = None,
    scope: str | None = None,
    exclusions: str | None = None,
    mandatory_rules: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    procedure: str | None = None,
    validations: list[dict[str, str]] | None = None,
    technical_design: str | None = None,
    operational_design: str | None = None,
    risks: list[str] | None = None,
    blocking_rule: str | None = None,
    *,
    sections: dict[str, str] | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Fill the Blueprint's definition sections. State → defined.

    BLP-012: in addition to the legacy named parameters, the handler now
    accepts a ``sections`` dict mapping section IDs (e.g. ``"BLP:3"``)
    to content strings. This is the same format used by
    ``blueprint.synthesize`` (BLP-007).

    When both a named parameter and a ``sections`` entry target the same
    section, the ``sections`` entry wins. The named parameters are kept
    for backward compatibility.

    The section IDs are validated against ``BLP_TEMPLATE.md`` via
    ``arqux.blueprint.template.parse_blp_template()`` — unknown IDs are
    rejected with ``INVALID_ARGS``.
    """
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_DEFINED)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    # Validate dynamic sections against the template (BLP-012 / BLP-013).
    sections = sections or {}
    if sections:
        from ...blueprint.template import parse_blp_template
        tmpl_result = parse_blp_template(path=path)
        if tmpl_result.profile != "OUT-WORK":
            return CortexOUT.error(
                f"cannot validate sections: {tmpl_result.message}",
                code="TEMPLATE_MISSING",
            )
        valid_ids = set(tmpl_result.fields.get("markers", {}).keys())
        unknown = [sid for sid in sections if sid not in valid_ids]
        if unknown:
            return CortexOUT.error(
                f"unknown section IDs: {unknown}. Valid IDs: {sorted(valid_ids)}",
                code="INVALID_ARGS",
                unknown=unknown,
                valid_ids=sorted(valid_ids),
            )

    # Update status
    fm["status"] = BP_DEFINED
    fm["updated_at"] = _now_iso()

    # Apply filled sections to body by replacing template placeholders.
    # Use regex-based section replacement for robustness.
    new_body = body

    # --- Marker-based section replacement ---
    # Helper: replace content between <!-- BLP:N --> markers
    # Preserves the section header (## §N: Title) if present.
    def _replace_marker(text: str, marker_id: str, content: str) -> str:
        open_tag = f"<!-- {marker_id} -->"
        close_tag = f"<!-- /{marker_id} -->"
        pattern = rf"{re.escape(open_tag)}.*?{re.escape(close_tag)}"

        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return text

        block = match.group(0)
        inner = block[len(open_tag):-len(close_tag)].strip()

        # Preserve section header (first line starting with ## §)
        header = ""
        for line in inner.split("\n"):
            if line.strip().startswith("## §"):
                header = line.rstrip()
                break

        if header:
            replacement = f"{open_tag}\n{header}\n\n{content}\n{close_tag}"
        else:
            replacement = f"{open_tag}\n{content}\n{close_tag}"

        return text.replace(block, replacement, 1)

    # §3 Preconditions
    if pre:
        pre_text = "\n".join(f"- [ ] {p}" for p in pre)
        new_body = _replace_marker(new_body, "BLP:3", pre_text)

    # §6 Scope (BLP:6.1) and Exclusions (BLP:6.2)
    if scope:
        new_body = _replace_marker(new_body, "BLP:6.1", f"- {scope}")
    if exclusions:
        new_body = _replace_marker(new_body, "BLP:6.2", f"- {exclusions}")

    # §7 Mandatory Rules
    if mandatory_rules:
        rules_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(mandatory_rules))
        new_body = _replace_marker(new_body, "BLP:7", rules_text)

    # §11 Work Procedure
    if procedure:
        new_body = _replace_marker(new_body, "BLP:11", procedure)

    # §12 Acceptance Criteria
    if acceptance_criteria:
        ac_text = "\n".join(f"- [ ] **AC-{i+1:02d}:** {ac}" for i, ac in enumerate(acceptance_criteria))
        new_body = _replace_marker(new_body, "BLP:12", ac_text)

    # §13 Required Validations
    if validations:
        val_text = "\n".join(
            f"| {v.get('type', 'test')} | {v.get('desc', '')} | `{v.get('cmd', '')}` | {v.get('expected', '')} |"
            for v in validations
        )
        new_body = _replace_marker(new_body, "BLP:13", val_text)

    # §15 Risks
    if risks:
        risk_text = "\n".join(f"| R-{i+1:02d} | {r} | _Impact_ | _Mitigation_ |" for i, r in enumerate(risks))
        new_body = _replace_marker(new_body, "BLP:15", risk_text)

    # §16 Blocking Rule
    if blocking_rule:
        new_body = _replace_marker(new_body, "BLP:16", blocking_rule[:200])

    # Apply dynamic sections (BLP-012) — these override any named param
    # above that targeted the same section.
    sections_written: list[str] = []
    sections_skipped: list[str] = []
    for section_id, section_content in (sections or {}).items():
        if not section_content:
            sections_skipped.append(section_id)
            continue
        before = new_body
        new_body = _replace_marker(new_body, section_id, section_content)
        if new_body != before:
            sections_written.append(section_id)
        else:
            sections_skipped.append(section_id)

    _write_blueprint(bp_path, fm, new_body)

    return CortexOUT.work(
        f"blueprint.define ok id={bp_id} sections_written={len(sections_written)}",
        blueprint_id=bp_id,
        status=BP_DEFINED,
        sections_written=sections_written,
        sections_skipped=sections_skipped,
    )


# ---------------------------------------------------------------------------
# blueprint.mature
# ---------------------------------------------------------------------------


def mature_blueprint(
    bp_id: str,
    mode: str = "async",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Enter maturation phase. State → maturing.

    Mode 'async' (default): cyclic iteration with Architect.
    Mode 'live': synchronous co-design with immediate feedback.
    """
    if mode not in ("live", "async"):
        return CortexOUT.error(
            f"invalid mode={mode!r} (must be 'live' or 'async')",
            code="INVALID_ARGS",
        )

    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    valid_from = fm.get("status", BP_DRAFT)
    if valid_from not in (BP_DEFINED, BP_BLOCKED, BP_DRAFT):
        return CortexOUT.error(
            f"cannot mature from {valid_from} (must be draft, defined or blocked)",
            code="INVALID_STATE",
        )

    fm["status"] = BP_MATURING
    fm["mature_mode"] = mode
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    if mode == "live":
        instruction = (
            "Live co-design mode active. Iterate sections immediately "
            "with Architect feedback — no waiting between cycles. "
            "Refine each section until Architect approves, "
            "then call blueprint.gate() for quality gates."
        )
    else:
        instruction = (
            "Cyclic maturation with Architect begins. "
            "Present each section, wait for feedback, adjust. "
            "Once all quality gates pass, call blueprint.ready()."
        )

    return CortexOUT.work(
        f"blueprint.mature ok id={bp_id} mode={mode}",
        blueprint_id=bp_id,
        status=BP_MATURING,
        mode=mode,
        instruction=instruction,
    )


# ---------------------------------------------------------------------------
# blueprint.ready
# ---------------------------------------------------------------------------


def ready_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Architect declares Blueprint ready for execution. State → ready."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_READY)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    # Verify quality gates: ALL must be true before ready.
    # This prevents agents from skipping the maturation cycle.
    gates_status = _read_quality_gates(fm)
    if gates_status:
        if not gates_status.get(LEARNING_GATE, True) and _has_learning_recorded(root, bp_id):
            gates_status[LEARNING_GATE] = True
        failed_gates = [g for g, v in gates_status.items() if not v]
        if failed_gates:
            if failed_gates == [LEARNING_GATE]:
                return CortexOUT.error(
                    "Cannot ready: has_learning_recorded is false. Call identity.record() first.",
                    code="LEARNING_NOT_RECORDED",
                    failed_gates=failed_gates,
                    instruction=_learning_instruction(f"blueprint.ready({bp_id})"),
                )
            return CortexOUT.error(
                f"maturation incomplete — {len(failed_gates)} quality gate(s) still false: "
                f"{', '.join(failed_gates)}. "
                f"Complete the cyclic maturation interaction with the Architect first.",
                code="MATURATION_INCOMPLETE",
                failed_gates=failed_gates,
                instruction=(
                    "Load the blueprint-workflow skill (§8.3) for maturation protocol. "
                    "Present each gate to the Architect. Only call ready() when ALL gates are true."
                ),
            )

    fm["status"] = BP_READY
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.ready",
        focus=f"Ejecutar {bp_id}",
        detail=f"{bp_id} ready for execution",
    )

    return CortexOUT.work(
        f"blueprint.ready ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_READY,
        instruction="Blueprint is executable. Governor: call blueprint.assign() to assign an executor.",
    )


# ---------------------------------------------------------------------------
# blueprint.assign
# ---------------------------------------------------------------------------


def assign_blueprint(
    bp_id: str,
    executor: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Governor assigns an executor to the Blueprint."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") != BP_READY:
        return CortexOUT.error(f"Blueprint is {fm.get('status')} — must be ready to assign", code="INVALID_STATE")

    fm["executor"] = executor
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.assign ok id={bp_id} executor={executor}",
        blueprint_id=bp_id,
        executor=executor,
        instruction=f"Executor {executor}: call blueprint.claim({bp_id!r}) to start.",
    )


# ---------------------------------------------------------------------------
# blueprint.claim
# ---------------------------------------------------------------------------


def claim_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Executor claims the Blueprint. State → in_progress."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_IN_PROGRESS)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    caller = (ctx or PermissionContext.from_env()).agent_id
    fm["status"] = BP_IN_PROGRESS
    fm["executor"] = caller
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.claim ok id={bp_id} executor={caller}",
        blueprint_id=bp_id,
        status=BP_IN_PROGRESS,
        executor=caller,
    )
