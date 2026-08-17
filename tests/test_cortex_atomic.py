"""Tests for BLP-003: arqux.cortex.atomic — atomic file writing.

Covers all acceptance criteria (AC-01 … AC-11) including serialization,
backup creation, dry-run, tmp cleanup on error, parent dir creation,
round-trip verification, overwrite vs new-file semantics, error handling,
unicode, and large documents.
"""

from __future__ import annotations

import os
import stat
import sys

import pytest

from arqux.cortex.atomic import (
    AtomicWriteError,
    WriteResult,
    atomic_write_json,
    atomic_write_text,
)
from arqux.cortex.writer import write_cortex_from_json


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _sample_doc() -> dict:
    """A representative JSON/dict CORTEX document."""
    return {
        "glossary": {
            "header": "$0",
            "comments": ["# -- $0: TEST GLOSSARY --"],
            "symbols": [],
        },
        "sections": [
            {
                "id": "$7",
                "title": "LESSONS",
                "comments": [],
                "entries": [
                    {
                        "sigil": "LNG",
                        "name": "lesson1",
                        "attrs": {"type": "behavioral", "severity": "high"},
                    },
                    {
                        "sigil": "AXM",
                        "name": "rule1",
                        "body": "Non-negotiable principle",
                    },
                ],
            },
            {
                "id": "$19",
                "title": "ARQUX METADATA",
                "comments": [],
                "entries": [
                    {
                        "sigil": "ARQX",
                        "name": "artifact",
                        "attrs": {"level": "2", "name": "brain"},
                    },
                ],
            },
        ],
    }


@pytest.fixture
def doc() -> dict:
    return _sample_doc()


def _large_doc(n_entries: int = 200) -> dict:
    """A large document with many entries for stress testing."""
    entries = []
    for i in range(n_entries):
        entries.append(
            {
                "sigil": "LNG",
                "name": f"lesson_{i}",
                "attrs": {"index": str(i), "severity": "low" if i % 2 else "high"},
            }
        )
    return {
        "glossary": {"header": "$0", "comments": [], "symbols": []},
        "sections": [
            {"id": "$7", "title": "BIG", "comments": [], "entries": entries},
        ],
    }


@pytest.fixture
def large_doc() -> dict:
    return _large_doc()


# ---------------------------------------------------------------------------
# AC-01: atomic_write_json writes valid CORTEX to path
# ---------------------------------------------------------------------------


class TestAtomicWriteJson:
    def test_writes_valid_cortex(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "out.cortex")
        result = atomic_write_json(doc, path)
        assert os.path.isfile(path)
        content = open(path, encoding="utf-8").read()
        expected = write_cortex_from_json(doc)
        assert content == expected

    def test_returns_write_result(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "out.cortex")
        result = atomic_write_json(doc, path)
        assert isinstance(result, WriteResult)
        assert result.path == str(os.path.abspath(path))
        assert result.dry_run is False

    def test_bytes_written_correct(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "out.cortex")
        result = atomic_write_json(doc, path)
        expected_bytes = len(write_cortex_from_json(doc).encode("utf-8"))
        assert result.bytes_written == expected_bytes


# ---------------------------------------------------------------------------
# AC-02: Backup file created at path.bak when file exists
# ---------------------------------------------------------------------------


class TestBackupCreation:
    def test_backup_created_when_file_exists(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "out.cortex")
        # Write initial content
        with open(path, "w", encoding="utf-8") as f:
            f.write("ORIGINAL CONTENT\n")
        result = atomic_write_json(doc, path)
        assert result.backup is not None
        assert os.path.isfile(result.backup)
        assert open(result.backup, encoding="utf-8").read() == "ORIGINAL CONTENT\n"

    def test_overwrite_creates_backup(self, doc: dict, tmp_path) -> None:
        """AC-11: Overwrite existing file: backup created, new content written."""
        path = str(tmp_path / "out.cortex")
        original = "OLD DATA\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)
        result = atomic_write_json(doc, path)
        assert result.backup is not None
        # backup has old content
        assert open(result.backup, encoding="utf-8").read() == original
        # path has new content
        assert open(path, encoding="utf-8").read() == write_cortex_from_json(doc)


