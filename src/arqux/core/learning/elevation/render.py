"""Render elevation diffs (governed, deterministic)."""
from __future__ import annotations

from ..protocol import LearningDocument
from .patch import Patch


def normalize_section_id(section_id: str) -> str:
    s = str(section_id or "").strip()
    return s if s.startswith("$") else f"${s}" if s else ""


def render_diff(document: LearningDocument, patch: Patch) -> str:
    """Render a human-readable diff for a proposed patch."""
    new_value = patch.new_entry_value or {}
    serialized = ", ".join(f'{k}:"{str(v)}"' for k, v in new_value.items())
    lines = [
        f"# Patch mode: {patch.mode}",
        f"# Reason: {patch.reason}",
    ]
    if patch.policy_id:
        lines.append(f"# Policy: {patch.policy_id}")
    lines.append(f"# Promotion score: {patch.promotion_score}")
    if patch.source_entries:
        lines.append(f"# Source entries: {', '.join(patch.source_entries)}")
    lines.append(f"# Affected files: {', '.join(patch.affected_files)}")
    lines.append("")
    affected = patch.affected_files[0] if patch.affected_files else ".arqux/brain.cortex"
    lines.append(f"--- {affected} (current)")
    lines.append(f"+++ {affected} (proposed)")
    lines.append(f"@@ {normalize_section_id(patch.target_section)} @@")
    lines.append(f"+{patch.new_entry_sigil}:{patch.new_entry_name}{{{serialized}}}")
    return "\n".join(lines)


__all__ = ["normalize_section_id", "render_diff"]
