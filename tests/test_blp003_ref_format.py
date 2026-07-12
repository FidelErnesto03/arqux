"""Tests for cortex.ref and cortex.format handlers (BLP-003)."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import ref_handler, format_handler
from arqux.permissions import PermissionContext


_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE_CORTEX = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# FCS   | focus | attrs | H | Working | Active attention anchor
GSIG:FCS{name:"focus", type:"attrs", risk:"H", layer:"Working", description:"Active attention anchor"}

$1: IDENTITY

IDN:test{name:"test", role:"assistant", status:"current"}

$2: FOCUS

FCS:primary{what:"Test focus", priority:"high", status:"current"}
"""


# ---------------------------------------------------------------------------
# cortex.ref
# ---------------------------------------------------------------------------


def test_ref_returns_known_sigil() -> None:
    result = ref_handler("WRK", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("sigil") == "WRK"
    assert result.fields.get("name") == "work"
    assert "description" in result.fields


def test_ref_case_insensitive() -> None:
    result = ref_handler("lng", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("sigil") == "LNG"
    assert result.fields.get("name") == "lesson"


def test_ref_unknown_sigil() -> None:
    result = ref_handler("XYZQ", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"
    assert "known_sigils" in result.fields


def test_ref_invalid_input() -> None:
    result = ref_handler("", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# cortex.format — CORTEX → HCORTEX
# ---------------------------------------------------------------------------


def test_format_cortex_to_hcortex(tmp_path: Path) -> None:
    src = tmp_path / "test.cortex"
    src.write_text(_SAMPLE_CORTEX)
    result = format_handler(path=str(src), target="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("target") == "hcortex"
    out = result.fields.get("content", "")
    # Section header is rendered as markdown.
    assert "## §1: IDENTITY" in out
    assert "## §2: FOCUS" in out
    # Sigil entry is rendered with attrs.
    assert "### FCS:primary" in out
    assert "what" in out and "Test focus" in out


def test_format_hcortex_to_cortex(tmp_path: Path) -> None:
    md = """## §1: IDENTITY

### IDN:test

- **name**: test
- **role**: assistant
- **status**: current

## §2: FOCUS

### FCS:primary

- **what**: Test focus
- **priority**: high
"""
    result = format_handler(content=md, target="cortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("target") == "cortex"
    out = result.fields.get("content", "")
    assert "$1: IDENTITY" in out
    assert "$2: FOCUS" in out
    assert "IDN:test{" in out
    assert "FCS:primary{" in out


def test_format_invalid_target() -> None:
    result = format_handler(content="x", target="bogus", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


def test_format_empty_content() -> None:
    result = format_handler(content="", target="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


def test_format_missing_both_content_and_path() -> None:
    result = format_handler(target="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


def test_format_path_not_found() -> None:
    result = format_handler(path="/nonexistent/file.cortex", target="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"
