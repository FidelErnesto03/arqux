"""Tests for ARQX:artifact metadata in $0.1 (BLP-041)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.constants import (
    ArtifactKind,
    ArtifactMetadata,
    ArtifactUsage,
    CortexLevel,
    W001_NO_METADATA,
)
from arqux.formats import (
    CortexArtifact,
    has_arqux_metadata,
    read_arqux_metadata,
    read_cortex_artifact,
    render_arqux_section,
)
from arqux.migrator import (
    _remove_legacy_metadata,
    migrate_file,
    migrate_identity_files,
)


# --- Fixtures ---------------------------------------------------------------

VALID_ARQX_ENTRY = """$0
# -- $0: GLOSSARY --
# Sigil | Name | Type | Risk | Layer | Description
# IDN   | identity   | attrs  | B | Semantic | Actor identity
# ARQX  | artifact   | attrs  | B | Semantic | ArqUX artifact metadata

$0.1: ARQUX METADATA

ARQX:artifact{level:3, name:"brain", usage:"state", kind:"native"}

$1: IDENTITY
IDN:governor{project:"test"}
"""


NO_METADATA = """$0
# Sigil | Name | Type | Risk | Layer | Description
# IDN   | identity   | attrs  | B | Semantic | Actor identity

$1: IDENTITY
IDN:governor{project:"test"}
"""

LEGACY_METADATA = """# §0 METADATA{
#   level: 3,
#   name: "brain",
#   usage: "state",
#   kind: "native"
# }

$0
# Sigil | Name | Type | Risk | Layer | Description
# IDN   | identity   | attrs  | B | Semantic | Actor identity

