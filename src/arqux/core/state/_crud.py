"""CRUD operations on .cortex files via CODEC-CORTEX."""

from __future__ import annotations

from pathlib import Path

from . import (
    _cc_mutations,
    _cc_parser,
    _cc_renderer,
    _cc_selectors,
    _cc_transactions,
    _cc_validator,
)

# --- CODEC-CORTEX dependency ------------------------------------------------


def requires_codec_cortex() -> None:
    """Raise RuntimeError if CODEC-CORTEX is not available."""
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

    Validates before writing. Returns the write result dict.

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = str(Path(path).resolve())
    doc = _cc_parser.parse_cortex(content, path=path)
    diags = _cc_validator.validate(doc)
    errors = [d for d in diags if d.get("severity") == "error"]
    if errors and not force:
        return {
            "path": path,
            "error": f"Validation failed ({len(errors)} errors). Use force=True to override.",
            "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')} (line {d.get('line','?')})" for d in errors],
        }

    result = _cc_transactions.atomic_write_cortex(doc, path, force=force)
    return {
        "path": path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "diagnostics": [str(d) for d in result.diagnostics] if result.diagnostics else [],
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


# --- _cortex_crud -- partial file mutation via CODEC-CORTEX CRUD -----------


def _parse_and_mutate(
    path: Path,
    mutate_fn,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Parse a .cortex file, apply *mutate_fn* on the AST, validate and write.

    *mutate_fn* receives the parsed ``CortexDocument`` and returns it (modified).
    """
    requires_codec_cortex()
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    doc = mutate_fn(doc)
    diags = _cc_validator.validate(doc)
    errors = [d for d in diags if d.get("severity") == "error"]
    if errors and not force:
        return {
            "error": f"Validation failed ({len(errors)} errors). Use force=True to override.",
            "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')}" for d in errors],
        }
    if dry_run:
        return {"dry_run": True, "path": str(path), "diagnostics": diags}
    try:
        result = _cc_transactions.atomic_write_cortex(doc, str(path), force=force)
    except Exception as e:
        return {"error": f"Atomic write failed: {e}", "non_bypassable": True}

    # P1-P: Auto-sign .cortex files with $INTEGRITY header after successful write.
    # NOTE: Auto-signing is intentionally disabled here because codec-cortex
    # writes files with its own format and re-reading them with $INTEGRITY
    # header prepended breaks subsequent parses. Auto-signing should be
    # applied at a higher level (e.g. via `arqux cortex-verify --sign` CLI
    # or post-commit hook). See EVIDENCE.md §5.1 for file-level integrity.
    #
    # To re-enable auto-signing in the future, ensure codec-cortex can
    # tolerate a `# $INTEGRITY: sha256:...` header line at the top of files
    # (or strip it before parsing).

    return {
        "path": str(path),
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "diagnostics": [str(d) for d in result.diagnostics] if result.diagnostics else [],
    }


def crud_read(path: str | Path, selector: str) -> dict:
    """Read entries matching *selector* from a .cortex file.

    Returns a dict with ``entries`` (list of matched entries).
    """
    requires_codec_cortex()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    _cc_selectors.parse_selector(selector)
    entries = _cc_selectors.select(doc, selector)
    return {
        "path": str(path),
        "selector": selector,
        "entries": [
            {"sigil": e.sigil, "name": e.name, "section": e.section, "value": e.value}
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

    Returns the write result dict.
    """
    p = Path(path)

    def _add(doc):
        _cc_mutations.add_entry(
            doc, section, sigil, name, value,
            create_section=create_section,
        )
        return doc

    return _parse_and_mutate(p, _add, force=force, dry_run=dry_run)


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

    For attrs entries use ``set_`` (dict of key/value pairs to merge).
    For cuerpo/bloque entries use ``replace_body``.
    """
    p = Path(path)

    def _update(doc):
        _cc_mutations.update_entry(
            doc, selector,
            set_=set_, replace_body=replace_body, append=append,
        )
        return doc

    return _parse_and_mutate(p, _update, force=force, dry_run=dry_run)


def crud_delete(
    path: str | Path,
    selector: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete an entry matching *selector* from a .cortex file."""
    p = Path(path)

    def _delete(doc):
        _cc_mutations.delete_entry(doc, selector, force=force)
        return doc

    return _parse_and_mutate(p, _delete, force=force, dry_run=dry_run)


def crud_move(
    path: str | Path,
    selector: str,
    to_section: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Move an entry from its current section to *to_section*."""
    p = Path(path)

    def _move(doc):
        _cc_mutations.move_entry(doc, selector, to_section)
        return doc

    return _parse_and_mutate(p, _move, force=force, dry_run=dry_run)


def crud_list(
    path: str | Path,
    *,
    section: str | None = None,
    sigil: str | None = None,
) -> dict:
    """List entries in a .cortex file, optionally filtered by section or sigil."""
    requires_codec_cortex()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))

    sel_parts = []
    if section:
        sel_parts.append(section)
    s = "/".join(sel_parts)
    sep = "/" if s else ""
    if sigil:
        s += f"{sep}{sigil}:*"
    else:
        s += f"{sep}*"
    entries = _cc_selectors.select(doc, s)

    return {
        "path": str(path),
        "entries": [
            {"sigil": e.sigil, "name": e.name, "section": e.section, "value": e.value}
            for e in entries
        ],
    }
