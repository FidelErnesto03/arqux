"""Contextual elevation logic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX
from ._common import (
    _HAS_CLE,
    _build_brain_doc,
    _hash_text,
    _load_policies,
    _resolve_policy_path,
    _resolve_project_root,
    detect_candidates,
    plan_patch,
    rebuild_index,
    render_diff,
)


def _preview_hash(diff: str) -> str:
    """Stable approval token for an exact learning elevation preview."""
    return _hash_text(diff)


def _planned_entry(target: Any) -> tuple[str, str, dict[str, Any]]:
    """Return the entry that would be written for a learning candidate."""
    new_sigil = target.target
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
    """Return blocking problems in a proposed learning elevation."""
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
    if new_sigil not in {"SES", "LNG", "KNW"}:
        problems.append(f"unexpected elevation target: {new_sigil}")
    return problems


def elevate_candidate(
    project_root: Path,
    candidate_id: str,
    *,
    dry_run: bool = True,
    confirm_hash: str | None = None,
) -> dict[str, Any]:
    """Elevate a candidate (SES→LNG or LNG→KNW).

    When ``dry_run=True`` (default), returns the diff without applying.
    When ``dry_run=False``, applies the elevation to brain.cortex.
    """
    if not _HAS_CLE:
        return {"error": "learning engine unavailable"}

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {"error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if not policy_set:
            return {"error": "policies_not_found"}

        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(brain_doc, policy_set, brain_hash, policy_hash)
        candidates = detect_candidates(brain_doc, index, policy_set)

        target = None
        for c in candidates:
            if c.candidate_id == candidate_id:
                target = c
                break
        if target is None:
            return {"error": f"candidate {candidate_id!r} not found"}

        patch = plan_patch(brain_doc, policy_set, target)
        if patch.mode == "block":
            return {"error": f"elevation blocked by policy: {patch.block_reason}"}

        diff = render_diff(brain_doc, patch)
        preview_hash = _preview_hash(diff)

        new_sigil = patch.new_entry_sigil or target.target
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

        from ...state import read_brain, write_brain_sections
        from ...formats import _build_brain_doc as _build_doc

        fm, sections, _ = read_brain(project_root)
        knw_line = f"{new_sigil}:{new_name} " + " ".join(f'{k}="{v}"' for k, v in new_value.items())
        existing = sections.get("KNOWLEDGE", "").strip()
        if existing:
            sections["KNOWLEDGE"] = existing + "\n" + knw_line
        else:
            sections["KNOWLEDGE"] = knw_line
        write_brain_sections(project_root, fm, sections)

        return {"mode": "applied", "diff": diff, "candidate": candidate_id, "preview_hash": preview_hash}

    except Exception as exc:
        return {"error": str(exc)}
