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


# --- BLP-046 / BUG-002 regression -------------------------------------
# The PULSE naming convention E_NNNN matches the _\d{4}$ suffix pattern.
# Before the fix every distinct event collapsed onto base "E", so a brain
# with 88 unique AUD:E_NNNN entries reported 87 false duplicates and
# fix=true would have renamed the entire evidence log.


_PULSE_SAMPLE = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# AUD   | audit      | attrs      | M | Prefrontal     | Audit event

$1: PULSE

AUD:E_0110{event:"E-0110", evidence:"a", result:"a", date:"2026-01-01"}
AUD:E_0111{event:"E-0111", evidence:"b", result:"b", date:"2026-01-02"}
AUD:E_0249{event:"E-0249", evidence:"c", result:"c", date:"2026-01-03"}
"""


def test_pulse_event_names_are_not_duplicates(tmp_path: Path) -> None:
    f = tmp_path / "brain.cortex"
    f.write_text(_PULSE_SAMPLE)
    result = file_validate_handler(str(f), ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("total_duplicates") == 0


def test_pulse_events_survive_fix_true(tmp_path: Path) -> None:
    """fix=true on a healthy brain must be a no-op on the evidence log."""
    f = tmp_path / "brain.cortex"
    f.write_text(_PULSE_SAMPLE)
    result = file_validate_handler(str(f), fix=True, ctx=_CONTEXT)
    assert result.profile == "OUT-WORK"
    assert result.fields.get("total_duplicates") == 0
    text = f.read_text(encoding="utf-8")
    for name in ("E_0110", "E_0111", "E_0249"):
        assert "AUD:" + name + "{" in text
    assert "_0001" not in text


_SUFFIXED_FAMILY = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson

$1: LESSONS

LNG:alpha{type:"process", cause:"c", prevention:"p", lesson:"base"}
LNG:alpha_0001{type:"process", cause:"c", prevention:"p", lesson:"extra one"}
LNG:alpha_0002{type:"process", cause:"c", prevention:"p", lesson:"extra two"}
"""


def test_suffixed_family_with_verbatim_base_is_a_duplicate_group(
    tmp_path: Path,
) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(_SUFFIXED_FAMILY)
    result = file_validate_handler(str(f), ctx=_CONTEXT)
    assert result.fields.get("total_duplicates", 0) >= 1


_ORPHAN_SUFFIX = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson

$1: LESSONS

LNG:beta{type:"process", cause:"c", prevention:"p", lesson:"base"}
LNG:gamma_0001{type:"process", cause:"c", prevention:"p", lesson:"orphan suffix"}
"""


def test_orphan_suffix_without_verbatim_base_is_not_a_duplicate(
    tmp_path: Path,
) -> None:
    """A _NNNN name whose base does not exist is a distinct entry."""
    f = tmp_path / "test.cortex"
    f.write_text(_ORPHAN_SUFFIX)
    result = file_validate_handler(str(f), ctx=_CONTEXT)
    assert result.fields.get("total_duplicates") == 0


def test_same_name_in_different_sections_is_not_a_duplicate(
    tmp_path: Path,
) -> None:
    f = tmp_path / "test.cortex"
    f.write_text(
        _SAMPLE.replace("$1: LESSONS", "$1: LESSONS")
        + "\n$2: MORE\n\nLNG:first{type:\"process\", cause:\"c\", "
        "prevention:\"p\", lesson:\"other section\"}\n"
    )
    result = file_validate_handler(str(f), ctx=_CONTEXT)
    assert result.fields.get("total_duplicates") == 0
