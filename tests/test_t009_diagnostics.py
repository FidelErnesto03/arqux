"""Regression tests for T-009 — enumerated diagnostics in sibling handlers,
non_bypassable surfacing, and task_create content-only obj."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import (
    entry_delete_handler,
    entry_move_handler,
    entry_update_handler,
)
from arqux.handlers.task import create_task, read_task
from arqux.handlers.workspace import init_workspace
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

# KNW is a critical sigil: an incomplete entry yields E032 errors on any
# mutation that re-validates the file.
_DIRTY_BRAIN = """$0

GSIG:KNW{name:"knowledge", type:"attrs", risk:"B", layer:"Semantic", description:"k"}
GSIG:LNG{name:"lesson", type:"attrs", risk:"M", layer:"Episodic", description:"l"}

$7: LESSONS

LNG:target{type:"process", cause:"c", lesson:"l", prevention:"p"}

$10: KNOWLEDGE

KNW:bad{name:"bad"}
"""


def _dirty_brain(tmp_path: Path) -> Path:
    f = tmp_path / "brain.cortex"
    f.write_text(_DIRTY_BRAIN)
    return f


# ---------------------------------------------------------------------------
# (1) enumerated diagnostics in entry.update / delete / move
# ---------------------------------------------------------------------------


def test_entry_update_enumerates_diagnostics(tmp_path: Path) -> None:
    f = _dirty_brain(tmp_path)
    out = entry_update_handler(str(f), "LNG:target", set_="lesson:updated", ctx=_CONTEXT)
    assert out.profile == "OUT-ERROR"
    assert out.fields["error_count"] >= 1
    diagnostics = out.fields["diagnostics"]
    assert len(diagnostics) == out.fields["error_count"]
    for i, diag in enumerate(diagnostics, 1):
        assert f"[{i}] {diag}" in out.message
    assert out.fields["non_bypassable"] is False


def test_entry_delete_enumerates_diagnostics(tmp_path: Path) -> None:
    f = _dirty_brain(tmp_path)
    out = entry_delete_handler(str(f), "LNG:target", ctx=_CONTEXT)
    assert out.profile == "OUT-ERROR"
    assert out.fields["error_count"] >= 1
    diagnostics = out.fields["diagnostics"]
    assert len(diagnostics) == out.fields["error_count"]
    for i, diag in enumerate(diagnostics, 1):
        assert f"[{i}] {diag}" in out.message
    assert out.fields["non_bypassable"] is False


def test_entry_move_enumerates_diagnostics(tmp_path: Path) -> None:
    f = _dirty_brain(tmp_path)
    out = entry_move_handler(str(f), "LNG:target", "$10", ctx=_CONTEXT)
    assert out.profile == "OUT-ERROR"
    assert out.fields["error_count"] >= 1
    diagnostics = out.fields["diagnostics"]
    assert len(diagnostics) == out.fields["error_count"]
    for i, diag in enumerate(diagnostics, 1):
        assert f"[{i}] {diag}" in out.message
    assert out.fields["non_bypassable"] is False


def test_entry_add_surfaces_non_bypassable(tmp_path: Path, monkeypatch) -> None:
    """A hard atomic-write failure surfaces non_bypassable=True."""
    import arqux.core.state._crud as crud_mod
    from arqux.handlers.cortex import entry_add_handler

    f = _dirty_brain(tmp_path)

    def boom(doc, path, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(crud_mod, "atomic_write_json", boom)
    out = entry_add_handler(
        str(f), "$7", "LNG", "new_entry",
        'type:"process", cause:"c", lesson:"l", prevention:"p"',
        force=True, ctx=_CONTEXT,
    )
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("non_bypassable") is True


# ---------------------------------------------------------------------------
# (3) task_create content-only obj
# ---------------------------------------------------------------------------


def _proj_with_cycle(tmp_path: Path) -> Path:
    from arqux.handlers.cycle import create_cycle, synthesize_cycle
    from arqux.handlers.project import init_project

    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "proj"
    proj.mkdir()
    init_workspace(path=str(ws), ctx=_CONTEXT)
    init_project(name="proj", path=str(proj), ctx=_CONTEXT)
    cycle_result = create_cycle(name="CYCLE-P", path=str(proj), ctx=_CONTEXT)
    cycle_id = cycle_result.fields["cycle_id"]
    synthesize_cycle(
        cycle_id=cycle_id,
        content=(
            "$1:{purpose: test}$2:{scope: test}$3:{CYC-OBJ-1: test objective}"
            "$4:{guideline: test}$5:{checkpoint: test}$6:{BLP index}$7:{metrics: 0}"
            "$8:{rule: test}$9:{gates: none}"
        ),
        path=str(proj),
        ctx=_CONTEXT,
    )
    return proj


def test_task_create_content_only_with_obj(tmp_path: Path) -> None:
    """obj omitted — content carries it: accepted, obj + lists persisted."""

    proj = _proj_with_cycle(tmp_path)
    out = create_task(
        content=(
            '$1:{obj:"Content-only objective", '
            'pre:["pre 1"], ac:["ac 1"], blk:["blocker 1"]}'
        ),
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    task_id = out.fields["task_id"]

    read_result = read_task(task_id=task_id, path=str(proj), ctx=_CONTEXT)
    content_field = read_result.fields.get("content", "")
    assert "Content-only objective" in content_field
    assert "pre 1" in content_field
    assert "ac 1" in content_field
    assert "blocker 1" in content_field


def test_task_create_without_obj_anywhere_fails_loudly(tmp_path: Path) -> None:
    """No obj param and no obj in content (or no content) → INVALID_ARGS."""
    proj = _proj_with_cycle(tmp_path)
    out = create_task(path=str(proj), ctx=_CONTEXT)
    assert out.profile == "OUT-ERROR"
    assert out.fields.get("code") == "INVALID_ARGS"
    assert "obj" in out.message

    out2 = create_task(
        content='$1:{pre:["pre 1"]}',
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out2.profile == "OUT-ERROR"
    assert out2.fields.get("code") == "INVALID_ARGS"
