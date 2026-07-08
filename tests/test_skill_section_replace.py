"""Regression tests for CORTEX skill section replacement."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.skill import _replace_skill_section, edit_skill


def test_replace_intermediate_section_preserves_later_sections() -> None:
    body = (
        "$1: IDENTITY\n"
        "SKL:test{}\n"
        "\n"
        "$2: DESCRIPTION\n"
        "DESC:old{}\n"
        "\n"
        "$3: CANON\n"
        "old body\n"
        "\n"
        "$4: RULES\n"
        "RULE:keep{}\n"
    )

    updated = _replace_skill_section(body, "$3", "DESC:new{value:\"ok\"}")

    assert updated is not None
    assert "$3: CANON\nDESC:new{value:\"ok\"}\n" in updated
    assert "$4: RULES\nRULE:keep{}\n" in updated
    assert "old body" not in updated


def test_replace_last_section() -> None:
    body = "$1: IDENTITY\nSKL:test{}\n\n$2: DESCRIPTION\nold\n"

    updated = _replace_skill_section(body, "2", "new")

    assert updated == "$1: IDENTITY\nSKL:test{}\n\n$2: DESCRIPTION\nnew\n"


def test_replace_zero_section_without_title() -> None:
    body = "$0\nADA:old{}\n\n$1: IDENTITY\nSKL:test{}\n"

    updated = _replace_skill_section(body, "$0", "ADA:new{status:\"active\"}")

    assert updated == "$0\nADA:new{status:\"active\"}\n$1: IDENTITY\nSKL:test{}\n"


def test_strips_duplicate_header_from_new_content() -> None:
    body = "$2.1: DETAILS\nold\n\n$3: NEXT\nkeep\n"

    updated = _replace_skill_section(body, "$2.1", "$2.1: DETAILS\nnew")

    assert updated == "$2.1: DETAILS\nnew\n$3: NEXT\nkeep\n"


def test_duplicate_same_section_header_is_replaced_as_part_of_section() -> None:
    body = (
        "$3: CANON\n"
        "first stale body\n"
        "$3: CANON\n"
        "duplicate stale body\n"
        "$4: RULES\n"
        "keep\n"
    )

    updated = _replace_skill_section(body, "3", "clean body")

    assert updated == "$3: CANON\nclean body\n$4: RULES\nkeep\n"


def test_new_content_may_contain_cortex_characters() -> None:
    body = "$1: IDENTITY\nold\n$2: NEXT\nkeep\n"
    content = "DESC:example{value:\"$x:{y}\", note:\"colon: ok\"}"

    updated = _replace_skill_section(body, "1", content)

    assert updated == "$1: IDENTITY\nDESC:example{value:\"$x:{y}\", note:\"colon: ok\"}\n$2: NEXT\nkeep\n"


def test_missing_section_returns_none() -> None:
    body = "$1: IDENTITY\nSKL:test{}\n"

    assert _replace_skill_section(body, "2", "new") is None


def test_edit_skill_section_preserves_protocol_tail(tmp_path: Path) -> None:
    arqux_dir = tmp_path / ".arqux"
    skill_dir = arqux_dir / "skills"
    skill_dir.mkdir(parents=True)
    (arqux_dir / "meta-brain.cortex").write_text("$1: META\nIDN:workspace{}\n", encoding="utf-8")
    skill_path = skill_dir / "protocol.skill.md"
    skill_path.write_text(
        "$1: IDENTITY\n"
        "SKL:protocol{}\n"
        "\n"
        "$2: SUMMARY\n"
        "before\n"
        "\n"
        "$3: STARTUP\n"
        "old startup\n"
        "\n"
        "$4: RESPONSE\n"
        "must survive\n"
        "\n"
        "$5: CLOSURE\n"
        "must also survive\n",
        encoding="utf-8",
    )

    result = edit_skill(
        name="protocol",
        section="$3",
        content="$3: STARTUP\nnew startup",
        path=str(tmp_path),
    )

    updated = skill_path.read_text(encoding="utf-8")
    assert result.profile == "OUT-WORK"
    assert "$3: STARTUP\nnew startup\n" in updated
    assert "$4: RESPONSE\nmust survive\n" in updated
    assert "$5: CLOSURE\nmust also survive\n" in updated
    assert "old startup" not in updated
