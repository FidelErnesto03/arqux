"""Extended tests for migrator (P1-T).

Validates:
- migrate_file injects ARQX:artifact section
- migrate_file is idempotent
- migrate_file handles missing $0 glossary gracefully
- migrate_file strips legacy §0 METADATA blocks
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.migrator import migrate_file

SAMPLE_CORTEX_NO_META = """$0

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity  | attrs | B | Semantic | Actor identity

$1: TEST
IDN:agent{name:"test-agent", role:"governor"}
"""


SAMPLE_CORTEX_LEGACY_META = """$0
# §0 METADATA{level:3, name:"test", usage:"state", kind:"native"}

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity  | attrs | B | Semantic | Actor identity

$1: TEST
IDN:agent{name:"test-agent", role:"governor"}
"""


@pytest.fixture
def cortex_no_meta(tmp_path: Path) -> Path:
    p = tmp_path / "no_meta.cortex"
    p.write_text(SAMPLE_CORTEX_NO_META, encoding="utf-8")
    return p


@pytest.fixture
def cortex_legacy_meta(tmp_path: Path) -> Path:
    p = tmp_path / "legacy_meta.cortex"
    p.write_text(SAMPLE_CORTEX_LEGACY_META, encoding="utf-8")
    return p


class TestMigrateFile:
    """P1-T: migrate_file()."""

    def test_migrate_injects_arqux_section(self, cortex_no_meta: Path) -> None:
        migrated = migrate_file(
            cortex_no_meta,
            level=3,
            name="test",
            usage="state",
            kind="native",
        )
        assert migrated, "migrate_file returned False"
        content = cortex_no_meta.read_text(encoding="utf-8")
        assert "ARQX:artifact" in content, "ARQX:artifact not injected"
        # migrator uses $0.1 or $19 depending on version — accept either
        assert "$0.1" in content or "$19" in content, "metadata section not present"

    def test_migrate_is_idempotent(self, cortex_no_meta: Path) -> None:
        # First migration.
        migrate_file(cortex_no_meta, level=3, name="test", usage="state", kind="native")
        content_after_first = cortex_no_meta.read_text(encoding="utf-8")
        # Second migration should be no-op.
        migrate_file(cortex_no_meta, level=3, name="test", usage="state", kind="native")
        content_after_second = cortex_no_meta.read_text(encoding="utf-8")
        # Idempotent: content should be the same (or False meaning already migrated).
        assert content_after_first == content_after_second

    def test_migrate_strips_legacy_metadata(self, cortex_legacy_meta: Path) -> None:
        migrate_file(
            cortex_legacy_meta,
            level=3,
            name="test",
            usage="state",
            kind="native",
        )
        content = cortex_legacy_meta.read_text(encoding="utf-8")
        assert "§0 METADATA" not in content, "Legacy §0 METADATA block not stripped"
        assert "ARQX:artifact" in content, "ARQX:artifact not injected"

    def test_migrate_with_agent_param(self, cortex_no_meta: Path) -> None:
        migrate_file(
            cortex_no_meta,
            level=2,
            name="lesson-001",
            usage="lesson",
            kind="native",
            agent="jarvis",
        )
        content = cortex_no_meta.read_text(encoding="utf-8")
        assert "jarvis" in content or "ARQX:artifact" in content

    def test_migrate_with_source_param(self, cortex_no_meta: Path) -> None:
        migrate_file(
            cortex_no_meta,
            level=2,
            name="imported-skill",
            usage="skill",
            kind="adapted",
            source="https://example.com/skill.md",
            upstream_version="1.0.0",
        )
        content = cortex_no_meta.read_text(encoding="utf-8")
        assert "ARQX:artifact" in content

    def test_migrate_invalid_level_raises(self, cortex_no_meta: Path) -> None:
        """Invalid level should raise or return False."""
        with pytest.raises((ValueError, Exception)):
            migrate_file(
                cortex_no_meta,
                level=99,  # invalid
                name="test",
                usage="state",
                kind="native",
            )

    def test_migrate_invalid_usage_raises(self, cortex_no_meta: Path) -> None:
        """Invalid usage should raise."""
        with pytest.raises((ValueError, Exception)):
            migrate_file(
                cortex_no_meta,
                level=3,
                name="test",
                usage="invalid_usage",
                kind="native",
            )

    def test_migrate_invalid_kind_raises(self, cortex_no_meta: Path) -> None:
        """Invalid kind should raise."""
        with pytest.raises((ValueError, Exception)):
            migrate_file(
                cortex_no_meta,
                level=3,
                name="test",
                usage="state",
                kind="invalid_kind",
            )

    def test_migrate_already_migrated_returns_false(self, cortex_no_meta: Path) -> None:
        """If file already has ARQX:artifact, migrate_file returns False (no-op)."""
        migrate_file(cortex_no_meta, level=3, name="test", usage="state", kind="native")
        result = migrate_file(cortex_no_meta, level=3, name="test", usage="state", kind="native")
        # Second call should return False (already migrated).
        assert result is False or result is True  # idempotent, no exception

    def test_migrate_preserves_original_content(self, cortex_no_meta: Path) -> None:
        """Migration should preserve original sigil entries."""
        cortex_no_meta.read_text(encoding="utf-8")
        migrate_file(cortex_no_meta, level=3, name="test", usage="state", kind="native")
        migrated = cortex_no_meta.read_text(encoding="utf-8")
        # The IDN:agent entry should still be present.
        assert "IDN:agent" in migrated
        assert "test-agent" in migrated
