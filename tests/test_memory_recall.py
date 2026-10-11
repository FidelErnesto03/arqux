"""BLP-003 CA-01..CA-04 and CA-06: recall contract, determinism, abstention.

Recall returns content, provenance, confidence and a ranking reason (CA-01),
deterministically (CA-02), citing the CORTEX source (CA-03), abstaining on low
confidence (CA-04), and never mutating the canonical CORTEX (CA-06).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from arqux.memory import LocalStore, RecallService

SAMPLE = """$0
$0:format{cortex:0.1,encoding:UTF-8}
KNW:knowledge{type:attrs,weight:B,fields:"topic:text|content:text|status:text|confidence:dec|date:text",focus:content,desc:"Knowledge"}
$1:KNOW
KNW:cortex{topic:"CORTEX",content:"lineal sigil codec",status:"current",confidence:0.9,date:"2026-10-01"}
KNW:other{topic:"unrelated",content:"unrelated topic here",status:"current",confidence:0.9,date:"2026-10-02"}
KNW:weak{topic:"weak",content:"weak memory",status:"current",confidence:0.2,date:"2026-10-03"}
"""


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "brain.cortex"
    source.write_text(SAMPLE, encoding="utf-8")
    return source


def _store(tmp_path: Path) -> LocalStore:
    return LocalStore(tmp_path / "index.json", [_source(tmp_path)])


def test_recall_returns_content_provenance_confidence_and_reason(tmp_path: Path) -> None:
    results = RecallService(_store(tmp_path)).recall("CORTEX sigil codec")
    assert results and not results[0].abstained
    result = results[0]
    assert result.content, "content missing"
    assert result.provenance, "provenance missing"
    assert 0.0 <= result.confidence <= 1.0
    assert result.ranking_reason
    assert result.trust == "untrusted_data"


def test_ranking_is_deterministic(tmp_path: Path) -> None:
    service = RecallService(_store(tmp_path))
    first = [r.address for r in service.recall("cortex codec")]
    second = [r.address for r in service.recall("cortex codec")]
    assert first == second
    assert first, "nothing recalled"


def test_result_references_the_cortex_source(tmp_path: Path) -> None:
    source = _source(tmp_path)
    results = RecallService(LocalStore(tmp_path / "index.json", [source])).recall("cortex")
    assert str(source) in results[0].provenance


def test_abstains_on_low_confidence_and_declares_the_reason(tmp_path: Path) -> None:
    results = RecallService(_store(tmp_path), min_confidence=0.8).recall("weak")
    assert results[0].abstained
    assert "confianza" in results[0].abstention_reason


def test_abstains_without_a_lexical_match(tmp_path: Path) -> None:
    results = RecallService(_store(tmp_path)).recall("zzzz-nothing-matches")
    assert results[0].abstained
    assert results[0].abstention_reason


def test_recall_does_not_mutate_the_canonical_cortex(tmp_path: Path) -> None:
    source = _source(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    RecallService(LocalStore(tmp_path / "index.json", [source])).recall("cortex")
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    assert before == after
