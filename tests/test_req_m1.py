"""REQ M1 regression tests (nicho.md): REQ-02 task.run bound-session gate,
REQ-03 cycle seal + ERR_HASH_MISMATCH, REQ-04 loss_count gate,
REQ-06 init --force guard.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from click.testing import CliRunner

from arqux.core.state._crud import cortex_verify, cortex_write
from arqux.execution import mint_execution_key
from arqux.handlers import cycle, project, workspace
from arqux.handlers.task import create_task, run_task
from arqux.permissions import PermissionContext
from arqux.session_identity import open_session


def _setup_project(workspace_root: Path, governor_ctx) -> Path:
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    project_dir = workspace_root / "my-app"
    project_dir.mkdir()
    project.init_project(name="my-app", path=str(project_dir))
    return project_dir


def _fill_manifest_placeholders(manifest_path: Path) -> None:
    text = manifest_path.read_text(encoding="utf-8")
    text = re.sub(
        r"(?<!\w)_([\w¿¡][\w\s\-/.,;:¿?!¡()]*?)_(?!\w)",
        "filled",
        text,
    )
    manifest_path.write_text(text, encoding="utf-8")


def _close_cycle(project_dir: Path) -> Path:
    """Create + close CYCLE-01; returns the cycle directory."""
    import os

    cwd = os.getcwd()
    try:
        os.chdir(project_dir)
        cycle.create_cycle(name="A")
        manifest = project_dir / ".arqux" / "cycles" / "CYCLE-01" / "MANIFEST.md"
        if manifest.exists():
            _fill_manifest_placeholders(manifest)
        result = cycle.close_cycle(cycle_id="CYCLE-01", summary="done")
        assert "status=closed" in result.to_text()
    finally:
        os.chdir(cwd)
    return project_dir / ".arqux" / "cycles" / "CYCLE-01"


# ---------------------------------------------------------------------------
# REQ-03 — seal.cortex on cycle close + ERR_HASH_MISMATCH on tamper


def test_close_cycle_writes_seal(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cdir = _close_cycle(project_dir)

    seal = cdir / "seal.cortex"
    assert seal.exists()
    text = seal.read_text(encoding="utf-8")
    assert "SEL:seal{" in text
    assert "HSH:" in text

    # Every sealed artifact hash matches the file on disk.
    for m in re.finditer(r'HSH:\w+\{file:"([^"]+)", sha256:"([0-9a-f]{64})"\}', text):
        rel, digest = m.groups()
        assert not rel.endswith("seal.cortex")
        actual = hashlib.sha256((cdir / rel).read_bytes()).hexdigest()
        assert actual == digest

    # Manifest carries the root seal hash.
    manifest = (cdir / "MANIFEST.md").read_text(encoding="utf-8")
    assert "seal_sha256" in manifest

    # The seal itself verifies clean.
    report = cortex_verify(seal)
    assert report["valid"]
    assert not [d for d in report["diagnostics"] if "HASH_MISMATCH" in d]


def test_seal_reports_hash_mismatch(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cdir = _close_cycle(project_dir)

    tampered = cdir / "cycle.cortex"
    tampered.write_text(tampered.read_text(encoding="utf-8") + "# drift\n")

    report = cortex_verify(cdir / "seal.cortex")
    assert not report["valid"]
    assert any("ERR_HASH_MISMATCH" in d and "cycle.cortex" in d
               for d in report["diagnostics"])


def test_seal_reports_missing_artifact(workspace_root: Path, governor_ctx) -> None:
    project_dir = _setup_project(workspace_root, governor_ctx)
    cdir = _close_cycle(project_dir)

    (cdir / "cycle.cortex").unlink()
    report = cortex_verify(cdir / "seal.cortex")
    assert not report["valid"]
    assert any("ERR_HASH_MISMATCH" in d for d in report["diagnostics"])


# ---------------------------------------------------------------------------
# REQ-04 — loss_count in verify + write gate


def test_cortex_verify_reports_loss_count(tmp_path: Path) -> None:
    f = tmp_path / "doc.cortex"
    f.write_text(
        "$0\n\n$0:format{cortex:1.0, encoding:UTF-8}\n\n"
        'IDN:idn_contract{type:"attrs", weight:"H", focus:"name", '
        'fields:"name:text|status:text", desc:"Identity", open:true}\n\n'
        "$1: IDENTITY\n\nIDN:test{name:\"test\", status:\"current\"}\n",
        encoding="utf-8",
    )
    report = cortex_verify(f)
    assert report["valid"]
    assert report["loss_count"] == 0


def test_cortex_write_rejects_lossy_roundtrip(
    tmp_path: Path, governor_ctx, monkeypatch
) -> None:
    """A brain write with round-trip loss is rejected unless force=True."""
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()
    workspace.init_workspace(path=str(ws_root), ctx=governor_ctx)
    project.init_project(name="proj", path=str(proj_root), ctx=governor_ctx)
    brain = proj_root / ".arqux" / "brain.cortex"
    src = brain.read_text(encoding="utf-8")
    digest_before = brain.read_bytes()

    import arqux.core.state._crud as crud

    monkeypatch.setattr(crud, "_roundtrip_loss_count", lambda _t: 2)
    result = cortex_write(brain, src)
    assert "error" in result
    assert "E_LOSS" in str(result["diagnostics"])
    assert brain.read_bytes() == digest_before

    forced = cortex_write(brain, src, force=True)
    assert "error" not in forced


# ---------------------------------------------------------------------------
# REQ-06 — arqux init refuses a governed workspace without --force


def test_init_aborts_without_force(tmp_path: Path) -> None:
    from arqux.cli import main

    runner = CliRunner()
    assert runner.invoke(main, ["init", "--path", str(tmp_path)]).exit_code == 0

    second = runner.invoke(main, ["init", "--path", str(tmp_path)])
    assert second.exit_code != 0
    assert "--force" in second.output

    third = runner.invoke(main, ["init", "--path", str(tmp_path), "--force"])
    assert third.exit_code == 0


# ---------------------------------------------------------------------------
# REQ-02 — task.run requires a bound session once identity exists


def test_run_task_rejects_unbound_session(
    tmp_path: Path, governor_ctx
) -> None:
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()
    workspace.init_workspace(path=str(ws_root), ctx=governor_ctx)
    project.init_project(name="proj", path=str(proj_root), ctx=governor_ctx)
    cycle.create_cycle(name="C", path=str(proj_root), ctx=governor_ctx)

    # Session identity exists for another agent — nothing bound to this ctx.
    open_session(proj_root, agent="alice", project="proj",
                 execution=mint_execution_key())

    created = create_task(
        obj="T", proc=["do thing"],
        path=str(proj_root), ctx=governor_ctx,
    )
    tid = created.fields["task_id"]
    intruder = PermissionContext(agent_id="mallory", role="executor")
    result = run_task(task_id=tid, path=str(proj_root), ctx=intruder)
    assert result.profile == "OUT-ERROR"
    assert "UNBOUND" in str(result.fields) or "UNBOUND" in result.to_text()


def test_run_task_dry_run_ungated(tmp_path: Path, governor_ctx) -> None:
    """dry_run only reports the plan — no mutation, so no session gate."""
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()
    workspace.init_workspace(path=str(ws_root), ctx=governor_ctx)
    project.init_project(name="proj", path=str(proj_root), ctx=governor_ctx)
    cycle.create_cycle(name="C", path=str(proj_root), ctx=governor_ctx)
    open_session(proj_root, agent="alice", project="proj",
                 execution=mint_execution_key())

    created = create_task(
        obj="T", proc=["do thing"],
        path=str(proj_root), ctx=governor_ctx,
    )
    tid = created.fields["task_id"]
    intruder = PermissionContext(agent_id="mallory", role="executor")
    result = run_task(task_id=tid, path=str(proj_root), ctx=intruder, dry_run=True)
    assert result.profile != "OUT-ERROR" or "UNBOUND" not in result.to_text()
