"""Cortex entry CRUD and file validation handlers."""

from __future__ import annotations

import json as _json
import re as _re
from collections import defaultdict
from pathlib import Path
from typing import Any

# BLP-005: Use ArqUX's own atomic writer instead of CODEC-CORTEX transactions.
from ...cortex.atomic import atomic_write_json
from ...cortex.parse_content import parse_content_entry
from ...cortex.reader import cortex_to_dict
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import (
    crud_add,
    crud_delete,
    crud_list,
    crud_move,
    crud_read,
    crud_update,
)
from .read_write import _next_number

DEFAULT_LIST_LIMIT = 50


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
        # cuerpo / bloque entry — collapse newlines so the rendering
        # stays one line (compact format contract).
        body = " ".join(value.split("\n"))
        return f"{sigil}:{name}{{{body}}}"
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


def _crud_error(result: dict[str, Any], code: str) -> CortexOUT:
    """Enumerate crud diagnostics (index + message) and surface non_bypassable."""
    diagnostics = result.get("diagnostics") or []
    message = result["error"]
    if diagnostics:
        message += " " + " ".join(
            f"[{i}] {d}" for i, d in enumerate(diagnostics, 1)
        )
    return CortexOUT.error(
        message,
        code=code,
        error_count=len(diagnostics),
        diagnostics=diagnostics,
        non_bypassable=bool(result.get("non_bypassable")),
    )


