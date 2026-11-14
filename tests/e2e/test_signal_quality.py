"""Signal-quality suite — finding 2.11 and lesson `verifier_signal_noise`.

A verifier that fires on 100% of entries verifies nothing: the real E-codes
get buried (582 W001/582 entries in ARQUX, OUT-AUDIT H-08). Health is
``E == 0``; warnings are deduplicated and never invalidate.
"""

from __future__ import annotations

from pathlib import Path

from arqux.cortex_out import OUT_ERROR
from arqux.handlers.cortex.read_write import verify_handler

HEALTHY_BRAIN = """$0

$1: METADATA

IDN:test{name:"test", kind:"brain"}

$2: FOCUS

FCS:current{what:"test", priority:"high", status:"current", survive:"work"}

$3: OBJECTIVES

OBJ:main{goal:"exist", status:"current", success:"verified", survive:"work"}

$4: LESSONS

LNG:healthy{type:"process", cause:"c", lesson:"l", prevention:"p"}
"""


def _brain(tmp_path: Path, text: str) -> Path:
    b = tmp_path / "brain.cortex"
    b.write_text(text, encoding="utf-8")
    return b


def _diagnostic_codes(out) -> list[str]:
    import re

    codes: list[str] = []
    for d in out.fields.get("diagnostics", []) or []:
        if isinstance(d, dict):
            codes.append(str(d.get("code", "")))
            continue
        m = re.match(r"\[([A-Z]\d+_[A-Z0-9_]+)\]", str(d))
        codes.append(m.group(1) if m else str(d))
    return codes


def test_healthy_brain_has_no_w001_name_noise(tmp_path):
    """H-2: no W001_MISSING_FIELDS `name` per entry on a healthy brain."""
    out = verify_handler(str(_brain(tmp_path, HEALTHY_BRAIN)))
    assert out.fields["valid"] is True, out.fields.get("diagnostics")
    assert not [c for c in _diagnostic_codes(out) if "W001" in c]


def test_entry_name_lives_in_the_key_not_as_field(tmp_path):
    """H-2: the entry name (`LNG:healthy`) is the key; it is not a field."""
    out = verify_handler(str(_brain(tmp_path, HEALTHY_BRAIN)))
    assert out.fields["entries"] >= 3


def test_real_corruption_is_flagged_not_buried(tmp_path):
    """A duplicated entry is a real E-code and must be visible."""
    dup = HEALTHY_BRAIN + '\nLNG:healthy{type:"process", cause:"dup", lesson:"dup", prevention:"dup"}\n'
    out = verify_handler(str(_brain(tmp_path, dup)))
    codes = _diagnostic_codes(out)
    assert any(c.startswith("E") for c in codes), out.fields.get("diagnostics")


def test_verify_missing_file_is_explicit(tmp_path):
    out = verify_handler(str(tmp_path / "nope.cortex"))
    assert out.profile == OUT_ERROR
    assert out.fields.get("code") == "NOT_FOUND"
