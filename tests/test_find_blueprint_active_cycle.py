"""Regression tests: _find_blueprint must resolve by active cycle (FCS:current).

Bug: find_project_root returns the .arqux dir, but _find_blueprint built
brain_path as root/.arqux/brain.cortex (i.e. .arqux/.arqux/brain.cortex),
so the active-cycle mechanism was silently skipped and resolution fell
back to "most recent cycle first", colliding bp_ids across cycles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers.blueprint._helpers import _find_blueprint

ARQUX_DIR = ".arqux"

BRAIN_TEMPLATE = """$0
$2: FOCUS
FCS:current{{status:current,what:"test",cycle:"{cycle}"}}
$6: PULSE
"""

BLP_TEMPLATE = """---
blueprint_id: "BLP-001"
title: "{title}"
cycle: "{cycle}"
status: "draft"
---
# {title}
"""


def _make_project(tmp_path: Path, active_cycle: str) -> Path:
    """Two cycles (CYCLE-02 older, CYCLE-03 newer) with colliding BLP-001."""
    arqx = tmp_path / ARQUX_DIR
    arqx.mkdir(parents=True)
    (arqx / "brain.cortex").write_text(BRAIN_TEMPLATE.format(cycle=active_cycle))
    for cycle, title in (("CYCLE-02", "older-cycle-blp"), ("CYCLE-03", "newer-cycle-blp")):
        bp_dir = arqx / "cycles" / cycle / "blueprints"
        bp_dir.mkdir(parents=True)
        (bp_dir / "BLP-001.md").write_text(BLP_TEMPLATE.format(title=title, cycle=cycle))
    return arqx


def test_resolves_active_cycle_not_newest(tmp_path: Path):
    """Active cycle CYCLE-02 must win over newer CYCLE-03."""
    arqx = _make_project(tmp_path, "CYCLE-02")
    bp_path, fm, _ = _find_blueprint(arqx, "BLP-001")
    assert bp_path is not None
    assert "CYCLE-02" in str(bp_path)
    assert fm["title"] == "older-cycle-blp"


def test_resolves_newest_when_active(tmp_path: Path):
    """Active cycle CYCLE-03 resolves CYCLE-03 (sanity)."""
    arqx = _make_project(tmp_path, "CYCLE-03")
    bp_path, fm, _ = _find_blueprint(arqx, "BLP-001")
    assert bp_path is not None
    assert "CYCLE-03" in str(bp_path)
    assert fm["title"] == "newer-cycle-blp"


def test_fcs_location_agnostic(tmp_path: Path):
    """FCS:current resolves regardless of which section hosts it ($1 legacy)."""
    arqx = tmp_path / ARQUX_DIR
    arqx.mkdir(parents=True)
    (arqx / "brain.cortex").write_text(
        "$0\n"
        "$1: METADATA\n"
        'FCS:current{status:current,what:"test",cycle:"CYCLE-02"}\n'
        "$6: PULSE\n"
    )
    for cycle, title in (("CYCLE-02", "older-cycle-blp"), ("CYCLE-03", "newer-cycle-blp")):
        bp_dir = arqx / "cycles" / cycle / "blueprints"
        bp_dir.mkdir(parents=True)
        (bp_dir / "BLP-001.md").write_text(BLP_TEMPLATE.format(title=title, cycle=cycle))
    bp_path, fm, _ = _find_blueprint(arqx, "BLP-001")
    assert bp_path is not None
    assert "CYCLE-02" in str(bp_path)


def test_fallback_newest_without_cycle_hint(tmp_path: Path):
    """Without a cycle field in FCS:current, fallback picks most recent cycle."""
    arqx = tmp_path / ARQUX_DIR
    arqx.mkdir(parents=True)
    (arqx / "brain.cortex").write_text(
        "$0\n$2: FOCUS\n"
        'FCS:current{status:current,what:"test"}\n'
        "$6: PULSE\n"
    )
    for cycle, title in (("CYCLE-02", "older-cycle-blp"), ("CYCLE-03", "newer-cycle-blp")):
        bp_dir = arqx / "cycles" / cycle / "blueprints"
        bp_dir.mkdir(parents=True)
        (bp_dir / "BLP-001.md").write_text(BLP_TEMPLATE.format(title=title, cycle=cycle))
    bp_path, fm, _ = _find_blueprint(arqx, "BLP-001")
    assert bp_path is not None
    assert "CYCLE-03" in str(bp_path)
