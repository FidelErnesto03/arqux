"""
arqux.concurrency — File locking primitives (NEW in v0.4.0).

Solves ALTO-2 (race condition in ID generation) detected in the
v2.0 experimental benchmark.

Provides:
    - `file_lock()` context manager using fcntl.flock (POSIX).
    - `next_blueprint_id_safe()` — race-free blueprint ID generation.
    - `next_task_id_safe()` — race-free task ID generation.
    - `next_cycle_id_safe()` — race-free cycle ID generation.

Design:
    - Uses fcntl.flock(LOCK_EX) on a sidecar `.lock` file.
    - Falls back to threading.Lock() on non-POSIX systems (Windows).
    - Lock files live at `<dir>/.<name>.lock` (hidden, gitignored).
    - Context manager ensures lock release even on exceptions.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO

# --- Platform detection ----------------------------------------------------

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

# Fallback per-thread locks for non-POSIX systems.
# NOTE: This only protects against in-process race conditions, not
# cross-process. On Windows, true cross-process locking requires
# msvcrt.locking or win32file — out of scope for v0.4.0.
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


@contextmanager
def file_lock(
    lock_path: Path | str,
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Generator[IO[bytes] | None, None, None]:
    """Acquire an exclusive file lock.

    On POSIX systems, uses fcntl.flock(LOCK_EX) on a sidecar file.
    On non-POSIX, falls back to threading.Lock (in-process only).

    Args:
        lock_path: Path to the lock file (created if it doesn't exist).
        timeout: Maximum seconds to wait for the lock.
        poll_interval: Sleep duration between lock attempts (fallback mode).

    Yields:
        File handle (POSIX) or None (fallback).

    Raises:
        TimeoutError: If lock cannot be acquired within `timeout` seconds.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Per-thread lock key (for fallback mode and to avoid re-entrancy issues).
    lock_key = str(lock_path.resolve())

    if _HAS_FCNTL:
        # POSIX: use fcntl.flock for cross-process locking.
        import time as _time
        fh = lock_path.open("a+b")
        deadline = _time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if _time.monotonic() >= deadline:
                    fh.close()
                    raise TimeoutError(
                        f"could not acquire lock {lock_path} within {timeout}s"
                    )
                _time.sleep(poll_interval)
        try:
            yield fh
        finally:
            with suppress(OSError):
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()
    else:
        # Fallback: threading.Lock (in-process only).
        with _THREAD_LOCKS_GUARD:
            if lock_key not in _THREAD_LOCKS:
                _THREAD_LOCKS[lock_key] = threading.Lock()
            tlock = _THREAD_LOCKS[lock_key]

        acquired = tlock.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(
                f"could not acquire thread lock {lock_path} within {timeout}s"
            )
        try:
            yield None
        finally:
            tlock.release()


# --- Race-free ID generators ----------------------------------------------


def next_blueprint_id_safe(bp_dir: Path) -> str:
    """Generate the next blueprint ID (BLP-NNN) with file locking.

    Race-free version of `handlers.blueprint._next_blueprint_id`.
    Two concurrent calls will get different IDs.

    IMPORTANT: This function creates a placeholder file to reserve the ID.
    The caller should overwrite this file with the actual blueprint content.
    Without the placeholder, a second caller could get the same ID after
    we release the lock but before the caller writes the file.

    Args:
        bp_dir: Directory containing BLP-*.md files.

    Returns:
        Next blueprint ID (e.g. "BLP-001").
    """
    bp_dir.mkdir(parents=True, exist_ok=True)
    lock_file = bp_dir / ".blueprints.lock"
    with file_lock(lock_file):
        existing = []
        for f in bp_dir.glob("BLP-*.md"):
            m = re.match(r"BLP-(\d+)\.md", f.name)
            if m:
                existing.append(int(m.group(1)))
        n = max(existing) + 1 if existing else 1
        bp_id = f"BLP-{n:03d}"
        # Create a placeholder file to reserve the ID.
        # This prevents a second caller from getting the same ID even
        # after we release the lock.
        placeholder = bp_dir / f"{bp_id}.md"
        placeholder.write_text(f"<!-- reserved by next_blueprint_id_safe at {__import__('time').time()} -->", encoding="utf-8")
        return bp_id


def next_task_id_safe(project_root: Path, cycle_id: str, tasks_dir_name: str = "tasks") -> str:
    """Generate the next task ID (T-NNN) with file locking.

    Race-free version of `state.next_task_id`.

    IMPORTANT: Creates a placeholder .cortex file to reserve the ID.

    Args:
        project_root: Path to .arqux/ directory.
        cycle_id: Cycle identifier (e.g. "CYCLE-01").
        tasks_dir_name: Subdirectory name for tasks (default: "tasks").

    Returns:
        Next task ID (e.g. "T-001").
    """
    tasks_dir = project_root / "cycles" / cycle_id / tasks_dir_name
    tasks_dir.mkdir(parents=True, exist_ok=True)
    lock_file = tasks_dir / ".tasks.lock"
    with file_lock(lock_file):
        existing = sorted(
            p.stem.replace(".cortex", "")
            for p in tasks_dir.glob("T-*.cortex")
        )
        if not existing:
            n = 1
        else:
            last = existing[-1].removeprefix("T-")
            try:
                n = int(last) + 1
            except ValueError:
                n = len(existing) + 1
        task_id = f"T-{n:03d}"
        # Reserve the ID with a placeholder file.
        placeholder = tasks_dir / f"{task_id}.cortex"
        placeholder.write_text(
            f"# $0 reserved by next_task_id_safe at {__import__('time').time()}\n",
            encoding="utf-8",
        )
        return task_id


def next_cycle_id_safe(project_root: Path) -> str:
    """Generate the next cycle ID (CYCLE-NN) with file locking.

    Race-free version of `state.next_cycle_id`.

    IMPORTANT: Creates a placeholder directory to reserve the ID.

    Args:
        project_root: Path to .arqux/ directory.

    Returns:
        Next cycle ID (e.g. "CYCLE-01").
    """
    cycles_base = project_root / "cycles"
    cycles_base.mkdir(parents=True, exist_ok=True)
    lock_file = cycles_base / ".cycles.lock"
    with file_lock(lock_file):
        existing = sorted(
            p.name for p in cycles_base.iterdir() if p.is_dir()
        )
        if not existing:
            n = 1
        else:
            last = existing[-1].removeprefix("CYCLE-")
            try:
                n = int(last) + 1
            except ValueError:
                n = len(existing) + 1
        cycle_id = f"CYCLE-{n:02d}"
        # Reserve the ID with a placeholder directory.
        placeholder_dir = cycles_base / cycle_id
        placeholder_dir.mkdir(parents=True, exist_ok=True)
        # Create a MANIFEST.md placeholder so the cycle is "valid".
        (placeholder_dir / "MANIFEST.md").write_text(
            f"---\ncycle_id: \"{cycle_id}\"\nstatus: \"reserved\"\n---\n# Reserved\n",
            encoding="utf-8",
        )
        return cycle_id
