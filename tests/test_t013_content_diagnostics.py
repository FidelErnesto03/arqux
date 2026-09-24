"""Regression tests for T-013 — canal-I content diagnostics.

Canal-I consumers (entry.add, task.create, skill.*) surface a
``content_ignored`` field listing parsed-but-unused content keys
(unknown keys, separator-fused leftovers), and empty scalar list
values no longer produce phantom task bullets.
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cortex import entry_add_handler
from arqux.handlers.skill import edit_skill, import_skill
from arqux.handlers.task import create_task, read_task
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test", role="governor")

_BRAIN = """$0

# -- $0: TEST GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson

$7: LESSONS

LNG:existing{type:"process", cause:"c", lesson:"l", prevention:"p"}
"""


def _proj_with_cycle(tmp_path: Path) -> Path:
    from arqux.handlers.cycle import create_cycle, synthesize_cycle
    from arqux.handlers.project import init_project
    from arqux.handlers.workspace import init_workspace

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


# ---------------------------------------------------------------------------
# (1) content_ignored / warnings
# ---------------------------------------------------------------------------


def test_task_create_reports_unknown_content_keys(tmp_path: Path) -> None:
    """A typo'd content key (objs:) is reported instead of silently dropped."""
    proj = _proj_with_cycle(tmp_path)
    out = create_task(
        obj="Test obj",
        content='$1:{obj:"Objective", objs:"typo key", pre:["pre 1"]}',
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields.get("content_ignored") == ["objs"]


def test_task_create_reports_fused_separator_leftovers(tmp_path: Path) -> None:
    """__-separated content fuses keys into obj — the loss is reported."""
    proj = _proj_with_cycle(tmp_path)
    out = create_task(
        content='$1:{obj:"Objective text"__pre:[pre 1]__ac:[ac 1]}',
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    ignored = out.fields.get("content_ignored", [])
    assert "pre (fused)" in ignored
    assert "ac (fused)" in ignored


def test_task_create_no_warning_when_all_keys_used(tmp_path: Path) -> None:
    proj = _proj_with_cycle(tmp_path)
    out = create_task(
        obj="Test obj",
        content='$1:{obj:"Objective", pre:["pre 1"], ac:["ac 1"]}',
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert "content_ignored" not in out.fields


def test_task_create_warns_when_content_does_not_parse(tmp_path: Path) -> None:
    proj = _proj_with_cycle(tmp_path)
    out = create_task(
        obj="Fallback obj",
        content="not valid cortex content at all",
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields.get("content_ignored") == ["<content did not parse>"]


def test_entry_add_reports_unparsed_content(tmp_path: Path) -> None:
    f = tmp_path / "brain.cortex"
    f.write_text(_BRAIN)
    out = entry_add_handler(
        str(f), "$7", "LNG", "warned",
        'type:"process", cause:"c", lesson:"l", prevention:"p"',
        content="not valid cortex content at all",
        force=True,
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields.get("content_ignored") == ["<content did not parse>"]


def test_entry_add_no_warning_when_content_parses(tmp_path: Path) -> None:
    f = tmp_path / "brain.cortex"
    f.write_text(_BRAIN)
    out = entry_add_handler(
        str(f), "$7", "LNG", "clean",
        content='LNG:clean{type:"process", cause:"c", lesson:"l", prevention:"p"}',
        force=True,
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert "content_ignored" not in out.fields


def test_skill_import_reports_unknown_content_keys(tmp_path: Path) -> None:
    """skill.import CORTEX form: unknown keys reported, body still written."""
    from arqux.handlers.workspace import init_workspace

    init_workspace(path=str(tmp_path), ctx=_CONTEXT)
    out = import_skill(
        source="dummy",
        name="warn-skill",
        content='$1:{source:"real-source", name:"warn-skill", body:"Skill body.", bogus:"x"}',
        path=str(tmp_path),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields.get("content_ignored") == ["bogus"]


def test_skill_edit_reports_unknown_content_keys(tmp_path: Path) -> None:
    """skill.edit CORTEX form: unknown keys reported, body still written."""
    from arqux.handlers.skill import convert_skill
    from arqux.handlers.workspace import init_workspace

    init_workspace(path=str(tmp_path), ctx=_CONTEXT)
    import_skill(
        source="manual",
        name="edit-warn",
        content="# Initial skill content\n",
        path=str(tmp_path),
        ctx=_CONTEXT,
    )
    convert_skill(name="edit-warn", path=str(tmp_path), ctx=_CONTEXT)
    out = edit_skill(
        name="edit-warn",
        content='$1:{name:"edit-warn", body:"# Replaced via CORTEX", bogus:"typo key"}',
        path=str(tmp_path),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    assert out.fields.get("content_ignored") == ["bogus"]


# ---------------------------------------------------------------------------
# (2) phantom bullets from empty scalar list values
# ---------------------------------------------------------------------------


def test_task_create_empty_scalar_list_no_phantom_bullet(tmp_path: Path) -> None:
    """pre:"" coerces to [] — no bare '- ' bullet in the task file."""
    proj = _proj_with_cycle(tmp_path)
    out = create_task(
        obj="Test obj",
        content='$1:{obj:"Empty lists", pre:"", ac:""}',
        path=str(proj),
        ctx=_CONTEXT,
    )
    assert out.profile == "OUT-WORK", str(out.fields)
    task_id = out.fields["task_id"]
    read_result = read_task(task_id=task_id, path=str(proj), ctx=_CONTEXT)
    content_field = read_result.fields.get("content", "")
    assert "\n- \n" not in content_field
    assert "- \n" not in content_field
