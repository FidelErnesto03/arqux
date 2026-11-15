"""Tests for the public ideatic emit helper (BLP-006 / gap 2.12/U4).

``emit_ideatic`` is the stable public entrypoint for emitting CORTEX text
from a document model, used by tooling and tests that need a single
emission surface.
"""
from __future__ import annotations

from arqux.cortex import emit_ideatic
from arqux.cortex.reader import cortex_to_dict


def _document() -> dict:
    return {
        "glossary": {"comments": ["# emit test"]},
        "sections": [
            {
                "id": "$1",
                "title": "FOCUS",
                "entries": [
                    {
                        "sigil": "FCS",
                        "name": "current",
                        "attrs": {
                            "what": "emit helper",
                            "priority": "high",
                            "status": "current",
                            "survive": "work",
                        },
                    }
                ],
            }
        ],
    }


def test_emit_ideatic_returns_cortex_text() -> None:
    text = emit_ideatic(_document())
    assert isinstance(text, str)
    assert "$1" in text
    assert "FCS:current" in text


def test_emit_ideatic_round_trips_through_reader() -> None:
    text = emit_ideatic(_document())
    doc = cortex_to_dict(text)
    sections = doc.get("sections", [])
    assert sections, "emitted text must parse back into sections"
    flat = str(doc)
    assert "emit helper" in flat


def test_emit_ideatic_strict_flag_is_respected() -> None:
    # strict=False must not raise where strict=True validates harder;
    # both paths return text for a well-formed document.
    assert emit_ideatic(_document(), strict=True)
    assert emit_ideatic(_document(), strict=False)
