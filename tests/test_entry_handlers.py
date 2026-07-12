"""Tests for cortex.entry.* MCP handlers."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import (
    entry_add_handler,
    entry_delete_handler,
    entry_get_handler,
    entry_list_handler,
    entry_update_handler,
)
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# OBJ   | objective  | attrs      | H | Working        | Active goal

$1: IDENTITY

IDN:test{name:"test", role:"test", kind:"brain"}

$2: FOCUS

FCS:primary{what:"Test focus", priority:"high", status:"current", survive:"work"}

$3: OBJECTIVES

OBJ:goal1{goal:"Test objective", status:"current", success:"verified", survive:"work"}
"""


def test_entry_get_returns_matching(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_get_handler(str(f), "FCS:*", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("count", 0) >= 1
    entries = result.fields.get("entries", [])
    assert entries[0]["sigil"] == "FCS"


def test_entry_get_not_found(tmp_path: Path) -> None:
    result = entry_get_handler(str(tmp_path / "nope.cortex"), "FCS:*", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"


def test_entry_add_and_read(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    add = entry_add_handler(str(f), "$3", "OBJ", "goal2", 'goal:"Second", status:"current", success:"verified", survive:"work"', force=True, ctx=_CONTEXT)
    assert add.profile == "OUT-WORK", str(add.fields)
    # Entry is stored with _XXXX suffix — the returned name includes it
    stored_name = add.fields.get("name", "goal2_0001")
    get = entry_get_handler(str(f), f"OBJ:{stored_name}", ctx=_CONTEXT)
    assert get.profile == "OUT-WORK"
    assert get.fields.get("count", 0) == 1


def test_entry_update_priority(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    upd = entry_update_handler(str(f), "FCS:primary", set_='priority:low', force=True, ctx=_CONTEXT)
    assert upd.profile == "OUT-WORK", str(upd.fields)
    get = entry_get_handler(str(f), "FCS:primary", ctx=_CONTEXT)
    assert get.fields["entries"][0]["value"]["priority"] == "low"


def test_entry_delete(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    # Add a second OBJ first so brain still has one
    entry_add_handler(str(f), "$3", "OBJ", "goal2", 'goal:"Extra", status:"current", success:"verified", survive:"work"', force=True, ctx=_CONTEXT)
    dl = entry_delete_handler(str(f), "OBJ:goal1", force=True, ctx=_CONTEXT)
    assert dl.profile == "OUT-WORK", str(dl.fields)
    get = entry_get_handler(str(f), "OBJ:*", ctx=_CONTEXT)
    names = [e["name"] for e in get.fields.get("entries", [])]
    assert "goal1" not in names
    assert any(n.startswith("goal2") for n in names)


def test_entry_list_all(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    assert lst.fields.get("count", 0) >= 3


def test_entry_list_filtered(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), sigil="OBJ", ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    assert lst.fields.get("count", 0) >= 1
    assert lst.fields["entries"][0]["sigil"] == "OBJ"
