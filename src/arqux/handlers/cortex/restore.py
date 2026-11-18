"""cortex.restore_backup — sanctioned restore from a .bak generation.

Backup protocol (issue
2026-11-17-protocolo-oficial-de-copias-de-respaldo-bak-bak-):

- Writers (``arqux/cortex/atomic.py``) keep exactly two generations next
  to every governed .cortex file: ``<name>.bak`` (the state immediately
  before the last write) and ``<name>.bak.1`` (the generation before
  that). Both are safety nets for the last write, NOT history — history
  lives in PULSE/timelog and in ``arqux backup`` tarballs.
- Manual copy/rename of a .bak over its target is FORBIDDEN
  (AXM:no_direct_edit). This handler is the only sanctioned restore path:
  it validates the backup first, acquires the same lock the writers use,
  rotates the current state into the backup chain, and replaces the
  target atomically.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path

from ...concurrency import reentrant_file_lock
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import cortex_read

MAX_GENERATION = 1  # .bak (0) and .bak.1 (1) — matches atomic.py rotation.


def _mtime(path: Path) -> str:
    with contextlib.suppress(OSError):
        return path.stat().st_mtime.__str__()
    return ""


def restore_backup_handler(
    path: str,
    generation: int = 0,
    dry_run: bool = True,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Restore a .cortex file from its .bak / .bak.1 generation.

    Default is a dry-run preview (no mutation). Pass dry_run=False and
    force=True to apply. The current state is rotated into the backup
    chain before the restore, so the pre-restore state is never lost.
    """
    if generation not in (0, 1):
        return CortexOUT.error(
            f"invalid generation={generation} (must be 0 for .bak or 1 for .bak.1)",
            code="INVALID_ARGS",
        )

    target = Path(path).resolve()
    name = target.name
    for suffix in (".bak.1", ".bak"):
        if name.endswith(suffix):
            target = target.with_name(name[: -len(suffix)])
            break
    bak = target.with_name(target.name + (".bak" if generation == 0 else ".bak.1"))

    if not bak.exists():
        return CortexOUT.error(f"backup not found: {bak}", code="NOT_FOUND")

    # Validate the backup parses before offering it as a restore source.
    try:
        parsed = cortex_read(bak)
    except FileNotFoundError:
        return CortexOUT.error(f"backup not found: {bak}", code="NOT_FOUND")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(
            f"backup is not parseable as CORTEX, restore aborted: {exc}",
            code="VALIDATION_FAILED",
        )

    entry_count = sum(len(s.get("entries", [])) for s in parsed.get("sections", []))
    details = {
        "target": str(target),
        "source": str(bak),
        "generation": generation,
        "source_bytes": bak.stat().st_size,
        "source_mtime": _mtime(bak),
        "source_sections": len(parsed.get("sections", [])),
        "source_entries": entry_count,
        "target_exists": target.exists(),
        "target_bytes": target.stat().st_size if target.exists() else None,
    }

    if dry_run:
        return CortexOUT.work(
            f"cortex.restore_backup preview target={target.name} source={bak.name} "
            f"entries={entry_count} (dry_run — pass dry_run=False force=True to apply)",
            dry_run=True,
            **details,
        )

    if not force:
        return CortexOUT.error(
            "refusing to restore without force=True (deliberate recovery operation)",
            code="FORCE_REQUIRED",
        )
    if not target.exists():
        return CortexOUT.error(
            f"target not found: {target} (restore only replaces an existing file)",
            code="NOT_FOUND",
        )

    # Same lock the writers use (core/state/_crud.py), so a concurrent
    # write cannot interleave with the rotation + replace.
    with reentrant_file_lock(target.with_name(target.name + ".lock")):
        fd, tmp_path = tempfile.mkstemp(
            dir=target.parent, prefix=target.name + ".", suffix=".restore"
        )
        os.close(fd)
        try:
            # 1. Snapshot the backup we are about to restore from.
            shutil.copy2(bak, tmp_path)
            # 2. Rotate the current state into the chain (.bak -> .bak.1,
            #    target -> .bak): the pre-restore state survives the restore.
            current_bak = target.with_name(target.name + ".bak")
            previous_bak = current_bak.with_name(current_bak.name + ".1")
            if current_bak.exists():
                with contextlib.suppress(OSError):
                    os.replace(current_bak, previous_bak)
            shutil.copy2(target, current_bak)
            # 3. Atomic replace of the target with the backup content.
            os.replace(tmp_path, target)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)
            return CortexOUT.error(f"restore failed: {exc}", code="RESTORE_FAILED")

    return CortexOUT.work(
        f"cortex.restore_backup ok target={target.name} restored_from={bak.name} "
        f"entries={entry_count} (pre-restore state rotated to {current_bak.name})",
        dry_run=False,
        rotated_to=str(current_bak),
        **details,
    )


handler_schemas = [
    {
        "name": "cortex.restore_backup",
        "fn": restore_backup_handler,
        "description": (
            "Restore a .cortex file from its .bak (generation=0, default) or "
            ".bak.1 (generation=1) backup — the ONLY sanctioned restore path "
            "(manual copy/rename is forbidden, AXM:no_direct_edit). Validates "
            "the backup first; dry_run=True (default) previews without "
            "mutating; applying requires dry_run=False and force=True. The "
            "pre-restore state is rotated into the backup chain, never lost. "
            "Backups are a safety net for the last write, not history — for "
            "history use PULSE/timelog or arqux backup tarballs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the .cortex file (or to its .bak/.bak.1).",
                },
                "generation": {
                    "type": "integer",
                    "enum": [0, 1],
                    "default": 0,
                    "description": "0 = .bak (most recent), 1 = .bak.1.",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": True,
                    "description": "Preview without mutating (default true).",
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Required (with dry_run=False) to apply the restore.",
                },
            },
            "required": ["path"],
        },
    },
]
