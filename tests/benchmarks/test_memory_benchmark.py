"""BLP-004 CA-02: a reproducible Memory Core benchmark.

The corpus is synthetically generated — no secrets, no personal data, no
production credentials (L-SEC-02). The benchmark publishes corpus, environment,
commands and results to ``docs/release/benchmark-0.9.0.json``, and asserts only
structural properties: timings are recorded, never asserted, so the suite is
not flaky and the numbers are honest measurements, not claims.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

from arqux.memory import LocalStore, RecallService, build_index

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "release" / "benchmark-0.9.0.json"

TOPICS = 50


def _synthetic_cortex(n_records: int) -> str:
    lines = [
        "$0",
        "$0:format{cortex:0.1,encoding:UTF-8}",
        (
            "KNW:knowledge{type:attrs,weight:B,"
            'fields:"topic:text|content:text|status:text|confidence:dec",'
            'focus:content,desc:"Knowledge"}'
        ),
        "$1:SYNTHETIC",
    ]
    for i in range(n_records):
        lines.append(
            f'KNW:rec{i}{{topic:"topic{i % TOPICS}",'
            f'content:"synthetic memory {i} topic{i % TOPICS}",'
            'status:"current",confidence:0.9}'
        )
    return "\n".join(lines) + "\n"


def test_benchmark_publishes_reproducible_evidence(tmp_path: Path) -> None:
    n_records = 200
    source = tmp_path / "synthetic.cortex"
    source.write_text(_synthetic_cortex(n_records), encoding="utf-8")

    t0 = time.perf_counter()
    index = build_index([source])  # cold start: no derived index exists yet
    cold_start_ms = (time.perf_counter() - t0) * 1000

    store = LocalStore(tmp_path / "index.json", [source])
    t0 = time.perf_counter()
    store.rebuild()
    rebuild_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    second = store.rebuild()
    rebuild_again_ms = (time.perf_counter() - t0) * 1000

    service = RecallService(store)
    queries = ["topic0", "topic10", "topic25"]
    t0 = time.perf_counter()
    hits = [service.recall(q) for q in queries]
    recall_ms = (time.perf_counter() - t0) * 1000

    report = {
        "version": "0.9.0",
        "corpus": {
            "file": "synthetic.cortex",
            "records": n_records,
            "synthetic": True,
            "contains_secrets": False,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "commands": ["python -m pytest tests/benchmarks -q"],
        "results": {
            "cold_start_ms": round(cold_start_ms, 3),
            "rebuild_ms": round(rebuild_ms, 3),
            "rebuild_again_ms": round(rebuild_again_ms, 3),
            "recall_total_ms": round(recall_ms, 3),
            "recall_queries": len(queries),
            "records_projected": len(index.records),
            "source_bytes": source.stat().st_size,
            "index_bytes": (tmp_path / "index.json").stat().st_size,
            "content_hash": index.content_hash,
        },
        "limitations": [
            "Timings are indicative on this host; they are not a claim about other hardware.",
            "Recall uses lexical + temporal ranking; no semantic model is involved (CA-06).",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Structural, deterministic assertions (no timing assertions).
    assert len(index.records) == n_records
    assert second.content_hash == index.content_hash, "rebuild is not idempotent"
    assert all(hit and not hit[0].abstained for hit in hits), "recall abstained unexpectedly"
    assert report["results"]["content_hash"]
    assert report["corpus"]["contains_secrets"] is False
