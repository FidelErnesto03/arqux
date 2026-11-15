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


# ---------------------------------------------------------------------------
# entry.list selector vocab — parity with cortex.entry.get
# ---------------------------------------------------------------------------


def test_entry_list_selector_section_and_sigil(tmp_path: Path) -> None:
    """selector='$N/SIGIL' filters by section + sigil."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), selector="$3/OBJ", ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    entries = lst.fields["entries"]
    assert entries and all(
        e["sigil"] == "OBJ" and e["section"] == "$3" for e in entries
    )


def test_entry_list_selector_full(tmp_path: Path) -> None:
    """selector='$N/SIGIL:name' filters down to the exact entry."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), selector="$3/OBJ:goal1", ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    entries = lst.fields["entries"]
    assert len(entries) == 1
    assert entries[0]["name"] == "goal1"


def test_entry_list_selector_sigil_only(tmp_path: Path) -> None:
    """selector='SIGIL' / 'SIGIL:*' filters by sigil across sections."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    for sel in ("OBJ", "OBJ:*"):
        lst = entry_list_handler(str(f), selector=sel, ctx=_CONTEXT)
        assert lst.profile == "OUT-WORK", sel
        assert lst.fields["count"] >= 1
        assert all(e["sigil"] == "OBJ" for e in lst.fields["entries"])


def test_entry_list_selector_name_prefix(tmp_path: Path) -> None:
    """Trailing '*' in the name component is a prefix match (entry.get rule)."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), selector="OBJ:go*", ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    assert [e["name"] for e in lst.fields["entries"]] == ["goal1"]


def test_entry_list_selector_section_only(tmp_path: Path) -> None:
    """selector='$N' lists every entry in the section (entry.get parity)."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), selector="$2", ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    entries = lst.fields["entries"]
    assert entries and all(e["section"] == "$2" for e in entries)


def test_entry_list_selector_deprecated_name_rejected(tmp_path: Path) -> None:
    """':_' is rejected (T-022), matching the rest of the entry.* family."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), selector="OBJ:_", ctx=_CONTEXT)
    assert lst.profile == "OUT-ERROR"
    assert lst.fields.get("code") == "INVALID_ARGS"


def test_entry_list_explicit_params_override_selector(tmp_path: Path) -> None:
    """Explicit section/sigil params win over selector-derived components."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(
        str(f), selector="$3/OBJ", sigil="FCS", ctx=_CONTEXT,
    )
    assert lst.profile == "OUT-WORK"
    assert all(e["sigil"] == "FCS" for e in lst.fields["entries"])
    # The effective filters are echoed back for verification.
    assert lst.fields["sigil"] == "FCS"
    assert lst.fields["selector"] == "$3/OBJ"


def test_entry_list_selector_no_match_is_empty(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    lst = entry_list_handler(str(f), selector="$3/FCS:*", ctx=_CONTEXT)
    assert lst.profile == "OUT-WORK"
    assert lst.fields["count"] == 0
    assert lst.fields["entries"] == []
