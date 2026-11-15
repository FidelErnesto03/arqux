"""Tests for cross-corpus queries (BLP-006 / gap 2.6).

``cortex.corpus.list`` and ``cortex.corpus.query`` give selectors a
transversal view: they address a corpus root, not a single file.
"""
from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex_corpus import (
    corpus_list_handler,
    corpus_query_handler,
)


def _corpus(tmp_path: Path) -> Path:
    (tmp_path / "a.cortex").write_text("$0\n", encoding="utf-8")
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "b.cortex").write_text("$0\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("nope", encoding="utf-8")
    return tmp_path


def test_corpus_list_finds_all_cortex_files(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    out = corpus_list_handler(path=str(root))
    assert out.fields["count"] == 2
    files = out.fields["files"]
    assert any(f.endswith("a.cortex") for f in files)
    assert any(f.endswith("b.cortex") for f in files)


def test_corpus_query_filters_by_pattern(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    out = corpus_query_handler(pattern="nested", path=str(root))
    assert out.fields["count"] == 1
    assert out.fields["matches"][0].endswith("b.cortex")


def test_corpus_query_no_match_returns_zero(tmp_path: Path) -> None:
    root = _corpus(tmp_path)
    out = corpus_query_handler(pattern="zzz-no-match", path=str(root))
    assert out.fields["count"] == 0
    assert out.fields["matches"] == []


def test_corpus_handlers_registered() -> None:
    from arqux.handlers import REGISTRY

    names = set(REGISTRY) if not isinstance(REGISTRY, dict) else set(REGISTRY)
    assert any("corpus" in n for n in names), sorted(names)[:30]
