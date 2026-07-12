"""Tests for arqux backup / restore (P0-E).

Validates:
- backup creates .tar.gz + .sha256 sidecar
- backup includes .arqux/ contents
- restore verifies sha256 before extracting
- restore fails on corrupt backup
- restore backs up current state to .arqux.prev/
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest

from arqux.backup import backup, restore, _compute_sha256, _should_exclude
from arqux.handlers.workspace import init_workspace


@pytest.fixture
def workspace_with_state(tmp_path: Path) -> Path:
    """Create a workspace with some state in .arqux/."""
    init_workspace(path=str(tmp_path))
    arqux_dir = tmp_path / ".arqux"
    # Add a sentinel file to verify backup/restore.
    sentinel = arqux_dir / "sentinel.txt"
    sentinel.write_text("test-sentinel-content", encoding="utf-8")
    return tmp_path


class TestBackup:
    """P0-E: backup() must create tar.gz + sha256 sidecar."""

    def test_backup_creates_tarball(self, workspace_with_state: Path, monkeypatch) -> None:
        monkeypatch.chdir(workspace_with_state)
        result = backup()
        assert "backup" in result.message.lower() or "ok" in result.message.lower()
        backup_path = Path(result.payload.get("backup", "")) if hasattr(result, "payload") else None
        if backup_path is None:
            # Look for any .tar.gz in workspace
            tars = list(workspace_with_state.glob("arqux-*.tar.gz"))
            assert tars, "No backup tarball created"
            backup_path = tars[0]
        assert backup_path.exists(), f"Backup file {backup_path} does not exist"

    def test_backup_creates_sha256_sidecar(self, workspace_with_state: Path, monkeypatch) -> None:
        monkeypatch.chdir(workspace_with_state)
        backup()
        sha_files = list(workspace_with_state.glob("arqux-*.tar.gz.sha256"))
        assert sha_files, "No .sha256 sidecar created"

    def test_backup_includes_sentinel(self, workspace_with_state: Path, monkeypatch) -> None:
        monkeypatch.chdir(workspace_with_state)
        backup()
        tars = list(workspace_with_state.glob("arqux-*.tar.gz"))
        assert tars
        with tarfile.open(tars[0], "r:gz") as tar:
            names = tar.getnames()
        assert any("sentinel.txt" in n for n in names), "Sentinel file not in backup"

    def test_backup_excludes_pycache(self, workspace_with_state: Path, monkeypatch) -> None:
        # Create a __pycache__ dir to verify exclusion.
        (workspace_with_state / ".arqux" / "__pycache__").mkdir(exist_ok=True)
        (workspace_with_state / ".arqux" / "__pycache__" / "x.pyc").write_text("pyc", encoding="utf-8")
        monkeypatch.chdir(workspace_with_state)
        backup()
        tars = list(workspace_with_state.glob("arqux-*.tar.gz"))
        with tarfile.open(tars[0], "r:gz") as tar:
            names = tar.getnames()
        assert not any("__pycache__" in n for n in names), "__pycache__ leaked into backup"

    def test_should_exclude_patterns(self) -> None:
        assert _should_exclude("__pycache__")
        assert _should_exclude("file.pyc")
        assert _should_exclude("file.bak")
        assert not _should_exclude("brain.cortex")
        assert not _should_exclude("meta-brain.cortex")


class TestRestore:
    """P0-E: restore() must verify sha256 and extract."""

    def test_restore_recreates_arqux(self, workspace_with_state: Path, monkeypatch) -> None:
        monkeypatch.chdir(workspace_with_state)
        backup()
        tars = list(workspace_with_state.glob("arqux-*.tar.gz"))
        backup_file = tars[0]

        # Delete .arqux/
        import shutil
        shutil.rmtree(workspace_with_state / ".arqux")
        assert not (workspace_with_state / ".arqux").exists()

        # Restore
        result = restore(str(backup_file))
        assert (workspace_with_state / ".arqux").exists()
        assert (workspace_with_state / ".arqux" / "sentinel.txt").exists()

    def test_restore_fails_on_corrupt_backup(self, workspace_with_state: Path, monkeypatch) -> None:
        monkeypatch.chdir(workspace_with_state)
        backup()
        tars = list(workspace_with_state.glob("arqux-*.tar.gz"))
        backup_file = tars[0]

        # Corrupt the tarball
        backup_file.write_text("corrupt-data", encoding="utf-8")
        # Update sha256 to match corrupt content (so integrity check passes
        # but extraction fails) OR leave sha256 stale (integrity check fails).
        # We leave it stale to test sha256 verification.
        result = restore(str(backup_file))
        # Should fail with INTEGRITY_ERROR or RESTORE_FAILED
        assert "ERROR" in result.message.upper() or "error" in result.message.lower() or "mismatch" in result.message.lower()

    def test_restore_backs_up_current_state(self, workspace_with_state: Path, monkeypatch) -> None:
        """restore() should back up current .arqux/ to .arqux.prev/ before extracting."""
        monkeypatch.chdir(workspace_with_state)
        # Add original sentinel.
        (workspace_with_state / ".arqux" / "sentinel.txt").write_text("original", encoding="utf-8")
        backup()
        tars = list(workspace_with_state.glob("arqux-*.tar.gz"))
        backup_file = tars[0]

        # Modify current state.
        (workspace_with_state / ".arqux" / "sentinel.txt").write_text("modified", encoding="utf-8")

        # Restore.
        restore(str(backup_file))

        prev_dir = workspace_with_state / ".arqux.prev"
        assert prev_dir.exists(), ".arqux.prev/ not created"
        assert (prev_dir / "sentinel.txt").read_text(encoding="utf-8") == "modified", \
            ".arqux.prev/ should contain pre-restore state"

    def test_compute_sha256_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        h1 = _compute_sha256(f)
        h2 = _compute_sha256(f)
        assert h1 == h2
        # Known sha256 of "hello"
        assert h1 == hashlib.sha256(b"hello").hexdigest()


class TestBackupNoWorkspace:
    """Edge case: backup() with no workspace should return error."""

    def test_backup_no_workspace(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = backup()
        assert "ERROR" in result.message.upper() or "not found" in result.message.lower()
