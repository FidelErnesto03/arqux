"""Adapter form coverage (BLP-002 T-2.8 / AC-04).

The native CORTEX reader today emits exactly two entry shapes:
``attrs`` (dict body that parses as key:value) and ``body`` (cuerpo — prose).
``block`` (bloque) and ``attrs-pos`` are recognised by the adapter as
defensive branches for brains written by future readers; they are tested
here directly with synthetic dicts. Every form round-trips through
``NativeLearningDocument.iter_entries``.
"""
from __future__ import annotations

from arqux.core.learning.document import from_cortex_dict
from arqux.core.learning.protocol import LearningEntry
from arqux.cortex.reader import cortex_to_dict


def _entries(doc):
    return list(doc.iter_entries())


# --- forma 1: attrs (real reader) -------------------------------------------

def test_form_attrs_real_reader():
    text = "$0\n\n$1: S\nLNG:hot{type:\"process\", cause:\"repeated\"}\n"
    doc = from_cortex_dict(cortex_to_dict(text))
    rows = _entries(doc)
    assert rows == [("$1", LearningEntry(sigil="LNG", name="hot", value={"type": "process", "cause": "repeated"}, section="$1", type="attrs"))]


# --- forma 2: cuerpo (real reader) ------------------------------------------

def test_form_cuerpo_real_reader():
    text = "$0\n\n$1: S\nLNG:child{\nfree-flowing prose that is not attrs\nsecond line\n}\n"
    doc = from_cortex_dict(cortex_to_dict(text))
    rows = _entries(doc)
    assert len(rows) == 1
    assert rows[0][1].type == "cuerpo"
    assert "prose" in rows[0][1].value


# --- forma 3: attrs-pos (synthetic; reader does not emit today) -------------

def test_form_attrs_pos_synthetic():
    doc = from_cortex_dict({
        "sections": [
            {"id": "$1", "entries": [
                {"sigil": "HDL", "name": "handler", "attrs_pos": {"positional": "value"}},
            ]},
        ],
    })
    rows = _entries(doc)
    assert len(rows) == 1
    assert rows[0][1].type == "attrs-pos"
    assert rows[0][1].value == {"positional": "value"}


# --- forma 4: bloque (synthetic; reader does not emit today) -----------------

def test_form_bloque_synthetic():
    doc = from_cortex_dict({
        "sections": [
            {"id": "$1", "entries": [
                {"sigil": "BLK", "name": "block", "block": "parte 1\nparte 2"},
            ]},
        ],
    })
    rows = _entries(doc)
    assert len(rows) == 1
    assert rows[0][1].type == "bloque"
    assert "parte 1" in rows[0][1].value


def test_unrecognised_entry_shape_falls_back_to_cuerpo():
    doc = from_cortex_dict({
        "sections": [{"id": "$1", "entries": [{"sigil": "X", "name": "y", "weird": 1}]}],
    })
    rows = _entries(doc)
    assert rows[0][1].type == "cuerpo"
    assert rows[0][1].value == {}
