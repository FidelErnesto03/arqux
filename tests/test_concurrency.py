"""Tests for arqux.concurrency — file locking and race-free ID generators."""

from __future__ import annotations

import time

import pytest

# ---------------------------------------------------------------------------
# file_lock context manager
# ---------------------------------------------------------------------------


def test_file_lock_acquire_release(tmp_path) -> None:
    """file_lock acquires and releases an exclusive lock."""
    from arqux.concurrency import file_lock

    lock_file = tmp_path / "test.lock"
    with file_lock(lock_file) as fh:
        assert fh is not None
        # Lock should be held here
    # After context exits, lock is released


def test_file_lock_creates_file(tmp_path) -> None:
    """file_lock creates the lock file if it doesn't exist."""
    from arqux.concurrency import file_lock

    lock_file = tmp_path / ".test.lock"
    with file_lock(lock_file):
        assert lock_file.exists()


def test_file_lock_exclusive(tmp_path) -> None:
    """Two concurrent file_lock calls are exclusive (serializes correctly)."""
    from arqux.concurrency import file_lock

    lock_file = tmp_path / "exclusive.lock"
    results = []

    def acquire_later() -> None:
        time.sleep(0.05)
        with file_lock(lock_file, timeout=5.0):
            results.append("late")

    with file_lock(lock_file):
        results.append("early")
        import threading
        t = threading.Thread(target=acquire_later, daemon=True)
        t.start()
        time.sleep(0.1)
        # "early" should be before "late"
        assert results == ["early"]
        time.sleep(0.1)

    t.join(timeout=2)
    assert results == ["early", "late"]


def test_file_lock_timeout(tmp_path) -> None:
    """file_lock raises TimeoutError when lock can't be acquired."""
    from arqux.concurrency import file_lock

    lock_file = tmp_path / "timeout.lock"
    with file_lock(lock_file), pytest.raises(TimeoutError), file_lock(lock_file, timeout=0.01, poll_interval=0.005):  # noqa: SIM117
        pass


# ---------------------------------------------------------------------------
# next_blueprint_id_safe
# ---------------------------------------------------------------------------


def test_next_blueprint_id_first(tmp_path) -> None:
    """next_blueprint_id_safe returns BLP-001 for empty directory."""
    from arqux.concurrency import next_blueprint_id_safe

    bp_dir = tmp_path / "blueprints"
    bp_id = next_blueprint_id_safe(bp_dir)
    assert bp_id == "BLP-001"


def test_next_blueprint_id_increments(tmp_path) -> None:
    """next_blueprint_id_safe returns sequential IDs."""
    from arqux.concurrency import next_blueprint_id_safe

    bp_dir = tmp_path / "blueprints"
    id1 = next_blueprint_id_safe(bp_dir)
    id2 = next_blueprint_id_safe(bp_dir)
    assert id1 == "BLP-001"
    assert id2 == "BLP-002"


def test_next_blueprint_id_existing(tmp_path) -> None:
    """next_blueprint_id_safe respects existing BLP files."""
    from arqux.concurrency import next_blueprint_id_safe

    bp_dir = tmp_path / "blueprints"
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-005.md").write_text("# existing", encoding="utf-8")

    bp_id = next_blueprint_id_safe(bp_dir)
    assert bp_id == "BLP-006"


# ---------------------------------------------------------------------------
# next_task_id_safe
# ---------------------------------------------------------------------------


def test_next_task_id_first(tmp_path) -> None:
    """next_task_id_safe returns T-001 for empty directory."""
    from arqux.concurrency import next_task_id_safe

    ciclo = "CYCLE-01"
    task_id = next_task_id_safe(tmp_path, ciclo)
    assert task_id == "T-001"


def test_next_task_id_increments(tmp_path) -> None:
    """next_task_id_safe returns sequential task IDs."""
    from arqux.concurrency import next_task_id_safe

    ciclo = "CYCLE-01"
    t1 = next_task_id_safe(tmp_path, ciclo)
    t2 = next_task_id_safe(tmp_path, ciclo)
    assert t1 == "T-001"
    assert t2 == "T-002"


# ---------------------------------------------------------------------------
# next_cycle_id_safe
# ---------------------------------------------------------------------------


def test_next_cycle_id_first(tmp_path) -> None:
    """next_cycle_id_safe returns CYCLE-01 for empty directory."""
    from arqux.concurrency import next_cycle_id_safe

    cycle_id = next_cycle_id_safe(tmp_path)
    assert cycle_id == "CYCLE-01"


def test_next_cycle_id_increments(tmp_path) -> None:
    """next_cycle_id_safe returns sequential cycle IDs."""
    from arqux.concurrency import next_cycle_id_safe

    c1 = next_cycle_id_safe(tmp_path)
    c2 = next_cycle_id_safe(tmp_path)
    assert c1 == "CYCLE-01"
    assert c2 == "CYCLE-02"


def test_next_cycle_id_existing(tmp_path) -> None:
    """next_cycle_id_safe respects existing cycles."""
    from arqux.concurrency import next_cycle_id_safe

    cycles_base = tmp_path / "cycles"
    cycles_base.mkdir(parents=True, exist_ok=True)
    (cycles_base / "CYCLE-03").mkdir()

    cycle_id = next_cycle_id_safe(tmp_path)
    assert cycle_id == "CYCLE-04"


# ---------------------------------------------------------------------------
# file_lock — fallback (non-POSIX) path
# ---------------------------------------------------------------------------


def test_file_lock_fallback(monkeypatch, tmp_path) -> None:
    """file_lock uses threading fallback when _HAS_FCNTL is False."""
    from arqux.concurrency import file_lock

    monkeypatch.setattr("arqux.concurrency._HAS_FCNTL", False)
    lock_file = tmp_path / "fallback.lock"
    with file_lock(lock_file) as fh:
        assert fh is None  # threading fallback yields None
    # After release, can acquire again
    with file_lock(lock_file) as fh:
        assert fh is None


def test_file_lock_fallback_timeout(monkeypatch, tmp_path) -> None:
    """file_lock fallback raises TimeoutError when lock held."""

    from arqux.concurrency import file_lock

    monkeypatch.setattr("arqux.concurrency._HAS_FCNTL", False)
    lock_file = tmp_path / "timeout_fallback.lock"

    # Acquire once (will be held)
    with file_lock(lock_file), pytest.raises(TimeoutError), file_lock(lock_file, timeout=0.05, poll_interval=0.01):
        pass


# ---------------------------------------------------------------------------
# next_blueprint_id_safe — edge cases
# ---------------------------------------------------------------------------


def test_next_blueprint_id_mixed_existing(tmp_path) -> None:
    """next_blueprint_id_safe handles multiple existing files."""
    from arqux.concurrency import next_blueprint_id_safe

    bp_dir = tmp_path / "blueprints"
    bp_dir.mkdir(parents=True, exist_ok=True)
    (bp_dir / "BLP-002.md").write_text("# existing 2", encoding="utf-8")
    (bp_dir / "BLP-005.md").write_text("# existing 5", encoding="utf-8")
    (bp_dir / "BLP-001.md").write_text("# existing 1", encoding="utf-8")

    bp_id = next_blueprint_id_safe(bp_dir)
    assert bp_id == "BLP-006"
