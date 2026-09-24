"""Regression tests for T-005 — unbounded list outputs.

Covers pagination (limit/offset + total/returned/offset/next_offset),
sigil/section filters and the compact one-entry-per-line format on
cortex.entry.list, plus pagination/compact on handler.list, task.list
and blueprint.list.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers import project, workspace
from arqux.handlers.blueprint._read import list_blueprints
from arqux.handlers.cortex import entry_list_handler
from arqux.handlers.handler import list_handlers
from arqux.handlers.task import create_task, list_tasks
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")


def _big_brain(tmp_path: Path, count: int = 78) -> Path:
    """A brain-like .cortex with *count* LNG entries in distinct sections."""
    f = tmp_path / "big.cortex"
    lines = ["$0", ""]
    for i in range(count):
        lines += [
            f"${i + 1}: SEC_{i}",
            "",
            f'LNG:e_{i:03d}{{type:"process", cause:"c", lesson:"l{i}", prevention:"p"}}',
            "",
        ]
    f.write_text("\n".join(lines))
    return f


# ---------------------------------------------------------------------------
# cortex.entry.list — pagination, filters, compact
# ---------------------------------------------------------------------------


def test_entry_list_default_cap_paginates(tmp_path: Path) -> None:
    f = _big_brain(tmp_path)
    page1 = entry_list_handler(str(f), ctx=_CONTEXT)
    assert page1.profile == "OUT-WORK"
    assert page1.fields["total"] == 78
    assert page1.fields["returned"] == 50
    assert page1.fields["offset"] == 0
    assert page1.fields["next_offset"] == 50

    page2 = entry_list_handler(str(f), offset=50, ctx=_CONTEXT)
    assert page2.fields["returned"] == 28
    assert page2.fields["next_offset"] is None

    names1 = [e["name"] for e in page1.fields["entries"]]
    names2 = [e["name"] for e in page2.fields["entries"]]
    assert len(names1) + len(names2) == 78
    assert not set(names1) & set(names2)


def test_entry_list_limit_recovers_full_listing(tmp_path: Path) -> None:
    f = _big_brain(tmp_path)
    full = entry_list_handler(str(f), limit=100, ctx=_CONTEXT)
    assert full.fields["returned"] == 78
    assert full.fields["next_offset"] is None


def test_entry_list_filters_by_sigil_and_section(tmp_path: Path) -> None:
    f = _big_brain(tmp_path, count=10)
    by_sigil = entry_list_handler(str(f), sigil="LNG", ctx=_CONTEXT)
    assert by_sigil.fields["total"] == 10
    assert all(e["sigil"] == "LNG" for e in by_sigil.fields["entries"])

    by_section = entry_list_handler(str(f), section="$3", ctx=_CONTEXT)
    assert by_section.fields["total"] == 1
    assert by_section.fields["entries"][0]["name"] == "e_002"

    both = entry_list_handler(str(f), sigil="LNG", section="$5", ctx=_CONTEXT)
    assert both.fields["total"] == 1
    assert both.fields["entries"][0]["name"] == "e_004"


def test_entry_list_compact_one_entry_per_line(tmp_path: Path) -> None:
    f = _big_brain(tmp_path, count=3)
    out = entry_list_handler(str(f), format="compact", ctx=_CONTEXT)
    assert out.fields["format"] == "compact"
    content = out.fields["content"]
    lines = content.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("LNG:e_000{")
    assert lines[2].startswith("LNG:e_002{")


def test_entry_list_compact_multiline_cuerpo_stays_one_line(tmp_path: Path) -> None:
    """A multi-line cuerpo body is collapsed, not truncated — one line per entry."""
    f = tmp_path / "cuerpo.cortex"
    f.write_text(
        "$0\n\n"
        "$5: PROCEDURES\n\n"
        "AXM:rule1{\n"
        "First principle line.\n"
        "Second principle line.\n"
        "Third principle line.\n"
        "}\n"
    )
    out = entry_list_handler(str(f), format="compact", ctx=_CONTEXT)
    assert out.fields["count"] == 1
    lines = out.fields["content"].splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("AXM:rule1{")
    assert "First principle line." in lines[0]
    assert "Second principle line." in lines[0]
    assert "Third principle line." in lines[0]
    assert "\n" not in out.fields["content"]


def test_entry_list_invalid_limit_offset(tmp_path: Path) -> None:
    f = _big_brain(tmp_path, count=3)
    bad_limit = entry_list_handler(str(f), limit=0, ctx=_CONTEXT)
    assert bad_limit.profile == "OUT-ERROR"
    assert bad_limit.fields.get("code") == "INVALID_ARGS"
    bad_offset = entry_list_handler(str(f), offset=-1, ctx=_CONTEXT)
    assert bad_offset.profile == "OUT-ERROR"
    assert bad_offset.fields.get("code") == "INVALID_ARGS"
    bad_type = entry_list_handler(str(f), limit="many", ctx=_CONTEXT)
    assert bad_type.profile == "OUT-ERROR"
    assert bad_type.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# handler.list — pagination + compact
# ---------------------------------------------------------------------------


def test_handler_list_full_default_cap_paginates() -> None:
    page1 = list_handlers("FULL")
    assert page1["_total"] == 88
    assert page1["_returned"] == 50
    assert page1["_offset"] == 0
    assert page1["_next_offset"] == 50

    page2 = list_handlers("FULL", offset=50)
    assert page2["_returned"] == 38
    assert page2["_next_offset"] is None

    names = [
        h["name"]
        for m in page1.values() if isinstance(m, dict)
        for h in m["handlers"]
    ] + [
        h["name"]
        for m in page2.values() if isinstance(m, dict)
        for h in m["handlers"]
    ]
    assert len(names) == 88


def test_handler_list_compact_returns_names_only() -> None:
    out = list_handlers("NANO", compact=True)
    handlers = out["handler"]["handlers"]
    assert all(isinstance(h, str) for h in handlers)
    assert "handler.list" in handlers


def test_handler_list_nano_unchanged_default() -> None:
    out = list_handlers("NANO")
    assert out["_total"] == 8
    assert out["_returned"] == 8
    assert out["_next_offset"] is None


def test_handler_list_invalid_limit() -> None:
    with pytest.raises(ValueError):
        list_handlers("FULL", limit=0)


# ---------------------------------------------------------------------------
# task.list / blueprint.list — pagination
# ---------------------------------------------------------------------------


def _proj_with_tasks(tmp_path: Path, n: int) -> Path:
    from arqux.handlers.cycle import create_cycle, synthesize_cycle

    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "proj"
    proj.mkdir()
    workspace.init_workspace(path=str(ws), ctx=_CONTEXT)
    project.init_project(name="proj", path=str(proj), ctx=_CONTEXT)
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
    for _ in range(n):
        create_task(obj="paginated task", path=str(proj), ctx=_CONTEXT)
    return proj


def test_task_list_pagination(tmp_path: Path) -> None:
    proj = _proj_with_tasks(tmp_path, 3)
    out = list_tasks(limit=2, path=str(proj), ctx=_CONTEXT)
    assert out.fields["total"] == 3
    assert out.fields["returned"] == 2
    assert out.fields["next_offset"] == 2
    out2 = list_tasks(limit=2, offset=2, path=str(proj), ctx=_CONTEXT)
    assert out2.fields["returned"] == 1
    assert out2.fields["next_offset"] is None


def test_task_list_no_limit_returns_all(tmp_path: Path) -> None:
    proj = _proj_with_tasks(tmp_path, 3)
    out = list_tasks(path=str(proj), ctx=_CONTEXT)
    assert out.fields["total"] == 3
    assert out.fields["returned"] == 3
    assert out.fields["next_offset"] is None


def test_blueprint_list_pagination(tmp_path: Path) -> None:
    from arqux.handlers.blueprint.lifecycle import create_blueprint

    proj = _proj_with_tasks(tmp_path, 0)
    for _ in range(3):
        create_blueprint(obj="paginated blp", path=str(proj), ctx=_CONTEXT)

    out = list_blueprints(limit=2, path=str(proj), ctx=_CONTEXT)
    assert out.fields["total"] == 3
    assert out.fields["returned"] == 2
    assert out.fields["next_offset"] == 2
    out2 = list_blueprints(limit=2, offset=2, path=str(proj), ctx=_CONTEXT)
    assert out2.fields["returned"] == 1
    assert out2.fields["next_offset"] is None
