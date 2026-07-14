"""Blueprint helpers and constants.

Private helpers, shared constants, and the read-only handler functions
(``read_blueprint``, ``list_blueprints``).
"""

from __future__ import annotations

import re
import time as _time
from pathlib import Path
from typing import Any

from ...constants import (
    ARQUX_DIR,
    BLUEPRINTS_DIR,
    CYCLES_DIR,
)
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root, read_brain

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLUEPRINT_TEMPLATE = "BLP_TEMPLATE.md"
MAX_VERIFICATION_LOOPS = 3
LEARNING_GATE = "has_learning_recorded"
QUALITY_GATES = [
    "has_clear_objective",
    "has_verifiable_preconditions",
    "has_scope_and_exclusions",
    "has_acceptance_criteria",
    "has_work_procedure",
    "has_required_validations",
    LEARNING_GATE,
]
MATURATION_GATES = [gate for gate in QUALITY_GATES if gate != LEARNING_GATE]

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


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _learning_instruction(action: str) -> str:
    return (
        f"Record learning for {action}: call identity.record("
        "lesson='<what changed or failed>', kind='process', "
        "cause='<blueprint evidence>') before closing this governance step."
    )


def _now_iso() -> str:
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())


def _resolve_root(path: str | None = None) -> Path | None:
    """Find the .arqux/ root. Returns .arqux/ path."""
    return find_project_root(start=path)


def _blueprints_dir(root: Path, cycle_id: str) -> Path:
    """Return blueprints/ directory for a cycle."""
    return root / CYCLES_DIR / cycle_id / BLUEPRINTS_DIR


def next_blueprint_id_safe(bp_dir: Path) -> str:
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
        return f"invalid transition: {from_state} \u2192 {to_state}"
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


def _find_workspace_template(root: Path, template_name: str) -> Path | None:
    """Walk up from root to find .arqux/templates/<template_name>."""
    cursor = root
    while True:
        tmpl = cursor / ARQUX_DIR / "templates" / template_name
        if tmpl.exists():
            return tmpl
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


def scan_markers(text: str) -> list[str]:
    """Scan text for all ``<!-- BLP:ID -->`` markers and return their IDs.

    Discards closing markers (``<!-- /BLP:ID -->``). Returns IDs in order
    of appearance, e.g. ``[\"BLP:TITLE\", \"BLP:1\", \"BLP:2\", ...]``.
    """
    import re
    return re.findall(r"<!-- (BLP:[\w.]+) -->", text)


# ---------------------------------------------------------------------------
# Blueprint helpers
# ---------------------------------------------------------------------------


def _find_blueprint(root: Path, bp_id: str, *, path_hint: str | None = None) -> tuple[Path | None, dict[str, Any] | None, str | None]:
    """Find a Blueprint by ID. Respects path_hint (explicit path) first,
    then active cycle, then falls back to global search.

    Returns (path, fm, body).
    """
    cycles_base = root / CYCLES_DIR
    if not cycles_base.exists():
        return None, None, None

    # 1. Explicit path hint
    if path_hint:
        bp_path = _resolve_blueprint_path(root, bp_id, path_hint=path_hint)
        if bp_path and bp_path.exists():
            result = _read_blueprint(bp_path)
            if result:
                return bp_path, result[0], result[1]
        return None, None, None

    # 2. Active cycle
    from ...state import crud_read
    try:
        brain_path = root / ".arqux" / "brain.cortex"
        if brain_path.exists():
            cur = crud_read(brain_path, "$1/FCS:current")
            fcs = cur.get("entries", [{}])[0].get("value", {}) if cur.get("entries") else {}
            active_cycle = fcs.get("cycle", "")
            if active_cycle:
                bp_path = cycles_base / active_cycle / BLUEPRINTS_DIR / f"{bp_id}.md"
                if bp_path.exists():
                    result = _read_blueprint(bp_path)
                    if result:
                        return bp_path, result[0], result[1]
    except Exception:
        pass

    # 3. Fallback: global search
    for cdir in sorted(cycles_base.iterdir()):
        bp_path = cdir / BLUEPRINTS_DIR / f"{bp_id}.md"
        if bp_path.exists():
            result = _read_blueprint(bp_path)
            if result:
                return bp_path, result[0], result[1]
    return None, None, None


def _resolve_blueprint_path(root: Path, bp_id: str, *, path_hint: str | None = None) -> Path | None:
    """Resolve a blueprint path, scoped by path_hint if provided.

    If path_hint is a directory, searches that directory for the blueprint.
    If path_hint is a cycle directory, searches its blueprints/ subdirectory.
    """
    if not path_hint:
        return None
    hint = Path(path_hint)
    if not hint.is_absolute():
        hint = root / hint
    # Direct path to the file
    direct = hint if hint.suffix == ".md" else hint / f"{bp_id}.md"
    if direct.exists():
        return direct
    # hint is a cycle directory
    bp_sub = hint / BLUEPRINTS_DIR / f"{bp_id}.md"
    if bp_sub.exists():
        return bp_sub
    return None


def _read_quality_gates(fm: dict[str, Any]) -> dict[str, bool] | None:
    """Extract quality gates from the Blueprint frontmatter.

    The frontmatter parser flattens multi-line YAML structures into individual
    keys. We check for the expected gate keys directly. If legacy Blueprints
    have the original 6 gates but no learning gate, the learning gate defaults
    to false so they must pass through the new learning contract before ready
    or approve.
    Returns dict of gate_name: bool, or None if no gates found.
    """
    gates = {}
    for name in QUALITY_GATES:
        raw = fm.get(name)
        if raw is not None:
            if isinstance(raw, bool):
                gates[name] = raw
            elif isinstance(raw, str):
                gates[name] = raw.strip().rstrip(",").lower() == "true"
    if not gates:
        return None
    if len(gates) == len(QUALITY_GATES) - 1 and LEARNING_GATE not in gates:
        gates[LEARNING_GATE] = False
    return gates if len(gates) == len(QUALITY_GATES) else None


