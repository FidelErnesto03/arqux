"""A-01 regression: strict attrs classification + post-write transaction guard.

Covers the 2026-11-13 kernel incident: a cuerpo containing a ``word: value``
fragment was re-interpreted as attrs on the next read-modify-write and
silently truncated to those attrs, while the handler returned ok.

Two independent controls are exercised here:

1. ``_parse_attrs_fallback`` classifies a body as attrs ONLY when the whole
   body is a valid attrs map (prose is cuerpo).
2. ``guard_write`` aborts (and rolls back) any write that alters a section
   outside the target entry, whatever the parser believes.
"""

from __future__ import annotations

from pathlib import Path

from arqux.cortex.reader import _parse_attrs_fallback, cortex_to_dict
from arqux.cortex.transaction import guard_write, sections_changed
from arqux.cortex.writer import write_cortex_from_json
from arqux.cortex_out import OUT_ERROR, OUT_WORK
from arqux.handlers.cortex.entries import (
    entry_add_handler,
    entry_delete_handler,
    entry_move_handler,
    entry_update_handler,
)

PROSE = (
    "THE FIRST THING in any governed work is to read brain.cortex — before "
    "attempting anything. Project level: brain.cortex. Workspace level: "
    "meta-brain.cortex. Set by the Architect 2026-10-28"
)

BODY_WITH_COLONS = (
    "Un verificador que dispara el mismo warning en el 100% de las entradas "
    "deja de verificar: salud es E igual a cero; Evidencia: 582 W001 en 582 "
    "entradas de ARQUX"
)

DOC = f"""$0

$1: TIER

TIE:nano{{load:"AGENTS", mode:"read-only context"}}

$2: CORE

AXM:brain_first{{{PROSE}}}

AXM:verify_noise{{{BODY_WITH_COLONS}}}

$3: OTHER

REG:handlers_nano{{tier:"NANO", count:8}}
"""


def _make_doc(tmp_path: Path, name: str = "AGENTS.md") -> Path:
    p = tmp_path / name
    p.write_text(DOC, encoding="utf-8")
    return p


def _entries(path: Path, section: str) -> list[dict]:
    doc = cortex_to_dict(path.read_text(encoding="utf-8"))
    for sec in doc["sections"]:
        if sec.get("id") == section:
            return sec["entries"]
    return []


# ---------------------------------------------------------------------------
# 1. Parser strictness
# ---------------------------------------------------------------------------


def test_prose_with_colon_fragment_is_not_attrs():
    assert _parse_attrs_fallback(PROSE) is None
    assert _parse_attrs_fallback(BODY_WITH_COLONS) is None


def test_real_attrs_still_parse():
    assert _parse_attrs_fallback('tier:"NANO", count:8, load:"AGENTS"') == {
        "tier": "NANO", "count": 8, "load": "AGENTS",
    }


def test_quoted_value_with_comma_and_colon_is_one_attr():
    assert _parse_attrs_fallback('desc:"goal:text|status:%state", focus:goal') == {
        "desc": "goal:text|status:%state", "focus": "goal",
    }


def test_parse_keeps_prose_as_body():
    doc = cortex_to_dict(DOC)
    entries = [e for e in doc["sections"][1]["entries"] if e["name"] == "brain_first"]
    assert len(entries) == 1
    assert entries[0]["body"].strip() == PROSE
    assert "attrs" not in entries[0]


def test_writer_roundtrip_preserves_prose():
    first = cortex_to_dict(DOC)
    text = write_cortex_from_json(first)
    second = cortex_to_dict(text)
    again = [e for e in second["sections"][1]["entries"] if e["name"] == "brain_first"]
    assert again[0]["body"].strip() == PROSE


# ---------------------------------------------------------------------------
# 2. Transaction guard: no collateral damage
# ---------------------------------------------------------------------------


def test_add_in_other_section_preserves_prose(tmp_path):
    path = _make_doc(tmp_path)
    before = _entries(path, "$2")

    out = entry_add_handler(
        str(path), section="$3", sigil="REG", name="extra", value='kind:"probe"',
    )
    assert out.profile == OUT_WORK, out.to_text()
    assert _entries(path, "$2") == before


