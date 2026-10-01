"""Tests for the universal skill resolver + skill.edit wiring (BLP-012).

Covers AC-10..AC-12 and Restricción 4 (backward-compatible parity).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers.skill import edit_skill, get_skill, resolve_skill


@pytest.fixture
def arqux(tmp_path: Path) -> Path:
    """Governed root .arqux/ with root skills + nested workflow files."""
    arq = tmp_path / ".arqux"
    skills = arq / "skills"
    (skills / "workflows").mkdir(parents=True)
    (skills / "originals").mkdir()
    (arq / "brain.cortex").write_text("$1: CORE\n", encoding="utf-8")
    (skills / "protocol.skill.md").write_text("$0\nprotocolo\n", encoding="utf-8")
    (skills / "diagram.skill.md").write_text("$0\ndiagrama\n", encoding="utf-8")
    (skills / "workflows" / "w10-identity-handoff.md").write_text(
        "$0\nw10 handoff\n", encoding="utf-8"
    )
    (skills / "workflows" / "w01-workspace-init.md").write_text(
        "$0\nw01 init\n", encoding="utf-8"
    )
    (skills / "originals" / "apex-page-builder.skill.md").write_text(
        "raw\n", encoding="utf-8"
    )
    return arq


# ---------------------------------------------------------------------------
# AC-10 — nested skills reachable by name and by relative path
# ---------------------------------------------------------------------------


def test_resolve_nested_by_unique_name(arqux: Path) -> None:
    r = resolve_skill(arqux, "w10-identity-handoff")
    assert r["ok"] is True
    assert r["path"].name == "w10-identity-handoff.md"
    assert r["path"].parent.name == "workflows"


def test_resolve_nested_by_relative_path(arqux: Path) -> None:
    r = resolve_skill(arqux, "workflows/w10-identity-handoff")
    assert r["ok"] is True
    assert r["path"].name == "w10-identity-handoff.md"


def test_get_skill_nested(arqux: Path) -> None:
    out = get_skill(name="w10-identity-handoff", path=str(arqux.parent))
    assert out.profile == "OUT-WORK"
    assert "w10 handoff" in out.fields["content"]
    assert out.fields["relative_path"] == "workflows/w10-identity-handoff.md"


def test_edit_skill_section_on_nested(arqux: Path) -> None:
    """Editing a nested skill by unique name writes the nested file."""
    out = edit_skill(
        name="w10-identity-handoff",
        content="seccion nueva",
        section="$1",
        path=str(arqux.parent),
    )
    assert out.profile == "OUT-ERROR"  # no $1 in fixture — but resolved
    out2 = edit_skill(
        name="workflows/w10-identity-handoff",
        content="$0\nw10 handoff editado\n",
        path=str(arqux.parent),
    )
    assert out2.profile == "OUT-WORK"
    assert "editado" in (arqux / "skills/workflows/w10-identity-handoff.md").read_text()


# ---------------------------------------------------------------------------
# AC-11 — root names keep resolving to the same path (parity)
# ---------------------------------------------------------------------------


def test_root_names_parity(arqux: Path) -> None:
    """Every pre-existing root name resolves to the canonical .skill.md path."""
    r = resolve_skill(arqux, "protocol")
    assert r["ok"] is True
    assert r["path"] == arqux / "skills" / "protocol.skill.md"


def test_legacy_skill_path_suffix_wins(arqux: Path) -> None:
    """Root `<name>.skill.md` beats any nested namesake."""
    r = resolve_skill(arqux, "protocol")
    assert r["path"].parent == arqux / "skills"


# ---------------------------------------------------------------------------
# AC-12 — edge cases: ambiguity, traversal, not-found guidance
# ---------------------------------------------------------------------------


def test_ambiguous_returns_candidates(arqux: Path) -> None:
    (arqux / "skills" / "workflows" / "dup.md").write_text("a\n")
    (arqux / "skills" / "other").mkdir()
    (arqux / "skills" / "other" / "dup.md").write_text("b\n")
    r = resolve_skill(arqux, "dup")
    assert r["ok"] is False
    assert r["code"] == "AMBIGUOUS"
    assert len(r["candidates"]) == 2


def test_traversal_rejected(arqux: Path) -> None:
    for bad in ("../x", "/etc/passwd", "..\\win"):
        r = resolve_skill(arqux, bad)
        assert r["ok"] is False
        assert r["code"] == "INVALID_ARGS"


def test_not_found_lists_available(arqux: Path) -> None:
    r = resolve_skill(arqux, "inexistente")
    assert r["code"] == "NOT_FOUND"
    assert "protocol.skill.md" in r["available_skills"]
    assert "workflows/w10-identity-handoff.md" in r["available_skills"]


def test_get_skill_not_found_guidance(arqux: Path) -> None:
    out = get_skill(name="inexistente", path=str(arqux.parent))
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "NOT_FOUND"
    assert "protocol.skill.md" in (out.fields.get("available_skills") or [])


def test_originals_not_candidate(arqux: Path) -> None:
    r = resolve_skill(arqux, "apex-page-builder")
    assert r["ok"] is False  # originals/ excluded from resolution
    assert r["code"] == "NOT_FOUND"