# ---------------------------------------------------------------------------
# AC-03: No backup when keep_backup=False
# ---------------------------------------------------------------------------


class TestNoBackup:
    def test_no_backup_when_keep_backup_false(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "out.cortex")
        with open(path, "w", encoding="utf-8") as f:
            f.write("ORIGINAL\n")
        result = atomic_write_json(doc, path, keep_backup=False)
        assert result.backup is None
        assert not os.path.isfile(path + ".bak")
        # new content written
        assert open(path, encoding="utf-8").read() == write_cortex_from_json(doc)

    def test_no_backup_for_new_file(self, doc: dict, tmp_path) -> None:
        """AC-12: Write to new file: no backup, content written."""
        path = str(tmp_path / "new.cortex")
        result = atomic_write_json(doc, path)
        assert result.backup is None
        assert not os.path.isfile(path + ".bak")
        assert os.path.isfile(path)
        assert open(path, encoding="utf-8").read() == write_cortex_from_json(doc)


# ---------------------------------------------------------------------------
# AC-04: dry_run=True doesn't write to filesystem
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_no_file_written(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "dry.cortex")
        result = atomic_write_json(doc, path, dry_run=True)
        assert result.dry_run is True
        assert not os.path.isfile(path)
        assert not os.path.isfile(path + ".tmp")
        assert not os.path.isfile(path + ".bak")

    def test_dry_run_bytes_correct(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "dry.cortex")
        result = atomic_write_json(doc, path, dry_run=True)
        expected = len(write_cortex_from_json(doc).encode("utf-8"))
        assert result.bytes_written == expected
        assert result.backup is None

    def test_dry_run_text(self, tmp_path) -> None:
        path = str(tmp_path / "dry.txt")
        result = atomic_write_text("hello\n", path, dry_run=True)
        assert result.dry_run is True
        assert result.bytes_written == len("hello\n".encode("utf-8"))
        assert not os.path.isfile(path)


# ---------------------------------------------------------------------------
# AC-05: Tmp file cleaned up on error
# ---------------------------------------------------------------------------


class TestTmpCleanupOnError:
    def test_tmp_cleaned_on_readonly_dir(self, doc: dict, tmp_path) -> None:
        """Simulate error by writing to a read-only directory."""
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        os.chmod(str(ro_dir), stat.S_IRUSR | stat.S_IXUSR)  # r-x, no write
        path = str(ro_dir / "out.cortex")
        try:
            with pytest.raises(AtomicWriteError):
                atomic_write_json(doc, path)
            # tmp file should not linger
            assert not os.path.isfile(path + ".tmp")
        finally:
            # restore so tmp_path cleanup works
            os.chmod(str(ro_dir), stat.S_IRWXU)

    def test_tmp_cleaned_on_backup_failure(self, tmp_path) -> None:
        """If backup creation fails, tmp file is cleaned up."""
        path = str(tmp_path / "out.cortex")
        # Create a file so backup path is attempted
        with open(path, "w", encoding="utf-8") as f:
            f.write("data\n")
        # Remove read permission on the original so copy2 fails reading it.
        # (We are not root, so this is enforced.)
        if os.geteuid() == 0:
            pytest.skip("Cannot test permission failure as root")
        os.chmod(path, stat.S_IWUSR)  # write-only, no read
        try:
            with pytest.raises(AtomicWriteError, match="backup"):
                atomic_write_text("new content\n", path, keep_backup=True)
            assert not os.path.isfile(path + ".tmp")
        finally:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    def test_tmp_cleaned_on_rename_failure(self, tmp_path) -> None:
        """If atomic rename fails (target is a directory), tmp is cleaned up."""
        path = str(tmp_path / "out.cortex")
        # Make the target path a directory so os.replace fails.
        os.makedirs(path)
        try:
            with pytest.raises(AtomicWriteError, match="replace"):
                atomic_write_text("new content\n", path, keep_backup=False)
            assert not os.path.isfile(path + ".tmp")
        finally:
            os.rmdir(path)


# ---------------------------------------------------------------------------
# AC-06: Parent directory created if it doesn't exist
# ---------------------------------------------------------------------------


