"""cortex.gc handler — garbage collection for duplicate entries.

Scans a .cortex file for entries with the same sigil:name in the same
section and removes duplicates (conserving the first occurrence).

BLP-002 G-5: Created to address the accumulation of duplicate entries
without any mechanism for automated cleanup.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import crud_delete, crud_list, find_project_root


def gc_handler(
    path: str,
    *,
    dry_run: bool = True,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Garbage-collect duplicate entries in a .cortex file.

    Duplicates are entries that share the same (section, sigil, name).
    With ``dry_run=True`` (default), returns the list of duplicates
    without modifying the file.  With ``dry_run=False`` and
    ``force=True``, removes duplicates, conserving the first occurrence.

    Args:
        path: Path to the .cortex file (e.g., ``brain.cortex``).
        dry_run: If True (default), preview without mutating.
        force: Required to perform the actual deletion.
        ctx: Permission context.

    Returns:
        ``OUT-WORK`` with ``duplicates`` list and ``removed`` count.
    """
    src_path = Path(path)
    if not src_path.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    # List all entries (format=cortex gives raw entry strings we can
    # parse, but we need structured info.  Use format=hcortex for dicts.)
    try:
        result = crud_list(str(src_path), sigil=None, section=None)
    except Exception as exc:
        return CortexOUT.error(str(exc), code="LIST_ERROR")

    entries = result.get("entries", [])

    # Group by (section, sigil, name)
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for e in entries:
        sec = e.get("section", "")
        sigil = e.get("sigil", "")
        name = e.get("name", "")
        if not sigil or not name:
            continue
        groups[(sec, sigil, name)].append(e)

    duplicates: list[dict] = []
    for (sec, sigil, name), group in groups.items():
        if len(group) <= 1:
            continue
        # Keep the first, mark the rest as duplicates
        for dup in group[1:]:
            duplicates.append({
                "section": sec,
                "sigil": sigil,
                "name": name,
                "count": len(group),
                "first_kept": group[0].get("name", str(group[0])),
            })

    if not duplicates:
        return CortexOUT.work(
            f"cortex.gc ok — 0 duplicates found in {path}",
            path=path, dry_run=dry_run, force=force,
            duplicates=[], removed=0,
        )

    if dry_run:
        return CortexOUT.work(
            f"cortex.gc dry_run — {len(duplicates)} duplicate(s) detected",
            path=path, dry_run=True, force=False,
            duplicates=duplicates, removed=0,
        )

    if not force:
        return CortexOUT.error(
            f"{len(duplicates)} duplicates found — pass force=True to remove",
            code="CONFIRM_REQUIRED",
        )

    # Apply: remove duplicates (entries 2..N for each group)
    removed = 0
    failed = 0
    for dup in duplicates:
        sec = dup["section"]
        sigil = dup["sigil"]
        name = dup["name"]
        selector = f"{sec}/{sigil}:{name}" if sec else f"{sigil}:{name}"
        try:
            del_result = crud_delete(str(src_path), selector, force=True)
            if "error" in del_result:
                failed += 1
            else:
                removed += 1
        except Exception:
            failed += 1

    # PULSE.
    try:
        root = find_project_root(start=path)
        if root is not None:
            agent = (ctx or PermissionContext.from_env()).agent_id
            event_id = next_pulse_event_id(root)
            append_pulse_to_brain(
                root,
                event_id=event_id,
                task_id="-",
                kind="handler_call",
                agent=agent,
                payload=f"[cortex.gc] removed={removed} failed={failed}",
            )
    except Exception:
        pass

    return CortexOUT.work(
        f"cortex.gc ok — {removed} duplicate(s) removed (failed={failed})",
        path=path, dry_run=False, force=True,
        duplicates=duplicates, removed=removed, failed=failed,
    )
