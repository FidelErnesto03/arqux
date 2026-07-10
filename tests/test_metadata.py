"""Tests for §0 METADATA declaration and validation (BLP-035)."""

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
    _parse_metadata_section,
    read_cortex_artifact,
    render_metadata_block,
    strip_metadata_block,
    validate_metadata,
)
from arqux.migrator import (
    has_metadata_block,
    migrate_file,
    migrate_identity_files,
)


# --- Fixtures ---------------------------------------------------------------

VALID_LEVEL_3 = """# §0 METADATA{
#   level: 3,
#   name: "brain",
#   usage: "state",
#   kind: "native"
# }

$0
GSIG:IDN:identity|attrs|B|Semantic|Actor identity

$1: IDENTITY
IDN:governor{project:"test"}
"""

VALID_LEVEL_1 = """# §0 METADATA{
#   level: 1,
#   name: "jarvis",
#   usage: "identity",
#   kind: "native",
#   agent: "jarvis"
# }

$0
GSIG:IDN:identity|attrs|B|Semantic|Actor identity
"""

VALID_LEVEL_0_LESSON = """# §0 METADATA{
#   level: 0,
#   name: "jarvis-lessons",
#   usage: "lesson",
#   kind: "native",
#   agent: "jarvis"
# }

$0
GSIG:LNG:lesson|attrs|M|Episodic|Learned lesson
"""

NO_METADATA = """$0
GSIG:IDN:identity|attrs|B|Semantic|Actor identity
"""


# --- parse tests ------------------------------------------------------------

class TestParseMetadataSection:
    def test_parses_canonical_block(self) -> None:
        data = _parse_metadata_section(VALID_LEVEL_3)
        assert data is not None
        assert data["level"] == 3
        assert data["name"] == "brain"
        assert data["usage"] == "state"
        assert data["kind"] == "native"

    def test_parses_optional_agent_field(self) -> None:
        data = _parse_metadata_section(VALID_LEVEL_1)
        assert data is not None
        assert data["agent"] == "jarvis"

    def test_returns_none_when_absent(self) -> None:
        assert _parse_metadata_section(NO_METADATA) is None
        assert _parse_metadata_section("") is None

    def test_raises_on_malformed_entry_without_colon(self) -> None:
        bad = """# §0 METADATA{
#   level: 3,
#   this_has_no_colon
# }
"""
        with pytest.raises(ValueError, match="malformed entry"):
            _parse_metadata_section(bad)

    def test_handles_compact_single_line_form(self) -> None:
        compact = '# §0 METADATA{level: 2, name: "owasp", usage: "skill", kind: "inherited"}'
        data = _parse_metadata_section(compact)
        assert data is not None
        assert data["level"] == 2
        assert data["kind"] == "inherited"


# --- validate_metadata tests ------------------------------------------------

class TestValidateMetadata:
    def test_valid_level_3_returns_metadata(self) -> None:
        meta = validate_metadata(VALID_LEVEL_3)
        assert meta.level is CortexLevel.BRAIN
        assert meta.name == "brain"
        assert meta.usage is ArtifactUsage.STATE
        assert meta.kind is ArtifactKind.NATIVE

    def test_valid_level_1_with_agent(self) -> None:
        meta = validate_metadata(VALID_LEVEL_1)
        assert meta.level is CortexLevel.BEHAVIORAL
        assert meta.agent == "jarvis"

    def test_valid_level_0_lesson(self) -> None:
        meta = validate_metadata(VALID_LEVEL_0_LESSON)
        assert meta.level is CortexLevel.PACKAGE
        assert meta.usage is ArtifactUsage.LESSON
        assert meta.agent == "jarvis"

    def test_missing_metadata_returns_default_level_0(self) -> None:
        meta = validate_metadata(NO_METADATA)
        assert meta.level is CortexLevel.PACKAGE
        assert meta.name == "<unknown>"

    def test_missing_metadata_returns_default_when_empty(self) -> None:
        meta = validate_metadata("")
        assert meta.level is CortexLevel.PACKAGE

    def test_missing_required_field_raises(self) -> None:
        bad = """# §0 METADATA{
#   level: 3,
#   name: "brain",
#   usage: "state"
# }
"""
        with pytest.raises(ValueError, match="missing required field: 'kind'"):
            validate_metadata(bad)

    def test_invalid_level_raises(self) -> None:
        bad = """# §0 METADATA{
#   level: 7,
#   name: "brain",
#   usage: "state",
#   kind: "native"
# }
"""
        with pytest.raises(ValueError, match="Invalid level"):
            validate_metadata(bad)

    def test_invalid_usage_raises(self) -> None:
        bad = """# §0 METADATA{
#   level: 3,
#   name: "brain",
#   usage: "weird",
#   kind: "native"
# }
"""
        with pytest.raises(ValueError, match="Invalid usage"):
            validate_metadata(bad)

    def test_invalid_kind_raises(self) -> None:
        bad = """# §0 METADATA{
#   level: 2,
#   name: "skill",
#   usage: "skill",
#   kind: "magic"
# }
"""
        with pytest.raises(ValueError, match="Invalid kind"):
            validate_metadata(bad)

    def test_inherited_skill_with_source_and_upstream(self) -> None:
        text = """# §0 METADATA{
#   level: 2,
#   name: "owasp-top10",
#   usage: "skill",
#   kind: "inherited",
#   source: "https://owasp.org/Top10/",
#   upstream_version: "2021"
# }
"""
        meta = validate_metadata(text)
        assert meta.kind is ArtifactKind.INHERITED
        assert meta.source == "https://owasp.org/Top10/"
        assert meta.upstream_version == "2021"


