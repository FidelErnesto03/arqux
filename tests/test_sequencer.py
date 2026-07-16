"""Tests for Universal Sequencer (``arqux.core.sequencer``)."""

from __future__ import annotations

from arqux.core.sequencer import Sequencer

SAMPLE_BODY = """\
<!-- BLP:TITLE -->
# BLP-001: Test
<!-- /BLP:TITLE -->

<!-- BLP:1 -->
## §1: Planteamiento del Problema

_Describe el problema que aborda este Blueprint. ¿Qué evidencia existe de que es real?_

**Evidencia:**
- _Evidencia 1_
- _Evidencia 2_

**Impacto de no resolverlo:**
_
<!-- /BLP:1 -->

<!-- BLP:2 -->
## §2: Objetivo

_Concreto, verificable, autocontenido. Un ejecutor leyendo solo esta sección debe entender qué lograr._
<!-- /BLP:2 -->

<!-- BLP:3 -->
## §3: Precondiciones

_¿Qué debe existir o ser cierto ANTES de que comience la ejecución? Cada precondición debe ser verificable._

- [ ] _Precondición 1 — verificable mediante comando o inspección_
- [ ] _Precondición 2 — verificable mediante comando o inspección_
<!-- /BLP:3 -->

<!-- BLP:4 -->
## §4: Principio Rector

Written content with no _markers_.
<!-- /BLP:4 -->
"""


def test_scan_detects_all_segments() -> None:
    """Sequencer detects all segments in a template body."""
    seq = Sequencer("BLP")
    result = seq.scan(SAMPLE_BODY)
    # BLP:TITLE + 4 sections = 5 total
    assert result.total == 5, f"expected 5, got {result.total}"


def test_scan_pending_segments() -> None:
    """Segments with _..._ markers are reported as pending."""
    seq = Sequencer("BLP")
    result = seq.scan(SAMPLE_BODY)
    # §1, §2, §3 have markers; §4 is written (no markers)
    pending_ids = [s.id for s in result.pending]
    assert "1" in pending_ids, "§1 should be pending"
    assert "2" in pending_ids, "§2 should be pending"
    assert "3" in pending_ids, "§3 should be pending"
    assert "4" not in pending_ids, "§4 should NOT be pending (written content)"


def test_scan_next_pending_is_first() -> None:
    """next_pending returns the lowest-ID pending segment."""
    seq = Sequencer("BLP")
    result = seq.scan(SAMPLE_BODY)
    assert result.next_pending is not None
    assert result.next_pending.id == "1"
    assert "Planteamiento" in result.next_pending.header


def test_scan_no_pending_returns_none() -> None:
    """When all segments are written, next_pending is None."""
    body = """\
<!-- CYCLE:1 -->
## §1: Scope

Written content.
<!-- /CYCLE:1 -->

<!-- CYCLE:2 -->
## §2: Constraints

No markers here.
<!-- /CYCLE:2 -->
"""
    seq = Sequencer("CYCLE")
    result = seq.scan(body)
    assert result.next_pending is None
    assert result.total == 2
    assert result.completed == 2


def test_empty_segment_is_pending() -> None:
    """Empty segments (no content) are reported as pending."""
    body = """\
<!-- BLP:1 -->
## §1: Empty

<!-- /BLP:1 -->
"""
    seq = Sequencer("BLP")
    result = seq.scan(body)
    assert result.total == 1
    assert len(result.pending) == 1
    assert result.pending[0].has_content is False


def test_extract_header() -> None:
    """_extract_header finds the ## §N: line."""
    text = "some text\n## §3: Preconditions\nmore text"
    header = Sequencer._extract_header(text)
    assert header == "## §3: Preconditions"


def test_extract_header_empty_when_missing() -> None:
    """_extract_header returns empty when no ## §N: line."""
    text = "just text\nno header here\n"
    header = Sequencer._extract_header(text)
    assert header == ""
