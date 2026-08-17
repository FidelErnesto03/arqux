"""CRUD operations on .cortex files via ArqUX's own CORTEX components.

BLP-005: Replaces CODEC-CORTEX mutations/transactions with ArqUX's
own reader, CRUD, and atomic writer modules.
"""

from __future__ import annotations

from pathlib import Path

from . import (
    _cc_parser,
    _cc_renderer,
    _cc_selectors,
    _cc_validator,
)

# --- ArqUX CORTEX components (BLP-001..004) ---------------------------------

from ...cortex.reader import cortex_to_dict
from ...cortex.writer import write_cortex_from_json
from ...cortex.crud import (
    add_entry as _ax_add_entry,
    update_entry as _ax_update_entry,
    delete_entry as _ax_delete_entry,
    move_entry as _ax_move_entry,
    select_entries as _ax_select_entries,
    list_entries as _ax_list_entries,
)
from ...cortex.atomic import atomic_write_json, atomic_write_text, WriteResult

# --- CODEC-CORTEX dependency ------------------------------------------------


def requires_codec_cortex() -> None:
    """Raise RuntimeError if CODEC-CORTEX is not available.

    BLP-005: Most write/mutation operations no longer require
    CODEC-CORTEX (they use ArqUX's own components).  This check is
    retained for read/verify/render functions that still delegate to
    CODEC-CORTEX's parser/validator/renderer.
    """
    from ...state import _HAS_CODEC_CORTEX as _cc_available

    if not _cc_available:
        raise RuntimeError(
            "CODEC-CORTEX is required. Install with: pip install codec-cortex>=0.4.0"
        )


# --- Generic .cortex file operations -----------------------------------------


def cortex_read(path: str | Path) -> dict:
    """Parse a .cortex file into its AST representation.

    Returns a dict with:
        path: str
        sections: list of {id, title, entries, comments}
        glossary: {sigils, types, micro, contracts}
        content: str (raw text)

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    return {
        "path": str(path),
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "entries": [{"sigil": e.sigil, "name": e.name, "value": e.value} for e in s.entries],
                "comment_count": len(s.comments or []),
            }
            for s in doc.sections
        ],
        "glossary": {
            "sigil_count": len(doc.glossary.sigils) if doc.glossary else 0,
            "type_count": len(doc.glossary.types) if doc.glossary else 0,
        } if doc.glossary else {},
        "content": text,
        "size_bytes": len(text),
    }


def cortex_write(
    path: str | Path,
    content: str,
    *,
    force: bool = False,
) -> dict:
    """Parse *content* as CORTEX text and atomically write to *path*.

    BLP-005: Uses ArqUX's own reader (cortex_to_dict) and atomic
    writer (atomic_write_json) instead of CODEC-CORTEX transactions.

    Validates before writing (if CODEC-CORTEX validator is available).
    Returns the write result dict.
    """
    path = str(Path(path).resolve())

    # Parse content to dict using ArqUX reader.
    doc = cortex_to_dict(content)

    # Optional validation via CODEC-CORTEX (if available).
    from ...state import _HAS_CODEC_CORTEX as _cc_available
    if _cc_available and _cc_validator is not None:
        try:
            ast_doc = _cc_parser.parse_cortex(content, path=path)
            diags = _cc_validator.validate(ast_doc)
            errors = [d for d in diags if d.get("severity") == "error"]
            if errors and not force:
                return {
                    "path": path,
                    "error": f"Validation failed ({len(errors)} errors). Use force=True to override.",
                    "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')} (line {d.get('line','?')})" for d in errors],
                }
        except Exception:
            # Validation is best-effort — proceed with write.
            pass

    result = atomic_write_json(doc, path)
    return {
        "path": result.path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "diagnostics": [],
        "dry_run": result.dry_run,
    }


def cortex_verify(path: str | Path) -> dict:
    """Verify a .cortex file using CODEC-CORTEX validator.

    Returns a dict with path, valid (bool), diagnostics.

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    diags = _cc_validator.validate(doc)
    errors = [d for d in diags if d.get("severity") == "error"]
    return {
        "path": str(path),
        "valid": len(errors) == 0,
        "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')} (line {d.get('line','?')})" for d in diags],
        "sections": len(doc.sections),
        "entries": sum(len(s.entries) for s in doc.sections),
    }


