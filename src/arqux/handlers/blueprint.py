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

    bp_path = bp_dir / f"{bp_id}.md"
    bp_path.write_text(body, encoding="utf-8")

    return CortexOUT.work(
        f"blueprint.create ok id={bp_id} cycle={cycle_id}",
        blueprint_id=bp_id,
        cycle=cycle_id,
        status=BP_DRAFT,
        path=str(bp_path),
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

    # Write body with filled sections
    sections = {}
    if pre:
        sections["preconditions"] = "\n".join(f"- [ ] {p}" for p in pre)
    if scope:
        sections["scope"] = scope
    if exclusions:
        sections["exclusions"] = exclusions
    if mandatory_rules:
        sections["mandatory_rules"] = "\n".join(f"1. {r}" for r in mandatory_rules)
    if acceptance_criteria:
        sections["acceptance_criteria"] = "\n".join(f"- [ ] **AC-{i+1:02d}:** {ac}" for i, ac in enumerate(acceptance_criteria))
    if procedure:
        sections["procedure"] = procedure
    if validations:
        sections["validations"] = "\n".join(
            f"| {v.get('type', 'test')} | {v.get('desc', '')} | `{v.get('cmd', '')}` | {v.get('expected', '')} |"
            for v in validations
        )
    if technical_design:
        sections["technical_design"] = technical_design
    if operational_design:
        sections["operational_design"] = operational_design
    if risks:
        sections["risks"] = "\n".join(risks)
    if blocking_rule:
        sections["blocking_rule"] = blocking_rule

    _write_blueprint(bp_path, fm, body)

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
# blueprint.update
# ---------------------------------------------------------------------------


def update_blueprint(
    bp_id: str,
    note: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update Blueprint progress."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    fm["updated_at"] = _now_iso()
    body += f"\n\n> [{_now_iso()}] {note}"
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.update ok id={bp_id}",
        blueprint_id=bp_id,
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

    loop_count = fm.get("verification_loop", 0)
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
