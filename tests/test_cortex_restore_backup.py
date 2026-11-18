"""Tests for cortex.restore_backup (backup protocol restore handler).

Issue 2026-11-17-protocolo-oficial-de-copias-de-respaldo-bak-bak-:
the handler is the only sanctioned restore path from .bak/.bak.1 —
dry-run by default, force-gated apply, backup validated before use,
pre-restore state rotated into the chain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.constants import OUT_ERROR
from arqux.handlers.cortex.restore import restore_backup_handler

V1 = """$0

$0:format{cortex:1.0, encoding:UTF-8}

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity  | attrs | B | Semantic | Actor identity
IDN:idn_contract{type:"attrs", weight:"B", fields:"value:any?", focus:"value", desc:"Actor identity", open:true}

$1: TEST
IDN:marker{name:"version-1"}
"""

V2 = V1.replace("version-1", "version-2")
V3 = V2.replace("version-2", "version-3")


@pytest.fixture
def rotated_file(tmp_path: Path) -> Path:
    """A .cortex file with two backup generations, as writers leave it.

    current = V3, .bak = V2, .bak.1 = V1.
    """
    p = tmp_path / "brain.cortex"
    p.write_text(V3, encoding="utf-8")
    (tmp_path / "brain.cortex.bak").write_text(V2, encoding="utf-8")
    (tmp_path / "brain.cortex.bak.1").write_text(V1, encoding="utf-8")
    return p


def _read_marker(p: Path) -> str:
    return "version-1" if "version-1" in p.read_text(encoding="utf-8") else (
        "version-2" if "version-2" in p.read_text(encoding="utf-8") else "version-3"
    )


def _ok(result) -> bool:
    return result.profile != OUT_ERROR


class TestRestoreBackupPreview:
    def test_preview_is_default_and_non_mutating(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file))
        assert _ok(result), result.to_text()
        assert result.fields.get("dry_run") is True
        # Nothing changed on disk.
        assert _read_marker(rotated_file) == "version-3"
        assert _read_marker(rotated_file.with_name("brain.cortex.bak")) == "version-2"

    def test_preview_reports_source_details(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file))
        assert result.fields["source_entries"] == 1
        assert result.fields["generation"] == 0
        assert result.fields["target_bytes"] == len(V3)

    def test_generation_1_selects_bak1(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file), generation=1)
        assert result.fields["source"].endswith("brain.cortex.bak.1")
        assert result.fields["source_bytes"] == len(V1)

    def test_invalid_generation_rejected(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file), generation=2)
        assert not _ok(result), result.to_text()

    def test_missing_backup_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "solo.cortex"
        p.write_text(V3, encoding="utf-8")
        result = restore_backup_handler(str(p))
        assert not _ok(result), result.to_text()

    def test_unparseable_backup_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.cortex"
        p.write_text(V3, encoding="utf-8")
        (tmp_path / "bad.cortex.bak").write_text("this is not cortex {{{", encoding="utf-8")
        result = restore_backup_handler(str(p))
        assert not _ok(result), result.to_text()
        # Target untouched.
        assert _read_marker(p) == "version-3"


class TestRestoreBackupApply:
    def test_apply_without_force_refused(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file), dry_run=False)
        assert not _ok(result), result.to_text()
        assert _read_marker(rotated_file) == "version-3"

    def test_apply_restores_and_rotates(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file), dry_run=False, force=True)
        assert _ok(result), result.to_text()
        # Target now holds the .bak content (V2).
        assert _read_marker(rotated_file) == "version-2"
        # Pre-restore state (V3) was rotated into the chain.
        assert _read_marker(rotated_file.with_name("brain.cortex.bak")) == "version-3"
        # Old .bak (V2) moved to .bak.1.
        assert _read_marker(rotated_file.with_name("brain.cortex.bak.1")) == "version-2"
        assert result.fields.get("rotated_to", "").endswith("brain.cortex.bak")

    def test_apply_from_generation_1(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file), generation=1, dry_run=False, force=True)
        assert _ok(result), result.to_text()
        assert _read_marker(rotated_file) == "version-1"
        assert _read_marker(rotated_file.with_name("brain.cortex.bak")) == "version-3"

    def test_restored_content_is_identical_to_source(self, rotated_file: Path) -> None:
        bak1 = rotated_file.with_name("brain.cortex.bak.1")
        expected = bak1.read_bytes()
        restore_backup_handler(str(rotated_file), generation=1, dry_run=False, force=True)
        assert rotated_file.exists()
        assert rotated_file.read_bytes() == expected

    def test_missing_target_refused(self, tmp_path: Path) -> None:
        (tmp_path / "ghost.cortex.bak").write_text(V1, encoding="utf-8")
        result = restore_backup_handler(str(tmp_path / "ghost.cortex"), dry_run=False, force=True)
        assert not _ok(result), result.to_text()

    def test_accepts_bak_path_as_input(self, rotated_file: Path) -> None:
        result = restore_backup_handler(str(rotated_file.with_name("brain.cortex.bak")))
        assert result.fields["target"].endswith("brain.cortex")
