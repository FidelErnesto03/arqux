"""Tests for _cortex_crud layer in state.py."""

from __future__ import annotations

from pathlib import Path

from arqux.state import (
    crud_read,
    crud_add,
    crud_update,
    crud_delete,
    crud_move,
    crud_list,
)


_SAMPLE_CORTEX = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# OBJ   | objective  | attrs      | H | Working        | Active goal
# DESC  | description | cuerpo     | B | Semantic       | Structured description

$1: IDENTITY

IDN:test{name:"test", role:"test", kind:"brain"}

$2: FOCUS

FCS:primary{what:"Test focus", priority:"high", status:"current", survive:"work"}

$3: OBJECTIVES

OBJ:goal1{goal:"Test objective", status:"current", success:"verified", survive:"work"}
"""


def test_crud_read_returns_entries(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    result = crud_read(f, "FCS:*")
    assert result["path"] == str(f)
    entries = result["entries"]
    assert len(entries) >= 1
    assert entries[0]["sigil"] == "FCS"
    assert entries[0]["name"] == "primary"


def test_crud_read_with_section_selector(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    result = crud_read(f, "$1/IDN:*")
    assert len(result["entries"]) >= 1
    assert result["entries"][0]["sigil"] == "IDN"


def test_crud_add_attrs_entry(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    result = crud_add(f, "$3", "OBJ", "goal2", {"goal": "Another objective", "status": "current", "success": "verified", "survive": "work"}, force=True)
    assert "error" not in result, result.get("error")
    # Verify it was added
    r2 = crud_read(f, "OBJ:*")
    names = [e["name"] for e in r2["entries"]]
    assert "goal2" in names


def test_crud_add_with_create_section(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    result = crud_add(f, "$5", "LNG", "test_lesson", {"type": "behavioral", "cause": "test", "lesson": "Test", "prevention": "test"}, create_section=True, force=True)
    assert "error" not in result, result.get("error")
    r2 = crud_list(f, section="$5")
    assert len(r2["entries"]) >= 1


def test_crud_update_attrs(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    result = crud_update(f, "$2/FCS:primary", set_={"priority": "low"}, force=True)
    assert "error" not in result, result.get("error")
    r2 = crud_read(f, "$2/FCS:primary")
    assert r2["entries"][0]["value"]["priority"] == "low"


def test_crud_delete_entry(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    # Add a second OBJ first so brain still has one after deletion
    crud_add(f, "$3", "OBJ", "goal2", {"goal": "Extra obj", "status": "current", "success": "verified", "survive": "work"}, force=True)
    result = crud_delete(f, "$3/OBJ:goal1", force=True)
    assert "error" not in result, result.get("error")
    r2 = crud_read(f, "OBJ:*")
    names = [e["name"] for e in r2["entries"]]
    assert "goal1" not in names
    assert "goal2" in names


def test_crud_list_filters(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_CORTEX)
    # All entries
    all_ = crud_list(f)
    assert len(all_["entries"]) >= 3
    # By sigil
    by_sigil = crud_list(f, sigil="FCS")
    assert len(by_sigil["entries"]) >= 1
    assert by_sigil["entries"][0]["sigil"] == "FCS"
    # By section
    by_sec = crud_list(f, section="$2")
    assert len(by_sec["entries"]) >= 1


def test_crud_read_not_found(tmp_path: Path) -> None:
    f = tmp_path / "nonexistent.cortex"
    try:
        crud_read(f, "FCS:*")
        assert False, "should raise"
    except FileNotFoundError:
        pass
