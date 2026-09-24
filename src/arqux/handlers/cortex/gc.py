"""cortex.gc handler — garbage collection for duplicate entries.

Scans a .cortex file for entries with the same sigil:name in the same
section and removes duplicates (conserving the first ``first_kept``
occurrences).

BLP-002 G-5: Created to address the accumulation of duplicate entries
without any mechanism for automated cleanup.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ...cortex.atomic import atomic_write_json
from ...cortex.reader import cortex_to_dict
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root


def gc_handler(
    path: str,
    *,
    dry_run: bool = True,
    force: bool = False,
    first_kept: int = 1,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Garbage-collect duplicate entries in a .cortex file.

    Duplicates are entries that share the same (section, sigil, name).
    With ``dry_run=True`` (default), returns the list of duplicates
    without modifying the file.  With ``dry_run=False`` and
    ``force=True``, removes duplicates, conserving the first
    ``first_kept`` occurrences.

    Args:
        path: Path to the .cortex file (e.g., ``brain.cortex``).
        dry_run: If True (default), preview without mutating.
        force: Required to perform the actual deletion.
        first_kept: Number of occurrences to keep per duplicate group.
        ctx: Permission context.

    Returns:
        ``OUT-WORK`` with ``duplicates`` list and ``removed`` count.
        ``bytes_written``/``file_bytes`` report the whole file size after
        the rewrite (unlike ``entry.add``, where ``bytes_written`` is the
        serialized entry size).
    """
    src_path = Path(path)
    if not src_path.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")

    try:
        doc = cortex_to_dict(src_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    try:
        first_kept = max(1, int(first_kept))
    except (TypeError, ValueError):
        return CortexOUT.error(
            f"invalid first_kept={first_kept!r} (must be an integer >= 1)",
            code="INVALID_ARGS",
        )

    duplicates: list[dict] = []
    for sec in doc.get("sections", []):
        sec_id = sec.get("id", "")
        entries = sec.get("entries", [])
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for idx, entry in enumerate(entries):
            sigil = entry.get("sigil", "")
            name = entry.get("name", "")
            if not sigil or not name:
                continue
            groups[(sigil, name)].append(idx)
        drop: set[int] = set()
        for (sigil, name), idxs in groups.items():
            if len(idxs) <= first_kept:
                continue
            for idx in idxs[first_kept:]:
                drop.add(idx)
                duplicates.append({
                    "section": sec_id,
                    "sigil": sigil,
                    "name": name,
                    "count": len(idxs),
                    "first_kept": first_kept,
                    "kept_names": [entries[i].get("name", name) for i in idxs[:first_kept]],
                })
        if drop:
            sec["entries"] = [
                e for i, e in enumerate(entries) if i not in drop
            ]

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

    try:
        result = atomic_write_json(doc, str(src_path))
        removed = len(duplicates)
        failed = 0
    except Exception:
        return CortexOUT.error(
            f"cortex.gc failed — 0 of {len(duplicates)} duplicate(s) removed",
            code="GC_ERROR",
        )

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
        bytes_written=result.bytes_written,
        file_bytes=result.bytes_written,
        backup=result.backup,
    )
