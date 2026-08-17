"""BLP-004: JSON-facing handlers for CORTEX read/write/CRUD.

These handlers accept JSON/dict input and use ArqUX's own
writer, CRUD, and atomic modules. No CODEC-CORTEX dependency
for writing.

Each handler reads a ``.cortex`` file, converts it to the JSON
dict model via :mod:`arqux.cortex.reader`, performs the operation
via :mod:`arqux.cortex.crud`, and writes it back atomically via
:mod:`arqux.cortex.atomic`.
"""

from __future__ import annotations

from pathlib import Path

from .atomic import atomic_write_json
from .crud import add_entry, delete_entry, list_entries, select_entries, update_entry
from .reader import cortex_to_dict

__all__ = [
    "cortex_write_json",
    "cortex_read_json",
    "entry_add_json",
    "entry_update_json",
    "entry_delete_json",
    "entry_list_json",
]


def cortex_write_json(path: str, doc: dict, *, force: bool = False) -> dict:
    """Write a JSON doc as CORTEX to path.

    Parameters
    ----------
    path:
        Target file path.
    doc:
        The JSON/dict document model (see :mod:`arqux.cortex.writer`).
    force:
        Reserved for future use (overwrite even if content identical).

    Returns
    -------
    dict
        ``{"path": ..., "bytes_written": ..., "backup": ..., "dry_run": ...}``
    """
    result = atomic_write_json(doc, path, force=force)
    return {
        "path": result.path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "dry_run": result.dry_run,
    }


def cortex_read_json(path: str, *, section: str | None = None) -> dict:
    """Read a ``.cortex`` file and return as JSON dict.

    Parameters
    ----------
    path:
        File path to read.
    section:
        If given, return only the matching section's entries in the
        ``entries`` field (in addition to the full ``doc``).

    Returns
    -------
    dict
        ``{"path": ..., "doc": {...}, "sections": N, "entries": N}``

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    """
    text = Path(path).read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    sections = doc.get("sections", [])

    if section is not None:
        # Filter to only the requested section
        sections = [s for s in sections if s.get("id") == section]
        doc["sections"] = sections

    total_entries = sum(len(s.get("entries", [])) for s in sections)
    return {
        "path": str(path),
        "doc": doc,
        "sections": len(sections),
        "entries": total_entries,
    }


def entry_add_json(
    path: str,
    section: str,
    sigil: str,
    name: str,
    *,
    attrs: dict | None = None,
    body: str | None = None,
    create_section: bool = False,
) -> dict:
    """Add an entry to a ``.cortex`` file.

    Reads file → dict → ``add_entry`` → atomic write.

    Parameters
    ----------
    path:
        File path to modify.
    section:
        Section id (e.g. ``"$1"``).
    sigil:
        Entry sigil (e.g. ``"LNG"``).
    name:
        Entry name (e.g. ``"test"``).
    attrs:
        Attrs dict for attrs-type entries.  Mutually exclusive with *body*.
    body:
        Body text for cuerpo-type entries.  Mutually exclusive with *attrs*.
    create_section:
        If ``True``, create the section if it doesn't exist.

    Returns
    -------
    dict
        ``{"path": ..., "bytes_written": ..., "backup": ..., "added": "SIGIL:name"}``

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If neither *attrs* nor *body* is provided, or both are.
    """
    if attrs is not None and body is not None:
        raise ValueError("attrs and body are mutually exclusive — provide only one")
    text = Path(path).read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    value = attrs if attrs is not None else body
    add_entry(doc, section, sigil, name, value, create_section=create_section)
    result = atomic_write_json(doc, path)
    return {
        "path": result.path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "added": f"{sigil}:{name}",
    }


def entry_update_json(
    path: str,
    selector: str,
    *,
    set_: dict | None = None,
    replace_body: str | None = None,
    append: bool = False,
) -> dict:
    """Update an entry in a ``.cortex`` file.

    Reads file → dict → ``update_entry`` → atomic write.

    Parameters
    ----------
    path:
        File path to modify.
    selector:
        CORTEX selector (e.g. ``"$1/LNG:test"``).
    set_:
        Attrs to merge into existing attrs (attrs entries only).
    replace_body:
        New body text (cuerpo entries only).
    append:
        If ``True`` and *replace_body* is given, append to existing body.

    Returns
    -------
    dict
        ``{"path": ..., "bytes_written": ..., "backup": ..., "selector": ...}``

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If no entries match, or on type mismatch.
    """
    text = Path(path).read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    update_entry(doc, selector, set_=set_, replace_body=replace_body, append=append)
    result = atomic_write_json(doc, path)
    return {
        "path": result.path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "selector": selector,
    }


def entry_delete_json(path: str, selector: str) -> dict:
    """Delete an entry from a ``.cortex`` file.

    Reads file → dict → ``delete_entry`` → atomic write.

    Parameters
    ----------
    path:
        File path to modify.
    selector:
        CORTEX selector (e.g. ``"$1/LNG:test"``).

    Returns
    -------
    dict
        ``{"path": ..., "bytes_written": ..., "backup": ...,
        "selector": ..., "deleted_count": N}``

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If no entries match.
    """
    text = Path(path).read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    # Count before delete for reporting
    matched = select_entries(doc, selector)
    delete_entry(doc, selector)
    result = atomic_write_json(doc, path)
    return {
        "path": result.path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "selector": selector,
        "deleted_count": len(matched),
    }


def entry_list_json(
    path: str,
    *,
    section: str | None = None,
    sigil: str | None = None,
) -> dict:
    """List entries in a ``.cortex`` file.

    Reads file → dict → ``list_entries``.

    Parameters
    ----------
    path:
        File path to read.
    section:
        If given, filter to this section id.
    sigil:
        If given, filter to this sigil.

    Returns
    -------
    dict
        ``{"path": ..., "entries": [...], "count": N}``

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    """
    text = Path(path).read_text(encoding="utf-8")
    doc = cortex_to_dict(text)
    entries = list_entries(doc, section=section, sigil=sigil)
    return {
        "path": str(path),
        "entries": entries,
        "count": len(entries),
    }
