"""Regression tests for KNW metric recomputation (frozen-metrics issue)."""

from __future__ import annotations

from pathlib import Path

from arqux.sync import _merge_real_metrics, recompute_brain_metrics


def _mk_project(tmp_path: Path) -> Path:
    cyc = tmp_path / ".arqux" / "cycles" / "CYCLE-01"
    (cyc / "blueprints").mkdir(parents=True)
    (cyc / "tasks").mkdir(parents=True)
    (cyc / "MANIFEST.md").write_text('---\nstatus: "closed"\n---\n',
                                     encoding="utf-8")
    (cyc / "blueprints" / "BLP-001.md").write_text(
        '---\nstatus: "done"\n---\n', encoding="utf-8")
    (cyc / "blueprints" / "BLP-002.md").write_text(
        '---\nstatus: "draft"\n---\n', encoding="utf-8")
    (cyc / "tasks" / "T-001.cortex").write_text(
        '$0\n\nWRK:task{id:"T-001", status:"done"}\n', encoding="utf-8")
    (cyc / "tasks" / "T-002.cortex").write_text(
        '$0\n\nWRK:task{id:"T-002", status:"in_progress"}\n', encoding="utf-8")
    return tmp_path


def test_recompute_counts(tmp_path: Path) -> None:
    root = _mk_project(tmp_path)
    m = recompute_brain_metrics(root)
    assert m["blueprints_done"] == 1
    assert m["blueprints_draft"] == 1
    assert m["blueprints_cancelled"] == 0
    assert m["cycles_closed"] == 1
    assert m["cycles_open"] == 0
    assert m["tasks_done"] == 1
    assert m["tasks_active"] == 1


def test_merge_overrides_fixed_constant(tmp_path: Path) -> None:
    root = _mk_project(tmp_path)
    (root / ".arqux" / "cycles" / "CYCLE-01" / "tasks" / "T-003.cortex"
     ).write_text('WRK:task{id:"T-003", status:"done"}', encoding="utf-8")
    # handler passes the fixed constant 1; real count is 2 → must win
    merged = _merge_real_metrics(root, {"tasks_done": 1, "other": 7})
    assert merged["tasks_done"] == 2
    assert merged["other"] == 7
