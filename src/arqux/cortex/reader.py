"""BLP-004: CORTEX text → dict JSON model converter.

Uses CODEC-CORTEX parser for parsing, with regex-based fallback.

The returned dict matches the input model expected by
:mod:`arqux.cortex.writer` (BLP-001)::

    {
        "glossary": {"header": "$0", "comments": [...], "symbols": [...]},
        "sections": [
            {
                "id": "$N",
                "title": "...",
                "entries": [
                    {"sigil": "LNG", "name": "test", "attrs": {...}},
                    {"sigil": "AXM", "name": "rule1", "body": "multi-line text"}
                ],
                "comments": [...]
            }
        ]
    }
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["cortex_to_dict"]


# ---------------------------------------------------------------------------
# Parser ownership
# ---------------------------------------------------------------------------
# ARQUX's own parser (_parse_fallback) is the single authority. External
# codec-cortex packages are convention-only and are never preferred — an
# installed codec must not silently diverge from ARQUX parse semantics.


# ---------------------------------------------------------------------------
# Regex fallback patterns
# ---------------------------------------------------------------------------

# Section header:  $0  or  $1: TITLE  or  $19: ARQUX METADATA
_SECTION_RE = re.compile(
    r"^(?P<id>\$\d+)(?:\s*:\s*(?P<title>.+))?$"
)

# Single-line attrs entry:  SIGIL:name{key:"value", ...}
_ATTRS_INLINE_RE = re.compile(
    r"^(?P<sigil>[A-Z][A-Z0-9_]*)\s*:\s*(?P<name>[^\s{]+)\s*\{(?P<body>.*)\}\s*$"
)

# Multi-line entry start:  SIGIL:name{  (attrs may begin on the same line;
# the writer emits single-line opens whose quoted values re-wrap)
_ENTRY_START_RE = re.compile(
    r"^(?P<sigil>[A-Z][A-Z0-9_]*)\s*:\s*(?P<name>[^\s{]+)\s*\{"
)

# GSIG/GCON declarations in glossary — skip in fallback
_GSIG_RE = re.compile(r"^GSIG:|GCON:")

# Comment line
_COMMENT_RE = re.compile(r"^#")


# ---------------------------------------------------------------------------
# Regex fallback path (no CODEC-CORTEX)
# ---------------------------------------------------------------------------


def _parse_fallback(text: str) -> dict:
    """Regex-based fallback parser for CORTEX text.

    Best-effort: handles common patterns but may not cover all edge cases.
    """
    lines = text.split("\n")
    glossary_comments: list[str] = []
    glossary_symbols: list[dict[str, Any]] = []
    glossary_header = "$0"
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    current_comments: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Comment line
        if _COMMENT_RE.match(stripped):
            current_comments.append(stripped)
            i += 1
            continue

        # Section header
        m = _SECTION_RE.match(stripped)
        if m:
            sid = m.group("id")
            title = m.group("title")
            title = title.strip() if title else None

            # First section ($0) is glossary
            if sid == "$0" and not sections and current_section is None:
                glossary_header = sid
                # Comments before $0 are glossary comments
                glossary_comments = list(current_comments)
                current_comments = []
                current_section = {
                    "id": sid,
                    "title": None,  # glossary has no title in our model
                    "entries": [],
                    "comments": [],
                }
                # Don't add glossary to sections — handled separately
                # But we still need to track it for entry collection
                i += 1
                continue

            # Close previous section
            if current_section is not None:
                if current_section.get("id") == "$0":
                    # Comments accumulated after $0 header are glossary comments
                    glossary_comments.extend(current_comments)
                    # T-024: glossary entries round-trip as symbols
                    glossary_symbols.extend(current_section.get("entries", []))
                else:
                    # Append any pending comments to the section
                    current_section["comments"].extend(current_comments)
                    if current_section not in sections:
                        sections.append(current_section)

            current_section = {
                "id": sid,
                "title": title,
                "entries": [],
                "comments": [],
            }
            sections.append(current_section)
            current_comments = []
            i += 1
            continue

        # GSIG/GCON declarations — skip in fallback
        if _GSIG_RE.match(stripped):
            i += 1
            continue

        # Single-line attrs entry:  SIGIL:name{...}
        m = _ATTRS_INLINE_RE.match(stripped)
        if m and current_section is not None:
            sigil = m.group("sigil")
            name = m.group("name")
            body = m.group("body").strip()
            attrs = _parse_attrs_fallback(body)
            if attrs is not None:
                current_section["entries"].append({
                    "sigil": sigil, "name": name, "attrs": attrs,
                })
            else:
                # Can't parse attrs — treat as body
                current_section["entries"].append({
                    "sigil": sigil, "name": name, "body": body,
                })
            i += 1
            continue

        # Multi-line entry start:  SIGIL:name{  (content may follow the
        # opening brace on the same line; the entry closes when brace
        # depth returns to 0, tracked outside quoted strings — quotes may
        # stay open across physical lines)
        m = _ENTRY_START_RE.match(stripped)
        if m and current_section is not None:
            sigil = m.group("sigil")
            name = m.group("name")
            body_lines = [stripped[m.end() :]]
            i += 1
            depth = 1
            in_str = False
            done = False
            while i <= len(lines) and not done:
                for ch in body_lines[-1]:
                    if in_str:
                        if ch == '"':
                            in_str = False
                    elif ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            body_lines[-1] = body_lines[-1].rstrip("}").rstrip()
                            done = True
                            break
                if not done:
                    if i >= len(lines):
                        break
                    body_lines.append(lines[i])
                    i += 1
            body = "\n".join(body_lines).strip("\n")
            # Try to parse as attrs first
            attrs = _parse_attrs_fallback(body)
            if attrs is not None and attrs:
                current_section["entries"].append({
                    "sigil": sigil, "name": name, "attrs": attrs,
                })
            else:
                current_section["entries"].append({
                    "sigil": sigil, "name": name, "body": body,
                })
            continue

        # Unrecognized line — skip
        i += 1

    # Attach remaining comments
    if current_comments:
        if current_section is not None and current_section.get("id") == "$0":
            glossary_comments.extend(current_comments)
        elif sections:
            sections[-1]["comments"].extend(current_comments)

    # T-024: glossary entries at end-of-input round-trip as symbols
    if current_section is not None and current_section.get("id") == "$0":
        glossary_symbols.extend(current_section.get("entries", []))

    return {
        "glossary": {
            "header": glossary_header,
            "comments": glossary_comments,
            "symbols": glossary_symbols,
        },
        "sections": sections,
    }


# Attrs pattern:  key:"value"  or  key:value  or  key:value,
_ATTR_PAIR_RE = re.compile(
    r'(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*'
    r'(?P<val>"(?:[^"\\]|\\.)*"|true|false|'
    r'-?\d+\.?\d*|[A-Za-z_][A-Za-z0-9_]*)'
)


def _parse_attrs_fallback(body: str) -> dict | None:
    """Best-effort attrs parsing for the fallback path.

    Returns a dict of attrs, or ``None`` if the body doesn't look like attrs.
    """
    if not body.strip():
        return {}

    # Heuristic: if the body contains lines without key:value patterns,
    # it's probably cuerpo text, not attrs.
    attrs: dict[str, Any] = {}
    matches = list(_ATTR_PAIR_RE.finditer(body))
    if not matches:
        return None

    for m in matches:
        key = m.group("key")
        raw_val = m.group("val")
        attrs[key] = _coerce_attr_value(raw_val)

    return attrs


def _coerce_attr_value(raw: str) -> Any:
    """Convert a raw attr value string to its Python type."""
    if raw.startswith('"') and raw.endswith('"'):
        # Unquote and unescape
        inner = raw[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    if raw == "true":
        return True
    if raw == "false":
        return False
    # Try int
    try:
        return int(raw)
    except ValueError:
        pass
    # Try float
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def cortex_to_dict(text: str) -> dict:
    """Parse CORTEX text and convert to ArqUX JSON dict model.

    Uses CODEC-CORTEX parser (``cortex.core`` or ``codec_cortex``) if
    available.  Falls back to regex-based parsing if CODEC-CORTEX is
    unavailable or raises an error on the input.

    Returns dict matching :mod:`arqux.cortex.writer` input model::

        {
            "glossary": {"header": "$0", "comments": [...], "symbols": [...]},
            "sections": [
                {"id": "$N", "title": "...", "entries": [...], "comments": [...]}
            ]
        }

    Parameters
    ----------
    text:
        CORTEX text string.

    Returns
    -------
    dict
        The JSON dict model.

    Raises
    ------
    ValueError
        If *text* is not a string.
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected str, got {type(text).__name__}")

    # Handle empty / whitespace-only text
    if not text.strip():
        return {
            "glossary": {"header": "$0", "comments": [], "symbols": []},
            "sections": [],
        }

    # ARQUX's own parser is the single authority (CODEC-CORTEX is a
    # convention, not an implementation — see reader module docstring).
    return _parse_fallback(text)
