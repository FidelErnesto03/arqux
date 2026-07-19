"""Tests for cortex.entry.add content + entry.get/list format=native (BLP-005)."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import (
    entry_add_handler,
    entry_get_handler,
    entry_list_handler,
)
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# OBJ   | objective  | attrs      | H | Working        | Active goal
GSIG:FCS{name:"focus", type:"attrs", risk:"H", layer:"Working", description:"Active attention anchor"}
GSIG:LNG{name:"lesson", type:"attrs", risk:"M", layer:"Episodic", description:"Learned lesson"}
GSIG:OBJ{name:"objective", type:"attrs", risk:"H", layer:"Working", description:"Active goal"}

$1: IDENTITY

IDN:test{name:"test", role:"test", kind:"brain"}

$2: FOCUS

FCS:primary{what:"Test focus", priority:"high", status:"current", survive:"work"}

$3: OBJECTIVES

OBJ:goal1{goal:"Test objective", status:"current", success:"verified", survive:"work"}
"""


# ---------------------------------------------------------------------------
# entry.add with content (canal I)
# ---------------------------------------------------------------------------


def test_entry_add_with_content_overrides_individual_params(tmp_path: Path) -> None:
    """When content is provided, it overrides individual sigil/name/value."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)

    # Pass dummy values for sigil/name/value; content should override.
    result = entry_add_handler(
        str(f),
        "$3",
        "OBJ",  # will be overridden by content
        "dummy",  # will be overridden by content
        "dummy-value",  # will be overridden by content
        content='OBJ:from_content{goal:"From content", status:"planned", success:"auto"}',
        force=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    stored_name = result.fields.get("name", "")
    assert stored_name.startswith("from_content")
    assert result.fields.get("sigil") == "OBJ"

    # Verify the entry was actually written.
    get = entry_get_handler(str(f), f"OBJ:{stored_name}", ctx=_CONTEXT)
    assert get.profile == "OUT-WORK"
    assert get.fields.get("count", 0) == 1


def test_entry_add_without_content_retrocompatible(tmp_path: Path) -> None:
    """Without content, individual params must work as before."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_add_handler(
        str(f),
        "$3",
        "OBJ",
        "retro",
        'goal:"Retro", status:"current"',
        force=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("sigil") == "OBJ"
    assert result.fields.get("name", "").startswith("retro")


def test_entry_add_invalid_content_does_not_crash(tmp_path: Path) -> None:
    """Invalid content must not crash — falls back to individual params."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_add_handler(
        str(f),
        "$3",
        "OBJ",
        "fallback",
        'goal:"Fallback", status:"current"',
        content="not valid cortex content",
        force=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("name", "").startswith("fallback")


# ---------------------------------------------------------------------------
# entry.get format=cortex (canal I)
# ---------------------------------------------------------------------------


def test_entry_get_format_cortex_returns_raw_strings(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_get_handler(str(f), "FCS:*", format="cortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("format") == "cortex"
    entries = result.fields.get("entries", [])
    assert len(entries) >= 1
    # Each entry is a raw CORTEX string.
    assert isinstance(entries[0], str)
    assert "FCS:" in entries[0]


def test_entry_get_format_hcortex_returns_dicts(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_get_handler(str(f), "FCS:*", format="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("format") == "hcortex"
    entries = result.fields.get("entries", [])
    assert len(entries) >= 1
    # Each entry is a parsed dict.
    assert isinstance(entries[0], dict)
    assert entries[0].get("sigil") == "FCS"


def test_entry_get_default_format_is_hcortex(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_get_handler(str(f), "FCS:*", ctx=_CONTEXT)
    assert result.fields.get("format") == "hcortex"


def test_entry_get_invalid_format(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_get_handler(str(f), "FCS:*", format="bogus", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# entry.list format=cortex (canal I)
# ---------------------------------------------------------------------------


def test_entry_list_format_cortex_returns_raw_strings(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_list_handler(str(f), sigil="OBJ", format="cortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("format") == "cortex"
    entries = result.fields.get("entries", [])
    assert len(entries) >= 1
    assert isinstance(entries[0], str)
    assert entries[0].startswith("OBJ:")


def test_entry_list_format_hcortex_returns_dicts(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_list_handler(str(f), sigil="OBJ", format="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("format") == "hcortex"
    entries = result.fields.get("entries", [])
    assert len(entries) >= 1
    assert isinstance(entries[0], dict)


def test_entry_list_default_format_is_hcortex(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_list_handler(str(f), ctx=_CONTEXT)
    assert result.fields.get("format") == "hcortex"


def test_entry_list_invalid_format(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_list_handler(str(f), format="bogus", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# BLP-017 — content supplies the section via the $N: prefix (BUG-002 fix C)
# ---------------------------------------------------------------------------


def test_entry_add_content_supplies_section(tmp_path: Path) -> None:
    """When section is None/empty, content's $N: prefix must set the section.

    Reproduces BUG-002 defect 2-subpoint: content carries the section so the
    caller is not forced to pass it positionally. Pre-fix this raised
    'int' object has no attribute 'strip' or silently ignored the section.
    """
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_add_handler(
        str(f),
        "",  # section omitted -> must come from content
        "LNG",  # overridden by content anyway
        "dummy",
        "dummy-value",
        content='$6:{LNG:E_0100{type:"process", cause:"regression test", lesson:"section from content", prevention:"use content $N:"}}',
        create_section=True,
        force=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("section") == "$6", str(result.fields)
    assert result.fields.get("sigil") == "LNG"

    # Verify the entry really landed in $6.
    get = entry_get_handler(str(f), "LNG:*", ctx=_CONTEXT)
    assert get.profile == "OUT-WORK"
    assert get.fields.get("count", 0) >= 1


def test_entry_add_explicit_section_wins_over_content(tmp_path: Path) -> None:
    """Merge rule: an explicit positional section must beat content's $N:."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = entry_add_handler(
        str(f),
        "$3",  # explicit section wins
        "OBJ",
        "explicit",
        'goal:"explicit", status:"current"',
        content='$9:{OBJ:from_content{goal:"content", status:"current", success:"verified", survive:"work"}}',
        force=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("section") == "$3", str(result.fields)