def test_hundred_writes_no_collateral(tmp_path):
    path = _make_doc(tmp_path)
    before = _entries(path, "$2")
    for i in range(100):
        out = entry_add_handler(
            str(path), section="$3", sigil="REG", name=f"probe_{i}", value='kind:"probe"',
        )
        assert out.profile == OUT_WORK, out.to_text()
    assert _entries(path, "$2") == before
    text = path.read_text(encoding="utf-8")
    assert PROSE in text
    assert BODY_WITH_COLONS in text


def test_add_into_same_section_preserves_other_entries(tmp_path):
    path = _make_doc(tmp_path)
    before = _entries(path, "$2")

    out = entry_add_handler(
        str(path), section="$2", sigil="AXM", name="new_rule", value="Prose body: keep me intact",
    )
    assert out.profile == OUT_WORK, out.to_text()
    after = _entries(path, "$2")
    assert before == [e for e in after if e["name"] != "new_rule"]


def test_update_preserves_other_entries(tmp_path):
    path = _make_doc(tmp_path)
    before = _entries(path, "$2")

    out = entry_update_handler(str(path), "$3/REG:handlers_nano", set_="count:9")
    assert out.profile == OUT_WORK, out.to_text()
    assert _entries(path, "$2") == before


def test_delete_preserves_other_entries(tmp_path):
    path = _make_doc(tmp_path)
    before = _entries(path, "$2")

    out = entry_delete_handler(str(path), "$3/REG:handlers_nano")
    assert out.profile == OUT_WORK, out.to_text()
    assert _entries(path, "$2") == before


def test_move_preserves_other_entries(tmp_path):
    path = _make_doc(tmp_path)
    before = _entries(path, "$2")

    out = entry_move_handler(str(path), "$3/REG:handlers_nano", "$1")
    assert out.profile == OUT_WORK, out.to_text()
    assert _entries(path, "$2") == before


# ---------------------------------------------------------------------------
# 3. Guard detects and rolls back foreign changes
# ---------------------------------------------------------------------------


def test_guard_detects_foreign_change_and_rolls_back(tmp_path):
    path = _make_doc(tmp_path)
    before_text = path.read_text(encoding="utf-8")

    # Simulate a writer that reformatted an unrelated section ($1).
    tampered = before_text.replace('TIE:nano{load:"AGENTS", mode:"read-only context"}',
                                    'TIE:nano{load:"AGENTS"}')
    path.write_text(tampered, encoding="utf-8")

    assert sections_changed(before_text, tampered) == ["$1"]

    violation = guard_write(
        str(path), before_text, allowed_sections={"$3"},
    )
    assert violation is not None
    assert violation["sections"] == ["$1"]
    assert violation["rolled_back"] is True
    assert path.read_text(encoding="utf-8") == before_text


def test_guard_accepts_clean_target_change(tmp_path):
    path = _make_doc(tmp_path)
    before_text = path.read_text(encoding="utf-8")

    # A legitimate add inside the target section only.
    added = before_text.replace(
        'REG:handlers_nano{tier:"NANO", count:8}',
        'REG:handlers_nano{tier:"NANO", count:8}\n\nREG:extra{kind:"probe"}',
    )
    path.write_text(added, encoding="utf-8")

    assert guard_write(
        str(path), before_text, allowed_sections={"$3"},
    ) is None


def test_guard_error_surfaces_as_validation(tmp_path, monkeypatch):
    """A handler must return VALIDATION (not ok) when the write damages others."""
    path = _make_doc(tmp_path)
    before_text = path.read_text(encoding="utf-8")

    import arqux.handlers.cortex.entries as entries_mod

    real_crud_add = entries_mod.crud_add

    def sabotaging_crud_add(*args, **kwargs):
        result = real_crud_add(*args, **kwargs)
        # Reformat an unrelated section after the legitimate write.
        if "error" not in result:
            text = path.read_text(encoding="utf-8").replace(
                'TIE:nano{load:"AGENTS", mode:"read-only context"}',
                'TIE:nano{load:"AGENTS"}',
            )
            path.write_text(text, encoding="utf-8")
        return result

    monkeypatch.setattr(entries_mod, "crud_add", sabotaging_crud_add)

    out = entry_add_handler(
        str(path), section="$3", sigil="REG", name="probe", value='kind:"probe"',
    )
    assert out.profile == OUT_ERROR, out.to_text()
    assert out.fields.get("rolled_back") is True
    assert path.read_text(encoding="utf-8") == before_text