def cortex_render(path: str | Path) -> str:
    """Render a .cortex file to HCORTEX READ markdown.

    Returns the rendered markdown text.

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    return _cc_renderer.render_hcortex_read(doc)


# --- _cortex_crud -- partial file mutation via ArqUX CRUD (BLP-005) ---------


def _read_and_mutate(
    path: Path,
    mutate_fn,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Read a .cortex file, apply *mutate_fn* on the dict, and write.

    BLP-005: Uses ArqUX's reader (cortex_to_dict) to parse, applies
    *mutate_fn* on the JSON dict model, and writes atomically via
    atomic_write_json.

    *mutate_fn* receives the parsed dict and returns it (modified).
    """
    text = path.read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    doc = mutate_fn(doc)

    # Optional validation via CODEC-CORTEX (if available).
    from ...state import _HAS_CODEC_CORTEX as _cc_available
    if _cc_available and _cc_validator is not None:
        try:
            # Re-serialize to text for CODEC validation.
            cortex_text = write_cortex_from_json(doc)
            ast_doc = _cc_parser.parse_cortex(cortex_text, path=str(path))
            diags = _cc_validator.validate(ast_doc)
            errors = [d for d in diags if d.get("severity") == "error"]
            if errors and not force:
                return {
                    "error": f"Validation failed ({len(errors)} errors). Use force=True to override.",
                    "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')}" for d in errors],
                }
        except Exception:
            # Validation is best-effort — proceed with write.
            pass

    if dry_run:
        return {"dry_run": True, "path": str(path), "diagnostics": []}
    try:
        result = atomic_write_json(doc, str(path))
    except Exception as e:
        return {"error": f"Atomic write failed: {e}", "non_bypassable": True}

    return {
        "path": str(path),
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "diagnostics": [],
    }


def crud_read(path: str | Path, selector: str) -> dict:
    """Read entries matching *selector* from a .cortex file.

    BLP-005: Uses ArqUX's reader + select_entries.

    Supports both ``$N/SIGIL:name`` (ArqUX format) and ``SIGIL:name``
    (legacy CODEC format without section prefix). When no section
    prefix is given, all sections are searched.

    Returns a dict with ``entries`` (list of matched entries).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = cortex_to_dict(text)

    # Try ArqUX selector format first ($N/SIGIL:name).
    try:
        entries = _ax_select_entries(doc, selector)
    except ValueError:
        # Fallback: legacy CODEC selector without section prefix (SIGIL:name).
        # Search all sections for matching sigil/name.
        entries = _select_all_sections(doc, selector)

    return {
        "path": str(path),
        "selector": selector,
        "entries": [
            {"sigil": e.get("sigil"), "name": e.get("name"), "section": e.get("section"), "value": e.get("attrs") or e.get("body")}
            for e in entries
        ],
    }


def crud_add(
    path: str | Path,
    section: str,
    sigil: str,
    name: str,
    value: str | dict,
    *,
    create_section: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Add an entry to a .cortex file.

    BLP-005: Uses ArqUX's add_entry + atomic_write_json.

    Returns the write result dict.
    """
    p = Path(path)

    # Parse value: if it's a string that looks like attrs, try to parse it.
    parsed_value = _parse_value(value)

    def _add(doc):
        _ax_add_entry(
            doc, section, sigil, name, parsed_value,
            create_section=create_section,
        )
        return doc

    return _read_and_mutate(p, _add, force=force, dry_run=dry_run)


