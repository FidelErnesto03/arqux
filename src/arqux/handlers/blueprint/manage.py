"""Blueprint management handlers.

update, gate, task
"""

from __future__ import annotations

import re
from typing import Any

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext

from ._helpers import (
    BP_DONE,
    BP_IN_PROGRESS,
    BP_MATURING,
    BP_REVIEW,
    LEARNING_GATE,
    MATURATION_GATES,
    QUALITY_GATES,
    _find_blueprint,
    _has_learning_recorded,
    _learning_instruction,
    _now_iso,
    _record_bp_evidence,
    _resolve_root,
    _write_blueprint,
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
    assert body is not None  # _find_blueprint guarantees body on success

    fm["updated_at"] = _now_iso()

    # Section refinement takes priority over note
    if section:
        sec_input = section.lstrip("§").strip()

        # Build replacement content
        if puml:
            section_content = f"{content or ''}\n\n```puml\n{puml}\n```"
        elif content:
            section_content = content.strip()
        else:
            return CortexOUT.error(
                "section requires 'content' or 'puml' parameter",
                code="INVALID_ARGS",
            )

        # Resolve marker ID: accept "BLP:3" directly, or derive "3" → "BLP:3"
        if sec_input.startswith("BLP:"):
            marker_id = sec_input
            sec_num = sec_input.replace("BLP:", "")
        else:
            sec_num = sec_input
            marker_id = f"BLP:{sec_num}"

        # Validate marker against frontmatter map if available
        blp_markers_raw = fm.get("blp_markers@", "")
        if blp_markers_raw and isinstance(blp_markers_raw, str):
            known = [m.strip().strip('"') for m in blp_markers_raw.strip("[]").split(",") if m.strip()]
            if known and marker_id not in known:
                return CortexOUT.error(
                    f"marker {marker_id} not in blueprint marker map. Known: {known}",
                    code="NOT_FOUND",
                )

        # Marker-based replacement
        open_tag = f"<!-- {marker_id} -->"
        close_tag = f"<!-- /{marker_id} -->"
        marker_pattern = rf"{re.escape(open_tag)}.*?{re.escape(close_tag)}"

        marker_match = re.search(marker_pattern, body, re.DOTALL)
        if marker_match:
            # Preserve section header (## §N: Title) from existing content
            existing_block = marker_match.group(0)
            inner = existing_block[len(open_tag):-len(close_tag)].strip()
            header = ""
            for line in inner.split("\n"):
                if line.strip().startswith("## §"):
                    header = line.rstrip()
                    break
            if header and not section_content.strip().startswith("## §"):
                section_content = f"{header}\n\n{section_content}"
            marker_replacement = f"{open_tag}\n{section_content}\n{close_tag}"
            body = re.sub(
                marker_pattern,
                marker_replacement,
                body, count=1, flags=re.DOTALL,
            )
        else:
            # Fallback: legacy section-header-based replacement
            section_titles = {
                "1": "Problem Statement",
                "2": "Objective",
                "3": "Preconditions",
                "4": "Guiding Principle",
                "5": "Context",
                "6": "Scope & Exclusions",
                "7": "Mandatory Rules",
                "8": "Technical Design",
                "9": "Operational Design",
                "10": "Contracts",
                "11": "Work Procedure",
                "12": "Acceptance Criteria",
                "13": "Required Validations",
                "14": "Tasks",
                "15": "Risks",
                "16": "Blocking Rule",
                "17": "Expected Output",
                "18": "Quality Contract",
            }
            section_title = section_titles.get(sec_num, "")
            section_header = f"## §{sec_num}:"
            replacement_header = f"{section_header} {section_title}".rstrip()

            def _replace_section(body: str, header: str, new_content: str) -> str:
                pattern = (
                    re.escape(header)
                    + fr".*?(?=\n## §(?!{sec_num}\b)\d+:|\$)"
                )
                match = re.search(pattern, body, flags=re.DOTALL)
                if not match:
                    return None
                full = match.group(0)
                hdr_end = full.index("\n") if "\n" in full else len(full)
                hdr = full[:hdr_end]
                clean = new_content.strip()
                clean_lines = clean.split("\n")
                if clean_lines[0].strip().startswith("## §"):
                    clean = "\n".join(clean_lines[1:]).strip()
                result = body.replace(full, hdr + "\n" + clean + "\n", 1)
                if result == body:
                    return None
                return result

            section_content_full = f"{replacement_header}\n\n{section_content}\n"
            new_body = _replace_section(body, section_header, section_content_full)
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

    fields = {
        "blueprint_id": bp_id,
        "section": section,
        "note": note,
    }
    if section:
        fields["instruction"] = _learning_instruction(f"blueprint.update({bp_id}, section={section})")
    return CortexOUT.work(
        f"blueprint.update ok id={bp_id}",
        **fields,
    )


# ---------------------------------------------------------------------------
# blueprint.gate
# ---------------------------------------------------------------------------


def gate_blueprint(
    bp_id: str,
    gate: str = "all",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Approve one or all Blueprint quality gates after Architect maturation."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") != BP_MATURING:
        return CortexOUT.error(
            f"blueprint is {fm.get('status')} — must be maturing to approve gates",
            code="INVALID_STATE",
        )

    requested = MATURATION_GATES if gate == "all" else [gate]
    invalid = [name for name in requested if name not in QUALITY_GATES]
    if invalid:
        return CortexOUT.error(
            f"unknown quality gate(s): {', '.join(invalid)}",
            code="INVALID_ARGS",
            invalid_gates=invalid,
        )

    approved: list[str] = []
    blocked: list[str] = []
    for name in requested:
        if name == LEARNING_GATE and not _has_learning_recorded(root, bp_id):
            blocked.append(name)
            continue
        fm[name] = True
        approved.append(name)

    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    if blocked:
        return CortexOUT.error(
            "learning gate requires recorded learning evidence. Call identity.record() first.",
            code="LEARNING_NOT_RECORDED",
            approved_gates=approved,
            blocked_gates=blocked,
            instruction=_learning_instruction(f"blueprint.gate({bp_id}, {gate})"),
        )

    return CortexOUT.work(
        f"blueprint.gate ok id={bp_id} approved={len(approved)}",
        blueprint_id=bp_id,
        approved_gates=approved,
        status=fm.get("status"),
        instruction="Call blueprint.ready() when all required maturation gates are approved.",
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

    # Record evidence in brain PULSE
    _record_bp_evidence(root, bp_id, "blueprint.task",
                        f"task {task_id} marked as {status}{' — ' + evidence if evidence else ''}",
                        task_id=task_id, ctx=ctx)

    fields = {
        "blueprint_id": bp_id,
        "task_id": task_id,
        "status": status,
    }
    if status == "completed":
        fields["instruction"] = _learning_instruction(f"blueprint.task({bp_id}, {task_id})")
    return CortexOUT.work(
        f"blueprint.task ok id={bp_id} task={task_id} status={status}",
        **fields,
    )
