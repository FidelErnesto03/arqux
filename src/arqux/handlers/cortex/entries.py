"""Cortex entry CRUD and file validation handlers."""

from __future__ import annotations

import json as _json
import re as _re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...cortex.parse_content import parse_content_entry
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import (
    _cc_parser,
    _cc_transactions,
    crud_add,
    crud_delete,
    crud_list,
    crud_move,
    crud_read,
    crud_update,
)
from .read_write import _next_number


def entry_get_handler(
    path: str,
    selector: str,
    *,
    format: str = "hcortex",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read entries matching a CORTEX selector from a .cortex file.

    Two output formats (BLP-005):

    - ``format="hcortex"`` (default, canal E): renders entries as
      human-readable markdown dicts. This is the legacy behaviour.
    - ``format="cortex"`` (canal I): returns entries as raw CORTEX
      entry strings (``SIGIL:name{...}``). Used for handler-to-handler
      communication.
    """
    if format not in ("hcortex", "cortex"):
        return CortexOUT.error(
            f"invalid format={format!r} (must be 'hcortex' or 'cortex')",
            code="INVALID_ARGS",
        )

    try:
        result = crud_read(path, selector)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    entries = result.get("entries", [])
    if format == "cortex":
        # Render each entry as a raw CORTEX entry string.
        entries_out = [_entry_to_cortex(e) for e in entries]
        return CortexOUT.work(
            f"entry.get ok path={path} selector={selector} count={len(entries_out)} format=cortex",
            path=path,
            selector=selector,
            format="cortex",
            count=len(entries_out),
            entries=entries_out,
        )

    # Default HCORTEX format (legacy).
    return CortexOUT.work(
        f"entry.get ok path={path} selector={selector} count={len(entries)}",
        path=path,
        selector=selector,
        format="hcortex",
        count=len(entries),
        entries=entries,
    )


def _entry_to_cortex(entry: dict[str, Any]) -> str:
    """Render a parsed entry dict back as a CORTEX entry string."""
    if not isinstance(entry, dict):
        return ""
    sigil = entry.get("sigil", "")
    name = entry.get("name", "")
    value = entry.get("value")
    if isinstance(value, dict):
        attrs = ", ".join(
            f'{k}:{_quote_attr(v)}' for k, v in value.items()
        )
        return f"{sigil}:{name}{{{attrs}}}"
    if isinstance(value, str) and value:
        # cuerpo / bloque entry.
        return f"{sigil}:{name}{{{value}}}"
    return f"{sigil}:{name}"


def _quote_attr(val: Any) -> str:
    """Quote a value for CORTEX attrs output."""
    s = str(val)
    if s == "":
        return '""'
    if any(c in s for c in (" ", ",", '"', "'", "{", "}")):
        escaped = s.replace('"', '\\"')
        return f'"{escaped}"'
    return s


def entry_add_handler(
    path: str,
    section: str,
    sigil: str,
    name: str,
    value: str,
    *,
    content: str | None = None,
    create_section: bool = False,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Add a new entry to a .cortex file.

    Automatically appends a sequential _XXXX suffix to the name
    (per-section counter) to prevent silent overwrites.

    BLP-005: ``content`` accepts a CORTEX entry string of the form
    ``$N:{sigil:name{key:val,...}}`` or ``sigil:name{key:val,...}``.
    When provided, fields extracted from ``content`` override the
    individual ``section``, ``sigil``, ``name`` and ``value`` params
    (merge rule: content wins).
    """
    # Merge content CORTEX (canal I) over individual params.
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            sigil = parsed.get("__sigil__", sigil)
            name = parsed.get("__name__", name)
            # Strip the meta keys before serialising the value body.
            body_keys = {k: v for k, v in parsed.items()
                         if k not in ("__sigil__", "__name__")}
            if body_keys:
                # crud_add expects the attrs body WITHOUT outer braces
                # (e.g. 'key:val, key2:val2'). The braces are added by
                # the writer.
                value = ", ".join(
                    f'{k}:{_quote_attr(v)}' for k, v in body_keys.items()
                )

    suffix = _next_number(path, section)
    numbered_name = f"{name}{suffix}"

    try:
        result = crud_add(path, section, sigil, numbered_name, value, create_section=create_section, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="ADD_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.add ok path={path} {sigil}:{numbered_name} in {section}",
        path=path, section=section, sigil=sigil, name=numbered_name,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_update_handler(
    path: str,
    selector: str,
    *,
    set_: str | None = None,
    replace_body: str | None = None,
    append: bool = False,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update an entry selected by a CORTEX selector.

    For attrs entries: pass ``set_`` as JSON key:value pairs (e.g. ``status:done,priority:high``).
    For cuerpo entries: pass ``replace_body`` with the new body text.
    """
    set_dict = None
    if set_:
        try:
            set_dict = _json.loads(f"{{{set_}}}")
        except _json.JSONDecodeError:
            try:
                set_dict = {}
                for pair in set_.split(","):
                    pair = pair.strip()
                    if ":" not in pair:
                        continue
                    k, v = pair.split(":", 1)
                    k = k.strip().strip('"').strip("'")
                    v = v.strip().strip('"').strip("'")
                    set_dict[k] = v
            except Exception:
                return CortexOUT.error(f"invalid set_ format: {set_}", code="INVALID_ARGS")

    try:
        result = crud_update(path, selector, set_=set_dict, replace_body=replace_body, append=append, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="UPDATE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.update ok path={path} selector={selector}",
        path=path, selector=selector,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_delete_handler(
    path: str,
    selector: str,
    *,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Delete an entry matching a CORTEX selector from a .cortex file."""
    try:
        result = crud_delete(path, selector, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="DELETE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.delete ok path={path} selector={selector}",
        path=path, selector=selector,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_move_handler(
    path: str,
    selector: str,
    to_section: str,
    *,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Move an entry between sections in a .cortex file."""
    try:
        result = crud_move(path, selector, to_section, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="MOVE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="CRUD_ERROR")
    return CortexOUT.work(
        f"entry.move ok path={path} selector={selector} to={to_section}",
        path=path, selector=selector, to_section=to_section,
        bytes_written=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_list_handler(
    path: str,
    *,
    section: str | None = None,
    sigil: str | None = None,
    format: str = "hcortex",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List entries in a .cortex file, optionally filtered by section or sigil.

    BLP-005: ``format`` selects the output representation:

    - ``format="hcortex"`` (default, canal E): returns parsed entry
      dicts (legacy behaviour).
    - ``format="cortex"`` (canal I): returns raw CORTEX entry strings
      for handler-to-handler communication.
    """
    if format not in ("hcortex", "cortex"):
        return CortexOUT.error(
            f"invalid format={format!r} (must be 'hcortex' or 'cortex')",
            code="INVALID_ARGS",
        )

    try:
        result = crud_list(path, section=section, sigil=sigil)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="LIST_ERROR")

    entries = result.get("entries", [])
    if format == "cortex":
        entries_out = [_entry_to_cortex(e) for e in entries]
        return CortexOUT.work(
            f"entry.list ok path={path} count={len(entries_out)} format=cortex",
            path=path, section=section, sigil=sigil,
            format="cortex",
            count=len(entries_out),
            entries=entries_out,
        )

    return CortexOUT.work(
        f"entry.list ok path={path} count={len(entries)}",
        path=path, section=section, sigil=sigil,
        format="hcortex",
        count=len(entries),
        entries=entries,
    )


def file_validate_handler(
    path: str,
    fix: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Scan a .cortex file for duplicate entry names and optionally fix them.

    Groups entries by (section, sigil, name). When multiple entries share
    the same name in the same section, they are flagged as duplicates.
    With fix=true, duplicates are renamed with a _XXXX suffix.
    """

    target = Path(path)
    if not target.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    try:
        text = target.read_text(encoding="utf-8")
        doc = _cc_parser.parse_cortex(text, path=str(path))
    except Exception as exc:
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    def _strip_suffix(n: str) -> str:
        return _re.sub(r"_\d{4}$", "", n)

    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    for sec in doc.sections:
        for entry in sec.entries or []:
            base = _strip_suffix(entry.name)
            groups[(sec.id, entry.sigil, base)].append({
                "section": sec.id,
                "sigil": entry.sigil,
                "name": entry.name,
                "base": base,
                "entry": entry,
            })

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}
    if not duplicates:
        return CortexOUT.work(
            f"file.validate ok — 0 duplicates found in {path}",
            path=path, fix=fix, total_duplicates=0,
        )

    report = []
    for (sec_id, sigil, base), entries in sorted(duplicates.items()):
        for idx, e in enumerate(entries):
            new_name = f"{base}_{idx + 1:04d}"
            if e["name"] != new_name:
                report.append({
                    "section": sec_id,
                    "sigil": sigil,
                    "old_name": e["name"],
                    "new_name": new_name,
                })

    if not fix:
        return CortexOUT.work(
            f"file.validate ok — {len(report)} duplicate(s) detected (dry-run, fix=false)",
            path=path, fix=fix, total_duplicates=len(report),
            duplicates=report,
        )

    for r in report:
        for sec in doc.sections:
            if sec.id != r["section"]:
                continue
            for ent in sec.entries or []:
                if ent.name == r["old_name"]:
                    ent.name = r["new_name"]
                    break

    try:
        result = _cc_transactions.atomic_write_cortex(doc, str(target), force=True)
        return CortexOUT.work(
            f"file.validate ok — {len(report)} duplicate(s) renamed",
            path=path, fix=fix, total_duplicates=len(report),
            renamed=report,
            bytes_written=result.bytes_written,
            backup=result.backup,
        )
    except Exception as exc:
        return CortexOUT.error(str(exc), code="VALIDATION_FAILED")