def crud_update(
    path: str | Path,
    selector: str,
    *,
    set_: dict | None = None,
    replace_body: str | None = None,
    append: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an entry selected by *selector* in a .cortex file.

    BLP-005: Uses ArqUX's update_entry + atomic_write_json.
    Note: ArqUX's update_entry does NOT have a ``force`` parameter.

    Supports both ``$N/SIGIL:name`` (ArqUX format) and ``SIGIL:name``
    (legacy CODEC format without section prefix).

    For attrs entries use ``set_`` (dict of key/value pairs to merge).
    For cuerpo/bloque entries use ``replace_body``.
    """
    p = Path(path)

    def _update(doc):
        resolved = _resolve_legacy_selector(doc, selector)
        _ax_update_entry(
            doc, resolved,
            set_=set_, replace_body=replace_body, append=append,
        )
        return doc

    return _read_and_mutate(p, _update, force=force, dry_run=dry_run)


def crud_delete(
    path: str | Path,
    selector: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete an entry matching *selector* from a .cortex file.

    BLP-005: Uses ArqUX's delete_entry + atomic_write_json.
    Note: ArqUX's delete_entry does NOT have a ``force`` parameter.

    Supports both ``$N/SIGIL:name`` (ArqUX format) and ``SIGIL:name``
    (legacy CODEC format without section prefix).
    """
    p = Path(path)

    def _delete(doc):
        resolved = _resolve_legacy_selector(doc, selector)
        _ax_delete_entry(doc, resolved)
        return doc

    return _read_and_mutate(p, _delete, force=force, dry_run=dry_run)


def crud_move(
    path: str | Path,
    selector: str,
    to_section: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Move an entry from its current section to *to_section*.

    BLP-005: Uses ArqUX's move_entry + atomic_write_json.

    Supports both ``$N/SIGIL:name`` (ArqUX format) and ``SIGIL:name``
    (legacy CODEC format without section prefix).
    """
    p = Path(path)

    def _move(doc):
        resolved = _resolve_legacy_selector(doc, selector)
        _ax_move_entry(doc, resolved, to_section)
        return doc

    return _read_and_mutate(p, _move, force=force, dry_run=dry_run)


def crud_list(
    path: str | Path,
    *,
    section: str | None = None,
    sigil: str | None = None,
) -> dict:
    """List entries in a .cortex file, optionally filtered by section or sigil.

    BLP-005: Uses ArqUX's reader + list_entries.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    entries = _ax_list_entries(doc, section=section, sigil=sigil)

    return {
        "path": str(path),
        "entries": [
            {"sigil": e.get("sigil"), "name": e.get("name"), "section": e.get("section"), "value": e.get("attrs") or e.get("body")}
            for e in entries
        ],
    }


# --- Helpers ----------------------------------------------------------------


def _resolve_legacy_selector(doc: dict, selector: str) -> str:
    """Convert a legacy CODEC selector (``SIGIL:name``) to ArqUX format.

    If *selector* is already in ``$N/SIGIL:name`` format, return as-is.
    If *selector* is in legacy ``SIGIL:name`` format, find the section
    containing the matching entry and return ``$N/SIGIL:name``.

    For wildcard selectors (``SIGIL:*``), returns the first section
    that contains entries with that sigil.

    Raises ``ValueError`` if no matching section is found.
    """
    import re
    # Already in $N/ format?
    if selector.strip().startswith("$"):
        return selector
    # Parse SIGIL:name or SIGIL:* or SIGIL:_
    m = re.match(r"^([A-Za-z][A-Za-z0-9]*):(.+)$", selector.strip())
    if not m:
        raise ValueError(f"Invalid selector: {selector!r}")
    sigil = m.group(1)
    name = m.group(2)

    for sec in doc.get("sections", []):
        for entry in sec.get("entries", []):
            if entry.get("sigil") != sigil:
                continue
            if name in ("*", "_"):
                return f"{sec['id']}/{sigil}:{name}"
            if entry.get("name") == name:
                return f"{sec['id']}/{sigil}:{name}"
    raise ValueError(f"No entries match selector {selector!r}")


def _select_all_sections(doc: dict, selector: str) -> list[dict]:
    """Search all sections for entries matching a legacy CODEC selector.

    Handles selectors without a section prefix:
    - ``SIGIL:name`` → match entries with this sigil and name in any section.
    - ``SIGIL:*`` → match all entries with this sigil in any section.
    - ``SIGIL:_`` → match the first entry with this sigil in any section.

    Returns a list of entry dicts annotated with ``section`` info.
    """
    import re
    # Parse SIGIL:name or SIGIL:* or SIGIL:_
    m = re.match(r"^([A-Za-z][A-Za-z0-9]*):(.+)$", selector.strip())
    if not m:
        return []
    sigil = m.group(1)
    name = m.group(2)

    results: list[dict] = []
    for sec in doc.get("sections", []):
        sec_id = sec.get("id", "")
        for entry in sec.get("entries", []):
            if entry.get("sigil") != sigil:
                continue
            if name in ("*", "_"):
                results.append({
                    "sigil": entry.get("sigil"),
                    "name": entry.get("name"),
                    "section": sec_id,
                    "attrs": entry.get("attrs"),
                    "body": entry.get("body"),
                })
                if name == "_":
                    return results
            elif entry.get("name") == name:
                results.append({
                    "sigil": entry.get("sigil"),
                    "name": entry.get("name"),
                    "section": sec_id,
                    "attrs": entry.get("attrs"),
                    "body": entry.get("body"),
                })
    return results


def _parse_value(value: str | dict) -> str | dict:
    """Parse a value into the form expected by add_entry.

    If *value* is a dict, return it as-is (attrs entry).
    If *value* is a string that looks like attrs (``key:val, key2:val2``),
    attempt to parse it into a dict.
    Otherwise, return the string as-is (cuerpo body entry).
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        # Try to parse as attrs: "key:val, key2:val2"
        # This is a best-effort parse — if it doesn't look like attrs,
        # treat it as a cuerpo body string.
        stripped = value.strip()
        if not stripped:
            return value
        # Heuristic: if it contains key:value pairs with commas, try parsing.
        if ":" in stripped and not stripped.startswith("{"):
            try:
                from ...formats import _parse_attrs
                parsed = _parse_attrs(stripped)
                if parsed:
                    return parsed
            except Exception:
                pass
        return value
    return value


# --- Backward-compatibility alias -------------------------------------------


# BLP-005: _parse_and_mutate was the old name (CODEC-CORTEX era).
# Renamed to _read_and_mutate to reflect the new ArqUX-based implementation.
# Alias kept for backward compatibility with imports in __init__.py / state.py.
_parse_and_mutate = _read_and_mutate
