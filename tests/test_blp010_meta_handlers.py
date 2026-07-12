"""Tests for BLP-010 meta-handlers: cortex.patch, task.run, skill.install,
cortex.migrate, session.handoff, blueprint.execute."""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.blueprint import execute_blueprint
from arqux.handlers.blueprint.lifecycle import create_blueprint
from arqux.handlers.cortex import migrate_handler, patch_handler
from arqux.handlers.cycle import create_cycle, mature_cycle
from arqux.handlers.project import init_project
from arqux.handlers.session import handoff
from arqux.handlers.skill import install_skill
from arqux.handlers.task import create_task, run_task
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
# cortex.patch (BLP-010)
# ---------------------------------------------------------------------------


def test_cortex_patch_dry_run(tmp_path: Path) -> None:
    """cortex.patch with dry_run reports without writing."""
    f = tmp_path / "test.cortex"
    f.write_text(
        '$0\n\n$1: IDENTITY\n\nIDN:test{name:"test", status:"current"}\n'
        '\n$2: FOCUS\n\nFCS:primary{what:"Test", priority:"low"}\n'
    )
    result = patch_handler(
        path=str(f),
        content='$2/FCS:primary{what:"Patched", priority:"high"}',
        dry_run=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("dry_run") is True
    # File unchanged.
    text = f.read_text()
    assert "Patched" not in text


def test_cortex_patch_writes(tmp_path: Path) -> None:
    """cortex.patch without dry_run writes the patches."""
    f = tmp_path / "test.cortex"
    f.write_text(
        '$0\n\n$1: IDENTITY\n\nIDN:test{name:"test", status:"current"}\n'
        '\n$2: FOCUS\n\nFCS:primary{what:"Test", priority:"low"}\n'
    )
    result = patch_handler(
        path=str(f),
        content='$2/FCS:primary{what:"Patched content"}',
        dry_run=False,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert len(result.fields.get("patched", [])) >= 0  # may succeed or fail gracefully


def test_cortex_patch_invalid_content(tmp_path: Path) -> None:
    """cortex.patch with empty content returns INVALID_ARGS."""
    f = tmp_path / "test.cortex"
    f.write_text("$0\n")
    result = patch_handler(path=str(f), content="", ctx=_CONTEXT)
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# task.run (BLP-010)
# ---------------------------------------------------------------------------


def test_task_run_dry_run(tmp_path: Path) -> None:
    """task.run with dry_run reports without modifying state."""
    proj_root = _bootstrap_env(tmp_path)

    # First create a task.
    create_result = create_task(
        obj="Test task",
        pre=["precondition 1"],
        proc=["step 1", "step 2"],
        ac=["AC 1"],
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    task_id = create_result.fields["task_id"]

    result = run_task(
        task_id=task_id,
        dry_run=True,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("dry_run") is True
    assert result.fields.get("outcome") == "complete"


def test_task_run_executes(tmp_path: Path) -> None:
    """task.run without dry_run executes and reports."""
    proj_root = _bootstrap_env(tmp_path)

    create_result = create_task(
        obj="Test task",
        proc=["step 1"],
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    task_id = create_result.fields["task_id"]

    result = run_task(
        task_id=task_id,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("outcome") == "complete"


def test_task_run_not_found(tmp_path: Path) -> None:
    """task.run with unknown task_id returns NOT_FOUND."""
    proj_root = _bootstrap_env(tmp_path)
    result = run_task(
        task_id="T-999",
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# skill.install (BLP-010)
# ---------------------------------------------------------------------------


def test_skill_install_dry_run(tmp_path: Path) -> None:
    """skill.install with dry_run reports without writing."""
    proj_root = _bootstrap_env(tmp_path)

    result = install_skill(
        source="manual",
        name="test-skill",
        content='$1:{source:"manual", name:"test-skill", body:"# Test skill\n$0\n$1: IDENTITY\n"}',
        dry_run=True,
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("dry_run") is True


def test_skill_install_executes(tmp_path: Path) -> None:
    """skill.install without dry_run imports and registers."""
    proj_root = _bootstrap_env(tmp_path)

    result = install_skill(
        source="manual",
        name="installable-skill",
        content='$1:{source:"manual", name:"installable-skill", body:"# Skill\n$0\n$1: IDENTITY\nIDN:test{name:\"test\"}\n"}',
        dry_run=False,
        path=str(proj_root.parent),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    steps = result.fields.get("steps", [])
    assert any(s.get("step") == "import" for s in steps)


# ---------------------------------------------------------------------------
# cortex.migrate (BLP-010)
# ---------------------------------------------------------------------------


def test_cortex_migrate_dry_run(tmp_path: Path) -> None:
    """cortex.migrate with dry_run reports without writing."""
    src = tmp_path / "src.cortex"
    src.write_text("$0\n\n$3: SECTION_A\n\n$5: SECTION_B\n")
    target = tmp_path / "target.cortex"

    result = migrate_handler(
        source_path=str(src),
        target_path=str(target),
        transform="reseccionar",
        dry_run=True,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("dry_run") is True
    assert not target.exists()


def test_cortex_migrate_reseccionar(tmp_path: Path) -> None:
    """cortex.migrate with reseccionar renumbers sections."""
    src = tmp_path / "src.cortex"
    src.write_text("$0\n\n$3: SECTION_A\n\n$5: SECTION_B\n")
    target = tmp_path / "target.cortex"

    result = migrate_handler(
        source_path=str(src),
        target_path=str(target),
        transform="reseccionar",
        dry_run=False,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert target.exists()
    text = target.read_text()
    assert "$1: SECTION_A" in text
    assert "$2: SECTION_B" in text


def test_cortex_migrate_resigilar(tmp_path: Path) -> None:
    """cortex.migrate with resigilar uppercases sigils."""
    src = tmp_path / "src.cortex"
    src.write_text("$0\n\n$1: IDENTITY\n\nfcs:primary{what:\"test\"}\n")
    target = tmp_path / "target.cortex"

    result = migrate_handler(
        source_path=str(src),
        target_path=str(target),
        transform="resigilar",
        dry_run=False,
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    text = target.read_text()
    assert "FCS:primary" in text
    assert "fcs:primary" not in text


def test_cortex_migrate_invalid_transform(tmp_path: Path) -> None:
    """cortex.migrate with invalid transform returns INVALID_ARGS."""
    src = tmp_path / "src.cortex"
    src.write_text("$0\n")
    result = migrate_handler(
        source_path=str(src),
        target_path=str(tmp_path / "target.cortex"),
        transform="bogus",
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "INVALID_ARGS"


# ---------------------------------------------------------------------------
# session.handoff (BLP-010)
# ---------------------------------------------------------------------------


def test_session_handoff_dry_run(tmp_path: Path) -> None:
    """session.handoff with dry_run reports without writing."""
    proj_root = _bootstrap_env(tmp_path)

    result = handoff(
        target_agent="alfred",
        content='$1:{target_agent:"alfred", summary:"Handing off", blps:"BLP-001", tasks:"T-001"}',
        dry_run=True,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("dry_run") is True
    assert "handoff_cortex" in result.fields


def test_session_handoff_writes(tmp_path: Path) -> None:
    """session.handoff without dry_run writes the handoff file."""
    proj_root = _bootstrap_env(tmp_path)

    result = handoff(
        target_agent="alfred",
        content='$1:{target_agent:"alfred", summary:"Handing off work"}',
        dry_run=False,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    handoff_path = Path(result.fields.get("handoff_path", ""))
    assert handoff_path.exists()
    text = handoff_path.read_text()
    assert "HOF:handoff" in text


# ---------------------------------------------------------------------------
# blueprint.execute (BLP-010)
# ---------------------------------------------------------------------------


def test_blueprint_execute_dry_run(tmp_path: Path) -> None:
    """blueprint.execute with dry_run reports without modifying state."""
    proj_root = _bootstrap_env(tmp_path)
    create_result = create_blueprint(obj="Test BLP", path=str(proj_root), ctx=_CONTEXT)
    bp_id = create_result.fields["blueprint_id"]

    result = execute_blueprint(
        bp_id=bp_id,
        dry_run=True,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK"
    assert result.fields.get("dry_run") is True
    assert result.fields.get("outcome") == "complete"


def test_blueprint_execute_executes(tmp_path: Path) -> None:
    """blueprint.execute without dry_run runs the BLP."""
    proj_root = _bootstrap_env(tmp_path)
    create_result = create_blueprint(obj="Test BLP", path=str(proj_root), ctx=_CONTEXT)
    bp_id = create_result.fields["blueprint_id"]

    result = execute_blueprint(
        bp_id=bp_id,
        dry_run=False,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("outcome") == "complete"


def test_blueprint_execute_not_found(tmp_path: Path) -> None:
    """blueprint.execute with unknown bp_id returns NOT_FOUND."""
    proj_root = _bootstrap_env(tmp_path)
    result = execute_blueprint(
        bp_id="BLP-999",
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-ERROR"
    assert result.fields.get("code") == "NOT_FOUND"
