"""Adapter tests (BLP-002 T-2.8): CORTEX dict -> learning document."""
from __future__ import annotations

from pathlib import Path

import pytest

from arqux.core.learning.document import (
    from_cortex_dict,
    load_brain_document,
)
from arqux.core.learning.protocol import LearningDocument
from arqux.cortex.reader import cortex_to_dict

SAMPLE = """$0

$1: IDENTITY
IDN:tester{name:"tester", role:"executor"}

$5: LESSONS
LNG:hot{type:"process", cause:"cold", lesson:"smells burn", prevention:"check water"}
WRK:stale{phase:"static"}
"""


def _doc():
    parsed = cortex_to_dict(SAMPLE)
    return from_cortex_dict(parsed)


def test_from_cortex_dict_requires_dict():
    with pytest.raises(TypeError):
        from_cortex_dict("nope")  # type: ignore[arg-type]


def test_protocol_recognised():
    assert isinstance(_doc(), LearningDocument)


def test_iter_entries_order():
    rows = list(_doc().iter_entries())
    assert [(s, e.sigil, e.name) for s, e in rows] == [
        ("$1", "IDN", "tester"),
        ("$5", "LNG", "hot"),
        ("$5", "WRK", "stale"),
    ]


def test_get_section():
    doc = _doc()
    assert doc.get_section("$1") is not None
    assert doc.get_section("$99") is None


def test_empty_document_is_readable():
    doc = from_cortex_dict({})
    assert list(doc.iter_entries()) == []


def test_load_brain_document(tmp_path: Path):
    arqux_dir = tmp_path / ".arqux"
    arqux_dir.mkdir()
    (arqux_dir / "brain.cortex").write_text(SAMPLE, encoding="utf-8")
    loaded = load_brain_document(tmp_path)
    assert loaded is not None
    assert any(s == "$5" for s, _ in loaded.iter_entries())


def test_load_brain_document_missing(tmp_path: Path):
    """Unreadable brain returns None — it is NOT an error by itself."""
    (tmp_path / ".arqux").mkdir()
    loaded = load_brain_document(tmp_path)
    assert loaded is None
