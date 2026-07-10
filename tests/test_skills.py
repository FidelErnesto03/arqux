"""Tests for SkillRepository, OriginalStore, AdaptedStore (BLP-040)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.constants import W005_MISSING_ORIGINAL_REF
from arqux.skill_store import (
    AdaptedStore,
    OriginalStore,
    SkillContract,
    SkillImportError,
    SkillNotFoundError,
    SkillRepository,
    STPDeclaration,
)


# --- Fixtures ---------------------------------------------------------------

@pytest.fixture
def arqux_root(tmp_path: Path) -> Path:
    """A fake .arqux/ workspace root."""
    return tmp_path / ".arqux"


@pytest.fixture
def repo(arqux_root: Path) -> SkillRepository:
    return SkillRepository(arqux_root)


# --- OriginalStore tests ----------------------------------------------------

class TestOriginalStore:
    def test_save_persists_with_metadata(self, arqux_root: Path) -> None:
        store = OriginalStore(arqux_root)
        decl = STPDeclaration(
            name="owasp-top10",
            kind="inherited",
            source="https://owasp.org/Top10/",
            upstream_version="2021",
        )
        path = store.save("owasp-top10", "# OWASP Top 10\n", decl)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "ARQX:artifact" in content
        assert 'name:"owasp-top10"' in content
        assert 'kind:"inherited"' in content
        assert 'source:"https://owasp.org/Top10/"' in content
        assert 'upstream_version:"2021"' in content

    def test_get_returns_contract(self, arqux_root: Path) -> None:
        store = OriginalStore(arqux_root)
        decl = STPDeclaration(name="owasp", kind="inherited", source="upstream")
        store.save("owasp", "# OWASP\n", decl)
        contract = store.get("owasp")
        assert contract.declaration.kind == "inherited"
        assert contract.declaration.source == "upstream"
        assert "# OWASP" in contract.content

    def test_get_not_found_raises(self, arqux_root: Path) -> None:
        store = OriginalStore(arqux_root)
        with pytest.raises(SkillNotFoundError):
            store.get("nonexistent")

    def test_exists(self, arqux_root: Path) -> None:
        store = OriginalStore(arqux_root)
        assert not store.exists("owasp")
        store.save("owasp", "# x\n", STPDeclaration(name="owasp", kind="inherited"))
        assert store.exists("owasp")

    def test_list_returns_names(self, arqux_root: Path) -> None:
        store = OriginalStore(arqux_root)
        store.save("a", "# a\n", STPDeclaration(name="a", kind="inherited"))
        store.save("b", "# b\n", STPDeclaration(name="b", kind="inherited"))
        assert store.list() == ["a", "b"]


# --- AdaptedStore tests -----------------------------------------------------

class TestAdaptedStore:
    def test_save_native_skill(self, arqux_root: Path) -> None:
        store = AdaptedStore(arqux_root)
        path = store.save("my-skill", "# My Skill\n")
        content = path.read_text(encoding="utf-8")
        assert 'kind:"native"' in content

    def test_save_adapted_with_original_ref(self, arqux_root: Path) -> None:
        store = AdaptedStore(arqux_root)
        path = store.save(
            "owasp", "# Adapted OWASP\n",
            original_ref="/skills/originals/owasp.skill.md",
        )
        content = path.read_text(encoding="utf-8")
        assert 'kind:"adapted"' in content
        assert 'source:"/skills/originals/owasp.skill.md"' in content

    def test_get_adapted_returns_contract(self, arqux_root: Path) -> None:
        store = AdaptedStore(arqux_root)
        store.save(
            "owasp", "# Adapted\n",
            original_ref="/skills/originals/owasp.skill.md",
        )
        contract = store.get("owasp")
        assert contract.kind == "adapted"
        assert contract.original_ref == "/skills/originals/owasp.skill.md"

    def test_adapted_without_original_ref_warns(self, arqux_root: Path) -> None:
        # AC: AdaptedStore without original_ref → Warning W005.
        store = AdaptedStore(arqux_root)
        # Manually craft a declaration with kind=adapted but no source.
        decl = STPDeclaration(name="x", kind="adapted")
        store.save("x", "# x\n", declaration=decl)
        contract = store.get("x")
        assert W005_MISSING_ORIGINAL_REF in contract.warnings


# --- SkillRepository tests --------------------------------------------------

class TestSkillRepository:
    def test_resolve_prefers_adapted_over_original(self, arqux_root: Path) -> None:
        repo = SkillRepository(arqux_root)
        # Save in originals first.
        decl_inherited = STPDeclaration(
            name="owasp", kind="inherited", source="upstream",
        )
        repo.original.save("owasp", "# Original OWASP\n", decl_inherited)
        # Save an adapted version.
        repo.adapted.save(
            "owasp", "# Adapted OWASP\n",
            original_ref="/skills/originals/owasp.skill.md",
        )
        contract = repo.resolve("owasp")
        assert contract.kind == "adapted"
        assert "# Adapted OWASP" in contract.content

    def test_resolve_falls_back_to_original(self, arqux_root: Path) -> None:
        repo = SkillRepository(arqux_root)
        decl = STPDeclaration(name="owasp", kind="inherited", source="upstream")
        repo.original.save("owasp", "# Original OWASP\n", decl)
        contract = repo.resolve("owasp")
        assert contract.kind == "inherited"
        assert "# Original OWASP" in contract.content

    def test_resolve_falls_back_to_native(self, arqux_root: Path) -> None:
        # A native skill shipped with ArqUX.
        repo = SkillRepository(arqux_root)
        # "cortex" is a known packaged skill.
        contract = repo.resolve("cortex")
        assert contract.kind == "native"
        assert contract.path.exists()

    def test_resolve_unknown_raises(self, arqux_root: Path) -> None:
        repo = SkillRepository(arqux_root)
        with pytest.raises(SkillNotFoundError):
            repo.resolve("nonexistent-skill-xyz")

    def test_import_skill_creates_both_stores(self, arqux_root: Path) -> None:
        repo = SkillRepository(arqux_root)
        result = repo.import_skill(
            source="https://example.com/skills/owasp.md",
            name="owasp",
            content="# OWASP\n",
            upstream_version="2021",
        )
        assert result["kind"] == "inherited"
        assert Path(result["original_path"]).exists()
        assert Path(result["adapted_path"]).exists()
        # Both files should have inherited metadata.
        original_contract = repo.original.get("owasp")
        adapted_contract = repo.adapted.get("owasp")
        assert original_contract.declaration.kind == "inherited"
        assert adapted_contract.declaration.kind == "inherited"
        assert original_contract.declaration.source == "https://example.com/skills/owasp.md"
        assert adapted_contract.declaration.source == "https://example.com/skills/owasp.md"

    def test_import_skill_overwrites_adapted_preserves_original(
        self, arqux_root: Path,
    ) -> None:
        # AC-02 edge case: re-importing overwrites adapted, preserves original.
        repo = SkillRepository(arqux_root)
        repo.import_skill(
            source="https://example.com/skills/owasp.md",
            name="owasp", content="# Original content\n",
        )
        # Modify adapted independently.
        repo.adapted.save(
            "owasp", "# Modified adapted\n",
            declaration=STPDeclaration(
                name="owasp", kind="adapted",
                source="https://example.com/skills/owasp.md",
            ),
        )
        # Re-import: original should be overwritten, adapted too.
        repo.import_skill(
            source="https://example.com/skills/owasp.md",
            name="owasp", content="# Re-imported content\n",
        )
        original = repo.original.get("owasp")
        assert "Re-imported content" in original.content

    def test_list_all_aggregates_across_stores(self, arqux_root: Path) -> None:
        repo = SkillRepository(arqux_root)
        repo.original.save(
            "a", "# a\n",
            STPDeclaration(name="a", kind="inherited", source="upstream"),
        )
        repo.adapted.save("b", "# b\n")
        # "cortex" is a native skill.
        all_skills = repo.list_all()
        names = [s["name"] for s in all_skills]
        assert "a" in names
        assert "b" in names
        # cortex is bundled — should be present.
        assert "cortex" in names


# --- STPDeclaration tests ---------------------------------------------------

class TestSTPDeclaration:
    def test_default_declaration_is_native(self) -> None:
        decl = STPDeclaration(name="my-skill")
        assert decl.kind == "native"
        assert decl.level == 2
        assert decl.usage == "skill"

    def test_inherited_declaration_carries_source(self) -> None:
        decl = STPDeclaration(
            name="owasp", kind="inherited",
            source="https://owasp.org", upstream_version="2021",
        )
        assert decl.kind == "inherited"
        assert decl.source == "https://owasp.org"

    def test_to_metadata_round_trips(self) -> None:
        decl = STPDeclaration(
            name="x", kind="adapted", source="upstream", upstream_version="v1",
        )
        meta = decl.to_metadata()
        assert meta.name == "x"
        assert meta.kind.value == "adapted"
        assert meta.source == "upstream"
        assert meta.upstream_version == "v1"
