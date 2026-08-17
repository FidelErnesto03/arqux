"""BLP-002: ArqUX's own CRUD operations over the JSON/dict CORTEX model.

This module replaces CODEC-CORTEX's ``mutations`` and ``selectors`` modules
with pure-Python operations that work on the same JSON/dict document model
introduced by :mod:`arqux.cortex.writer` (BLP-001).

No dependency on CODEC-CORTEX (``cortex.core`` or ``codec_cortex``).

JSON model (see :mod:`arqux.cortex.writer`)::

    {
        "glossary": {"header": "$0", "comments": [...], "symbols": [...]},
        "sections": [
            {
                "id": "$19",
                "title": "ARQUX METADATA",
                "comments": [],
                "entries": [
                    {"sigil": "ARQX", "name": "artifact", "attrs": {...}},
                    {"sigil": "AXM", "name": "rule1", "body": "multi-line text"}
                ]
            }
        ]
    }

Selector syntax::

    '$7/LNG:*'            → all LNG entries in section $7
    '$19/ARQX:artifact'   → the ARQX:artifact entry in section $19
    '$7/LNG:_'            → first LNG entry in section $7 (wildcard)
    '$7'                  → all entries in section $7
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "parse_selector",
    "select_entries",
    "add_entry",
    "update_entry",
    "delete_entry",
    "move_entry",
    "list_entries",
]

# ---------------------------------------------------------------------------
# Selector parsing
# ---------------------------------------------------------------------------

# Matches:  $7/LNG:*   $19/ARQX:artifact   $7/LNG:_   $7
_SELECTOR_RE = re.compile(
    r"""
    ^
    (?P<section>\$\d+)               # $7
    (?:                              # optional /SIGIL:NAME part
        /
        (?P<sigil>[A-Za-z][A-Za-z0-9]*)
        :
        (?P<name>[^/\s]+)            # name, '*' or '_'
    )?
    $
    """,
    re.VERBOSE,
)


def parse_selector(selector: str) -> dict:
    """Parse a CORTEX selector string into components.

    Formats::

        '$7/LNG:*'          → {"section": "$7", "sigil": "LNG", "name": "*"}
        '$19/ARQX:artifact' → {"section": "$19", "sigil": "ARQX", "name": "artifact"}
        '$7/LNG:_'          → {"section": "$7", "sigil": "LNG", "name": "_"}
        '$7'                → {"section": "$7", "sigil": None, "name": None}

    Raises ``ValueError`` if *selector* is malformed.
    """
    if not isinstance(selector, str):
        raise ValueError(f"Selector must be a str, got {type(selector).__name__}")
    m = _SELECTOR_RE.match(selector.strip())
    if not m:
        raise ValueError(f"Invalid selector: {selector!r}")
    return {
        "section": m.group("section"),
        "sigil": m.group("sigil"),
        "name": m.group("name"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_section(doc: dict, section_id: str) -> dict | None:
    """Return the section dict with *section_id*, or ``None``."""
    for section in doc.get("sections", []):
        if section.get("id") == section_id:
            return section
    return None


def _entry_matches(entry: dict, sigil: str | None, name: str | None) -> bool:
    """True if *entry* matches the parsed selector's sigil/name constraints."""
    if sigil is not None and entry.get("sigil") != sigil:
        return False
    if name is not None and name not in ("*", "_"):
        if entry.get("name") != name:
            return False
    return True


def _project_entry(entry: dict, section_id: str) -> dict:
    """Return a copy of *entry* annotated with its owning section id."""
    out: dict[str, Any] = {
        "sigil": entry.get("sigil"),
        "name": entry.get("name"),
        "section": section_id,
    }
    if "attrs" in entry:
        out["attrs"] = entry.get("attrs")
    if "body" in entry:
        out["body"] = entry.get("body")
    return out


# ---------------------------------------------------------------------------
# Select
# ---------------------------------------------------------------------------


def select_entries(doc: dict, selector: str) -> list[dict]:
    """Select entries from a JSON doc matching *selector*.

    Returns a list of entry dicts annotated with ``section`` info::

        [{"sigil":..., "name":..., "section":..., "attrs":...}]
        # or
        [{"sigil":..., "name":..., "section":..., "body":...}]

    Wildcard ``*`` matches all names.  Wildcard ``_`` matches the first
    entry with the matching sigil.
    """
    parts = parse_selector(selector)
    section = _find_section(doc, parts["section"])
    if section is None:
        return []
    sigil, name = parts["sigil"], parts["name"]

    # Section-only selector → all entries.
    if sigil is None and name is None:
        return [_project_entry(e, section["id"]) for e in section.get("entries", [])]

    results: list[dict] = []
    for entry in section.get("entries", []):
        if not _entry_matches(entry, sigil, name):
            continue
        results.append(_project_entry(entry, section["id"]))
        if name == "_":  # wildcard: first match only
            break
    return results


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


