"""Single source of truth for learning elevation target sections.

Resolution strategy (vigente, BLP-004): prefer the section that already exists in
the target brain for the canonical learning title, falling back to
``BrainSection``/``BRAIN_SECTION_TITLES`` constants. This preserves real/project
brains (where section numbering can drift from the template) while keeping one
resolver for all elevation paths.
"""
from __future__ import annotations

from typing import Any

from ...constants import BRAIN_SECTION_TITLES, BrainSection

# Canonical learning targets by meaning/title.
# Canon: docs/reference/cortex-brain-section-canon.md §4 (sigil → section).
_TITLE_FOR_SIGIL: dict[str, str] = {
    "AXM": "AXIOMS",
    "SES": "SESSIONS",
    "LNG": "LESSONS",
    "KNW": "KNOWLEDGE",
    "CNST": "RISKS",
    "RSK": "RISKS",
    "PFL": "RISKS",
    "STP": "ACTIVE_CONTEXT",
    "NXT": "ACTIVE_CONTEXT",
    "WRK": "ACTIVE_CONTEXT",
}

_ID_FOR_SIGIL: dict[str, str] = {
    "AXM": BrainSection.AXIOMS.value,
    "SES": BrainSection.SESSIONS.value,
    "LNG": BrainSection.LESSONS.value,
    "KNW": BrainSection.KNOWLEDGE.value,
    "CNST": BrainSection.RISKS.value,
    "RSK": BrainSection.RISKS.value,
    "PFL": BrainSection.RISKS.value,
    "STP": BrainSection.ACTIVE_CONTEXT.value,
    "NXT": BrainSection.ACTIVE_CONTEXT.value,
    "WRK": BrainSection.ACTIVE_CONTEXT.value,
}


def _normalize_id(sid: Any) -> str:
    s = str(sid or "").strip()
    if not s:
        return ""
    return s if s.startswith("$") else f"${s}"


def _doc_section_ids_by_title(document: Any) -> dict[str, str]:
    """Map uppercased section title -> section id from a learning document."""
    out: dict[str, str] = {}
    if document is None:
        return out
    # NativeLearningDocument exposes ._doc; be tolerant.
    raw = getattr(document, "_doc", None) or {}
    for sec in (raw.get("sections") or []):
        if not isinstance(sec, dict):
            continue
        sid = _normalize_id(sec.get("id"))
        title = str(sec.get("title") or "").strip().upper()
        if sid and title:
            out[title] = sid
    return out


def section_for_sigil(sigil: str, document: Any = None) -> str | None:
    """Return canonical target section id (e.g. "$6"/"$7") for *sigil*.

    If *document* is provided, prefer the section id present in that document
    whose title matches the canonical learning target (vigente). Otherwise fall
    back to ``BrainSection`` constants.
    """
    key = str(sigil or "").upper()
    title = _TITLE_FOR_SIGIL.get(key)
    if not title:
        return None
    if document is not None:
        by_title = _doc_section_ids_by_title(document)
        if title in by_title:
            return by_title[title]
    return _ID_FOR_SIGIL.get(key)


def section_title(section_id: str) -> str | None:
    """Return canonical/vigente title for a section id, if known."""
    sid = _normalize_id(section_id)
    title = BRAIN_SECTION_TITLES.get(sid)
    if title:
        return title
    return None


__all__ = ["section_for_sigil", "section_title"]
