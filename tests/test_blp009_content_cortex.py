"""Tests for BLP-009: content CORTEX en handlers existentes.

Validates that ``task.create``, ``skill.import``, and ``skill.edit``
accept a ``content`` CORTEX entry string and extract fields from it,
while remaining retrocompatible with callers that don't use ``content``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.handlers.task import create_task
from arqux.handlers.skill import import_skill, edit_skill, convert_skill
from arqux.handlers.cycle import create_cycle, mature_cycle
from arqux.handlers.project import init_project
from arqux.handlers.workspace import init_workspace
from arqux.permissions import PermissionContext


_CONTEXT = PermissionContext(agent_id="test-governor", role="governor")


def _bootstrap_env(tmp_path: Path) -> Path:
    """Create a fully-initialised ArqUX workspace+project+cycle. Returns project root."""
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()
    init_workspace(path=str(ws_root), ctx=_CONTEXT)
    init_project(name="test-proj", path=str(proj_root), ctx=_CONTEXT)
    result = create_cycle(name="CYCLE-TEST", path=str(proj_root), ctx=_CONTEXT)
    cycle_id = result.fields["cycle_id"]
    mature_cycle(cycle_id=cycle_id, path=str(proj_root), ctx=_CONTEXT)
    return proj_root


# ---------------------------------------------------------------------------
# task.create with content (BLP-009)
# ---------------------------------------------------------------------------


def test_task_create_with_content_overrides_params(tmp_path: Path) -> None:
    """When content is provided, parsed values override individual params."""
    proj_root = _bootstrap_env(tmp_path)

    result = create_task(
        obj="dummy obj",  # will be overridden by content
        content='$1:{obj:"From content", priority:"high", assignee:"executor-1"}',
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    task_id = result.fields.get("task_id")
    assert task_id is not None

    # Read the task back to verify the override worked.
    from arqux.handlers.task import read_task
    read_result = read_task(task_id=task_id, path=str(proj_root), ctx=_CONTEXT)
    assert read_result.profile == "OUT-WORK"
    # The OBJ section should contain "From content".
    content_field = read_result.fields.get("content", "")
    assert "From content" in content_field


def test_task_create_with_content_lists(tmp_path: Path) -> None:
    """Lists in content are parsed as Python lists."""
    proj_root = _bootstrap_env(tmp_path)

    result = create_task(
        obj="Test obj",
        content='$1:{pre:["precondition 1","precondition 2"], ac:["ac 1","ac 2"]}',
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    task_id = result.fields.get("task_id")

    from arqux.handlers.task import read_task
    read_result = read_task(task_id=task_id, path=str(proj_root), ctx=_CONTEXT)
    content_field = read_result.fields.get("content", "")
    assert "precondition 1" in content_field
    assert "ac 1" in content_field


def test_task_create_retrocompatible_without_content(tmp_path: Path) -> None:
    """Without content, individual params work as before."""
    proj_root = _bootstrap_env(tmp_path)

    result = create_task(
        obj="Retro task",
        pre=["pre 1"],
        proc=["step 1", "step 2"],
        ac=["ac 1"],
        priority="high",
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)


def test_task_create_invalid_content_does_not_crash(tmp_path: Path) -> None:
    """Invalid content falls back to individual params."""
    proj_root = _bootstrap_env(tmp_path)

    result = create_task(
        obj="Fallback task",
        content="not valid cortex content at all",
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)


# ---------------------------------------------------------------------------
# skill.import with content (BLP-009)
# ---------------------------------------------------------------------------


def test_skill_import_with_content_cortex_form(tmp_path: Path) -> None:
    """skill.import accepts content as CORTEX with source, name, body keys."""
    proj_root = _bootstrap_env(tmp_path)
    # Use the workspace .arqux/ for skill storage.
    ws_arqux = proj_root.parent / ".arqux"

    result = import_skill(
        source="dummy-source",
        name="dummy-name",
        content='$1:{source:"real-source", name:"real-skill", body:"This is the skill body content."}',
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("name") == "real-skill"
    assert result.fields.get("source") == "real-source"

    # Verify the file was written with the body content.
    storage = Path(result.fields["storage"])
    assert storage.exists()
    written = storage.read_text(encoding="utf-8")
    assert "This is the skill body content." in written


def test_skill_import_retrocompatible_with_raw_content(tmp_path: Path) -> None:
    """Without CORTEX form, content is treated as raw text."""
    proj_root = _bootstrap_env(tmp_path)

    raw = "# My Skill\n\nThis is raw markdown content for the skill.\n"
    result = import_skill(
        source="manual",
        name="raw-skill",
        content=raw,
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    storage = Path(result.fields["storage"])
    written = storage.read_text(encoding="utf-8")
    assert written == raw


# ---------------------------------------------------------------------------
# skill.edit with content (BLP-009)
# ---------------------------------------------------------------------------


def test_skill_edit_with_content_cortex_form(tmp_path: Path) -> None:
    """skill.edit accepts content as CORTEX with name, body, section keys."""
    proj_root = _bootstrap_env(tmp_path)

    # First, import a skill so we have something to edit.
    import_skill(
        source="manual",
        name="edit-target",
        content="# Initial skill content\n",
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    # Convert it so it lands in skills/ (not just originals/).
    convert_skill(name="edit-target", path=str(proj_root.parent), ctx=_CONTEXT)

    # Now edit using CORTEX content form.
    result = edit_skill(
        name="edit-target",
        content='$1:{name:"edit-target", body:"# Replaced content via CORTEX"}',
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("status") == "written"


def test_skill_edit_retrocompatible_with_raw_content(tmp_path: Path) -> None:
    """Without CORTEX form, content is treated as raw text."""
    proj_root = _bootstrap_env(tmp_path)

    # Import + convert.
    import_skill(
        source="manual",
        name="retro-edit",
        content="# Initial\n",
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    convert_skill(name="retro-edit", path=str(proj_root.parent), ctx=_CONTEXT)

    # Edit with raw text (no CORTEX).
    raw = "# Completely new content\n"
    result = edit_skill(
        name="retro-edit",
        content=raw,
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("status") == "written"