def add_entry(
    doc: dict,
    section_id: str,
    sigil: str,
    name: str,
    value: dict | str,
    *,
    create_section: bool = False,
) -> dict:
    """Add an entry to a JSON doc.  Modifies *doc* in-place.  Returns *doc*.

    If *value* is a ``dict`` → attrs entry ``{"sigil": sigil, "name": name, "attrs": value}``.
    If *value* is a ``str`` → cuerpo entry ``{"sigil": sigil, "name": name, "body": value}``.

    If *section_id* does not exist and ``create_section=True`` a new section
    ``{"id": section_id, "title": None, "entries": []}`` is created.

    Raises ``ValueError`` if the section is missing and ``create_section`` is
    ``False``, or if *value* is neither a dict nor a str.
    """
    if not isinstance(value, (dict, str)):
        raise ValueError(
            f"value must be dict (attrs) or str (cuerpo), got {type(value).__name__}"
        )

    section = _find_section(doc, section_id)
    if section is None:
        if not create_section:
            raise ValueError(f"Section {section_id!r} not found in doc")
        section = {"id": section_id, "title": None, "comments": [], "entries": []}
        doc.setdefault("sections", []).append(section)

    if isinstance(value, dict):
        entry: dict[str, Any] = {"sigil": sigil, "name": name, "attrs": value}
    else:
        entry = {"sigil": sigil, "name": name, "body": value}
    section.setdefault("entries", []).append(entry)
    return doc


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_entry(
    doc: dict,
    selector: str,
    *,
    set_: dict | None = None,
    replace_body: str | None = None,
    append: bool = False,
) -> dict:
    """Update entries matching *selector*.  Modifies *doc* in-place.  Returns *doc*.

    ``set_``: merge these attrs into existing attrs (attrs entries only).
    ``replace_body``: replace cuerpo body text (cuerpo entries only).
    ``append``: if ``True`` and ``replace_body`` is given, append to the
    existing body instead of replacing it.

    Raises ``ValueError`` if no entries match, on type mismatch
    (``set_`` on a cuerpo entry, ``replace_body`` on an attrs entry), or
    if neither ``set_`` nor ``replace_body`` is provided.
    """
    if set_ is None and replace_body is None:
        raise ValueError("update_entry requires at least one of set_ or replace_body")
    parts = parse_selector(selector)
    section = _find_section(doc, parts["section"])
    if section is None:
        raise ValueError(f"Section {parts['section']!r} not found in doc")

    sigil, name = parts["sigil"], parts["name"]
    matched = False
    for entry in section.get("entries", []):
        if not _entry_matches(entry, sigil, name):
            continue
        matched = True
        is_attrs = "attrs" in entry and entry["attrs"] is not None
        is_body = "body" in entry and entry["body"] is not None

        if set_ is not None:
            if not is_attrs:
                raise ValueError(
                    f"Cannot set_ attrs on cuerpo entry {entry.get('sigil')}:{entry.get('name')}"
                )
            entry["attrs"] = {**entry["attrs"], **set_}

        if replace_body is not None:
            if not is_body:
                raise ValueError(
                    f"Cannot replace_body on attrs entry {entry.get('sigil')}:{entry.get('name')}"
                )
            if append:
                entry["body"] = (entry["body"] or "") + replace_body
            else:
                entry["body"] = replace_body

        if name == "_":  # wildcard: first match only
            break

    if not matched:
        raise ValueError(f"No entries match selector {selector!r}")
    return doc


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_entry(doc: dict, selector: str) -> dict:
    """Delete entries matching *selector*.  Modifies *doc* in-place.  Returns *doc*.

    Raises ``ValueError`` if no entries match.
    """
    parts = parse_selector(selector)
    section = _find_section(doc, parts["section"])
    if section is None:
        raise ValueError(f"Section {parts['section']!r} not found in doc")

    sigil, name = parts["sigil"], parts["name"]
    entries = section.get("entries", [])

    if name == "_":
        # Delete first match only.
        for idx, entry in enumerate(entries):
            if _entry_matches(entry, sigil, name):
                del entries[idx]
                return doc
        raise ValueError(f"No entries match selector {selector!r}")

    # All other cases: delete every match (``*`` or specific name).
    kept = [e for e in entries if not _entry_matches(e, sigil, name)]
    if len(kept) == len(entries):
        raise ValueError(f"No entries match selector {selector!r}")
    section["entries"] = kept
    return doc


# ---------------------------------------------------------------------------
# Move
# ---------------------------------------------------------------------------


def move_entry(doc: dict, selector: str, to_section: str) -> dict:
    """Move entries matching *selector* to *to_section*.

    Modifies *doc* in-place.  Returns *doc*.

    Raises ``ValueError`` if *to_section* does not exist or no entries match.
    """
    dest = _find_section(doc, to_section)
    if dest is None:
        raise ValueError(f"Destination section {to_section!r} does not exist")

    parts = parse_selector(selector)
    src = _find_section(doc, parts["section"])
    if src is None:
        raise ValueError(f"Section {parts['section']!r} not found in doc")

    sigil, name = parts["sigil"], parts["name"]
    entries = src.get("entries", [])
    moved: list[dict] = []
    kept: list[dict] = []

    if name == "_":
        for idx, entry in enumerate(entries):
            if _entry_matches(entry, sigil, name):
                moved.append(entries.pop(idx))
                break
        if not moved:
            raise ValueError(f"No entries match selector {selector!r}")
        src["entries"] = entries
    else:
        for entry in entries:
            if _entry_matches(entry, sigil, name):
                moved.append(entry)
            else:
                kept.append(entry)
        if not moved:
            raise ValueError(f"No entries match selector {selector!r}")
        src["entries"] = kept

    dest.setdefault("entries", []).extend(moved)
    return doc


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def list_entries(
    doc: dict,
    *,
    section: str | None = None,
    sigil: str | None = None,
) -> list[dict]:
    """List entries, optionally filtered by *section* or *sigil*.

    Returns a list of entry dicts annotated with ``section`` info.
    """
    results: list[dict] = []
    for sec in doc.get("sections", []):
        if section is not None and sec.get("id") != section:
            continue
        for entry in sec.get("entries", []):
            if sigil is not None and entry.get("sigil") != sigil:
                continue
            results.append(_project_entry(entry, sec["id"]))
    return results
