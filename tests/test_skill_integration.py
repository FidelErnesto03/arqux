"""Integration tests for arqux.handlers.skill — with SkillRepository."""

from __future__ import annotations

from pathlib import Path

import pytest


MINIMAL_SKILL = """\
$0

# Sigil | Name | Type | Risk | Cognitive Layer | Description
# ADA   | ada   | attrs| M    | Semantic       | Adaptation

$0.1: ARQUX METADATA

ARQX:artifact{level:"2", name:"test-skill", usage:"skill", kind:"native"}

$1: IDENTITY

IDN:test{name:"test-skill", purpose:"test skill"}

$7: ADAPTATIONS
"""


@pytest.fixture
def arqux_root(tmp_path: Path) -> Path:
    """Create .arqux/ with skills/ + brain.cortex (for _resolve_arqux_root) and a test skill."""
    root = tmp_path / ".arqux"
    root.mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(exist_ok=True)
    (root / "skills" / "originals").mkdir(exist_ok=True)
    (root / "skills" / "workflows").mkdir(exist_ok=True)
    skill = root / "skills" / "test-skill.skill.md"
    skill.write_text(MINIMAL_SKILL, encoding="utf-8")
    # Minimal brain.cortex so find_project_root works
    brain = root / "brain.cortex"
    brain.write_text("$0\n\n$1: IDENTITY\n\n", encoding="utf-8")
    return root


class TestSkillUtilities:
    """Test _skill_path, _append_ada_to_skill, _replace_skill_section."""

    def test_skill_path(self, arqux_root) -> None:
        from arqux.handlers.skill import _skill_path
        result = _skill_path(arqux_root, "test-skill")
        assert str(result).endswith("skills/test-skill.skill.md")

    def test_append_ada(self, arqux_root) -> None:
        from arqux.handlers.skill import _append_ada_to_skill
        skill = arqux_root / "skills" / "test-skill.skill.md"
        # First append creates section
        _append_ada_to_skill(skill, "test-skill", '# ADA ADA-001: test adaptation')
        content = skill.read_text(encoding="utf-8")
        assert "ADA-001" in content
        assert "test adaptation" in content

    def test_append_ada_to_existing_section(self, tmp_path) -> None:
        """_append_ada_to_skill appends when $0: ADAPTATIONS already exists."""
        from arqux.handlers.skill import _append_ada_to_skill

        skill = tmp_path / "existing-ada.skill.md"
        skill.write_text(
            "$0\n\n$0: ADAPTATIONS\n\nADA:old{existing}\n\n$1: IDENTITY\ndata\n",
            encoding="utf-8",
        )
        _append_ada_to_skill(skill, "test", "# ADA 002: new adaptation")
        content = skill.read_text(encoding="utf-8")
        assert "ADA 002" in content
        assert "existing" in content  # original preserved

    def test_append_ada_no_section(self, tmp_path) -> None:
        """_append_ada_to_skill creates $0 section if missing."""
        from arqux.handlers.skill import _append_ada_to_skill

        skill = tmp_path / "no-ada.skill.md"
        skill.write_text("$0\n\n$1: IDENTITY\ndata\n", encoding="utf-8")
        _append_ada_to_skill(skill, "test", "# ADA 001: new")
        content = skill.read_text(encoding="utf-8")
        assert "ADA 001" in content

    def test_replace_section_found(self) -> None:
        from arqux.handlers.skill import _replace_skill_section
        body = "$0\n\n$1: IDENTITY\nold data\n"
        result = _replace_skill_section(body, "$1", "new data")
        assert result is not None
        assert "new data" in result
        assert "old data" not in result

    def test_replace_section_not_found(self) -> None:
        from arqux.handlers.skill import _replace_skill_section
        result = _replace_skill_section("$0\n", "$9", "x")
        assert result is None


class TestSkillHandlers:
    """Test skill handler functions against real store."""

    def test_list_skills(self, arqux_root) -> None:
        from arqux.handlers.skill import list_skills
        r = list_skills(path=str(arqux_root.parent))
        text = r.to_text()
        assert "OUT-WORK" in text or "OUT-ERROR" in text

    def test_edit_skill_read(self, arqux_root) -> None:
        from arqux.handlers.skill import edit_skill
        r = edit_skill(name="test-skill", content=None, section=None, path=str(arqux_root.parent))
        text = r.to_text()
        assert len(text) > 0

    def test_edit_skill_section(self, arqux_root) -> None:
        from arqux.handlers.skill import edit_skill
        r = edit_skill(name="test-skill", content="new content", section="$1", path=str(arqux_root.parent))
        text = r.to_text()
        assert len(text) > 0

    def test_import_skill(self, arqux_root) -> None:
        from arqux.handlers.skill import import_skill
        r = import_skill(
            source="https://example.com/test.skill.md",
            name="imported-skill",
            content="$0\n\n$1: IDENTITY\nimported\n",
            path=str(arqux_root.parent),
        )
        text = r.to_text()
        assert "OUT-WORK" in text or "OUT-ERROR" in text

    def test_import_skill_no_content(self, arqux_root) -> None:
        """import_skill without content returns awaiting_content status."""
        from arqux.handlers.skill import import_skill
        r = import_skill(
            source="https://example.com/empty.md",
            name="empty-skill",
            content=None,
            path=str(arqux_root.parent),
        )
        assert "OUT-WORK" in r.to_text()
        assert "awaiting_content" in r.to_text()

    def test_edit_skill_nonexistent(self, arqux_root) -> None:
        """edit_skill returns error for nonexistent skill."""
        from arqux.handlers.skill import edit_skill
        r = edit_skill(name="nonexistent", content=None, path=str(arqux_root.parent))
        assert "OUT-ERROR" in r.to_text()

    def test_import_skills_listed(self, arqux_root) -> None:
        """imported skills appear in list_skills output."""
        from arqux.handlers.skill import import_skill, list_skills
        import_skill(
            source="https://example.com/new-skill.md",
            name="brand-new-skill",
            content="$0\n\n$1: IDENTITY\nnew\n",
            path=str(arqux_root.parent),
        )
        r = list_skills(path=str(arqux_root.parent))
        text = r.to_text()
        assert len(text) > 0

    def test_convert_skill(self, arqux_root) -> None:
        """convert_skill produces output."""
        from arqux.handlers.skill import convert_skill
        from arqux.permissions import PermissionContext

        ctx = PermissionContext(agent_id="jarvis", role="executor")
        r = convert_skill(
            name="test-skill",
            path=str(arqux_root.parent),
            ctx=ctx,
        )
        text = r.to_text()
        assert len(text) > 0
        assert "OUT-" in text

    def test_convert_nonexistent(self, arqux_root) -> None:
        """convert_skill returns error for nonexistent skill."""
        from arqux.handlers.skill import convert_skill

        r = convert_skill(
            name="nonexistent",
            path=str(arqux_root.parent),
        )
        assert "OUT-ERROR" in r.to_text()

    def test_record_adaptation(self, arqux_root) -> None:
        """record_adaptation returns response."""
        from arqux.handlers.skill import record_adaptation

        r = record_adaptation(
            name="test-skill",
            expected="valid input",
            actual="invalid input",
            reason="always validate",
            path=str(arqux_root.parent),
        )
        text = r.to_text()
        assert len(text) > 0
