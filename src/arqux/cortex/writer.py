"""BLP-001: ArqUX's own CORTEX writer (JSON/dict → .cortex text).

Serialises a JSON/dict document model into valid CORTEX 0.1 text without
any dependency on CODEC-CORTEX (``cortex.core`` or ``codec_cortex``).

The only external dependency is :func:`arqux.formats._serialise_attrs`,
which handles string escaping (``\\`` → ``\\\\``, ``"`` → ``\\"``),
booleans (``true``/``false``), integers/floats (unquoted), and skips
``None`` values.

JSON model (input)::

    {
        "glossary": {
            "header": "$0",          # optional, defaults to "$0"
            "comments": ["# ..."],   # comment lines
            "symbols": [...]         # optional, ignored
        },
        "sections": [
            {
                "id": "$19",         # section identifier
                "title": "ARQUX METADATA",  # None for glossary-style
                "comments": [],      # optional comment lines
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "artifact",
                        "attrs": {"level": "2", ...},  # attrs-type
                        # OR
                        "body": "multi-line text"       # cuerpo-type
                    }
                ]
            }
        ]
    }
"""

from __future__ import annotations

from typing import Any

from ..formats import _serialise_attrs

__all__ = ["write_cortex_from_json"]


def _coerce_list_values(attrs: dict[str, Any]) -> dict[str, Any]:
    """Pre-process attrs: convert list/tuple values to comma-separated strings.

    ``_serialise_attrs()`` in :mod:`arqux.formats` double-escapes JSON-encoded
    lists, causing the parser to receive a string like ``["a", "b"]`` instead
    of a clean value.  The CORTEX parser (``cortex.core``) does not support
    list syntax ``[…]`` in attrs bodies, so we convert lists/tuples to
    comma-separated strings **before** delegating to ``_serialise_attrs``.

    This is a documented CORTEX format limitation: list/tuple attr values
    do not round-trip as lists — they round-trip as comma-separated strings.
    """
    coerced: dict[str, Any] = {}
    for key, value in attrs.items():
        if isinstance(value, (list, tuple)):
            # Join items with ", " — each item stringified.
            coerced[key] = ", ".join(str(item) for item in value)
        else:
            coerced[key] = value
    return coerced


def _format_attrs_entry(sigil: str, name: str, attrs: dict[str, Any]) -> str:
    """Format a single-line attrs entry: ``SIGIL:name{key:"value", ...}``."""
    coerced = _coerce_list_values(attrs)
    body = _serialise_attrs(coerced)
    return f"{sigil}:{name}{{{body}}}"


def _format_entry(entry: dict[str, Any]) -> str:
    """Format a single entry dict into CORTEX text.

    Raises ``ValueError`` if the entry has both ``attrs`` and ``body``,
    or neither.

    Raises ``ValueError`` (OBS-001) if a cuerpo body contains a line that
    is exactly ``}`` — this breaks the CORTEX parser's depth-aware brace
    matching and would cause silent data loss on round-trip.
    """
    sigil = entry["sigil"]
    name = entry["name"]
    has_attrs = "attrs" in entry and entry["attrs"] is not None
    has_body = "body" in entry and entry["body"] is not None
    if has_attrs and has_body:
        raise ValueError(
            f"Entry {sigil}:{name} has both 'attrs' and 'body' — they are mutually exclusive"
        )
    if has_attrs:
        return _format_attrs_entry(sigil, name, entry["attrs"])
    if has_body:
        body = entry["body"]
        # OBS-001: A line that is exactly "}" breaks the parser's depth-aware
        # brace matching, truncating the cuerpo body at that point.
        for line in body.split("\n"):
            if line.strip() == "}":
                raise ValueError(
                    f"Entry {sigil}:{name} cuerpo body contains a line that is "
                    f"exactly '}}' — this breaks CORTEX parser round-trip. "
                    f"Escape it or restructure."
                )
        return f"{sigil}:{name}{{\n{body}\n}}"
    raise ValueError(f"Entry {sigil}:{name} has neither 'attrs' nor 'body'")


def write_cortex_from_json(doc: dict) -> str:
    """Serialize a JSON/dict document to CORTEX text.

    No dependency on CODEC-CORTEX. Uses ArqUX's own serialization
    primitives from :mod:`arqux.formats`.

    Parameters
    ----------
    doc:
        The JSON/dict document model (see module docstring for schema).

    Returns
    -------
    str
        Valid CORTEX text string.

    Raises
    ------
    ValueError
        If *doc* is not a dict, or if any section/entry is malformed
        (missing required keys, wrong types).
    """
    # --- OBS-003: Input validation ---
    if doc is None:
        raise ValueError("Document cannot be None")
    if not isinstance(doc, dict):
        raise ValueError(f"Expected dict, got {type(doc).__name__}")

    lines: list[str] = []

    # --- Glossary ($0) ---
    glossary = doc.get("glossary", {})
    header = glossary.get("header", "$0")
    comments = glossary.get("comments", [])
    # symbols are ignored — comments carry the glossary

    lines.append(header)
    lines.append("")  # blank line after header
    for comment in comments:
        lines.append(comment)

    # --- Sections ---
    sections = doc.get("sections", [])
    for i, section in enumerate(sections):
        # OBS-003: validate section structure
        if not isinstance(section, dict):
            raise ValueError(
                f"Section {i} must be a dict, got {type(section).__name__}"
            )
        if "id" not in section:
            raise ValueError(f"Section {i} missing required 'id' key")

        sid = section["id"]
        title = section.get("title")
        section_comments = section.get("comments", [])
        entries = section.get("entries", [])

        # Section separator: ensure two blank lines before each section.
        # The previous content may already end with one blank line (e.g.
        # the trailing blank after the last entry), so we top up to two.
        if lines and lines[-1] == "":
            lines.append("")  # one more → two total
        else:
            lines.append("")
            lines.append("")

        # Section header
        if title is not None:
            lines.append(f"{sid}: {title}")
        else:
            lines.append(sid)
        lines.append("")  # blank line after header

        # Comments within section
        for comment in section_comments:
            lines.append(comment)

        # Entries — each followed by a blank line
        for j, entry in enumerate(entries):
            # OBS-003: validate entry structure
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Entry {j} in section {sid} must be a dict, "
                    f"got {type(entry).__name__}"
                )
            if "sigil" not in entry:
                raise ValueError(
                    f"Entry {j} in section {sid} missing required 'sigil' key"
                )
            if "name" not in entry:
                raise ValueError(
                    f"Entry {j} in section {sid} missing required 'name' key"
                )
            entry_text = _format_entry(entry)
            lines.append(entry_text)
            lines.append("")  # blank line after each entry

    # Ensure trailing newline
    result = "\n".join(lines)
    if not result.endswith("\n"):
        result += "\n"
    return result