class TestParentDirCreation:
    def test_parent_dir_created(self, doc: dict, tmp_path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        path = str(nested / "out.cortex")
        assert not nested.exists()
        result = atomic_write_json(doc, path)
        assert os.path.isfile(path)
        assert open(path, encoding="utf-8").read() == write_cortex_from_json(doc)

    def test_deep_nested_dirs(self, tmp_path) -> None:
        path = str(tmp_path / "x" / "y" / "z" / "file.txt")
        atomic_write_text("content\n", path)
        assert os.path.isfile(path)
        assert open(path, encoding="utf-8").read() == "content\n"


# ---------------------------------------------------------------------------
# AC-07: atomic_write_text writes raw text atomically
# ---------------------------------------------------------------------------


class TestAtomicWriteText:
    def test_writes_raw_text(self, tmp_path) -> None:
        path = str(tmp_path / "raw.txt")
        result = atomic_write_text("raw text content\n", path)
        assert isinstance(result, WriteResult)
        assert open(path, encoding="utf-8").read() == "raw text content\n"

    def test_bytes_written_text(self, tmp_path) -> None:
        path = str(tmp_path / "raw.txt")
        text = "héllo wörld\n"
        result = atomic_write_text(text, path)
        assert result.bytes_written == len(text.encode("utf-8"))

    def test_overwrite_with_backup(self, tmp_path) -> None:
        path = str(tmp_path / "raw.txt")
        with open(path, "w") as f:
            f.write("old\n")
        result = atomic_write_text("new\n", path, keep_backup=True)
        assert result.backup is not None
        assert open(result.backup).read() == "old\n"
        assert open(path).read() == "new\n"


# ---------------------------------------------------------------------------
# AC-08: WriteResult returns correct fields
# ---------------------------------------------------------------------------


class TestWriteResult:
    def test_result_fields_new_file(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "new.cortex")
        result = atomic_write_json(doc, path)
        assert result.path == str(os.path.abspath(path))
        assert result.backup is None
        assert result.bytes_written > 0
        assert result.dry_run is False
        assert result.diagnostics == []

    def test_result_fields_overwrite(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "out.cortex")
        with open(path, "w") as f:
            f.write("x\n")
        result = atomic_write_json(doc, path)
        assert result.backup == str(os.path.abspath(path + ".bak"))
        assert result.bytes_written == len(write_cortex_from_json(doc).encode("utf-8"))

    def test_result_fields_dry_run(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "dry.cortex")
        result = atomic_write_json(doc, path, dry_run=True)
        assert result.dry_run is True
        assert result.backup is None
        assert result.bytes_written > 0


# ---------------------------------------------------------------------------
# AC-09: No imports from cortex.core or codec_cortex
# ---------------------------------------------------------------------------


class TestNoCodecImports:
    def test_no_codec_cortex_import(self) -> None:
        import arqux.cortex.atomic as mod

        src = open(mod.__file__).read()
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "codec_cortex" not in stripped
                assert "cortex.core" not in stripped

    def test_module_not_dependent_at_runtime(self) -> None:
        import arqux.cortex.atomic as mod

        names = set(vars(mod))
        assert "codec_cortex" not in names
        for value in vars(mod).values():
            modname = getattr(value, "__name__", "")
            assert modname != "codec_cortex"
            assert modname != "cortex.core"


# ---------------------------------------------------------------------------
# AC-10: Round-trip: JSON → atomic_write → read file → verify
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_json_to_file_matches_writer(self, doc: dict, tmp_path) -> None:
        path = str(tmp_path / "rt.cortex")
        atomic_write_json(doc, path)
        on_disk = open(path, encoding="utf-8").read()
        expected = write_cortex_from_json(doc)
        assert on_disk == expected

    def test_text_to_file_exact(self, tmp_path) -> None:
        path = str(tmp_path / "rt.txt")
        text = "line1\nline2\nline3\n"
        atomic_write_text(text, path)
        assert open(path, encoding="utf-8").read() == text

    def test_round_trip_preserves_unicode(self, doc: dict, tmp_path) -> None:
        doc["sections"][0]["entries"].append(
            {"sigil": "LNG", "name": "unicode", "body": "café — naïve résumé ñ"}
        )
        path = str(tmp_path / "uni.cortex")
        atomic_write_json(doc, path)
        on_disk = open(path, encoding="utf-8").read()
        assert "café — naïve résumé ñ" in on_disk


# ---------------------------------------------------------------------------
# AC-13: AtomicWriteError raised on filesystem failure
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_error_on_readonly_dir(self, doc: dict, tmp_path) -> None:
        ro_dir = tmp_path / "ro"
        ro_dir.mkdir()
        os.chmod(str(ro_dir), stat.S_IRUSR | stat.S_IXUSR)
        path = str(ro_dir / "out.cortex")
        try:
            with pytest.raises(AtomicWriteError):
                atomic_write_json(doc, path)
        finally:
            os.chmod(str(ro_dir), stat.S_IRWXU)

    def test_error_is_exception_subclass(self) -> None:
        assert issubclass(AtomicWriteError, Exception)

    def test_text_error_on_readonly_dir(self, tmp_path) -> None:
        ro_dir = tmp_path / "ro2"
        ro_dir.mkdir()
        os.chmod(str(ro_dir), stat.S_IRUSR | stat.S_IXUSR)
        path = str(ro_dir / "out.txt")
        try:
            with pytest.raises(AtomicWriteError):
                atomic_write_text("data\n", path)
        finally:
            os.chmod(str(ro_dir), stat.S_IRWXU)


# ---------------------------------------------------------------------------
# AC-14: Unicode content written correctly
# ---------------------------------------------------------------------------


class TestUnicode:
    def test_unicode_text(self, tmp_path) -> None:
        path = str(tmp_path / "uni.txt")
        text = "héllo wörld — café ☃ 日本語\n"
        result = atomic_write_text(text, path)
        assert open(path, encoding="utf-8").read() == text
        assert result.bytes_written == len(text.encode("utf-8"))

    def test_unicode_json(self, doc: dict, tmp_path) -> None:
        doc["sections"][0]["entries"].append(
            {"sigil": "LNG", "name": "uni", "attrs": {"text": "café ☃ ñ"}}
        )
        path = str(tmp_path / "uni.cortex")
        atomic_write_json(doc, path)
        content = open(path, encoding="utf-8").read()
        assert "café" in content
        assert "☃" in content


# ---------------------------------------------------------------------------
# AC-15: Large document (many entries) written correctly
# ---------------------------------------------------------------------------


class TestLargeDocument:
    def test_large_doc_written(self, large_doc: dict, tmp_path) -> None:
        path = str(tmp_path / "large.cortex")
        result = atomic_write_json(large_doc, path)
        content = open(path, encoding="utf-8").read()
        expected = write_cortex_from_json(large_doc)
        assert content == expected
        assert result.bytes_written == len(expected.encode("utf-8"))
        # spot check a few entries
        assert "lesson_0" in content
        assert "lesson_199" in content

    def test_large_doc_entry_count(self, large_doc: dict, tmp_path) -> None:
        path = str(tmp_path / "large.cortex")
        atomic_write_json(large_doc, path)
        content = open(path, encoding="utf-8").read()
        # 200 entries
        assert content.count("LNG:lesson_") == 200

    def test_large_doc_overwrite_with_backup(self, large_doc: dict, tmp_path) -> None:
        path = str(tmp_path / "large.cortex")
        with open(path, "w") as f:
            f.write("old\n")
        result = atomic_write_json(large_doc, path)
        assert result.backup is not None
        assert open(result.backup).read() == "old\n"
        assert "lesson_199" in open(path, encoding="utf-8").read()


# ---------------------------------------------------------------------------
# OBS-005: Unique tmp file name — concurrent writes don't collide
# ---------------------------------------------------------------------------


class TestUniqueTmpFile:
    def test_concurrent_writes_no_collision(self, tmp_path) -> None:
        """Two concurrent writes to the same path must not collide.

        With a predictable ``path + ".tmp"`` name, the second write would
        either overwrite the first's tmp file or fail.  Using
        :func:`tempfile.mkstemp` guarantees unique tmp names so both
        writes complete successfully.
        """
        import threading

        path = str(tmp_path / "concurrent.cortex")
        errors: list[Exception] = []

        def _write(content: str) -> None:
            try:
                atomic_write_text(content, path, keep_backup=False)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=_write, args=("CONTENT_A\n",))
        t2 = threading.Thread(target=_write, args=("CONTENT_B\n",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == [], f"Concurrent writes failed: {errors}"
        # Final content must be one of the two (deterministic per run)
        final = open(path, encoding="utf-8").read()
        assert final in ("CONTENT_A\n", "CONTENT_B\n")
        # No tmp files should linger in the directory
        leftovers = [
            f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")
        ]
        assert leftovers == [], f"Tmp files left behind: {leftovers}"

    def test_sequential_writes_use_unique_tmp(self, tmp_path) -> None:
        """Each write creates a distinct tmp file; none use the predictable name."""
        path = str(tmp_path / "seq.cortex")
        atomic_write_text("first\n", path, keep_backup=False)
        atomic_write_text("second\n", path, keep_backup=False)
        # The predictable name should never have been used
        assert not os.path.isfile(path + ".tmp")
        # Final content is correct
        assert open(path, encoding="utf-8").read() == "second\n"


# ---------------------------------------------------------------------------
# OBS-001: File permissions preserved across atomic write
# ---------------------------------------------------------------------------


class TestPermissionPreservation:
    def test_permissions_preserved_0600(self, tmp_path) -> None:
        """A file with 0o600 permissions retains 0o600 after write."""
        path = str(tmp_path / "perms.cortex")
        with open(path, "w", encoding="utf-8") as f:
            f.write("original\n")
        os.chmod(path, 0o600)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

        atomic_write_text("new content\n", path, keep_backup=False)

        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_permissions_preserved_0644(self, tmp_path) -> None:
        """A file with 0o644 permissions retains 0o644 after write."""
        path = str(tmp_path / "perms2.cortex")
        with open(path, "w", encoding="utf-8") as f:
            f.write("original\n")
        os.chmod(path, 0o644)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o644

        atomic_write_text("new content\n", path, keep_backup=False)

        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o644, f"Expected 0o644, got {oct(mode)}"

    def test_new_file_default_permissions(self, tmp_path) -> None:
        """A brand-new file gets the default mkstemp permissions (0o600)."""
        path = str(tmp_path / "brandnew.cortex")
        atomic_write_text("content\n", path, keep_backup=False)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        # mkstemp creates with 0o600; no original to copy from
        assert mode == 0o600, f"Expected 0o600 for new file, got {oct(mode)}"


# ---------------------------------------------------------------------------
# OBS-008: os.fsync called before rename for crash-consistency
# ---------------------------------------------------------------------------


class TestFsyncBeforeRename:
    def test_fsync_called(self, tmp_path, monkeypatch) -> None:
        """Verify os.fsync is called on the tmp file descriptor."""
        fsync_called: list[int] = []
        real_fsync = os.fsync

        def _tracking_fsync(fd: int) -> None:
            fsync_called.append(fd)
            real_fsync(fd)

        monkeypatch.setattr(os, "fsync", _tracking_fsync)

        path = str(tmp_path / "fsync.cortex")
        atomic_write_text("synced content\n", path, keep_backup=False)

        assert len(fsync_called) >= 1, "os.fsync was not called"
        # File content is correct
        assert open(path, encoding="utf-8").read() == "synced content\n"

    def test_fsync_called_on_overwrite(self, tmp_path, monkeypatch) -> None:
        """fsync is called even when overwriting an existing file."""
        path = str(tmp_path / "fsync2.cortex")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old\n")

        fsync_called: list[int] = []
        real_fsync = os.fsync

        def _tracking_fsync(fd: int) -> None:
            fsync_called.append(fd)
            real_fsync(fd)

        monkeypatch.setattr(os, "fsync", _tracking_fsync)

        atomic_write_text("new\n", path, keep_backup=False)

        assert len(fsync_called) >= 1, "os.fsync was not called on overwrite"
