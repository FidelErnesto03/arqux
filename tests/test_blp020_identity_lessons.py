"""BLP-020 — curated behavioral lessons inside the level-1 identity contract.

Architect policy 2026-11-02 (Option A): the identity contract's BEHAVIORAL
LESSONS section is legitimate contract content — ``identity.record`` files
``kind=behavioral`` lessons there, everything else goes to the project brain.
The pre-write gate and the E023 verify filter are exempted *only* for that
exact combination: sigil LNG + kind behavioral + artifact ``usage:"identity"``
+ a section titled ``(BEHAVIORAL )?LESSONS``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from arqux import timelog_capture as tc
from arqux.core.state._crud import filter_dialect_false_positives

# --- Fixtures/text ----------------------------------------------------------

# A Level-1 identity contract that declares usage:"identity", its glossary
# (including the GSIG:LNG declaration BLP-020 adds) and a titled lessons
# section — the exact shape the sanctioned route produces.
LEVEL1_IDENTITY_WITH_LESSONS = (
    "$0\n\n"
    "# ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata\n"
    'GSIG:IDN{name:"identity", type:"attrs", risk:"B", layer:"Semantic", description:"Agent identity descriptor"}\n'
    'GSIG:AXM{name:"axiom", type:"attrs", risk:"H", layer:"Prefrontal", description:"Non-negotiable principles"}\n'
    'GSIG:LIM{name:"limit", type:"attrs", risk:"M", layer:"Prefrontal", description:"Hard limits"}\n'
    'GSIG:DESC{name:"description", type:"attrs", risk:"B", layer:"Semantic", description:"Description"}\n'
    'GSIG:LNG{name:"learning", type:"attrs", risk:"M", layer:"Working", description:"Curated behavioral lesson", fields:"type,cause,lesson,prevention,status"}\n\n'
    "$0.1: ARQUX METADATA\n\n"
    'ARQX:artifact{level:1, name:"alfred", usage:"identity", kind:"native"}\n\n'
    "$1: IDENTITY\n\n"
    'IDN:alfred{name:"Alfred", status:"current"}\n\n'
    "$2: AXIOMS\n\n"
    'AXM:architect_first{name:"architect_first", body:"x", status:"current"}\n\n'
    "$5: BEHAVIORAL LESSONS\n"
)

LEVEL3_BRAIN = (
    "$0\n\n"
    "# ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata\n\n"
    "$0.1: ARQUX METADATA\n\n"
    'ARQX:artifact{level:3, name:"brain", usage:"state", kind:"native"}\n\n'
    "$2: FOCUS\n\n"
    'FCS:current{what:"tests", priority:"high", survive:"work", status:"current"}\n\n'
    'OBJ:current{goal:"tests", success:"tests pass", survive:"work", status:"current"}\n'
)

# A Level-1 contract WITHOUT usage:"identity" (e.g. a skill contract): the
# exemption must not fire there.
LEVEL1_SKILL_CONTRACT = LEVEL1_IDENTITY_WITH_LESSONS.replace(
    'usage:"identity"', 'usage:"skill"'
)


def _write_identity(root: Path, text: str = LEVEL1_IDENTITY_WITH_LESSONS) -> Path:
    ident = root / ".arqux" / "identities" / "alfred.cortex"
    ident.parent.mkdir(parents=True, exist_ok=True)
    ident.write_text(text, encoding="utf-8")
    return ident


# --- Gate: pre-write exemption ----------------------------------------------


def test_gate_allows_behavioral_lng_in_identity(tmp_path):
    """kind=behavioral + LNG + usage:identity → the gate admits the write."""
    identity = _write_identity(tmp_path)
    assert tc.require_writable_destination(
        identity, "LNG", action="identity.record", entry_kind="behavioral"
    ) is None


def test_gate_rejects_nonbehavioral_lng_in_identity(tmp_path):
    """kind=rule (contextual) is still live state — rejected to the brain."""
    identity = _write_identity(tmp_path)
    rejection = tc.require_writable_destination(
        identity, "LNG", action="identity.record", entry_kind="rule"
    )
    assert rejection is not None
    assert rejection["code"] == "DESTINATION_NOT_ALLOWED"


def test_gate_rejects_lng_without_kind(tmp_path):
    """No entry_kind → the exemption cannot fire (unknown kind is live state)."""
    identity = _write_identity(tmp_path)
    rejection = tc.require_writable_destination(
        identity, "LNG", action="identity.record"
    )
    assert rejection is not None
    assert rejection["code"] == "DESTINATION_NOT_ALLOWED"


def test_gate_rejects_wrk_even_with_behavioral_kind(tmp_path):
    """Only LNG is exempt — WRK is never contract content."""
    identity = _write_identity(tmp_path)
    rejection = tc.require_writable_destination(
        identity, "WRK", action="identity.record", entry_kind="behavioral"
    )
    assert rejection is not None
    assert rejection["code"] == "DESTINATION_NOT_ALLOWED"


def test_gate_rejects_behavioral_lng_in_nonidentity_contract(tmp_path):
    """A level-1 skill contract (no usage:identity) is not exempted."""
    skill = tmp_path / "skill.cortex"
    skill.write_text(LEVEL1_SKILL_CONTRACT, encoding="utf-8")
    rejection = tc.require_writable_destination(
        skill, "LNG", action="identity.record", entry_kind="behavioral"
    )
    assert rejection is not None
    assert rejection["code"] == "DESTINATION_NOT_ALLOWED"


# --- Routing: record_lesson_handler_legacy -----------------------------------


def test_behavioral_lesson_lands_in_identity_lessons_section(tmp_path):
    """kind=behavioral → destination=identity, LNG inside BEHAVIORAL LESSONS,
    every GSIG preserved and no brain write attempted."""
    from arqux.handlers.cortex.learning import record_lesson_handler_legacy

    ident = _write_identity(tmp_path)
    brain = tmp_path / ".arqux" / "brain.cortex"
    brain.write_text(LEVEL3_BRAIN, encoding="utf-8")
    brain_before = brain.read_bytes()

    result = record_lesson_handler_legacy(
        lesson="Confirmar el destino antes de escribir una leccion",
        kind="behavioral", cause="c", prevention="p",
        agent_id="alfred", path=str(tmp_path),
    )

    assert result.profile == "OUT-WORK", result.to_text()
    assert result.fields["destination"] == "identity"

    text = ident.read_text(encoding="utf-8")
    lessons = text.split("$5: BEHAVIORAL LESSONS", 1)[1]
    assert re.search(r"^LNG:", lessons, re.M)
    assert "type:" in lessons and "behavioral" in lessons
    assert len(re.findall(r"(?m)^GSIG:", text)) == 5
    # No dual write: a behavioral lesson never touches the project brain.
    assert brain.read_bytes() == brain_before


def test_nonbehavioral_lesson_lands_in_brain_only(tmp_path):
    """kind=process → destination=brain; the identity stays byte-identical."""
    from arqux.handlers.cortex.learning import record_lesson_handler_legacy

    ident = _write_identity(tmp_path)
    before = ident.read_bytes()
    (tmp_path / ".arqux" / "brain.cortex").write_text(
        LEVEL3_BRAIN, encoding="utf-8"
    )

    result = record_lesson_handler_legacy(
        lesson="Correr pytest antes de tocar el codec",
        kind="process", cause="c", prevention="p",
        agent_id="alfred", path=str(tmp_path),
    )

    assert result.profile == "OUT-WORK", result.to_text()
    assert result.fields["destination"] == "brain"
    assert ident.read_bytes() == before


# --- Verify filter: E023 scoped to the lessons section ------------------------


def _entry(sigil: str, name: str, value: dict) -> SimpleNamespace:
    return SimpleNamespace(sigil=sigil, name=name, value=value)


def _section(sec_id: str, title: str, entries: list) -> SimpleNamespace:
    return SimpleNamespace(id=sec_id, title=title, entries=entries)


def _diag(code: str, sigil: str, entry: str, section: str) -> dict:
    return {
        "code": code, "sigil": sigil, "entry": entry,
        "section": section, "severity": "error",
    }


def _identity_doc() -> SimpleNamespace:
    return SimpleNamespace(sections=[
        _section("$0.1", "ARQUX METADATA", [
            _entry("ARQX", "artifact", {"level": 1, "usage": "identity"}),
        ]),
        _section("$5", "BEHAVIORAL LESSONS", [
            _entry("LNG", "confirmar", {"type": "behavioral", "lesson": "x"}),
        ]),
        _section("$6", "NOTES", [
            _entry("LNG", "colada", {"type": "behavioral", "lesson": "y"}),
        ]),
    ])


def test_e023_dropped_only_inside_lessons_section():
    """E023 on a behavioral LNG inside BEHAVIORAL LESSONS is dropped; the same
    sigil elsewhere in the contract is still reported."""
    diags = [
        _diag("E023_LEVEL1_LIVE_STATE", "LNG", "confirmar", "$5"),
        _diag("E023_LEVEL1_LIVE_STATE", "LNG", "colada", "$6"),
    ]
    kept = filter_dialect_false_positives(_identity_doc(), diags)
    assert kept == [diags[1]]


def test_e023_kept_for_nonbehavioral_lng_in_lessons_section():
    """A process-typed LNG in the lessons section is live state, not contract."""
    doc = _identity_doc()
    doc.sections[1].entries[0].value["type"] = "process"
    diags = [_diag("E023_LEVEL1_LIVE_STATE", "LNG", "confirmar", "$5")]
    kept = filter_dialect_false_positives(doc, diags)
    assert kept == diags


def test_e023_kept_for_other_live_sigils_in_lessons_section():
    """WRK/SES/FCS/OBJ in the lessons section are never exempted."""
    diags = [_diag("E023_LEVEL1_LIVE_STATE", "WRK", "current", "$5")]
    kept = filter_dialect_false_positives(_identity_doc(), diags)
    assert kept == diags


def test_e023_kept_when_artifact_is_not_identity():
    """A lessons-titled section does nothing outside usage:identity artifacts."""
    doc = _identity_doc()
    doc.sections[0].entries[0].value["usage"] = "skill"
    diags = [_diag("E023_LEVEL1_LIVE_STATE", "LNG", "confirmar", "$5")]
    kept = filter_dialect_false_positives(doc, diags)
    assert kept == diags


def test_unrelated_diag_codes_survive_the_exemption():
    """Codes other than E023 in the lessons section are untouched."""
    diags = [
        _diag("E032_CRITICAL_SIGIL_INCOMPLETE", "LNG", "confirmar", "$5"),
        _diag("W001_SOMETHING", "LNG", "confirmar", "$5"),
    ]
    kept = filter_dialect_false_positives(_identity_doc(), diags)
    assert kept == diags


# --- Automatic continuation event (Architect mandate 2026-11-02) -------------

# If an autonomous loop is pending and the expected intervention never comes,
# the next session bootstrap re-signals it — the continuation fires on the
# guaranteed first governed call instead of waiting forever.


def _brain_with_wrk(tmp_path: Path, wrk_body: str) -> Path:
    brain = tmp_path / ".arqux" / "brain.cortex"
    brain.parent.mkdir(parents=True, exist_ok=True)
    brain.write_text(
        "$0\n\n$0.1: ARQUX METADATA\n\n"
        'ARQX:artifact{level:3, name:"brain", usage:"state", kind:"native"}\n\n'
        "$5: WORKING STATE\n\n"
        f"WRK:current{{{wrk_body}}}\n",
        encoding="utf-8",
    )
    return brain


def test_pending_loop_surfaces_on_bootstrap(tmp_path):
    """A WRK:current declaring loop + unfinished phase is surfaced."""
    from arqux.handlers.session import _pending_autonomous_loop

    brain = _brain_with_wrk(
        tmp_path,
        'session:"SES017", loop:"A-H mandato", phase:"C2-implementando", '
        'next:"run tests"',
    )
    pending = _pending_autonomous_loop(brain)
    assert pending == {
        "loop": "A-H mandato", "phase": "C2-implementando", "next": "run tests"
    }


def test_finished_loop_is_not_resignaled(tmp_path):
    """phase done/H-/complet* closes the loop — nothing to resume."""
    from arqux.handlers.session import _pending_autonomous_loop

    for phase in ("done", "H-handoff", "completado"):
        brain = _brain_with_wrk(
            tmp_path, f'loop:"A-H", phase:"{phase}"'
        )
        assert _pending_autonomous_loop(brain) is None


def test_brain_without_loop_declares_nothing(tmp_path):
    """A WRK:current without loop/phase keys yields no pending signal."""
    from arqux.handlers.session import _pending_autonomous_loop

    brain = _brain_with_wrk(tmp_path, 'session:"S1", focus:"x"')
    assert _pending_autonomous_loop(brain) is None
