"""`blueprint` module — Blueprint lifecycle governance.

Handlers:
    blueprint.create   — create from template, state=draft
    blueprint.define   — fill definition sections, state=defined
    blueprint.mature   — enter maturation, state=maturing
    blueprint.ready    — architect declares ready, state=ready
    blueprint.assign   — governor assigns executor
    blueprint.claim    — executor claims blueprint, state=in_progress
    blueprint.update   — update progress
    blueprint.complete — declare execution complete, state=review
    blueprint.fail     — obstacle detected, state=blocked
    blueprint.approve  — auditor approves after cross-verification, state=done
    blueprint.re_delegate — re-delegate after verification fail
    blueprint.block_for_architect — 3rd fail → architect review
    blueprint.read     — read full blueprint (HCORTEX or CORTEX)
    blueprint.list     — list blueprints with filters
"""

from __future__ import annotations

import re
import time as _time
from pathlib import Path
from typing import Any

from ..constants import (
    ARQUX_DIR,
    BLUEPRINTS_DIR,
    CYCLES_DIR,
    OUT_WORK,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import (
    find_project_root,
    read_brain,
    write_brain_sections,
    write_cortex_pair,
)


BLUEPRINT_TEMPLATE = "BLP_TEMPLATE.md"
MAX_VERIFICATION_LOOPS = 3

# Blueprint states
BP_DRAFT = "draft"
BP_DEFINED = "defined"
BP_MATURING = "maturing"
BP_READY = "ready"
BP_IN_PROGRESS = "in_progress"
BP_BLOCKED = "blocked"
BP_REVIEW = "review"
BP_DONE = "done"
BP_CANCELLED = "cancelled"

VALID_TRANSITIONS = {
    BP_DRAFT: [BP_DEFINED, BP_CANCELLED],
    BP_DEFINED: [BP_MATURING, BP_DRAFT, BP_CANCELLED],
    BP_MATURING: [BP_READY, BP_DEFINED, BP_CANCELLED],
    BP_READY: [BP_IN_PROGRESS, BP_CANCELLED],
    BP_IN_PROGRESS: [BP_BLOCKED, BP_REVIEW],
    BP_BLOCKED: [BP_MATURING, BP_CANCELLED],
    BP_REVIEW: [BP_DONE, BP_IN_PROGRESS],  # in_progress = re-delegate
    BP_DONE: [],
    BP_CANCELLED: [],
}


def _now_iso() -> str:
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())


def _resolve_root(path: str | None = None) -> Path | None:
    """Find the .arqux/ root. Returns .arqux/ path."""
    return find_project_root(start=path)


def _blueprints_dir(root: Path, cycle_id: str) -> Path:
    """Return blueprints/ directory for a cycle."""
    return root / CYCLES_DIR / cycle_id / BLUEPRINTS_DIR


def _next_blueprint_id(bp_dir: Path) -> str:
    """Generate next blueprint ID (BLP-NNN)."""
    existing = []
    if bp_dir.exists():
        for f in bp_dir.glob("BLP-*.md"):
            m = re.match(r"BLP-(\d+)\.md", f.name)
            if m:
                existing.append(int(m.group(1)))
    n = max(existing) + 1 if existing else 1
    return f"BLP-{n:03d}"


def _transition(bp_id: str, from_state: str, to_state: str) -> str | None:
    """Validate transition. Returns error message or None if valid."""
    if to_state not in VALID_TRANSITIONS.get(from_state, []):
        return f"invalid transition: {from_state} → {to_state}"
    return None


def _write_blueprint(path: Path, fm: dict[str, Any], body: str) -> None:
    """Write blueprint HCORTEX .md file."""
    content = "---\n"
    for k, v in fm.items():
        if isinstance(v, bool):
            v = str(v).lower()
        elif isinstance(v, str):
            v = f'"{v}"'
        content += f"{k}: {v}\n"
    content += "---\n\n" + body
    path.write_text(content, encoding="utf-8")


