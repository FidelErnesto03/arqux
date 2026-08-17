"""BLP-003: Atomic file writing for ArqUX CORTEX files.

Replaces cortex.crud.transactions.atomic_write_cortex() with a pure
ArqUX implementation that uses write_cortex_from_json() for serialization.

No dependency on CODEC-CORTEX (``cortex.core`` or ``codec_cortex``).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .writer import write_cortex_from_json

__all__ = [
    "WriteResult",
    "AtomicWriteError",
    "atomic_write_json",
    "atomic_write_text",
]


@dataclass
class WriteResult:
    """Result of an atomic write operation."""
    path: str
    backup: str | None
    bytes_written: int
    diagnostics: list[dict] = field(default_factory=list)
    dry_run: bool = False


class AtomicWriteError(Exception):
    """Raised when atomic write fails."""
    pass


def atomic_write_json(
    doc: dict,
    path: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    keep_backup: bool = True,
) -> WriteResult:
    """Atomically write a JSON doc as CORTEX to path.

    1. Serialize *doc* to CORTEX text using :func:`write_cortex_from_json`.
    2. Write to a unique tmp file (via :func:`tempfile.mkstemp`).
    3. Copy original to ``path.bak`` (if *keep_backup* and file exists).
    4. Rename ``tmp`` → *path* (atomic on POSIX).

    No dependency on CODEC-CORTEX for writing.

    Parameters
    ----------
    doc:
        The JSON/dict document model (see :mod:`arqux.cortex.writer`).
    path:
        Target file path.
    force:
        Reserved for future use (overwrite even if content identical).
    dry_run:
        If ``True``, compute the result without touching the filesystem.
    keep_backup:
        If ``True`` (default), copy the pre-existing file to ``path.bak``.

    Returns
    -------
    WriteResult
        Metadata about the write (bytes, backup path, dry_run flag).

    Raises
    ------
    AtomicWriteError
        On any filesystem failure during the write.
    ValueError
        If *doc* is malformed (propagated from :func:`write_cortex_from_json`).
    """
    # Serialize
    text = write_cortex_from_json(doc)
    return atomic_write_text(text, path, dry_run=dry_run, keep_backup=keep_backup)


def atomic_write_text(
    text: str,
    path: str,
    *,
    dry_run: bool = False,
    keep_backup: bool = True,
) -> WriteResult:
    """Atomically write raw text to *path*.

    1. Write to a unique tmp file (via :func:`tempfile.mkstemp`).
    2. Copy original to ``path.bak`` (if *keep_backup* and file exists).
    3. Rename ``tmp`` → *path* (atomic on POSIX).

    Parameters
    ----------
    text:
        Raw text content to write.
    path:
        Target file path.
    dry_run:
        If ``True``, compute the result without touching the filesystem.
    keep_backup:
        If ``True`` (default), copy the pre-existing file to ``path.bak``.

    Returns
    -------
    WriteResult
        Metadata about the write (bytes, backup path, dry_run flag).

    Raises
    ------
    AtomicWriteError
        On any filesystem failure during the write.
    """
    path = str(Path(path).resolve())
    bytes_to_write = len(text.encode("utf-8"))

    if dry_run:
        return WriteResult(
            path=path,
            backup=None,
            bytes_written=bytes_to_write,
            diagnostics=[],
            dry_run=True,
        )

    # Ensure parent directory exists
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    # Create unique tmp file in same directory (for atomic rename on same filesystem)
    # OBS-005: Use tempfile.mkstemp so concurrent writes don't collide on a
    # predictable ``path + ".tmp"`` name.
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=parent or ".",
            prefix=os.path.basename(path) + ".",
            suffix=".tmp",
        )
        os.close(fd)  # We'll open it ourselves with proper encoding
    except OSError as e:
        raise AtomicWriteError(f"Cannot create tmp file: {e}")

    bak_path = path + ".bak"

    # Write tmp file content with fsync for crash-consistency (OBS-008)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    except OSError as e:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise AtomicWriteError(f"Cannot write tmp file: {e}")

    # OBS-001: Preserve permissions from the original file (best-effort)
    if os.path.exists(path):
        try:
            st = os.stat(path)
            os.chmod(tmp_path, st.st_mode)
        except OSError:
            pass  # best-effort

    # Backup original
    backup_created = None
    if keep_backup and os.path.exists(path):
        try:
            shutil.copy2(path, bak_path)
            backup_created = bak_path
        except OSError as e:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)
            raise AtomicWriteError(f"Cannot create backup: {e}")

    # Atomic rename
    try:
        os.replace(tmp_path, path)
    except OSError as e:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise AtomicWriteError(f"Cannot replace target file: {e}")

    return WriteResult(
        path=path,
        backup=backup_created,
        bytes_written=bytes_to_write,
        diagnostics=[],
        dry_run=False,
    )
