"""arqux backup / restore — governance state backup and recovery (BLP-011).

Usage:
    arqux backup              → creates arqux-<timestamp>.tar.gz + .sha256
    arqux restore <file>      → verifies hash, backs up current state, restores
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ARQUX_DIR, PRODUCT_NAME
from .cortex_out import CortexOUT
from .state import find_workspace_root

EXCLUDE_PATTERNS = (
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pulse.jsonl",
    "*.bak",
    "*.tmp",
    ".DS_Store",
)


def _should_exclude(name: str) -> bool:
    import fnmatch
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_PATTERNS)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_workspace_root(path: str | None = None) -> Path | None:
    ws = find_workspace_root(start=path)
    if ws is None:
        return None
    return ws.parent  # Return workspace root (parent of .arqux/)


def backup(path: str | None = None, ctx: Any = None) -> CortexOUT:
    """Create a timestamped .tar.gz backup of .arqux/ with sha256 integrity."""
    ws_root = _find_workspace_root(path)
    if ws_root is None:
        return CortexOUT.error("workspace not found", code="NOT_FOUND")
    arqux_dir = ws_root / ARQUX_DIR
    if not arqux_dir.is_dir():
        return CortexOUT.error(f"{arqux_dir} not found", code="NOT_FOUND")
    ts = _timestamp()
    backup_name = f"{PRODUCT_NAME}-{ts}.tar.gz"
    backup_path = ws_root / backup_name
    sha_path = ws_root / f"{backup_name}.sha256"

    with tarfile.open(backup_path, "w:gz") as tar:
        for entry in arqux_dir.rglob("*"):
            if entry.is_file() and not _should_exclude(entry.name):
                arcname = entry.relative_to(ws_root)
                tar.add(entry, arcname=arcname)

    digest = _compute_sha256(backup_path)
    sha_path.write_text(f"{digest}  {backup_name}\n", encoding="utf-8")

    size = backup_path.stat().st_size
    return CortexOUT.work(
        f"backup created: {backup_name} ({size} bytes, sha256={digest[:16]}...)",
        backup=str(backup_path),
        sha256_file=str(sha_path),
        size=size,
        digest=digest[:16],
    )


def restore(
    backup_path_str: str,
    path: str | None = None,
    ctx: Any = None,
) -> CortexOUT:
    """Restore .arqux/ from a backup file.

    Steps:
    1. Verify sha256 integrity
    2. Back up current .arqux/ (if exists) to .arqux.prev/
    3. Extract backup
    """
    backup_path = Path(backup_path_str).resolve()
    if not backup_path.exists():
        return CortexOUT.error(f"backup file not found: {backup_path}", code="NOT_FOUND")

    ws_root = _find_workspace_root(path)
    if ws_root is None:
        ws_root = backup_path.parent

    sha_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
    if not sha_path.exists():
        sha_path = ws_root / f"{backup_path.name}.sha256"
    if not sha_path.exists():
        return CortexOUT.error(
            f"sha256 file not found: expected {sha_path}",
            code="NOT_FOUND",
        )

    expected_digest = sha_path.read_text(encoding="utf-8").strip().split()[0]
    actual_digest = _compute_sha256(backup_path)
    if expected_digest != actual_digest:
        return CortexOUT.error(
            f"sha256 mismatch: expected {expected_digest}, got {actual_digest}",
            code="INTEGRITY_ERROR",
        )

    arqux_dir = ws_root / ARQUX_DIR
    if arqux_dir.is_dir():
        prev_dir = ws_root / f"{ARQUX_DIR}.prev"
        if prev_dir.exists():
            shutil.rmtree(prev_dir)
        shutil.copytree(arqux_dir, prev_dir)
        shutil.rmtree(arqux_dir)

    with tarfile.open(backup_path, "r:gz") as tar:
        tar.extractall(path=ws_root)

    if not arqux_dir.is_dir():
        return CortexOUT.error("restore failed: .arqux/ not found after extraction", code="RESTORE_FAILED")

    return CortexOUT.work(
        f"restore ok from {backup_path.name}",
        backup=backup_path.name,
        restored=str(arqux_dir),
        previous_backup=str(ws_root / f"{ARQUX_DIR}.prev") if (ws_root / f"{ARQUX_DIR}.prev").exists() else None,
    )
