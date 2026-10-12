"""BLP-046: legacy_task transform of cortex.migrate.

Covers the migration of ``tasks/*.cortex`` artifacts written before
CODEC-CORTEX v0.5, whose WRK/OBJ/AUD entries use a different field spelling
and therefore trip E032_CRITICAL_SIGIL_INCOMPLETE on every read.
"""

from __future__ import annotations

from pathlib import Path

from arqux.cortex.legacy_task import STRIP_FRONTMATTER, migrate_legacy_task
from arqux.cortex.reader import cortex_to_dict
from arqux.handlers.cortex import migrate_handler
from arqux.permissions import PermissionContext

_CTX = PermissionContext(agent_id="test", role="governor")


_LEGACY_TASK = """$0

# -- $0: ARQUX GOVERNANCE GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# WRK   | task       | attrs      | B | Working        | Task
# OBJ   | objective  | attrs      | H | Working        | Objective
# CLAIM | ac1        | attrs      | M | Prefrontal     | Acceptance criterion
# AUD   | evidence   | attrs      | M | Prefrontal     | Evidence

$1: TASK

WRK:task{id:"T-001", status:"done", governor:"hermes", assignee:"alfred", priority:"high", complexity:"standard", cycle:"CYCLE-02", created:"2026-07-11T13:29:09Z", updated:"2026-09-01T12:52:44Z"}

$2: OBJECTIVE

OBJ:objective{text:"Ejecutar la auditoria ejecutable de ArqUX"}

$3: ACCEPTANCE

CLAIM:ac1{criterion:"Auditoria siguiendo el protocolo"}

$4: EVIDENCE

AUD:evidence{text:"Fix aplicado en src/arqux/sync.py"}
"""


def test_strip_frontmatter_removes_yaml_header() -> None:
    assert STRIP_FRONTMATTER("---\nid: T-031\nstatus: draft\n---\n\n$0\n").startswith("$0")


def test_strip_frontmatter_keeps_pure_cortex() -> None:
    assert STRIP_FRONTMATTER(_LEGACY_TASK) == _LEGACY_TASK


def test_migrate_legacy_task_fills_required_fields() -> None:
    doc = migrate_legacy_task(cortex_to_dict(_LEGACY_TASK))
    flat = {
        f"{e['sigil']}:{e.get('name', '')}": e["attrs"]
        for s in doc["sections"]
        for e in s["entries"]
    }

    wrk = flat["WRK:task"]
    for field in ("phase", "current", "blocked", "survive", "status"):
        assert wrk.get(field), f"WRK:task.{field} empty"

    obj = flat["OBJ:objective"]
    assert obj["goal"] == "Ejecutar la auditoria ejecutable de ArqUX"
    assert "text" not in obj
    # success is derived from the task's own acceptance criteria
    assert "Auditoria siguiendo el protocolo" in obj["success"]

    aud = flat["AUD:evidence"]
    for field in ("event", "evidence", "result", "date"):
        assert aud.get(field), f"AUD:evidence.{field} empty"
    assert aud["evidence"].startswith("Fix aplicado")
    assert "text" not in aud


def test_migrate_maps_legacy_statuses() -> None:
    for legacy, expected in (
        ("draft", "planned"),
        ("in_progress", "current"),
        ("closed", "done"),
        ("cancelled", "deprecated"),
    ):
        doc = migrate_legacy_task(
            cortex_to_dict(_LEGACY_TASK.replace('status:"done"', f'status:"{legacy}"'))
        )
        wrk = next(
            e["attrs"]
            for s in doc["sections"]
            for e in s["entries"]
            if e["sigil"] == "WRK"
        )
        assert wrk["status"] == expected


def test_migrate_does_not_fabricate_success_criteria() -> None:
    src = _LEGACY_TASK.split("$3: ACCEPTANCE")[0]
    doc = migrate_legacy_task(cortex_to_dict(src))
    obj = next(
        e["attrs"] for s in doc["sections"] for e in s["entries"] if e["sigil"] == "OBJ"
    )
    assert "NO registrado" in obj["success"]


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    """A second pass must not rewrite the fields again."""
    doc1 = migrate_legacy_task(cortex_to_dict(_LEGACY_TASK))
    doc2 = migrate_legacy_task(doc1)
    assert doc1 == doc2


def test_handler_legacy_task_dry_run_does_not_write(tmp_path: Path) -> None:
    src = tmp_path / "T-001.cortex"
    src.write_text(_LEGACY_TASK, encoding="utf-8")
    dst = tmp_path / "out.cortex"

    result = migrate_handler(
        str(src), str(dst), "legacy_task", dry_run=True, ctx=_CTX
    )
    assert result.profile == "OUT-WORK"
    assert not dst.exists()


def test_handler_legacy_task_writes_valid_file(tmp_path: Path) -> None:
    src = tmp_path / "T-001.cortex"
    src.write_text(_LEGACY_TASK, encoding="utf-8")
    dst = tmp_path / "out.cortex"

    result = migrate_handler(str(src), str(dst), "legacy_task", ctx=_CTX)
    assert result.profile == "OUT-WORK"
    text = dst.read_text(encoding="utf-8")

    wrk = text[text.index("WRK:task") :]
    for field in ("phase", "current", "blocked", "survive"):
        assert field in wrk.split("\n", 1)[0]
