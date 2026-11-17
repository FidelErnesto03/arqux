"""Contextual elevation logic — native, governed implementation (BLP-004)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX
from ._common import (
    _build_brain_doc,
    _hash_text,
    _load_policies,
    _resolve_project_root,
    learning_engine_available,
)
from .algorithms import detect_candidates, plan_patch, render_diff
from .sections import section_for_sigil, section_title


def _preview_hash(diff: str) -> str:
    """Stable approval token for an exact learning elevation preview."""
    return _hash_text(diff)


def _brain_path(project_root: Path) -> Path:
    # project_root may be workspace/project root or .arqux dir.
    if (project_root / BRAIN_CORTEX).is_file() and project_root.name == ARQUX_DIR:
        return project_root / BRAIN_CORTEX
    if (project_root / ARQUX_DIR / BRAIN_CORTEX).is_file():
        return project_root / ARQUX_DIR / BRAIN_CORTEX
    return project_root / BRAIN_CORTEX


def _planned_entry(target: Any) -> tuple[str, str, dict[str, Any]]:
    new_sigil = getattr(target, "target", "KNW")
    new_name = getattr(target, "candidate_id", "elevated")
    new_value = {
        "topic": "elevated_knowledge",
        "content": str(getattr(target, "source_entries", [])),
        "status": "active",
    }
    return new_sigil, new_name, new_value


def _validate_elevation_payload(
    new_sigil: str,
    new_value: dict[str, Any],
    diff: str,
) -> list[str]:
    problems: list[str] = []
    serialized_values = [str(v).strip() for v in new_value.values()]
    if any(v in {"", "[]", "{}", "None"} for v in serialized_values):
        problems.append("proposed elevation contains empty fields")
    generic_markers = [
        "elevated_outcome",
        'input:""',
        'output:""',
        'date:""',
        'input=""',
        'output=""',
        'date=""',
    ]
    if any(marker in diff for marker in generic_markers):
        problems.append("proposed elevation contains generic or placeholder content")
    if new_sigil not in {"SES", "LNG", "KNW", "CNST", "STP"}:
        problems.append(f"unexpected elevation target: {new_sigil}")
    boilerplate = {"active", "pending", "follow_policy", "not_applicable", "not_specified"}
    for key, val in new_value.items():
        v = str(val).strip()
        if v.lower() in boilerplate:
            problems.append(f"boilerplate value in {key}: {v!r} — elevation refused")
    return problems


def _quote_cortex_val(val: Any) -> str:
    from ...formats import _escape_attr_string
    s = str(val)
    if any(c in s for c in (" ", ",", '"', "'", "{", "}", "\n", "\r", "\t")):
        return '"' + _escape_attr_string(s) + '"'
    return s


def _format_attrs(value: dict[str, Any]) -> str:
    return "{" + ", ".join(f"{k}:{_quote_cortex_val(v)}" for k, v in value.items()) + "}"


def _apply_patch_governed(brain_file: Path, section_id: str, sigil: str, name: str, value: dict[str, Any]) -> dict[str, Any]:
    from ...cortex.atomic import atomic_write_text
    from ...cortex.reader import cortex_to_dict
    from ...cortex.transaction import guard_write
    from ...cortex.writer import write_cortex_from_json

    before_text = brain_file.read_text(encoding="utf-8")
    doc = cortex_to_dict(before_text)
    sections = doc.setdefault("sections", [])
    target = None
    for sec in sections:
        if str(sec.get("id")) == str(section_id):
            target = sec
            break
    if target is None:
        target = {"id": str(section_id), "title": section_title(section_id) or "", "entries": [], "comments": []}
        sections.append(target)
    target.setdefault("entries", [])

    # Idempotent replace if same sigil:name exists in target section.
    entry = {"sigil": sigil, "name": name, "attrs": dict(value)}
    replaced = False
    for i, existing in enumerate(target.get("entries") or []):
        if isinstance(existing, dict) and existing.get("sigil") == sigil and existing.get("name") == name:
            target["entries"][i] = entry
            replaced = True
            break
    if not replaced:
        target["entries"].append(entry)

    after_text = write_cortex_from_json(doc)
    result = atomic_write_text(after_text, str(brain_file))
    violation = guard_write(str(brain_file), before_text, allowed_sections=[str(section_id)])
    if violation:
        return {"error": violation.get("error", "transaction guard rejected write"), **violation}
    return {"ok": True, "bytes_written": getattr(result, "bytes_written", None), "section": str(section_id)}


def elevate_candidate(
    project_root: Path,
    candidate_id: str,
    *,
    dry_run: bool = True,
    confirm_hash: str | None = None,
) -> dict[str, Any]:
    """Elevate a candidate (SES→LNG or LNG→KNW, governed).

    When ``dry_run=True`` (default), returns the diff without applying.
    When ``dry_run=False``, applies only with a valid ``confirm_hash`` and
    through governed write (writer+atomic+transaction guard).
    """
    ok, cause = learning_engine_available()
    if not ok:
        return {"error": "learning engine unavailable", "cause": cause or "unknown"}

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {"error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        candidates = detect_candidates(brain_doc)

        target = None
        for c in candidates:
            if getattr(c, "candidate_id", None) == candidate_id:
                target = c
                break
        if target is None:
            return {"error": f"candidate {candidate_id!r} not found"}

        patch = plan_patch(brain_doc, policy_set, target)
        if getattr(patch, "mode", "") == "block":
            return {"error": f"elevation blocked: {getattr(patch, 'reason', 'blocked')}"}

        diff = render_diff(brain_doc, patch)
        preview_hash = _preview_hash(diff)

        new_sigil = patch.new_entry_sigil or getattr(target, "target", "KNW")
        new_name = patch.new_entry_name
        new_value = patch.new_entry_value
        if not new_name or not new_value:
            fallback_sigil, fallback_name, fallback_value = _planned_entry(target)
            new_sigil = new_sigil or fallback_sigil
            new_name = new_name or fallback_name
            new_value = new_value or fallback_value

        validation_errors = _validate_elevation_payload(new_sigil, new_value, diff)

        if dry_run:
            return {
                "mode": "dry_run",
                "diff": diff,
                "candidate": candidate_id,
                "preview_hash": preview_hash,
                "validation_errors": validation_errors,
            }

        if confirm_hash != preview_hash:
            return {
                "error": (
                    "preview approval required before applying elevation. "
                    "Run dry-run, review the exact diff, then pass confirm_hash."
                ),
                "preview_hash": preview_hash,
                "diff": diff,
            }

        if validation_errors:
            return {
                "error": "unsafe elevation blocked: " + "; ".join(validation_errors),
                "preview_hash": preview_hash,
                "diff": diff,
            }

        root = _resolve_project_root(str(project_root)) or Path(project_root)
        brain_file = _brain_path(root)
        section = section_for_sigil(new_sigil, brain_doc) or patch.target_section
        applied = _apply_patch_governed(brain_file, section, new_sigil, new_name, new_value)
        if "error" in applied:
            return {"error": f"elevation write failed: {applied['error']}", "preview_hash": preview_hash, "diff": diff, **{k:v for k,v in applied.items() if k!='error'}}

        return {"mode": "applied", "diff": diff, "candidate": candidate_id, "preview_hash": preview_hash, "section": section}

    except Exception as exc:
        return {"error": str(exc)}


__all__ = ["elevate_candidate"]