def _section(body: str, number: int) -> str:
    match = re.search(rf"## \xdf{number}:.*?(?=\n## \xdf\d+:|$)", body, flags=re.DOTALL)
    return match.group(0) if match else ""


def _unchecked_items(body: str, section_number: int, prefix: str) -> list[str]:
    section = _section(body, section_number)
    items: list[str] = []
    pattern = re.compile(rf"^- \[([ ~x])\] \*\*({prefix}-\d+(?:\.\d+)?):\*\* (.+)$", re.MULTILINE)
    for marker, item_id, title in pattern.findall(section):
        if marker != "x":
            items.append(f"{item_id}: {title.strip()}")
    return items


def _has_required_validation_rows(body: str) -> bool:
    section = _section(body, 13)
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("|")
        and "---" not in line
        and "Tipo" not in line
        and "Type" not in line
        and "_Description_" not in line
    ]
    return bool(rows)


def _missing_required_artifacts(body: str, project_root: Path) -> list[str]:
    section = _section(body, 17)
    missing: list[str] = []
    in_files = False
    for raw_line in section.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if lower.startswith("archivos modificados") or lower.startswith("files modified"):
            in_files = True
            continue
        if in_files and not line:
            continue
        if in_files and not line.startswith("- "):
            break
        if not in_files or not line.startswith("- "):
            continue
        candidate = line[2:].strip()
        if " " in candidate or not any(sep in candidate for sep in ("/", ".")):
            continue
        if not (project_root / candidate).exists():
            missing.append(candidate)
    return missing


def _validate_execution_complete(body: str, evidence: str | None) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    pending_tasks = _unchecked_items(body, 14, "T")
    if pending_tasks:
        errors["missing_tasks"] = pending_tasks
    if _has_required_validation_rows(body) and not evidence:
        errors["missing_validations"] = ["completion evidence is required for declared validations"]
    return errors


def _validate_approval_ready(root: Path, bp_id: str, fm: dict[str, Any], body: str) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    missing_ac = _unchecked_items(body, 12, "AC")
    if missing_ac:
        errors["missing_acceptance_criteria"] = missing_ac
    missing_artifacts = _missing_required_artifacts(body, root.parent)
    if missing_artifacts:
        errors["missing_artifacts"] = missing_artifacts
    if not _has_learning_recorded(root, bp_id):
        errors["missing_learning"] = ["record learning with identity.record before approval"]
    if _has_required_validation_rows(body) and not fm.get("evidence"):
        errors["missing_validations"] = ["review evidence is required for declared validations"]
    return errors


def _has_learning_recorded(root: Path, bp_id: str) -> bool:
    """Return true when any workspace/project identity has an LNG for bp_id."""
    identity_dirs = [
        root / "identities",
        root.parent / ARQUX_DIR / "identities",
        root.parent.parent / ARQUX_DIR / "identities",
    ]
    needles = {bp_id.lower(), bp_id.lower().replace("-", "_")}
    for identity_dir in identity_dirs:
        if not identity_dir.exists():
            continue
        for identity_file in identity_dir.glob("*.cortex"):
            try:
                text = identity_file.read_text(encoding="utf-8").lower()
            except OSError:
                continue
            if "lng:" in text and any(needle in text for needle in needles):
                return True
    return False


def _record_to_brain(root: Path, bp_id: str, outcome: str, evidence: str) -> None:
    """Record Blueprint outcome in brain PULSE using CODEC-CORTEX (BLP-042)."""
    try:
        brain_path = root / ".arqux" / "brain.cortex"
        if not brain_path.exists():
            return

        from cortex.core.parser import parse_cortex
        from ..state import crud_add

        text = brain_path.read_text(encoding="utf-8")
        doc = parse_cortex(text)

        # Find PULSE section (usually $11 or latest section).
        pulse_sec = None
        for sec in doc.sections:
            if "PULSE" in sec.title.upper() or sec.id == "$11":
                pulse_sec = sec
                break
        if pulse_sec is None:
            return

        # Append the AUD entry via CODEC-CORTEX (single-line attrs, no
        # direct file write).
        esc_evidence = evidence.replace('"', '\\"')
        result = crud_add(
            brain_path,
            pulse_sec.id,
            "AUD",
            f"{bp_id}_{outcome}",
            f'kind:"blueprint", evidence:"{esc_evidence}", date:"{_now_iso()}"',
            create_section=False,
        )
        if "error" in result:
            return
    except Exception:
        pass


def _record_bp_evidence(
    root: Path,
    bp_id: str,
    handler: str,
    payload: str,
    *,
    task_id: str | None = None,
    ctx: PermissionContext | None = None,
) -> str | None:
    """Record a blueprint lifecycle event as evidence in brain PULSE.

    Uses append_pulse_to_brain() for consistent formatting with evidence.record handler.
    Returns the event_id if successful, None on failure.
    """
    try:
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id=task_id or bp_id,
            kind="blueprint_lifecycle",
            agent=agent,
            payload=f"[{handler}] {payload}",
        )
        return event_id
    except Exception:
        return None


def _prefill_from_context(body: str, root: Path, cycle_id: str) -> str:
    """Pre-fill the Blueprint template with context from brain.cortex and cycle manifest.

    This ensures the draft is immediately readable by the Architect, enabling
    the cyclic maturation interaction to begin immediately — no empty placeholder phase.
    """
    try:
        fm, sections, _ = read_brain(root)

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