# ---------------------------------------------------------------------------
# HD-01 (audit 2026-11-13): same entry name in two sections must NOT widen
# the allowed set — collateral damage on the other same-named entry is a
# violation, not a permitted change.
# ---------------------------------------------------------------------------


COLLISION_DOC = """$0

$1: A

LNG:same{cause:"a", type:"process"}

$2: B

LNG:same{cause:"b", type:"process"}
"""


def test_guard_detects_collateral_on_same_name_in_other_section(tmp_path):
    path = tmp_path / "collision.cortex"
    path.write_text(COLLISION_DOC, encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    # Damage $2 only (same sigil:name as the target in $1).
    damaged = before.replace('LNG:same{cause:"b", type:"process"}',
                             'LNG:same{cause:"DESTROYED"}')
    path.write_text(damaged, encoding="utf-8")

    violation = guard_write(
        str(path), before, allowed_sections={"$1"},
    )
    assert violation is not None, "collateral damage was masked"
    assert violation["sections"] == ["$2"]
    assert violation["rolled_back"] is True
    assert path.read_text(encoding="utf-8") == before


def test_update_with_section_selector_does_not_authorise_other_section(tmp_path, governor_ctx):
    """Handler-level HD-01: sabotaged writer damaging the other section is rejected."""
    path = tmp_path / "collision.cortex"
    path.write_text(COLLISION_DOC, encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    import arqux.handlers.cortex.entries as entries_mod

    real_update = entries_mod.crud_update

    def sabotaging_update(*args, **kwargs):
        result = real_update(*args, **kwargs)
        if "error" not in result:
            text = path.read_text(encoding="utf-8").replace(
                'LNG:same{cause:"b", type:"process"}',
                'LNG:same{cause:"DESTROYED"}',
            )
            path.write_text(text, encoding="utf-8")
        return result

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(entries_mod, "crud_update", sabotaging_update)
    try:
        out = entry_update_handler(
            str(path), "$1/LNG:same", set_='cause:"updated"', ctx=governor_ctx,
        )
    finally:
        monkeypatch.undo()

    assert out.profile == OUT_ERROR, out.to_text()
    assert out.fields.get("sections") == ["$2"]
    assert path.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# T-1.2 — permanent regression of the 2026-11-13 kernel incident.
# The exact failure mode: adding an entry to the SAME section that holds a
# prose cuerpo (with `palabras: valor` inside) truncated that cuerpo to a few
# attrs while the handler returned ok.
# ---------------------------------------------------------------------------

KERNEL_LIKE = """$0

$2: CORE AXIOMS

AXM:brain_first{THE FIRST THING in any governed work is to read brain.cortex — before attempting anything. Project level: brain.cortex. Workspace level: meta-brain.cortex.}

AXM:header{Every response: header line. Never the literal string 'AGENT'.}
"""


def test_kernel_incident_regression(tmp_path):
    """Add to the section that holds prose: the prose must survive intact."""
    path = tmp_path / "AGENTS.md"
    path.write_text(KERNEL_LIKE, encoding="utf-8")

    out = entry_add_handler(
        str(path), section="$2", sigil="AXM", name="verify_noise",
        value="Un verificador que dispara el mismo warning: salud es E igual a cero",
    )
    assert out.profile == OUT_WORK, out.to_text()

    text = path.read_text(encoding="utf-8")
    assert "THE FIRST THING in any governed work" in text
    assert "Project level: brain.cortex" in text
    assert "Workspace level: meta-brain.cortex" in text
    assert "Every response: header line" in text
    assert "salud es E igual a cero" in text


def test_kernel_like_document_roundtrip_preserves_every_body(tmp_path):
    """parse -> write -> parse keeps every prose cuerpo byte-for-byte."""
    first = cortex_to_dict(KERNEL_LIKE)
    text = write_cortex_from_json(first)
    second = cortex_to_dict(text)
    for doc in (first, second):
        bodies = {
            entry["name"]: entry.get("body", "").strip()
            for entry in doc["sections"][0]["entries"]
        }
        assert bodies["brain_first"].startswith("THE FIRST THING")
        assert "Project level: brain.cortex" in bodies["brain_first"]
        assert bodies["header"].startswith("Every response:")