# --- strip/render round-trip ------------------------------------------------

class TestStripAndRender:
    def test_strip_removes_block(self) -> None:
        stripped = strip_metadata_block(VALID_LEVEL_3)
        assert "§0 METADATA" not in stripped
        assert "$0" in stripped

    def test_strip_noop_when_absent(self) -> None:
        stripped = strip_metadata_block(NO_METADATA)
        assert stripped == NO_METADATA

    def test_render_produces_parseable_block(self) -> None:
        meta = ArtifactMetadata(
            level=CortexLevel.BRAIN,
            name="brain",
            usage=ArtifactUsage.STATE,
            kind=ArtifactKind.NATIVE,
        )
        block = render_metadata_block(meta)
        # Round-trip: rendered block can be re-parsed.
        reparsed = validate_metadata(block)
        assert reparsed.level is CortexLevel.BRAIN
        assert reparsed.name == "brain"

    def test_render_includes_optional_fields(self) -> None:
        meta = ArtifactMetadata(
            level=CortexLevel.PACKAGE,
            name="jarvis-lessons",
            usage=ArtifactUsage.LESSON,
            kind=ArtifactKind.NATIVE,
            agent="jarvis",
        )
        block = render_metadata_block(meta)
        assert '"jarvis"' in block
        assert "agent" in block


# --- read_cortex_artifact tests ---------------------------------------------

class TestReadCortexArtifact:
    def test_reads_file_with_metadata(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text(VALID_LEVEL_3, encoding="utf-8")
        art = read_cortex_artifact(p)
        assert isinstance(art, CortexArtifact)
        assert art.level is CortexLevel.BRAIN
        assert art.filename == "brain"
        assert art.path == p
        assert art.warnings == []
        # Payload preserves the §0 METADATA block (lossless read).
        assert "§0 METADATA" in art.payload

    def test_reads_file_without_metadata_warns(self, tmp_path: Path) -> None:
        p = tmp_path / "legacy.cortex"
        p.write_text(NO_METADATA, encoding="utf-8")
        art = read_cortex_artifact(p)
        assert art.level is CortexLevel.PACKAGE
        assert W001_NO_METADATA in art.warnings


# --- migrator tests ---------------------------------------------------------

class TestMigrator:
    def test_migrate_file_injects_block(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text("$0\nGSIG:IDN:identity|attrs|B|Semantic|Actor identity\n", encoding="utf-8")
        migrated = migrate_file(p, level=3, name="brain", usage="state", kind="native")
        assert migrated is True
        content = p.read_text(encoding="utf-8")
        assert has_metadata_block(content)
        # Original content preserved below the block.
        assert "$0" in content
        assert "GSIG:IDN" in content

    def test_migrate_file_idempotent(self, tmp_path: Path) -> None:
        p = tmp_path / "brain.cortex"
        p.write_text(VALID_LEVEL_3, encoding="utf-8")
        migrated = migrate_file(p, level=3, name="brain", usage="state", kind="native")
        assert migrated is False
        # File content unchanged.
        assert p.read_text(encoding="utf-8") == VALID_LEVEL_3

    def test_migrate_file_preserves_content_below_block(self, tmp_path: Path) -> None:
        original_body = "$0\nGSIG:IDN:identity|attrs|B|Semantic|Actor identity\n\n$1: IDENTITY\nIDN:governor{project:\"x\"}\n"
        p = tmp_path / "brain.cortex"
        p.write_text(original_body, encoding="utf-8")
        migrate_file(p, level=3, name="brain", usage="state", kind="native")
        content = p.read_text(encoding="utf-8")
        # The original body appears verbatim below the injected block.
        assert original_body in content

    def test_migrate_file_with_optional_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "jarvis.lessons.cortex"
        p.write_text("$0\nGSIG:LNG:lesson|attrs|M|Episodic|Lesson\n", encoding="utf-8")
        migrated = migrate_file(
            p, level=0, name="jarvis-lessons", usage="lesson", kind="native",
            agent="jarvis",
        )
        assert migrated is True
        art = read_cortex_artifact(p)
        assert art.metadata.agent == "jarvis"
        assert art.metadata.usage is ArtifactUsage.LESSON

    def test_migrate_identity_files_processes_directory(self, tmp_path: Path) -> None:
        ids_dir = tmp_path / "identities"
        ids_dir.mkdir()
        (ids_dir / "jarvis.cortex").write_text("$0\nGSIG:IDN\n", encoding="utf-8")
        (ids_dir / "alfred.cortex").write_text("$0\nGSIG:IDN\n", encoding="utf-8")
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
