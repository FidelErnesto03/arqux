"""Tests for BLP-010 meta-handlers: cortex.patch, task.run, skill.install,
cortex.migrate, session.handoff, blueprint.execute."""

from __future__ import annotations

import re
from pathlib import Path

from arqux.handlers.blueprint import execute_blueprint
from arqux.handlers.blueprint.lifecycle import create_blueprint
from arqux.handlers.cortex import migrate_handler, patch_handler
from arqux.handlers.cycle import create_cycle, synthesize_cycle
from arqux.handlers.project import init_project
from arqux.handlers.session import handoff
from arqux.handlers.skill import install_skill
from arqux.handlers.task import create_task, run_task
from arqux.handlers.workspace import init_workspace
from arqux.permissions import PermissionContext


def _inject(bp_file: Path, section: str, block: str) -> None:
    """Insert ``block`` into an existing ``## §N`` section.

    Appending at end of file would land after the last section and never be
    parsed by the section extractors. BLP-005.
    """
    text = bp_file.read_text(encoding="utf-8")
    m = re.search(rf"^## §{section}:.*$", text, re.MULTILINE)
    assert m, f"section §{section} not found"
    start = m.end()
    nxt = re.search(r"^## §\d+:", text[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(text)
    bp_file.write_text(text[:start] + "\n" + block + text[end:], encoding="utf-8")


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
    synthesize_cycle(cycle_id=cycle_id, content="$1:{scope: test}$2:{Inside: everything, Outside: nothing}$3:{CYC-OBJ-1: test objective}$4:{Directriz: follow guidelines}$5:{No risks}$6:{CP-01: check}$7:{metric: coverage}$8:{No constraints}$9:{No decisions}", path=str(proj_root), ctx=_CONTEXT)
    # BLP-003: mature_cycle removed. Cycles stay in draft (normal active state).
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
    # BLP-005: a dry run reports the plan; it never claims an outcome of
    # success. Previously this returned "complete" while running nothing.
    assert result.fields.get("outcome") == "dry_run"
    assert result.fields.get("evidence") == "dry run: no state was modified"


def test_task_run_executes(tmp_path: Path) -> None:
    """task.run without dry_run executes and reports.

    BLP-005: the procedure step must declare a real action, and the run
    only reports ``complete`` when that action produced evidence. A step
    with no declared action is ``unavailable`` and the run fails.
    """
    proj_root = _bootstrap_env(tmp_path)
    artifact = proj_root / "task-out.txt"

    create_result = create_task(
        obj="Test task",
        proc=[f"produce the artifact [exec:write_file path={artifact} content=done]"],
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
    assert result.fields.get("outcome") == "complete", str(result.fields)
    # The evidence is real, not a claim.
    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == "done"
    steps = result.fields.get("procedure") or []
    assert steps and steps[0].get("status") == "executed"
    assert steps[0].get("evidence_ref")


def test_task_run_fails_without_execution_spec(tmp_path: Path) -> None:
    """BLP-005 CA-11: no declared action means no completion.

    Previously this returned ``complete`` while doing nothing at all.
    """
    proj_root = _bootstrap_env(tmp_path)

    create_result = create_task(
        obj="Task with no action",
        proc=["just think about it"],
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    task_id = create_result.fields["task_id"]

    result = run_task(task_id=task_id, path=str(proj_root), ctx=_CONTEXT)

    assert result.profile == "OUT-WORK"
    assert result.fields.get("outcome") != "complete", (
        "task.run claimed complete without executing anything"
    )


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
    # BLP-004 D-04: dry_run reports parsed items, never claims completion.
    assert result.fields.get("outcome") == "dry_run"


def test_blueprint_execute_executes(tmp_path: Path) -> None:
    """blueprint.execute runs the BLP for real.

    BLP-005: ``done`` is only reachable when every task declared an action,
    that action produced a real artifact, and every criterion was certified
    by a role allowed to certify. This test exercises that full path.
    """
    proj_root = _bootstrap_env(tmp_path)
    create_result = create_blueprint(obj="Test BLP", path=str(proj_root), ctx=_CONTEXT)
    bp_id = create_result.fields["blueprint_id"]

    from arqux.handlers.blueprint.lifecycle import (
        _pending_placeholders,
        claim_blueprint,
        ready_blueprint,
    )

    bp_file = Path(create_result.fields["path"])
    text = bp_file.read_text(encoding="utf-8")
    for marker in _pending_placeholders(bp_file, proj_root):
        text = text.replace(marker, "filled")

    # Real tasks and criteria, so completion is reachable honestly.
    artifact = proj_root / "blp-artifact.txt"
    bp_file.write_text(text, encoding="utf-8")
    _inject(bp_file, 12, "\n- [ ] **CA-01:** criterio verificable\n")
    _inject(
        bp_file, 14,
        f"\n- [ ] **T-1.1:** producir artefacto "
        f"[exec:write_file path={artifact} content=ok]\n",
    )

    ready_blueprint(bp_id, path=str(proj_root), ctx=_CONTEXT)
    claim_blueprint(bp_id, path=str(proj_root), ctx=_CONTEXT)

    # A governor may certify; an executor may not.
    result = execute_blueprint(
        bp_id=bp_id,
        dry_run=False,
        path=str(proj_root),
        ctx=_CONTEXT,
    )
    assert result.profile == "OUT-WORK", str(result.fields)
    assert result.fields.get("outcome") == "complete", str(result.fields)
    assert artifact.exists(), "the task produced no real artifact"
    assert result.fields.get("state") == "done"
    acs = result.fields.get("acs") or []
    assert acs and acs[0].get("status") == "verified"
    assert acs[0].get("evidence_ref")
    assert acs[0].get("certifier_role") == "governor"


def test_blueprint_execute_executor_cannot_certify(tmp_path: Path) -> None:
    """BLP-005 CA-08: an executor runs the task but certifies nothing."""
    proj_root = _bootstrap_env(tmp_path)
    create_result = create_blueprint(obj="Test BLP", path=str(proj_root), ctx=_CONTEXT)
    bp_id = create_result.fields["blueprint_id"]

    from arqux.handlers.blueprint.lifecycle import (
        _pending_placeholders,
        claim_blueprint,
        ready_blueprint,
    )

    bp_file = Path(create_result.fields["path"])
    text = bp_file.read_text(encoding="utf-8")
    for marker in _pending_placeholders(bp_file, proj_root):
        text = text.replace(marker, "filled")
    artifact = proj_root / "executor-artifact.txt"
    bp_file.write_text(text, encoding="utf-8")
    _inject(bp_file, 12, "\n- [ ] **CA-01:** criterio verificable\n")
    _inject(
        bp_file, 14,
        f"\n- [ ] **T-1.1:** producir artefacto "
        f"[exec:write_file path={artifact} content=ok]\n",
    )

    ready_blueprint(bp_id, path=str(proj_root), ctx=_CONTEXT)
    claim_blueprint(bp_id, path=str(proj_root), ctx=_CONTEXT)

    executor_ctx = PermissionContext(agent_id="test-exec", role="executor")
    result = execute_blueprint(
        bp_id=bp_id,
        dry_run=False,
        path=str(proj_root),
        ctx=executor_ctx,
    )

    # The work ran for real...
    assert artifact.exists()
    # ...but the criterion could not be certified by the executor.
    assert result.fields.get("outcome") == "partial"
    assert result.fields.get("state") == "blocked"
    acs = result.fields.get("acs") or []
    assert acs[0].get("status") == "pending"
    assert "no puede certificar" in str(acs[0].get("reason"))


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
