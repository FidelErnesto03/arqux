"""Tests for the informational diagnostic family I (BLP-006 / A-02).

Family I completes the E/W/I verifier triad: informational diagnostics are
reported by ``cortex.verify`` and NEVER invalidate — ``valid`` only depends
on error-severity codec diagnostics.
"""
from __future__ import annotations

from pathlib import Path

from arqux.core.state import cortex_verify

_HEALTHY = """$0

$0:format{cortex:1.0, encoding:UTF-8}

IDN:idn_contract{type:"attrs", weight:"B", fields:"value:any?", focus:"value", desc:"Actor identity", open:true}
FCS:fcs_contract{type:"attrs", weight:"H", fields:"value:any?", focus:"value", desc:"Active attention anchor", open:true}
OBJ:obj_contract{type:"attrs", weight:"H", fields:"value:any?", focus:"value", desc:"Active goal", open:true}
LNG:lng_contract{type:"attrs", weight:"M", fields:"value:any?", focus:"value", desc:"Learned lesson", open:true}

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


def _codes(result: dict) -> list[str]:
    import re

    codes = []
    for d in result.get("diagnostics", []) or []:
        m = re.match(r"\[([A-Z]\d+_[A-Z0-9_]+)\]", str(d))
        codes.append(m.group(1) if m else str(d))
    return codes


def test_family_i_backend_info_is_emitted(tmp_path: Path) -> None:
    result = cortex_verify(_brain(tmp_path, _HEALTHY))
    assert result["valid"] is True, result["diagnostics"]
    assert "I001_CODEC_BACKEND_INFO" in _codes(result)


def test_placeholder_values_emit_i002_without_invalidating(tmp_path: Path) -> None:
    text = _HEALTHY.replace(
        'created:"2026-01-01"' if 'created:"2026-01-01"' in _HEALTHY else 'name:"test"',
        'name:"test", note:"see <timestamp>"',
        1,
    )
    # Ensure a placeholder actually lands in an entry value.
    text = text.replace('note:"see <timestamp>"', 'note:"pending <timestamp>"')
    result = cortex_verify(_brain(tmp_path, text))
    assert "I002_PLACEHOLDER_VALUE" in _codes(result)
    assert result["valid"] is True, result["diagnostics"]


def test_empty_sections_emit_i003(tmp_path: Path) -> None:
    text = _HEALTHY + "\n$8: EMPTY SECTION\n\n"
    result = cortex_verify(_brain(tmp_path, text))
    assert "I003_EMPTY_SECTION" in _codes(result)
    assert result["valid"] is True, result["diagnostics"]


def test_brain_with_only_info_diagnostics_stays_valid(tmp_path: Path) -> None:
    """AC-09 contract: I-codes alone never flip ``valid`` to False."""
    result = cortex_verify(_brain(tmp_path, _HEALTHY))
    i_only = [c for c in _codes(result) if c.startswith("I0")]
    e_or_w = [c for c in _codes(result) if c.startswith(("E0", "W0"))]
    assert i_only, "expected at least one family-I diagnostic"
    if not e_or_w:
        assert result["valid"] is True
