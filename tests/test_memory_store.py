"""BLP-002 CA-04, CA-05, CA-07, CA-08: the store degrades safely.

The derived index is never the source of truth. A corrupt, truncated,
tampered, expired or stale index is discarded whole and rebuilt from canonical
CORTEX — never repaired by guessing, never served partially (CA-04, CA-07).
An expired index is not consulted at all (CA-05). Every record points back to
its canonical CORTEX address (CA-08).
"""

from __future__ import annotations

import json
from pathlib import Path

from arqux.memory import LocalStore

SAMPLE = """$0
$0:format{cortex:0.1,encoding:UTF-8}
SES:session{type:attrs,weight:B,fields:"input:text|output:text|outcome:text|date:text",focus:outcome,desc:"Session"}
LNG:lesson{type:attrs,weight:M,fields:"type:text|cause:text|lesson:text|prevention:text",focus:lesson,desc:"Lesson"}
KNW:knowledge{type:attrs,weight:B,fields:"topic:text|content:text|status:text",focus:content,desc:"Knowledge"}
AUD:audit{type:attrs,weight:B,fields:"event:text|evidence:text|result:text|date:text",focus:result,desc:"Audit"}
$1:SESSIONS
SES:s1{input:"q",output:"a",outcome:"ok",date:"2026-10-01"}
$2:LESSONS
LNG:l1{type:"process",cause:"x",lesson:"y",prevention:"z"}
$3:KNOWLEDGE
KNW:k1{topic:"t",content:"c",status:"current"}
$4:OUTCOMES
AUD:a1{event:"e",evidence:"ev",result:"ok",date:"2026-10-02"}
"""

EXPECTED_KINDS = {"session", "lesson", "knowledge", "outcome"}


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "brain.cortex"
    source.write_text(SAMPLE, encoding="utf-8")
    return source


def test_index_absent_triggers_a_rebuild(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "index.json", [_source(tmp_path)])
    result = store.load()
    assert result.origin == "rebuild"
    assert result.reason == "index absent"
    assert {r.kind for r in result.records} == EXPECTED_KINDS


def test_corrupt_index_is_discarded_and_rebuilt(tmp_path: Path) -> None:
    index = tmp_path / "index.json"
    index.write_text("{ this is not json", encoding="utf-8")
    store = LocalStore(index, [_source(tmp_path)])

    result = store.load()

    assert result.origin == "rebuild"
    assert result.reason == "index corrupt"
    assert {r.kind for r in result.records} == EXPECTED_KINDS


def test_truncated_index_degrades_safely(tmp_path: Path) -> None:
    source = _source(tmp_path)
    index = tmp_path / "index.json"
    store = LocalStore(index, [source])
    store.rebuild()

    raw = index.read_text(encoding="utf-8")
    index.write_text(raw[: len(raw) // 2], encoding="utf-8")

    result = store.load()

    assert result.origin == "rebuild"
    # No partial/unverified data: the rebuilt set is complete.
    assert len(result.records) == 4


def test_tampered_index_is_not_trusted(tmp_path: Path) -> None:
    source = _source(tmp_path)
    index = tmp_path / "index.json"
    store = LocalStore(index, [source])
    store.rebuild()

    data = json.loads(index.read_text(encoding="utf-8"))
    data["records"][0]["payload"]["injected"] = "tampered"
    index.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    result = store.load()

    assert result.origin == "rebuild"
    assert result.reason == "index hash mismatch"
    assert all("injected" not in r.payload for r in result.records)


def test_expired_index_is_not_consulted(tmp_path: Path) -> None:
    source = _source(tmp_path)
    index = tmp_path / "index.json"
    store = LocalStore(index, [source], ttl_seconds=10)
    store.rebuild(now_epoch=1000.0)  # index is valid until 1010

    result = store.load(now_epoch=1020.0)

    assert result.origin == "rebuild"
    assert result.reason == "index expired"


def test_valid_index_is_reused(tmp_path: Path) -> None:
    source = _source(tmp_path)
    index = tmp_path / "index.json"
    store = LocalStore(index, [source], ttl_seconds=3600)
    store.rebuild(now_epoch=1000.0)

    result = store.load(now_epoch=1005.0)

    assert result.origin == "index"
    assert result.reason == "index valid"


def test_changed_source_invalidates_the_index(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = LocalStore(tmp_path / "index.json", [source])
    store.rebuild()

    source.write_text(SAMPLE + '\nKNW:k2{topic:"t2",content:"c2",status:"current"}\n', encoding="utf-8")

    result = store.load()

    assert result.origin == "rebuild"
    assert result.reason == "index stale"


def test_every_record_points_back_to_cortex(tmp_path: Path) -> None:
    """CA-08: the index is a projection; provenance cites the CORTEX source."""
    source = _source(tmp_path)
    store = LocalStore(tmp_path / "index.json", [source])
    records = store.query()
    assert len(records) == 4
    for record in records:
        assert record.provenance.derived_from == record.address
        assert str(source) in record.address
        assert record.provenance.source_sha256


def test_query_filters_by_kind_scope_and_prefix(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = LocalStore(tmp_path / "index.json", [source])
    assert len(store.query()) == 4
    assert [r.kind for r in store.query(kind="lesson")] == ["lesson"]
    assert store.query(prefix=str(source) + "#$3")[0].kind == "knowledge"
    assert all(r.scope == "project" for r in store.query(scope="project"))
