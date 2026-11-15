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

import pytest

from arqux.core.state import _crud

pytest.importorskip("arqux.core.state._crud")


# codec-cortex 1.0 keeps the $0 glossary out of ``doc.sections`` (it lands
# in ``doc.glossary``) and rejects non-declaration entries parked in $0 at
# parse time — the dialect-false-positive scenario this shim guards can no
# longer be produced by parsing through ``_cc_parser``. The shim's contract
# is unchanged, though, so the docs below are built through the real model
# classes (the same strategy the fake-object tests further down already
# use): any $0 entry shaped like a declaration must be exempted, anything
# else must keep its diagnostic.
from arqux.cortex.model import CortexDocument, Entry, Section

_DECL_FCS = {
    "type": "attrs", "weight": "H", "fields": "value:any?",
    "focus": "value", "desc": "Active attention anchor",
}
_DECL_OBJ = {
    "type": "attrs", "weight": "H", "fields": "value:any?",
    "focus": "value", "desc": "Active goal",
}


def _entry(section: str, sigil: str, name: str, value: dict) -> Entry:
    return Entry(section=section, sigil=sigil, name=name,
                 type="attrs", value=dict(value))


def _fixture_doc(zero_entries: list) -> CortexDocument:
    """Brain-shaped doc: $0 carries *zero_entries*; $2/$3 keep a valid
    active FCS/OBJ pair so level policy stays quiet outside the shim's
    scope."""
    doc = CortexDocument(meta={"path": "brain.cortex"})
    zero = Section(id="$0")
    zero.entries.extend(zero_entries)
    focus = Section(id="$2", title="FOCUS", entries=[
        _entry("$2", "FCS", "current", {
            "what": "sustain the test fixture", "priority": "medium",
            "status": "current", "survive": "work"}),
    ])
    objectives = Section(id="$3", title="OBJECTIVES", entries=[
        _entry("$3", "OBJ", "goal", {
            "goal": "keep the fixture valid",
            "success": "fixture verifies clean",
            "status": "current", "survive": "work"}),
    ])
    doc.sections.extend([zero, focus, objectives])
    return doc


def test_declarations_in_zero_do_not_trip_e033() -> None:
    doc = _fixture_doc([
        _entry("$0", "FCS", "focus", _DECL_FCS),
        _entry("$0", "OBJ", "objective", _DECL_OBJ),
    ])
    raw = _crud._cc_validator.validate(doc)
    raw_errors = [d for d in raw if d.get("severity") == "error"]

    # Precondition: the validator really does flag these. If a future
    # validator stops doing so, the shim becomes a no-op and this test
    # would otherwise pass vacuously.
    assert any(
        d.get("code") in _crud._DIALECT_FALSE_POSITIVES for d in raw_errors
    ), "fixture no longer reproduces the dialect false positive"

    kept = _crud.filter_dialect_false_positives(doc, raw)
    assert [d for d in kept if d.get("severity") == "error"] == []


def test_operational_entry_in_zero_is_still_reported() -> None:
    """A real FCS parked in $0 has no declaration shape and must survive."""
    orphan = _entry("$0", "FCS", "current", {
        "what": "orphan focus parked in zero", "priority": "medium",
        "status": "current", "survive": "work"})
    doc = _fixture_doc([
        _entry("$0", "OBJ", "objective", _DECL_OBJ),
        orphan,
    ])
    raw = _crud._cc_validator.validate(doc)
    kept = _crud.filter_dialect_false_positives(doc, raw)

    zero_entries = [
        (e.sigil, e.name) for s in doc.sections if s.id == "$0"
        for e in s.entries
    ]
    assert ("FCS", "current") in zero_entries, "fixture must park FCS:current in $0"

    # The declaration (OBJ:objective) is filtered out; the orphan
    # (FCS:current) is a real operational entry and must keep its E033.
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