def _read_blueprint(path: Path) -> tuple[dict[str, Any], str] | None:
    """Parse a blueprint .md file. Returns (fm, body) or None."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # Split frontmatter (--- ... ---) from body
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    fm_raw = parts[1].strip()
    body = parts[2].strip()
    fm: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"')
        if val == "true":
            val = True
        elif val == "false":
            val = False
        fm[key] = val
    return fm, body


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
    bp_id = _next_blueprint_id(bp_dir)

    # Copy template from package templates (always available after install).
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

    # Pre-fill context from brain.cortex and cycle manifest
    body = _prefill_from_context(body, root, cycle_id)

    bp_path = bp_dir / f"{bp_id}.md"
    bp_path.write_text(body, encoding="utf-8")

    return CortexOUT.work(
        f"blueprint.create ok id={bp_id} cycle={cycle_id}",
        blueprint_id=bp_id,
        cycle=cycle_id,
        status=BP_DRAFT,
        path=str(bp_path),
        instruction=(
            "IMMEDIATE NEXT STEP: call blueprint.define() to fill ALL 18 sections. "
            "The draft has basic brain context pre-filled, but the Architect expects "
            "a complete document with: §3 Preconditions, §6 Scope, §8 Technical Design (PUML), "
            "§9 Operational Design (PUML), §11 Work Procedure, §12 Acceptance Criteria, §14 Tasks. "
            "Do NOT present this draft to the Architect — define it FIRST, then enter maturation."
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
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Fill the Blueprint's definition sections. State → defined."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_DEFINED)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    # Update status
    fm["status"] = BP_DEFINED
    fm["updated_at"] = _now_iso()

    # Apply filled sections to body by replacing template placeholders.
    # Use regex-based section replacement for robustness.
    import re
    new_body = body

    # §3 Preconditions — replace the placeholder line(s)
    if pre:
        pre_text = "\n".join(f"- [ ] {p}" for p in pre)
        # Match the preconditions section: from "## §3:" to the next "## §"
        new_body = re.sub(
            r"(## §3: Preconditions\n\n).*?(\n## §4:)",
            rf"\1{pre_text}\n\2",
            new_body, count=1, flags=re.DOTALL,
        )

    # §6 Scope — replace in-scope items
    if scope:
        new_body = re.sub(
            r"(\*\*In scope:\*\*\n)- _Item 1_\n- _Item 2_",
            f"**In scope:**\n- {scope}",
            new_body, count=1,
        )
    if exclusions:
        new_body = re.sub(
            r"(\*\*Out of scope.*:\*\*\n)- _Item 1_\n- _Item 2_",
            f"**Out of scope:**\n- {exclusions}",
            new_body, count=1,
        )

    # §7 Mandatory Rules
    if mandatory_rules:
        rules_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(mandatory_rules))
        new_body = re.sub(
            r"1\. _Rule 1_\n2\. _Rule 2_",
            rules_text,
            new_body, count=1,
        )

    # §12 Acceptance Criteria
    if acceptance_criteria:
        ac_text = "\n".join(f"- [ ] **AC-{i+1:02d}:** {ac}" for i, ac in enumerate(acceptance_criteria))
        new_body = re.sub(
            r"- \[ \] \*\*AC-01:\*\* _Description.*_verification: command or procedure_\n- \[ \] \*\*AC-02:.*\n- \[ \] \*\*AC-03:.*",
            ac_text,
            new_body, count=1,
        )

    # §11 Work Procedure — replace phase placeholders
    if procedure:
        new_body = re.sub(
            r"(## §11: Work Procedure\n\n).*?(\n## §12:)",
            rf"\1{procedure}\n\2",
            new_body, count=1, flags=re.DOTALL,
        )

    # §13 Required Validations
    if validations:
        val_text = "\n".join(
            f"| {v.get('type', 'test')} | {v.get('desc', '')} | `{v.get('cmd', '')}` | {v.get('expected', '')} |"
            for v in validations
        )
        new_body = re.sub(
            r"\| test \| _Description_ \| `_command_` \| _output_ \|\n.*?\n.*?\n",
            val_text + "\n",
            new_body, count=1,
        )

    # §15 Risks
    if risks:
        risk_text = "\n".join(f"| R-{i+1:02d} | {r} | _Impact_ | _Mitigation_ |" for i, r in enumerate(risks))
        new_body = re.sub(
            r"\| R-01 \| _Description_ \| _Impact_ \| _Mitigation_ \|",
            risk_text,
            new_body, count=1,
        )

    # §16 Blocking Rule
    if blocking_rule:
        new_body = re.sub(
            r"1\. _Condition 1_",
            blocking_rule[:200],
            new_body, count=1,
        )

    _write_blueprint(bp_path, fm, new_body)

    return CortexOUT.work(
        f"blueprint.define ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_DEFINED,
    )


# ---------------------------------------------------------------------------
# blueprint.mature
# ---------------------------------------------------------------------------


def mature_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Enter maturation phase. State → maturing."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    valid_from = fm.get("status", BP_DRAFT)
    if valid_from not in (BP_DEFINED, BP_BLOCKED):
        return CortexOUT.error(
            f"cannot mature from {valid_from} (must be defined or blocked)",
            code="INVALID_STATE",
        )

    fm["status"] = BP_MATURING
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.mature ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_MATURING,
        instruction="Cyclic maturation with Architect begins. Load blueprint-workflow skill §7 for 6 quality gates. Present each gate to Architect until all pass, then call blueprint.ready().",
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
        failed_gates = [g for g, v in gates_status.items() if not v]
        if failed_gates:
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


# ---------------------------------------------------------------------------
# blueprint.task
# ---------------------------------------------------------------------------


_TASK_RE = re.compile(r"^(- \[[ ~x]\] \*\*T-\d+\.\d+:\*\* .+)$", re.MULTILINE)


def task_blueprint(
    bp_id: str,
    task_id: str,
    status: str,
    evidence: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update one task's checkbox in §14. Status: in_progress → [~], completed → [x]."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") not in (BP_IN_PROGRESS, BP_REVIEW, BP_DONE):
        return CortexOUT.error(
            f"blueprint is {fm.get('status')} — must be in_progress to update tasks",
            code="INVALID_STATE",
        )

    if status not in ("in_progress", "completed"):
        return CortexOUT.error("status must be 'in_progress' or 'completed'", code="INVALID_ARGS")

    marker = "[~]" if status == "in_progress" else "[x]"
    old_marker_pattern = r"^(- \[[ ~x]\] \*\*" + re.escape(task_id) + r":\*\* .+)$"
    match = re.search(old_marker_pattern, body, re.MULTILINE)
    if not match:
        return CortexOUT.error(f"task {task_id} not found in §14", code="NOT_FOUND")

    old_line = match.group(1)
    new_line = old_line.replace(old_line[2:5], marker, 1)
    ts = _now_iso()

    if evidence:
        new_line += f"\n  > [{ts}] {evidence}"

    body = body.replace(old_line, new_line, 1)
    fm["updated_at"] = ts
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.task ok id={bp_id} task={task_id} status={status}",
        blueprint_id=bp_id,
        task_id=task_id,
        status=status,
    )


# ---------------------------------------------------------------------------
# blueprint.ac
# ---------------------------------------------------------------------------


def ac_blueprint(
    bp_id: str,
    ac_id: str,
    status: str,
    evidence: str | None = None,
    reason: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Verify one AC in §12. Fail triggers auto re-delegate (max 3)."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") not in (BP_IN_PROGRESS, BP_REVIEW):
        return CortexOUT.error(
            f"blueprint is {fm.get('status')} — must be in_progress or review",
            code="INVALID_STATE",
        )

    if status not in ("verified", "failed"):
        return CortexOUT.error("status must be 'verified' or 'failed'", code="INVALID_ARGS")

    pattern = r"^(- \[[ ~x]\] \*\*" + re.escape(ac_id) + r":\*\* .+)$"
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        return CortexOUT.error(f"ac {ac_id} not found in §12", code="NOT_FOUND")

    old_line = match.group(1)
    ts = _now_iso()

    if status == "verified":
        new_line = old_line.replace(old_line[2:5], "[x]", 1)
        if evidence:
            new_line += f"\n  > [{ts}] Verified: {evidence}"
    else:
        new_line = old_line  # keep unchecked
        raw_loop = fm.get("verification_loop", 0)
        current = int(raw_loop) if isinstance(raw_loop, str) else raw_loop
        reason_text = reason or "AC verification failed"
        if evidence:
            new_line += f"\n  > [{ts}] FAIL (attempt {current + 1}): {reason_text} — {evidence}"
        else:
            new_line += f"\n  > [{ts}] FAIL (attempt {current + 1}): {reason_text}"

    body = body.replace(old_line, new_line, 1)
    fm["updated_at"] = ts
    _write_blueprint(bp_path, fm, body)

    if status == "failed":
        raw_loop = fm.get("verification_loop", 0)
        current = int(raw_loop) if isinstance(raw_loop, str) else raw_loop
        next_attempt = current + 1
        # Auto re-delegate (max 3 attempts). 3rd fail → block_for_architect.
        if fm.get("status") == BP_REVIEW and next_attempt < MAX_VERIFICATION_LOOPS:
            return re_delegate_blueprint(bp_id, path=path, ctx=ctx)
        elif fm.get("status") == BP_REVIEW:
            fm["verification_loop"] = next_attempt
            _write_blueprint(bp_path, fm, body)
            return CortexOUT.work(
                f"blueprint.ac ok id={bp_id} ac={ac_id} status=failed "
                f"attempt={next_attempt}/{MAX_VERIFICATION_LOOPS} — max loops reached",
                blueprint_id=bp_id,
                ac_id=ac_id,
                status="failed",
                verification_loop=next_attempt,
                max_loops=MAX_VERIFICATION_LOOPS,
                instruction="Call blueprint.block_for_architect() for manual review.",
            )

    return CortexOUT.work(
        f"blueprint.ac ok id={bp_id} ac={ac_id} status={status}",
        blueprint_id=bp_id,
        ac_id=ac_id,
        status=status,
    )


# ---------------------------------------------------------------------------
# blueprint.update
# ---------------------------------------------------------------------------


def update_blueprint(
    bp_id: str,
    note: str | None = None,
    section: str | None = None,
    content: str | None = None,
    puml: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update Blueprint progress (note) or refine a single section."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    fm["updated_at"] = _now_iso()

    # Section refinement takes priority over note
    if section:
        sec_num = section.lstrip("§").strip()
        section_header = f"## §{sec_num}:"
        # Build replacement content
        if puml:
            section_content = f"{section_header}\n\n{content or ''}\n\n```puml\n{puml}\n```\n"
        elif content:
            section_content = f"{section_header}\n\n{content}\n"
        else:
            return CortexOUT.error(
                "section requires 'content' or 'puml' parameter",
                code="INVALID_ARGS",
            )

        # Replace from section header to next section or end
        def _replace_section(body: str, header: str, new_content: str) -> str:
            pattern = re.escape(header) + r".*?(?=\n## §\d+:|$)"
            repl = new_content.rstrip()
            result = re.sub(pattern, repl, body, count=1, flags=re.DOTALL)
            if result == body:
                return None
            return result

        new_body = _replace_section(body, section_header, section_content)
        if new_body is None:
            return CortexOUT.error(
                f"section {section} not found in blueprint",
                code="NOT_FOUND",
            )
        body = new_body

    if note:
        body += f"\n\n> [{_now_iso()}] {note}"

    if not section and not note:
        return CortexOUT.error("provide 'note', 'section', or both", code="INVALID_ARGS")

    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.update ok id={bp_id}",
        blueprint_id=bp_id,
        section=section,
        note=note,
    )


# ---------------------------------------------------------------------------
# blueprint.complete
# ---------------------------------------------------------------------------


def complete_blueprint(
    bp_id: str,
    evidence: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Declare execution complete. State → review."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_REVIEW)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    fm["status"] = BP_REVIEW
    fm["updated_at"] = _now_iso()
    fm["evidence"] = evidence or ""
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.complete ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_REVIEW,
        instruction="Auditor: cross-verify results against design. Call blueprint.approve() or blueprint.re_delegate().",
    )


# ---------------------------------------------------------------------------
# blueprint.fail
# ---------------------------------------------------------------------------


def fail_blueprint(
    bp_id: str,
    reason: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Blueprint hit an obstacle. State → blocked."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    fm["status"] = BP_BLOCKED
    fm["blocked_reason"] = reason
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.fail ok id={bp_id} reason={reason!r}",
        blueprint_id=bp_id,
        status=BP_BLOCKED,
        reason=reason,
        instruction="Governor evaluates: re-plan (blueprint.mature) or cancel.",
    )


# ---------------------------------------------------------------------------
# blueprint.approve
# ---------------------------------------------------------------------------


def approve_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Auditor approves Blueprint after cross-verification. State → done."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_DONE)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    fm["status"] = BP_DONE
    fm["closed_at"] = _now_iso()
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    # Record completion in brain
    _record_to_brain(root, bp_id, "done", fm.get("evidence", ""))

    return CortexOUT.work(
        f"blueprint.approve ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_DONE,
        instruction="Record lessons via identity.record(). Check if cycle can be closed.",
    )


# ---------------------------------------------------------------------------
# blueprint.cancel
# ---------------------------------------------------------------------------


def cancel_blueprint(
    bp_id: str,
    reason: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Cancel a Blueprint. State → cancelled. Governor-only."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")
    fm["status"] = BP_CANCELLED
    fm["cancelled_reason"] = reason or "cancelled"
    fm["closed_at"] = _now_iso()
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)
    _record_to_brain(root, bp_id, "cancelled", reason or "")
    return CortexOUT.work(
        f"blueprint.cancel ok id={bp_id}",
        blueprint_id=bp_id, status=BP_CANCELLED, reason=reason,
    )


# ---------------------------------------------------------------------------
# blueprint.re_delegate
# ---------------------------------------------------------------------------


def re_delegate_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Re-delegate after verification failure. Max 3 times."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") != BP_REVIEW:
        return CortexOUT.error(f"Blueprint is {fm.get('status')} — must be in review to re-delegate", code="INVALID_STATE")

    raw_loop = fm.get("verification_loop", 0)
    loop_count = int(raw_loop) if isinstance(raw_loop, str) else raw_loop
    if loop_count >= MAX_VERIFICATION_LOOPS:
        return CortexOUT.error(
            f"max re-delegation loops ({MAX_VERIFICATION_LOOPS}) reached. Call blueprint.block_for_architect().",
            code="MAX_LOOPS",
        )

    loop_count += 1
    fm["status"] = BP_IN_PROGRESS
    fm["verification_loop"] = loop_count
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.re_delegate ok id={bp_id} loop={loop_count}/{MAX_VERIFICATION_LOOPS}",
        blueprint_id=bp_id,
        verification_loop=loop_count,
        max_loops=MAX_VERIFICATION_LOOPS,
        instruction=f"Executor retries with deviation feedback. Loop {loop_count} of {MAX_VERIFICATION_LOOPS}.",
    )


# ---------------------------------------------------------------------------
# blueprint.block_for_architect
# ---------------------------------------------------------------------------


def block_for_architect(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Mark Blueprint for Architect manual review (3rd fail)."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    fm["status"] = BP_BLOCKED
    fm["blocked_reason"] = f"Verification failed {MAX_VERIFICATION_LOOPS} times — Architect manual review required"
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.block_for_architect ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_BLOCKED,
        instruction="Present to Architect: 'Blueprint failed verification 3 times. Your decision?'",
    )


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
        # Convert HCORTEX to CORTEX
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_blueprint(root: Path, bp_id: str) -> tuple[Path | None, dict[str, Any] | None, str | None]:
    """Find a Blueprint by ID across all cycles. Returns (path, fm, body)."""
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return None, None, None
    for cdir in cycles_base.iterdir():
        bp_path = cdir / BLUEPRINTS_DIR / f"{bp_id}.md"
        if bp_path.exists():
            result = _read_blueprint(bp_path)
            if result:
                return bp_path, result[0], result[1]
    return None, None, None


def _read_quality_gates(fm: dict[str, Any]) -> dict[str, bool] | None:
    """Extract quality gates from the Blueprint frontmatter.

    The frontmatter parser flattens multi-line YAML structures into individual
    keys. We check for the 6 expected gate keys directly.
    Returns dict of gate_name: bool, or None if no gates found.
    """
    gate_names = [
        "has_clear_objective",
        "has_verifiable_preconditions",
        "has_scope_and_exclusions",
        "has_acceptance_criteria",
        "has_work_procedure",
        "has_required_validations",
    ]
    gates = {}
    for name in gate_names:
        raw = fm.get(name)
        if raw is not None:
            if isinstance(raw, bool):
                gates[name] = raw
            elif isinstance(raw, str):
                gates[name] = raw.strip().rstrip(",").lower() == "true"
    return gates if len(gates) == len(gate_names) else None


def _record_to_brain(root: Path, bp_id: str, outcome: str, evidence: str) -> None:
    """Record Blueprint outcome in brain PULSE."""
    try:
        project_dir = root.parent
        fm, sections, _ = read_brain(project_dir)
        pulse = sections.get("PULSE", "").strip()
        entry = (
            f"- [{_now_iso()}] AUD:{bp_id}_{outcome}{{kind:\"blueprint\", "
            f"evidence:{evidence!r}}}"
        )
        sections["PULSE"] = (pulse + "\n" + entry).strip() if pulse else entry
        write_brain_sections(project_dir, fm, sections)
    except Exception:
        pass


def _prefill_from_context(body: str, root: Path, cycle_id: str) -> str:
    """Pre-fill the Blueprint template with context from brain.cortex and cycle manifest.

    This ensures the draft is immediately readable by the Architect, enabling
    the cyclic maturation interaction to begin immediately — no empty placeholder phase.
    """
    try:
        project_dir = root.parent
        fm, sections, _ = read_brain(project_dir)

        # Extract knowledge from brain
        focus = sections.get("FOCUS", "").strip()
        knowledge = sections.get("KNOWLEDGE", "").strip()
        lessons = sections.get("LESSONS", "").strip()
        risks_section = sections.get("RISKS", "").strip()

        # Pre-fill §1 Problem Statement with project focus
        if focus:
            focus_line = focus.splitlines()[0] if focus else focus
            placeholder = "_Describe the problem this Blueprint addresses. What evidence exists that it's real?_"
            body = body.replace(placeholder, f"Addresses project focus: {focus_line}\n\n_Describe the specific problem within this scope._")

        # Pre-fill §3 Preconditions with known dependencies from brain knowledge
        if knowledge:
            knw_lines = [l.strip() for l in knowledge.splitlines() if l.strip()][:3]
            pre = "_\n".join(f"- [ ] Dependency identified from project brain: {l}" for l in knw_lines)
            placeholder = "- [ ] _Precondition 1 — verifiable via command or inspection_"
            body = body.replace(placeholder, pre, 1)

        # Pre-fill §4 Guiding Principle with relevant lessons
        if lessons:
            relevant = [l.strip() for l in lessons.splitlines() if l.strip()][:1]
            if relevant:
                placeholder = "_The rule that governs this Blueprint. Executor must follow it without exception._"
                body = body.replace(placeholder, f"Based on project lesson: {relevant[0]}")

        # Pre-fill §15 Risks with known risks from brain
        if risks_section:
            risk_lines = [l.strip() for l in risks_section.splitlines() if l.strip()][:2]
            placeholder = "| R-01 | _Description_ | _Impact_ | _Mitigation_ |"
            if risk_lines:
                body = body.replace(placeholder, f"| R-01 | Inherited from project brain | {risk_lines[0][:60]} | Review |", 1)

    except Exception:
        pass

    # Pre-fill from cycle manifest
    try:
        cycle_mf = root / CYCLES_DIR / cycle_id / "MANIFEST.md"
        if cycle_mf.exists():
            mf_text = cycle_mf.read_text(encoding="utf-8")
            # Extract cycle objectives for §2
            obj_match = re.search(r"CYC-OBJ-\d+:\s*([^\n]+)", mf_text)
            if obj_match:
                placeholder = "_Concrete, verifiable, self-contained. An executor reading only this section should understand what to achieve._"
                body = body.replace(placeholder, f"Contributes to cycle objective: {obj_match.group(1)}\n\n_Describe the specific Blueprint objective._")

            # Extract cycle guidelines for §7 Mandatory Rules
            guide_match = re.findall(r"(\d+\.\s+_[^\n]+_)\s*—\s*([^\n]+)", mf_text)
            if guide_match and len(guide_match) >= 1:
                guideline_text = guide_match[0][1][:100] if guide_match[0][1] else ""
                if guideline_text:
                    placeholder = "1. _Rule 1"
                    body = body.replace(placeholder, f"1. From cycle guideline: {guideline_text}\n2. _Rule 2", 1)
    except Exception:
        pass

    return body
