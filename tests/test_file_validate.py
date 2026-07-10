"""Tests for cortex.file.validate handler."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import file_validate_handler
from arqux.permissions import PermissionContext


_CONTEXT = PermissionContext(agent_id="test", role="governor")

_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson

$1: LESSONS

LNG:first{type:"process", lesson:"First"}
LNG:second{type:"process", lesson:"Second"}
"""

_SAMPLE_WITH_DUPS = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson

$1: LESSONS

LNG:dup{type:"process", cause:"test", prevention:"test", lesson:"First"}
LNG:dup{type:"process", cause:"test", prevention:"test", lesson:"Second"}
LNG:other{type:"process", cause:"test", prevention:"test", lesson:"Unique"}
"""


def test_validate_no_duplicates(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE)
    result = file_validate_handler(str(f), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("total_duplicates") == 0


def test_validate_detects_duplicates_dry_run(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_WITH_DUPS)
    result = file_validate_handler(str(f), fix=False, ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("total_duplicates", 0) >= 1
    assert result.fields.get("fix") is False
    # Verify file was NOT modified
    text = f.read_text(encoding="utf-8")
    assert "dup_0001" not in text


def test_validate_fixes_duplicates(tmp_path: Path) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SAMPLE_WITH_DUPS)
    result = file_validate_handler(str(f), fix=True, ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("total_duplicates", 0) >= 1
    assert result.fields.get("fix") is True
    # Verify file was modified — duplicates should be renamed
    text = f.read_text(encoding="utf-8")
    assert "dup_0001" in text
    assert "dup_0002" in text


def test_validate_not_found(tmp_path: Path) -> None:
    result = file_validate_handler(str(tmp_path / "nope.cortex"), ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
