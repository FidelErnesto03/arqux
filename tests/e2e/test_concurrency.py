"""Concurrency suite — CYCLE-14/BLP-001 measurement: without exclusion, two
processes read the old text and the second write silently discarded the
first (measured ~55% of concurrent cortex.entry.add lost).

These tests make lost writes fail loudly.
"""

from __future__ import annotations

import threading

from arqux.cortex_out import OUT_WORK
from arqux.handlers.cortex.entries import entry_add_handler

DOC = """$0

$1: SINK

REG:seed{kind:"probe"}
"""


def test_concurrent_adds_do_not_lose_writes(tmp_path, governor_ctx):
    f = tmp_path / "doc.cortex"
    f.write_text(DOC, encoding="utf-8")

    errors: list[str] = []
    barrier = threading.Barrier(8)

    def worker(i: int) -> None:
        barrier.wait()
        try:
            out = entry_add_handler(
                str(f), section="$1", sigil="REG", name=f"w{i}",
                value=f'kind:"probe", idx:{i}', ctx=governor_ctx,
            )
            if out.profile != OUT_WORK:
                errors.append(out.to_text())
        except Exception as exc:  # noqa: BLE001 - surfaced below
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    text = f.read_text(encoding="utf-8")
    missing = [i for i in range(8) if f"REG:w{i}" not in text]
    assert not missing, f"lost writes for {missing}"


def test_reentrant_lock_allows_nested_acquisition(tmp_path):
    from arqux.concurrency import reentrant_file_lock

    lock = tmp_path / "doc.cortex.lock"
    with reentrant_file_lock(lock), reentrant_file_lock(lock):
        assert True


def test_sequential_writes_keep_prior_entries(tmp_path, governor_ctx):
    f = tmp_path / "doc.cortex"
    f.write_text(DOC, encoding="utf-8")
    for i in range(20):
        out = entry_add_handler(
            str(f), section="$1", sigil="REG", name=f"s{i}",
            value='kind:"probe"', ctx=governor_ctx,
        )
        assert out.profile == OUT_WORK, out.to_text()
    text = f.read_text(encoding="utf-8")
    assert all(f"REG:s{i}" in text for i in range(20))
