"""Tests for skill.get (BLP-012) — read-only skill reading via MCP."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from arqux.handlers.skill import get_skill


@pytest.fixture
def arqux(tmp_path: Path) -> Path:
    arq = tmp_path / ".arqux"
    skills = arq / "skills"
    skills.mkdir(parents=True)
    (arq / "brain.cortex").write_text("$1: CORE\n", encoding="utf-8")
    (skills / "protocol.skill.md").write_text("$0\nprotocolo demo\n", encoding="utf-8")
    return arq


def test_skill_get_happy(arqux: Path) -> None:
    out = get_skill(name="protocol", path=str(arqux.parent))
    assert out.profile == "OUT-WORK"
    assert "protocolo demo" in out.fields["content"]
    assert out.fields["size"] > 0
    assert out.fields["relative_path"] == "protocol.skill.md"


def test_skill_get_not_found(arqux: Path) -> None:
    out = get_skill(name="nope", path=str(arqux.parent))
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "NOT_FOUND"
    assert "protocol.skill.md" in out.fields.get("available_skills", [])


def test_skill_get_content_override(arqux: Path) -> None:
    out = get_skill(content="name:protocol", path=str(arqux.parent))
    # content has no 'name' key parse? name comes from CORTEX key
    assert out.profile == "OUT-WORK"
    assert "protocolo demo" in out.fields["content"]


def test_skill_get_requires_name_when_no_content() -> None:
    out = get_skill()
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "INVALID_ARGS"


def test_skill_get_is_read_only(arqux: Path) -> None:
    """AC-06: file bytes identical before/after the call."""
    target = arqux / "skills" / "protocol.skill.md"
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    get_skill(name="protocol", path=str(arqux.parent))
    after = hashlib.sha256(target.read_bytes()).hexdigest()
    assert before == after
