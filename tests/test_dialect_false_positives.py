"""BLP-046 regression: ArqUX's glossary dialect must not trip E033/E032.

The fallback codec (0.6.2) reads ArqUX's ``SIGIL:name{type,weight,focus,desc}``
declarations as operational working memory parked in $0 and raises
E033_ZERO_SECTION_MEMORY_ENTRY plus E032_CRITICAL_SIGIL_INCOMPLETE against the
declarations themselves. `filter_dialect_false_positives` drops exactly those.

Two regressions are covered here:

1. The parser emits TWO sections with id ``$0`` for a project brain (header
   block + generated sigil-declaration block). The shim used ``next(...)`` and
   therefore only looked at the first one.
2. A real operational entry parked in $0 (an FCS with working-state fields, no
   declaration shape) must still be reported — the shim is not a blanket
   suppression.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.core.state import _crud

pytest.importorskip("arqux.core.state._crud")


_DECLARATIONS = """$0

# -- $0: ARQUX GOVERNANCE GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# OBJ   | objective  | attrs      | H | Working        | Active goal

FCS:focus{type:"attrs", weight:"H", fields:"value:any?", focus:"value", desc:"Active attention anchor"}
OBJ:objective{type:"attrs", weight:"H", fields:"value:any?", focus:"value", desc:"Active goal"}

$19: ARQUX METADATA

ARQX:artifact{level:2, name:"brain", usage:"state", kind:"native"}

$1: IDENTITY

IDN:governor{level:"2", project:"", path:"", governor:"alfred", created:"2026-09-03T14:15:00Z"}

$2: FOCUS

FCS:current{what:"sustain the test fixture", priority:"medium", status:"current", survive:"work"}

$3: OBJECTIVES

OBJ:goal{goal:"keep the fixture valid", success:"fixture verifies clean", status:"current", survive:"work"}
"""


def test_declarations_in_zero_do_not_trip_e033(tmp_path: Path) -> None:
    f = tmp_path / "brain.cortex"
    f.write_text(_DECLARATIONS, encoding="utf-8")
    text = _crud.Path(f).read_text(encoding="utf-8")
    doc = _crud._cc_parser.parse_cortex(text, path=str(f))
    raw = _crud._cc_validator.validate(doc)
    raw_errors = [d for d in raw if d.get("severity") == "error"]

    # Precondition: the codec really does flag these. If a future codec
    # release stops doing so, the shim becomes a no-op and this test would
    # otherwise pass vacuously.
    assert any(
        d.get("code") in _crud._DIALECT_FALSE_POSITIVES for d in raw_errors
    ), "fixture no longer reproduces the dialect false positive"

    kept = _crud.filter_dialect_false_positives(doc, raw)
    assert [d for d in kept if d.get("severity") == "error"] == []


def test_operational_entry_in_zero_is_still_reported(tmp_path: Path) -> None:
    """A real FCS parked in $0 has no declaration shape and must survive."""
    poisoned = _DECLARATIONS.replace(
        'OBJ:objective{type:"attrs", weight:"H", fields:"value:any?", '
        'focus:"value", desc:"Active goal"}',
        'OBJ:objective{type:"attrs", weight:"H", fields:"value:any?", '
        'focus:"value", desc:"Active goal"}\n\n'
        'FCS:current{what:"orphan focus parked in zero", '
        'priority:"medium", status:"current", survive:"work"}',
    )
    f = tmp_path / "poisoned.cortex"
    f.write_text(poisoned, encoding="utf-8")
    text = f.read_text(encoding="utf-8")
    doc = _crud._cc_parser.parse_cortex(text, path=str(f))
    raw = _crud._cc_validator.validate(doc)
    kept = _crud.filter_dialect_false_positives(doc, raw)

    zero_entries = [
        (getattr(e, "sigil", ""), getattr(e, "name", ""))
        for s in getattr(doc, "sections", [])
        if getattr(s, "id", "") == "$0"
        for e in getattr(s, "entries", [])
    ]
    assert ("FCS", "current") in zero_entries, "fixture must park FCS:current in $0"

    # The declaration (FCS:focus) is filtered out; the orphan (FCS:current)
    # is a real operational entry and must keep its E033.
    survivors = [
        d for d in kept
        if d.get("code") in _crud._DIALECT_FALSE_POSITIVES
        and (d.get("sigil"), d.get("entry")) == ("FCS", "current")
    ]
    assert survivors, "E033 against the real orphan entry was wrongly suppressed"
    assert _crud._is_glossary_declaration is not None


def test_filter_is_noop_without_zero_section() -> None:
    class _S:
        id = "$1"
        entries: list = []

    class _D:
        sections = [_S()]

    diags = [{"code": "E033_ZERO_SECTION_MEMORY_ENTRY", "sigil": "X", "entry": "y"}]
    assert _crud.filter_dialect_false_positives(_D(), diags) == diags


def test_filter_handles_multiple_zero_sections() -> None:
    """BLP-046: declarations may live in the SECOND $0 block."""

    class _E:
        def __init__(self, sigil, name, value):
            self.sigil = sigil
            self.name = name
            self.value = value

    class _S:
        def __init__(self, sid, entries):
            self.id = sid
            self.entries = entries

    decl = _E("FCS", "focus", {"type": "attrs", "weight": "H",
                               "focus": "value", "desc": "d"})
    class _D:
        sections = [_S("$0", []), _S("$0", [decl])]

    diags = [
        {"code": "E033_ZERO_SECTION_MEMORY_ENTRY", "sigil": "FCS",
         "entry": "focus"},
        {"code": "E032_CRITICAL_SIGIL_INCOMPLETE", "sigil": "FCS",
         "entry": "focus"},
    ]
    assert _crud.filter_dialect_false_positives(_D(), diags) == []


# --- Session records filed under LNG -----------------------------------------
#
# codec-cortex models LNG as the lesson triple (cause/lesson/prevention) and
# has no notion of a session summary filed under it. ArqUX writes those as
# ``LNG:session_E_NNNN{type:"session", session_id, summary, date}``. The shim
# exempts them, scoped by the entry's own ``type`` — an incomplete *lesson*
# must still be reported, which is the defect E032 exists to catch.


def test_session_record_exempts_e032() -> None:
    class _E:
        def __init__(self, sigil, name, value):
            self.sigil, self.name, self.value = sigil, name, value

    class _S:
        def __init__(self, sid, entries):
            self.id, self.entries = sid, entries

    rec = _E("LNG", "session_E_1405",
             {"type": "session", "session_id": "E-1405", "summary": "x", "date": "d"})
    class _Doc:
        sections = [_S("$5", [rec])]

    diags = [{"code": "E032_CRITICAL_SIGIL_INCOMPLETE",
              "sigil": "LNG", "entry": "session_E_1405"}]
    assert _crud.filter_dialect_false_positives(_Doc(), diags) == []


def test_incomplete_lesson_is_still_reported() -> None:
    """A rule lesson missing ``prevention`` is a real defect — never exempt."""

    class _E:
        def __init__(self, sigil, name, value):
            self.sigil, self.name, self.value = sigil, name, value

    class _S:
        def __init__(self, sid, entries):
            self.id, self.entries = sid, entries

    lesson = _E("LNG", "una", {"type": "rule", "cause": "c", "lesson": "l"})
    class _Doc:
        sections = [_S("$5", [lesson])]

    diags = [{"code": "E032_CRITICAL_SIGIL_INCOMPLETE",
              "sigil": "LNG", "entry": "una"}]
    assert _crud.filter_dialect_false_positives(_Doc(), diags) == diags