def entry_add_handler(
    path: str,
    section: str,
    sigil: str,
    name: str,
    value: str | None = None,
    *,
    content: str | None = None,
    create_section: bool = False,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Add a new entry to a .cortex file.

    Stores the entry under the requested name. When ``sigil:name``
    already exists in the section, appends a sequential ``_XXXX``
    suffix and reports the rename explicitly via the ``requested``
    and ``renamed`` fields (BLP-007: no silent renames).

    BLP-005: ``content`` accepts a CORTEX entry string of the form
    ``$N:{sigil:name{key:val,...}}`` or ``sigil:name{key:val,...}``.
    When provided, fields extracted from ``content`` override the
    individual ``section``, ``sigil``, ``name`` and ``value`` params
    (merge rule: content wins). ``value`` is optional when ``content``
    parses as CORTEX.

    Output metrics: ``bytes_written``/``entry_bytes`` report the size of
    the serialized entry as written on disk (writer's form, quoting
    included); ``file_bytes`` reports the whole file size.
    """
    # Normalise section so empty/None is treated as absent (BLP-017).
    if section is None:
        section = ""
    # Merge content CORTEX (canal I) over individual params.
    content_ignored: list[str] = []
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            sigil = parsed.get("__sigil__", sigil)
            name = parsed.get("__name__", name)
            # BLP-017: derive section from content's $N: prefix when the
            # positional section is absent. Explicit section always wins.
            if not section and parsed.get("__section__"):
                section = parsed["__section__"]
            # Strip the meta keys before serialising the value body.
            body_keys = {k: v for k, v in parsed.items()
                         if k not in ("__sigil__", "__name__", "__section__")}
            if body_keys:
                # crud_add expects the attrs body WITHOUT outer braces
                # (e.g. 'key:val, key2:val2'). The braces are added by
                # the writer.
                value = ", ".join(
                    f'{k}:{_quote_attr(v)}' for k, v in body_keys.items()
                )
        else:
            content_ignored = ["<content did not parse>"]
    if value is None:
        return CortexOUT.error(
            "value is required when content is absent or does not parse as CORTEX",
            code="INVALID_ARGS",
        )

    requested_name = name
    numbered_name = name
    while _entry_exists(path, section, sigil, numbered_name):
        numbered_name = f"{requested_name}{_next_number(path, section)}"

    try:
        result = crud_add(path, section, sigil, numbered_name, value, create_section=create_section, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="ADD_ERROR")

    if "error" in result:
        return _crud_error(result, "CRUD_ERROR")

    renamed = numbered_name != requested_name
    message = f"entry.add ok path={path} {sigil}:{numbered_name} in {section}"
    if renamed:
        message += f" renamed:{requested_name}->{numbered_name}"
    # entry_text is the writer-serialized entry (crud_add renders it via
    # the same _format_entry the writer uses), so entry_bytes matches the
    # bytes actually on disk even when quoting normalization kicks in.
    entry_text = result.get("entry_text", f"{sigil}:{numbered_name}{{{value}}}")
    file_bytes = result.get("bytes_written")
    fields: dict[str, Any] = {
        "path": path, "section": section, "sigil": sigil, "name": numbered_name,
        "bytes_written": len(entry_text.encode("utf-8")),
        "entry_bytes": len(entry_text.encode("utf-8")),
        "file_bytes": file_bytes,
        "backup": result.get("backup"),
    }
    if content_ignored:
        fields["content_ignored"] = content_ignored
    if force:
        fields["applied"] = entry_text
    if renamed:
        fields["requested"] = requested_name
        fields["renamed"] = numbered_name
    return CortexOUT.work(message, **fields)


def _entry_exists(path: str, section: str, sigil: str, name: str) -> bool:
    """True if ``sigil:name`` is already present in *section* of *path*.

    Read failures are treated as "no collision" — ``crud_add`` surfaces the
    real error (e.g. NOT_FOUND) afterwards.
    """
    try:
        selector = f"{section}/{sigil}:{name}" if section else f"{sigil}:{name}"
        found = crud_read(path, selector)
    except Exception:
        return False
    return any(e.get("name") == name for e in found.get("entries", []))


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

    Output metrics: ``bytes_written``/``file_bytes`` report the whole file
    size after the rewrite (unlike ``entry.add``, where ``bytes_written``
    is the serialized entry size).
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
        return _crud_error(result, "CRUD_ERROR")
    return CortexOUT.work(
        f"entry.update ok path={path} selector={selector}",
        path=path, selector=selector,
        bytes_written=result.get("bytes_written"),
        file_bytes=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_delete_handler(
    path: str,
    selector: str,
    *,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Delete an entry matching a CORTEX selector from a .cortex file.

    Output metrics: ``bytes_written``/``file_bytes`` report the whole file
    size after the rewrite (unlike ``entry.add``, where ``bytes_written``
    is the serialized entry size).
    """
    try:
        result = crud_delete(path, selector, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="DELETE_ERROR")

    if "error" in result:
        return _crud_error(result, "CRUD_ERROR")
    return CortexOUT.work(
        f"entry.delete ok path={path} selector={selector}",
        path=path, selector=selector,
        bytes_written=result.get("bytes_written"),
        file_bytes=result.get("bytes_written"),
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
    """Move an entry between sections in a .cortex file.

    Output metrics: ``bytes_written``/``file_bytes`` report the whole file
    size after the rewrite (unlike ``entry.add``, where ``bytes_written``
    is the serialized entry size).
    """
    try:
        result = crud_move(path, selector, to_section, force=force)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="MOVE_ERROR")

    if "error" in result:
        return _crud_error(result, "CRUD_ERROR")
    return CortexOUT.work(
        f"entry.move ok path={path} selector={selector} to={to_section}",
        path=path, selector=selector, to_section=to_section,
        bytes_written=result.get("bytes_written"),
        file_bytes=result.get("bytes_written"),
        backup=result.get("backup"),
    )


def entry_list_handler(
    path: str,
    *,
    section: str | None = None,
    sigil: str | None = None,
    format: str = "hcortex",
    limit: int | None = None,
    offset: int = 0,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List entries in a .cortex file, optionally filtered by section or sigil.

    BLP-005: ``format`` selects the output representation:

    - ``format="hcortex"`` (default, canal E): returns parsed entry
      dicts (legacy behaviour).
    - ``format="cortex"`` (canal I): returns raw CORTEX entry strings
      for handler-to-handler communication.
    - ``format="compact"``: one raw CORTEX entry per line in
      ``content`` — avoids giant single-line dict payloads.

    Output is paginated: ``limit`` (default 50) entries per page starting
    at ``offset``. Fields ``total``, ``returned``, ``offset`` and
    ``next_offset`` report the pagination state (``next_offset`` is None
    on the last page).
    """
    if format not in ("hcortex", "cortex", "compact"):
        return CortexOUT.error(
            f"invalid format={format!r} (must be 'hcortex', 'cortex' or 'compact')",
            code="INVALID_ARGS",
        )

    try:
        limit_i = DEFAULT_LIST_LIMIT if limit is None else int(limit)
        offset_i = int(offset)
    except (TypeError, ValueError):
        return CortexOUT.error(
            "limit and offset must be integers", code="INVALID_ARGS"
        )
    if limit_i < 1 or offset_i < 0:
        return CortexOUT.error(
            "limit must be >= 1 and offset must be >= 0", code="INVALID_ARGS"
        )

    try:
        result = crud_list(path, section=section, sigil=sigil)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except Exception as exc:
        return CortexOUT.error(str(exc), code="LIST_ERROR")

    entries = result.get("entries", [])
    total = len(entries)
    page = entries[offset_i : offset_i + limit_i]
    next_offset = offset_i + limit_i if offset_i + limit_i < total else None
    pagination = {
        "total": total,
        "returned": len(page),
        "offset": offset_i,
        "next_offset": next_offset,
    }

    if format == "compact":
        content = "\n".join(_entry_to_cortex(e) for e in page)
        return CortexOUT.work(
            f"entry.list ok path={path} count={len(page)} format=compact",
            path=path, section=section, sigil=sigil,
            format="compact",
            count=len(page),
            content=content,
            **pagination,
        )

    if format == "cortex":
        entries_out = [_entry_to_cortex(e) for e in page]
        return CortexOUT.work(
            f"entry.list ok path={path} count={len(entries_out)} format=cortex",
            path=path, section=section, sigil=sigil,
            format="cortex",
            count=len(entries_out),
            entries=entries_out,
            **pagination,
        )

    return CortexOUT.work(
        f"entry.list ok path={path} count={len(page)}",
        path=path, section=section, sigil=sigil,
        format="hcortex",
        count=len(page),
        entries=page,
        **pagination,
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

    BLP-005: Uses ArqUX's own reader + atomic_write_json instead of
    CODEC-CORTEX transactions.
    """

    target = Path(path)
    if not target.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    try:
        text = target.read_text(encoding="utf-8")
        doc = cortex_to_dict(text)
    except Exception as exc:
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    def _strip_suffix(n: str) -> str:
        return _re.sub(r"_\d{4}$", "", n)

    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    for sec in doc.get("sections", []):
        sec_id = sec.get("id", "")
        for entry in sec.get("entries", []):
            entry_name = entry.get("name", "")
            entry_sigil = entry.get("sigil", "")
            base = _strip_suffix(entry_name)
            groups[(sec_id, entry_sigil, base)].append({
                "section": sec_id,
                "sigil": entry_sigil,
                "name": entry_name,
                "base": base,
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

    # Apply renames in the dict model.
    for r in report:
        for sec in doc.get("sections", []):
            if sec.get("id") != r["section"]:
                continue
            for ent in sec.get("entries", []):
                if ent.get("name") == r["old_name"]:
                    ent["name"] = r["new_name"]
                    break

    try:
        result = atomic_write_json(doc, str(target))
        return CortexOUT.work(
            f"file.validate ok — {len(report)} duplicate(s) renamed",
            path=path, fix=fix, total_duplicates=len(report),
            renamed=report,
            bytes_written=result.bytes_written,
            backup=result.backup,
        )
    except Exception as exc:
        return CortexOUT.error(str(exc), code="VALIDATION_FAILED")
