"""Tests for cortex.read mode=native (BLP-004)."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import read_handler
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# FCS   | focus | attrs | H | Working | Active attention anchor
GSIG:FCS{name:"focus", type:"attrs", risk:"H", layer:"Working", description:"Active attention anchor"}

$1: IDENTITY

IDN:test{name:"test", role:"test", status:"current"}

$2: FOCUS

FCS:primary{what:"Test focus", priority:"high", status:"current"}
"""


def test_read_mode_cortex_returns_dict(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = read_handler(str(f), mode="cortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("mode") == "cortex"
    assert result.fields.get("format") == "cortex"
    assert "raw" in result.fields
    assert "sections" in result.fields
    assert "glossary" in result.fields


def test_read_mode_hcortex_returns_markdown(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = read_handler(str(f), mode="hcortex", ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("mode") == "hcortex"
    assert "content" in result.fields
    # HCORTEX content is markdown (non-empty, contains IDENTITY section).
    content = result.fields["content"]
    assert len(content) > 0
    assert "IDENTITY" in content or "test" in content


def test_read_default_mode_is_cortex(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = read_handler(str(f), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("mode") == "cortex"


def test_read_invalid_mode(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = read_handler(str(f), mode="bogus", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


def test_read_file_not_found() -> None:
    result = read_handler("/nonexistent/file.cortex", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"


def test_read_retrocompatibility_no_mode_arg(tmp_path: Path) -> None:
    """Callers using positional args must keep working."""
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    # No mode kwarg — defaults to "cortex".
    result = read_handler(str(f), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
