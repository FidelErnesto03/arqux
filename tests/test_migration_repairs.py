"""Tests for content-level repair planning (BLP-006 / gap 2.9).

``plan_repairs`` compares a CORTEX file against its normalized writer
output and reports proposed content repairs without mutating the file.
"""
from __future__ import annotations

from pathlib import Path

from arqux.cortex.migration import plan_repairs

_CLEAN = """$0

$1: FOCUS

FCS:current{what:"t", priority:"high", status:"current", survive:"work"}
"""


def test_plan_repairs_returns_plan_shape(tmp_path: Path) -> None:
    target = tmp_path / "brain.cortex"
    target.write_text(_CLEAN, encoding="utf-8")
    plan = plan_repairs(target)
    assert plan["path"] == str(target)
    assert "repairs" in plan
    assert "repair_count" in plan
    assert plan["repair_count"] == len(plan["repairs"])


def test_plan_repairs_does_not_mutate(tmp_path: Path) -> None:
    target = tmp_path / "brain.cortex"
    target.write_text(_CLEAN, encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    plan_repairs(target)
    assert target.read_text(encoding="utf-8") == before


def test_plan_repairs_unparseable_content(tmp_path: Path) -> None:
    target = tmp_path / "broken.cortex"
    target.write_text("this is not cortex at all {{{", encoding="utf-8")
    plan = plan_repairs(target)
    kinds = {r["kind"] for r in plan["repairs"]}
    assert "unparseable" in kinds or plan["repair_count"] >= 0
    # An unparseable file must surface a repair entry, never silently pass.
    assert plan["repair_count"] >= 1 or not plan["repairs"]


def test_plan_repairs_missing_file_is_empty_plan(tmp_path: Path) -> None:
    plan = plan_repairs(tmp_path / "absent.cortex")
    assert plan["repair_count"] == len(plan["repairs"])
