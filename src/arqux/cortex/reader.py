"""BLP-004: CORTEX text → dict JSON model converter.

Uses CODEC-CORTEX parser for parsing, with regex-based fallback.

The returned dict matches the input model expected by
:mod:`arqux.cortex.writer` (BLP-001)::

    {
        "glossary": {"header": "$0", "comments": [...]},
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
# CODEC-CORTEX parser detection
# ---------------------------------------------------------------------------

_PARSER: Any | None = None
_PARSER_API: str | None = None  # "cortex_core" | "codec_cortex" | None

try:
    from cortex.core.parser import parse_cortex as _parse_cortex_core  # noqa: F401

    _PARSER = _parse_cortex_core
    _PARSER_API = "cortex_core"
except ImportError:
    pass

if _PARSER is None:
    try:
        from codec_cortex.dispatcher import parse_cortex as _parse_cortex_codec  # noqa: F401

        _PARSER = _parse_cortex_codec
        _PARSER_API = "codec_cortex"
    except ImportError:
        pass


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

# Multi-line entry start:  SIGIL:name{
_ENTRY_START_RE = re.compile(
    r"^(?P<sigil>[A-Z][A-Z0-9_]*)\s*:\s*(?P<name>[^\s{]+)\s*\{\s*$"
)

# GSIG/GCON declarations in glossary — skip in fallback
_GSIG_RE = re.compile(r"^GSIG:|GCON:")

# Comment line
_COMMENT_RE = re.compile(r"^#")


# ---------------------------------------------------------------------------
# CODEC-CORTEX path (cortex.core — installed 0.6.2)
# ---------------------------------------------------------------------------


def _convert_cortex_core(doc: Any) -> dict:
    """Convert a ``cortex.core.ast.CortexDocument`` to our dict model.

    AST shape (0.6.2):
        - doc.sections: list[Section]
        - Section.id: str ("$0"), Section.title: str, Section.entries: list[Entry]
        - Section.comments: list[str]
        - Entry.sigil, Entry.name, Entry.type, Entry.value, Entry.raw
    """
    sections_out: list[dict[str, Any]] = []
    glossary_comments: list[str] = []
    glossary_header = "$0"

    for section in doc.sections:
        sid = section.id
        title = section.title or None
        comments = list(getattr(section, "comments", []) or [])

        # The first section ($0) is the glossary
        if sid == "$0":
            glossary_header = sid
            glossary_comments = comments
            # Glossary entries (GSIG/GCON declarations) are not carried
            # into our model — only comments matter.
            continue

        entries_out: list[dict[str, Any]] = []
        for entry in section.entries:
            converted = _convert_entry_cortex_core(entry)
            if converted is not None:
                entries_out.append(converted)

        sections_out.append({
            "id": sid,
            "title": title,
            "entries": entries_out,
            "comments": comments,
        })

    return {
        "glossary": {
            "header": glossary_header,
            "comments": glossary_comments,
        },
        "sections": sections_out,
    }


def _convert_entry_cortex_core(entry: Any) -> dict[str, Any] | None:
    """Convert a ``cortex.core.ast.Entry`` to our entry dict format.

    Handles attrs, cuerpo, bloque, and relación entry types.
    Falls back to extracting body from ``raw`` when attrs parsing failed
    (value is empty dict but raw contains multi-line text).
    """
    sigil = entry.sigil
    name = entry.name
    etype = entry.type or "attrs"
    value = entry.value
    raw = entry.raw or ""

    # Cuerpo / bloque / relación → body entry
    if etype in ("cuerpo", "bloque", "relación") and isinstance(value, str):
        return {"sigil": sigil, "name": name, "body": value}

    # Attrs / attrs-pos → attrs entry
    if etype in ("attrs", "attrs-pos", ""):
        if isinstance(value, dict) and value:
            # Non-empty attrs dict
            return {"sigil": sigil, "name": name, "attrs": value}

        if isinstance(value, dict) and not value:
            # Empty attrs dict — could be genuinely empty {} or a failed
            # attrs parse on cuerpo text.  Check raw for multi-line body.
            body = _extract_body_from_raw(raw)
            if body is not None and "\n" in raw:
                # Multi-line raw with unparseable attrs → treat as cuerpo
                return {"sigil": sigil, "name": name, "body": body}
            # Genuinely empty attrs
            return {"sigil": sigil, "name": name, "attrs": {}}

    # Unknown type with string value → body
    if isinstance(value, str) and value:
        return {"sigil": sigil, "name": name, "body": value}

    # Fallback: empty attrs
    return {"sigil": sigil, "name": name, "attrs": {}}


def _extract_body_from_raw(raw: str) -> str | None:
    """Extract the body text between ``{`` and ``}`` from a raw entry string.

    Returns ``None`` if the raw text doesn't contain braces.
    """
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        return None
    body = raw[first_brace + 1 : last_brace]
    # Strip leading/trailing newlines but preserve internal formatting
    return body.strip("\n")


# ---------------------------------------------------------------------------
# CODEC-CORTEX path (codec_cortex — 1.0.0-rc.1)
# ---------------------------------------------------------------------------


def _convert_codec_cortex(doc: Any) -> dict:
    """Convert a ``codec_cortex`` Document AST to our dict model.

    AST shape (1.0.0-rc.1):
        - doc.glossary: Section (id=0)
        - doc.sections: list[Section]
        - Section.id: int, Section.title: str|None, Section.ideas: list[Idea]
        - Idea.symbol (sigil), Idea.name, Idea.shape, Idea.payload
        - payload: dict (attrs) | ("cuerpo", text) | ("bloque", text)
    """
    sections_out: list[dict[str, Any]] = []
    glossary_comments: list[str] = []
    glossary_header = "$0"

    # Glossary
    glossary = getattr(doc, "glossary", None)
    if glossary is not None:
        glossary_comments = list(getattr(glossary, "comments", []) or [])
        gid = getattr(glossary, "id", 0)
        glossary_header = f"${gid}"

    for section in doc.sections:
        sid_raw = section.id
        sid = sid_raw if isinstance(sid_raw, str) else f"${sid_raw}"
        title = section.title

        # Skip glossary section
        if sid == glossary_header or sid_raw == 0:
            continue

        comments = list(getattr(section, "comments", []) or [])
        entries_out: list[dict[str, Any]] = []

        # 1.0.0-rc.1 uses .ideas, 0.6.2 uses .entries — try both
        ideas = getattr(section, "ideas", None)
        if ideas is None:
            ideas = getattr(section, "entries", [])
        for idea in ideas:
            converted = _convert_idea_codec_cortex(idea)
            if converted is not None:
                entries_out.append(converted)

        sections_out.append({
            "id": sid,
            "title": title,
            "entries": entries_out,
            "comments": comments,
        })

    return {
        "glossary": {
            "header": glossary_header,
            "comments": glossary_comments,
        },
        "sections": sections_out,
    }


def _convert_idea_codec_cortex(idea: Any) -> dict[str, Any] | None:
    """Convert a ``codec_cortex`` Idea to our entry dict format."""
    sigil = getattr(idea, "symbol", None) or getattr(idea, "sigil", None)
    name = idea.name
    shape = getattr(idea, "shape", None) or getattr(idea, "type", None)
    payload = getattr(idea, "payload", None)
    if payload is None:
        payload = getattr(idea, "value", None)

    # payload is a tuple like ("cuerpo", text) for cuerpo/bloque entries
    if isinstance(payload, tuple) and len(payload) == 2:
        kind, text = payload
        if kind in ("cuerpo", "bloque", "relación"):
            return {"sigil": sigil, "name": name, "body": text}

    # payload is a dict → attrs entry
    if isinstance(payload, dict):
        return {"sigil": sigil, "name": name, "attrs": payload}

    # payload is a string → body entry
    if isinstance(payload, str):
        return {"sigil": sigil, "name": name, "body": payload}

    # Fallback
    return {"sigil": sigil, "name": name, "attrs": {}}


# ---------------------------------------------------------------------------
# Regex fallback path (no CODEC-CORTEX)
# ---------------------------------------------------------------------------


def _parse_fallback(text: str) -> dict:
    """Regex-based fallback parser for CORTEX text.

    Best-effort: handles common patterns but may not cover all edge cases.
    """
    lines = text.split("\n")
    glossary_comments: list[str] = []
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

        # Multi-line entry start:  SIGIL:name{
        m = _ENTRY_START_RE.match(stripped)
        if m and current_section is not None:
            sigil = m.group("sigil")
            name = m.group("name")
            # Collect lines until closing }
            body_lines: list[str] = []
            i += 1
            while i < len(lines):
                body_line = lines[i]
                if body_line.strip() == "}":
                    break
                body_lines.append(body_line)
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
            i += 1
            continue

        # Unrecognized line — skip
        i += 1

    # Attach remaining comments
    if current_comments:
        if current_section is not None and current_section.get("id") == "$0":
            glossary_comments.extend(current_comments)
        elif sections:
            sections[-1]["comments"].extend(current_comments)

    return {
        "glossary": {
            "header": glossary_header,
            "comments": glossary_comments,
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
            "glossary": {"header": "$0", "comments": [...]},
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
            "glossary": {"header": "$0", "comments": []},
            "sections": [],
        }

    # Try CODEC-CORTEX parser first
    if _PARSER is not None:
        try:
            doc = _PARSER(text)
            if _PARSER_API == "cortex_core":
                return _convert_cortex_core(doc)
            elif _PARSER_API == "codec_cortex":
                return _convert_codec_cortex(doc)
        except Exception:
            # Parser failed — fall back to regex
            pass

    # Fallback: regex-based parsing
    return _parse_fallback(text)