$1: IDENTITY
IDN:governor{project:"test"}
"""


# --- read_arqux_metadata tests ---------------------------------------------

class TestReadArquxMetadata:
    def test_reads_valid_arqux_entry(self) -> None:
        meta = read_arqux_metadata(VALID_ARQX_ENTRY)
        assert meta.level is CortexLevel.BRAIN
        assert meta.name == "brain"
        assert meta.usage is ArtifactUsage.STATE
        assert meta.kind is ArtifactKind.NATIVE

    def test_returns_default_when_absent(self) -> None:
        meta = read_arqux_metadata(NO_METADATA)
        assert meta.level is CortexLevel.PACKAGE
        assert meta.name == "<unknown>"

    def test_returns_default_when_empty(self) -> None:
        meta = read_arqux_metadata("")
        assert meta.level is CortexLevel.PACKAGE

    def test_still_reads_legacy_block_as_fallback(self) -> None:
        meta = read_arqux_metadata(LEGACY_METADATA)
        assert meta.level is CortexLevel.BRAIN
        assert meta.name == "brain"


# --- has_arqux_metadata tests ------------------------------------------------

class TestHasArquxMetadata:
    def test_detects_new_format(self) -> None:
        assert has_arqux_metadata(VALID_ARQX_ENTRY) is True

    def test_detects_legacy_format(self) -> None:
        assert has_arqux_metadata(LEGACY_METADATA) is True

    def test_absent(self) -> None:
        assert has_arqux_metadata(NO_METADATA) is False
        assert has_arqux_metadata("") is False


# --- render/detect round-trip ------------------------------------------------

class TestRenderArquxSection:
    def test_render_produces_parseable_section(self) -> None:
        meta = ArtifactMetadata(
            level=CortexLevel.BRAIN,
            name="brain",
            usage=ArtifactUsage.STATE,
            kind=ArtifactKind.NATIVE,
        )
        section = render_arqux_section(meta)
        assert "$0.1:" in section
        assert "ARQX:artifact" in section
        assert "brain" in section
        # Round-trip: wrap in minimal $0 for parse_cortex
        doc = "$0\n# Sigil | Name\n" + section + "\n$1: TEST\n"
        reparsed = read_arqux_metadata(doc)
        assert reparsed.level is CortexLevel.BRAIN
        assert reparsed.name == "brain"


# --- _remove_legacy_metadata tests -------------------------------------------

class TestRemoveLegacyMetadata:
    def test_removes_legacy_block(self) -> None:
        stripped = _remove_legacy_metadata(LEGACY_METADATA)
        assert "§0 METADATA" not in stripped
        assert "$0" in stripped

    def test_noop_when_absent(self) -> None:
        stripped = _remove_legacy_metadata(NO_METADATA)
        assert stripped == NO_METADATA


# --- read_cortex_artifact tests ---------------------------------------------

class TestReadCortexArtifact:
    def test_reads_file_with_metadata(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text(VALID_ARQX_ENTRY, encoding="utf-8")
        art = read_cortex_artifact(p)
        assert isinstance(art, CortexArtifact)
        assert art.level is CortexLevel.BRAIN
        assert art.filename == "brain"
        assert art.path == p
        assert art.warnings == []

    def test_reads_file_without_metadata_warns(self, tmp_path: Path) -> None:
        p = tmp_path / "legacy.cortex"
        p.write_text(NO_METADATA, encoding="utf-8")
        art = read_cortex_artifact(p)
        assert art.level is CortexLevel.PACKAGE
        assert W001_NO_METADATA in art.warnings

    def test_reads_file_with_legacy_metadata(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text(LEGACY_METADATA, encoding="utf-8")
        art = read_cortex_artifact(p)
        assert isinstance(art, CortexArtifact)
        assert art.level is CortexLevel.BRAIN
        assert art.filename == "brain"


# --- migrator tests ---------------------------------------------------------

class TestMigrator:
    def test_migrate_file_injects_arqux_entry(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text("$0\n# Sigil | Name\n$1: IDENTITY\n", encoding="utf-8")
        migrated = migrate_file(p, level=3, name="brain", usage="state", kind="native")
        assert migrated is True
        content = p.read_text(encoding="utf-8")
        assert "ARQX:artifact" in content
        assert "$0.1:" in content
        assert "$1: IDENTITY" in content

    def test_migrate_file_idempotent(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text(VALID_ARQX_ENTRY, encoding="utf-8")
        migrated = migrate_file(p, level=3, name="brain", usage="state", kind="native")
        assert migrated is False

    def test_migrate_file_legacy_upgrade(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text(LEGACY_METADATA, encoding="utf-8")
        migrated = migrate_file(p, level=3, name="brain", usage="state", kind="native")
        assert migrated is True
        content = p.read_text(encoding="utf-8")
        assert "ARQX:artifact" in content
        assert "$0.1:" in content
        assert "§0 METADATA" not in content

    def test_migrate_file_preserves_content_below_section(self, tmp_path: Path) -> None:
        original_body = "$0\n# Sigil | Name\n\n$1: IDENTITY\nIDN:governor{project:\"x\"}\n"
        p = tmp_path / "brain.cortex"
        p.write_text(original_body, encoding="utf-8")
        migrate_file(p, level=3, name="brain", usage="state", kind="native")
        content = p.read_text(encoding="utf-8")
        # Original glossary and $1 body preserved (glossary line injected)
        assert "# Sigil | Name" in content
        assert '$1: IDENTITY' in content
        assert 'IDN:governor{project:"x"}' in content
        assert "ARQX:artifact" in content

    def test_migrate_identity_files_processes_directory(self, tmp_path: Path) -> None:
        ids_dir = tmp_path / "identities"
        ids_dir.mkdir()
        (ids_dir / "jarvis.cortex").write_text("$0\n# Sigil | Name\n", encoding="utf-8")
        (ids_dir / "alfred.cortex").write_text("$0\n# Sigil | Name\n", encoding="utf-8")
        results = migrate_identity_files(ids_dir)
        assert results == {"alfred": True, "jarvis": True}
        # Re-running is a no-op.
        results2 = migrate_identity_files(ids_dir)
        assert all(v is False for v in results2.values())

    def test_migrate_file_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            migrate_file(tmp_path / "missing.cortex", level=3, name="x", usage="state", kind="native")

    def test_migrate_skill_inherited_requires_source(self, tmp_path: Path) -> None:
        from arqux.migrator import migrate_skill_file
        p = tmp_path / "owasp.skill.md"
        p.write_text("$0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="inherited skills require"):
            migrate_skill_file(p, name="owasp", kind="inherited")
