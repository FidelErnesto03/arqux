"""Blueprint management handlers.

Simplified: update, task
"""

from __future__ import annotations

import re

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...sync import _read_gate_table
from ._helpers import (
    BP_DONE,
    BP_IN_PROGRESS,
    QUALITY_GATES,
    _effective_status,
    _find_blueprint,
    _now_iso,
    _record_bp_evidence,
    _resolve_root,
    _section,
    _write_blueprint,
)
from ._read import _body_title


def _markers_balanced(body: str) -> bool:
    """True when every ``<!-- BLP:N -->`` opener has a matching closer (BLP-014)."""
    opens = len(re.findall(r"<!--\s*BLP:[\w.]+\s*-->", body))
    closes = len(re.findall(r"<!--\s*/BLP:[\w.]+\s*-->", body))
    return opens == closes


# Any BLP marker (opener or closer), tolerant to whitespace, extra dashes and a
# space before the colon (BLP-014, N13).
_BLP_MARKER_RE = re.compile(r"<!-+\s*/?\s*BLP\s*:", re.IGNORECASE)
# Opener markers only, for the marker-set invariant.
_BLP_OPEN_RE = re.compile(r"<!--\s*BLP:[\w.]+\s*-->")
# Any markdown header carrying a § section marker (`##§`, `#  §`, ZWSP, ...).
_MD_SECTION_RE = re.compile(r"#{1,6}[^\S\n]*[\u200b-\u200f\u2060\ufeff]*[^\S\n]*§")

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
    cycle: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update Blueprint progress (note) or refine a single section."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id, cycle=cycle)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")
    assert body is not None  # _find_blueprint guarantees body on success

    fm["updated_at"] = _now_iso()
    markers_before = frozenset(re.findall(_BLP_OPEN_RE, body))

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

        # BLP-014: the handler owns the markers and section headers. Reject any
        # BLP marker (opener/closer) and any '## §' header except a single
        # leading one whose number matches the target section.
        if _BLP_MARKER_RE.search(section_content):
            return CortexOUT.error(
                "section content must not contain '<!-- BLP' markers "
                "(blueprint.update manages them)",
                code="INVALID_ARGS",
            )
        md_headers = _MD_SECTION_RE.findall(section_content)
        if md_headers:
            # Only the exact canonical leading ``## §N:`` (the form the Updater
            # recognises) whose N matches the target section is allowed.
            expected = f"## §{sec_num}:"
            if not (len(md_headers) == 1 and section_content.startswith(expected)):
                return CortexOUT.error(
                    "section content may contain at most one leading '## §N:' header "
                    "whose N matches the target section",
                    code="INVALID_ARGS",
                )

        # Validate marker against frontmatter map if available
        blp_markers_raw = fm.get("blp_markers@", "")
        if blp_markers_raw and isinstance(blp_markers_raw, str):
            known = [m.strip().strip('"') for m in blp_markers_raw.strip("[]").split(",") if m.strip()]
            if known and marker_id not in known:
                return CortexOUT.error(
                    f"marker {marker_id} not in blueprint marker map. Known: {known}",
                    code="NOT_FOUND",
                )

        # BLP-014: locate the section strictly by the marker pair — never by the
        # header text. The old header fallback swept to the next '## §M:' and
        # ate markers (silent corruption, N12), and also triggered on an
        # idempotent re-send (Updater no-op).
        open_tag = f"<!-- BLP:{sec_num} -->"
        close_tag = f"<!-- /BLP:{sec_num} -->"
        if open_tag not in body or close_tag not in body:
            return CortexOUT.error(
                f"section {section} not found via marker pair "
                f"({open_tag} ... {close_tag})",
                code="NOT_FOUND",
            )
        from ...core.updater import Updater
        body = Updater("BLP").replace(body, sec_num, section_content)

    if note:
        # BLP-014: the note path is a second write surface — same guards.
        if _BLP_MARKER_RE.search(note) or _MD_SECTION_RE.search(note):
            return CortexOUT.error(
                "note must not contain '<!-- BLP' markers or '## §' headers "
                "(blueprint.update manages them)",
                code="INVALID_ARGS",
            )
        body += f"\n\n> [{_now_iso()}] {note}"

    if not section and not note:
        return CortexOUT.error("provide 'note', 'section', or both", code="INVALID_ARGS")

    # BLP-003: keep quality_gates@ in sync with §18 on every update.
    for gate_key, gate_val in _read_gate_table(_section(body, 18), QUALITY_GATES).items():
        fm[gate_key] = gate_val
    fm.pop("quality_gates", None)
    fm.pop("quality_gates@", None)

    # BLP-014: never persist a mutated marker structure. Parity alone is not
    # enough — a corruption can drop an opener AND a closer (N12).
    markers_after = frozenset(re.findall(_BLP_OPEN_RE, body))
    if markers_after != markers_before or not _markers_balanced(body):
        return CortexOUT.error(
            "refusing to write: the set of <!-- BLP:N --> markers changed or is "
            "unbalanced after the update",
            code="VALIDATION",
            markers_expected=sorted(markers_before),
            markers_after=sorted(markers_after),
        )

    _write_blueprint(bp_path, fm, body)

    fields = {
        "blueprint_id": bp_id,
        "section": section,
        "note": note,
    }
    if section:
        fields["instruction"] = "Record learning via identity.record()"
    return CortexOUT.work(
        f"blueprint.update ok id={bp_id}",
        **fields,
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

    if _effective_status(fm) not in (BP_IN_PROGRESS, BP_DONE):
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
        fields["instruction"] = "Record learning: identity.record()"
    return CortexOUT.work(
        f"blueprint.task ok id={bp_id} task={task_id} status={status}",
        **fields,
    )


# ---------------------------------------------------------------------------
# blueprint.frontmatter.update (BLP-003 measure #2)
# ---------------------------------------------------------------------------


def update_frontmatter(
    bp_id: str,
    *,
    title: str | None = None,
    cycle: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Set/repair frontmatter scalars (``title``, ``cycle``).

    Provides the sanctioned write path for the two fields no other handler
    can set on an existing Blueprint. When ``title`` is omitted and the
    frontmatter title is empty, it is derived from the body (``BLP:TITLE``
    marker or ``# BLP-NNN:`` heading).
    """
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    changed: list[str] = []
    if title is not None:
        fm["title"] = title.strip()
        changed.append("title")
    if cycle is not None:
        fm["cycle"] = cycle.strip()
        changed.append("cycle")

    if not str(fm.get("title", "")).strip():
        derived = _body_title(body or "")
        if derived:
            fm["title"] = derived
            changed.append("title<-body")

    if not changed:
        return CortexOUT.error(
            "provide 'title' and/or 'cycle' (or a body title to derive)",
            code="INVALID_ARGS",
        )

    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    return CortexOUT.work(
        f"blueprint.frontmatter.update ok id={bp_id}",
        blueprint_id=bp_id,
        title=fm.get("title", ""),
        cycle=fm.get("cycle", ""),
        updated=sorted(changed),
    )
