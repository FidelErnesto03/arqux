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
            "symbols": [...]         # optional glossary entries (serialized after comments)
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
from .sigils import get_sigil

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


def _symbol_declaration(sigil: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a strict CORTEX 0.1 glossary declaration for *sigil*.

    ArqUX historically emitted the glossary as comments only.  CODEC-CORTEX
    1.0 validates the executable glossary, so a writer round-trip must emit a
    declaration for every sigil used by an idea.  The declaration is inferred
    from the document model and enriched with the local sigil cache when
    available.  All fields are optional at the contract level: ArqUX brains
    are intentionally open records and may evolve without changing the
    declaration.
    """
    shapes = {"body" if "body" in entry and entry.get("body") is not None else "attrs"
              for entry in entries}

    definition = get_sigil(sigil) or {}
    # A single glossary contract may describe a sigil used in both forms.  In
    # that case cuerpo is the lossless CODEC-CORTEX contract: attrs entries
    # remain syntactically valid bodies, while a cuerpo entry cannot be parsed
    # as an attrs map.  Uniform attrs sigils retain their richer contract.
    shape = "body" if "body" in shapes else next(iter(shapes), definition.get("type", "attrs"))
    label = str(definition.get("name") or sigil.lower())
    risk = str(definition.get("risk") or "B")
    weight = risk if risk in {"B", "M", "H"} else "B"
    description = str(definition.get("description") or f"ArqUX {sigil} entry")

    if shape == "body":
        return {
            "sigil": sigil,
            "name": label,
            "attrs": {
                "type": "cuerpo",
                "weight": weight,
                "focus": "$body",
                "desc": description,
            },
        }

    fields: list[str] = []
    cached_fields = definition.get("fields") if definition else None
    if isinstance(cached_fields, str) and cached_fields:
        fields = [part.strip().split(":", 1)[0]
                  for part in cached_fields.replace("|", ",").split(",")
                  if part.strip()]
    if not fields:
        # Unknown/custom sigils and open ArqUX records use a generic contract.
        # Copying every payload key into the glossary creates false duplicate-
        # looking text on round-trip and is unnecessary for parsing.
        fields = ["value"]
    # An attrs declaration needs a focus that belongs to its contract.  An
    # empty attrs entry is legal in ArqUX, so provide one optional placeholder
    # rather than generating an invalid declaration.
    if not fields:
        fields = ["value"]
    contract = "|".join(f"{key}:any?" for key in fields)
    return {
        "sigil": sigil,
        "name": label,
        "attrs": {
            "type": "attrs",
            "weight": weight,
            "fields": contract,
            "focus": fields[0],
            "desc": description,
        },
    }


def _generated_symbols(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministic declarations for all sigils used by sections."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        for entry in section.get("entries", []):
            if not isinstance(entry, dict):
                continue
            sigil = str(entry.get("sigil", ""))
            if sigil:
                grouped.setdefault(sigil, []).append(entry)
    return [_symbol_declaration(sigil, grouped[sigil]) for sigil in sorted(grouped)]


def write_cortex_from_json(doc: dict, *, strict: bool = False) -> str:
    """Serialize a JSON/dict document to CORTEX text.

    No dependency on CODEC-CORTEX. Uses ArqUX's own serialization
    primitives from :mod:`arqux.formats`.

    When ``strict`` is true, legacy glossary data and ``$0.1`` metadata are
    normalized into a document accepted by CODEC-CORTEX 1.0.0rc1. The
    default preserves ArqUX's historical JSON round-trip contract.

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
    symbols = glossary.get("symbols", [])
    sections = doc.get("sections", [])

    lines.append(header)
    lines.append("")  # blank line after header
    for comment in comments:
        lines.append(comment)

    # CODEC-CORTEX 1.0.0rc1 requires executable declarations such as
    # ``LNG:lesson{type:attrs,...}``. Older ArqUX documents stored these as
    # ``GSIG:LNG{...}``; strict mode upgrades those declarations.
    strict_symbols: list[dict[str, Any]] = []
    legacy_glossary_data: list[dict[str, Any]] = []
    for entry in symbols:
        if not isinstance(entry, dict):
            raise ValueError(
                f"Glossary symbol must be a dict, got {type(entry).__name__}"
            )
        attrs = entry.get("attrs")
        if strict and str(entry.get("sigil")) == "GSIG" and isinstance(attrs, dict):
            target = str(attrs.get("sigil") or entry.get("name") or "")
            if target:
                strict_symbols.append(_symbol_declaration(target, [entry]))
            continue
        if strict and isinstance(attrs, dict) and not {
            "type", "weight", "focus", "desc"
        }.issubset(attrs):
            legacy_glossary_data.append(entry)
            continue
        strict_symbols.append(entry)

    if not strict:
        strict_symbols = list(symbols)

    # T-024: glossary entries serialize after the comments.
    for entry in strict_symbols:
        lines.append(_format_entry(entry))
        lines.append("")  # blank line after each entry

    # CODEC-CORTEX validates that every sigil used outside the glossary has a
    # strict declaration. Legacy GSIG declarations were normalized above.
    declared: set[str] = set()
    for entry in strict_symbols:
        if not isinstance(entry, dict) or not isinstance(entry.get("attrs"), dict):
            continue
        attrs = entry["attrs"]
        if {"type", "weight", "focus", "desc"}.issubset(attrs):
            declared.add(str(entry.get("sigil")))
    if strict:
        for entry in _generated_symbols(sections):
            if entry["sigil"] in declared:
                continue
            lines.append(_format_entry(entry))
            lines.append("")
            declared.add(entry["sigil"])

    if strict and legacy_glossary_data:
        sections = list(sections)
        used_ids = {
            int(str(section.get("id", "")).lstrip("$").split(".", 1)[0])
            for section in sections
            if str(section.get("id", "")).lstrip("$").split(".", 1)[0].isdigit()
        }
        sections.insert(0, {
            "id": f"${max(used_ids or {0}) + 1}",
            "title": "MIGRATED GLOSSARY DATA",
            "comments": ["# Entries moved from the legacy glossary during CODEC migration."],
            "entries": legacy_glossary_data,
        })

    if strict:
        normalized_sections: list[dict[str, Any]] = []
        metadata_section: dict[str, Any] | None = None
        for section in sections:
            sid = str(section.get("id", ""))
            if sid == "$0.1":
                if metadata_section is None:
                    metadata_section = {
                        "id": "$19",
                        "title": "ARQUX METADATA",
                        "comments": list(section.get("comments", [])),
                        "entries": list(section.get("entries", [])),
                    }
                    normalized_sections.append(metadata_section)
                else:
                    metadata_section.setdefault("entries", []).extend(section.get("entries", []))
                continue
            if sid == "$19" and metadata_section is not None:
                metadata_section.setdefault("entries", []).extend(section.get("entries", []))
                continue
            normalized_sections.append(section)
        sections = normalized_sections

        # Recompute declarations after legacy glossary data has been moved
        # into a numeric section.
        #
        # The first pass above emitted each undeclared sigil but did NOT record
        # it in `declared`, so this second pass emitted every generated symbol
        # a second time. The result was a glossary with each declaration
        # duplicated — CODEC-CORTEX rejects that as E008_DUPLICATE_ENTRY, and
        # it is why `atomic_write_json` (strict=True) produced a different,
        # invalid document than `write_cortex_from_json` (strict=False).
        # `declared` is updated here as well, which makes the recomputation
        # idempotent for sigils that were genuinely added by the migration.
        for entry in _generated_symbols(sections):
            if entry["sigil"] in declared:
                continue
            lines.append(_format_entry(entry))
            lines.append("")
            declared.add(entry["sigil"])

    # The dispatcher in CODEC-CORTEX 1.0.0-rc.1 requires an explicit version
    # declaration. The PINNED codec-cortex (0.6.2) does not: it parses bare
    # ``$0`` and tolerates undeclared sigils. Emitting the rc.1 dialect
    # unconditionally made every ``cortex.entry.add`` / ``entry.update`` write
    # inject a ``$0:format{...}`` line plus a sigil-schema dictionary into
    # ``$0`` of documents that never asked for it, which the pinned validator
    # then reported as E033/E032 (BUG-1). The declaration is therefore emitted
    # only on the explicit strict path used by the migration handlers.
    if strict and not header.startswith("$0:format"):
        lines.append('$0:format{cortex:"0.1", encoding:"UTF-8"}')
        lines.append("")

    # --- Sections ---
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
