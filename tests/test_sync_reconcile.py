"""Regression tests for meta-brain sync and reconcile (BLP-008 / BUG-003).

BUG-003 (workspace issue): ``sync.run``/``reconcile`` hardcoded the selector
``$2/DOM:arqux``, so project metrics were written onto the workspace
self-DOM and the project's own ``DOM:<name>`` went stale. Reconcile also
aborted when the project brain had no ``OBJ`` entry in §3.
"""

from __future__ import annotations

from pathlib import Path

from arqux.constants import ARQUX_DIR
from arqux.handlers import project, workspace
from arqux.state import crud_read, crud_update
from arqux.sync import reconcile_brain, sync_brain


def _ws_and_project(workspace_root: Path, governor_ctx, name: str = "mi_proyecto") -> Path:
    """Workspace + project wired through the real handlers."""
    workspace.init_workspace(path=str(workspace_root), ctx=governor_ctx)
    proj = workspace_root / name
    proj.mkdir()
    project.init_project(name=name, path=str(proj), ctx=governor_ctx)
    return proj


def _meta_brain(workspace_root: Path) -> Path:
    return workspace_root / ARQUX_DIR / "meta-brain.cortex"


def test_sync_updates_project_dom_not_workspace_self(workspace_root: Path, governor_ctx) -> None:
    """``sync_brain`` with metrics must update ``DOM:<project>`` — not the
    hardcoded workspace self-entry ``DOM:arqux``."""
    proj = _ws_and_project(workspace_root, governor_ctx)
    meta = _meta_brain(workspace_root)

    sync_brain(proj, "test.sync", metrics={"tasks_done": 3})

    dom = crud_read(meta, "$2/DOM:mi_proyecto")
    assert dom["entries"], "DOM:mi_proyecto missing in meta-brain"
    attrs = dom["entries"][0]["value"]
    assert attrs.get("last_event") == "test.sync"
    assert attrs.get("tasks_done") == "3"

    # The workspace self-DOM must not absorb project metrics.
    self_dom = crud_read(meta, "$2/DOM:arqux")
    for e in self_dom["entries"]:
        assert e["value"].get("last_event") != "test.sync", (
            "project metrics leaked into workspace self-DOM"
        )


def test_sync_creates_dom_entry_when_missing(workspace_root: Path, governor_ctx) -> None:
    """If the meta-brain lacks ``DOM:<project>``, sync creates it instead of
    silently failing."""
    proj = _ws_and_project(workspace_root, governor_ctx)
    meta = _meta_brain(workspace_root)

    # Sanity: template meta-brain has no DOM:mi_proyecto yet.
    assert not crud_read(meta, "$2/DOM:mi_proyecto")["entries"]

    sync_brain(proj, "test.create", metrics={"tasks_done": 0})

    dom = crud_read(meta, "$2/DOM:mi_proyecto")
    assert dom["entries"], "sync must create DOM:mi_proyecto when absent"


def test_reconcile_tolerates_brain_without_obj(workspace_root: Path, governor_ctx) -> None:
    """``reconcile_brain`` must not abort when the brain §3 has no OBJ entry:
    it records the gap in ``errors[]`` and still syncs the meta-brain DOM."""
    proj = _ws_and_project(workspace_root, governor_ctx)
    brain = proj / ARQUX_DIR / "brain.cortex"

    # Strip the seeded OBJ entry so §3 has no OBJ at all.
    text = brain.read_text(encoding="utf-8")
    text = text.replace(
        'OBJ:onboard{name:"onboarding", goal:"Complete project onboarding: populate brain sections, open first cycle", status:"current", success:"brain valid and first cycle open", survive:"work"}',
        "",
    )
    brain.write_text(text, encoding="utf-8")
    assert not crud_read(brain, "$3/OBJ:*")["entries"]

    result = reconcile_brain(proj)

    assert any("OBJ" in e for e in result["errors"]), (
        f"missing-OBJ gap not documented: {result['errors']}"
    )
    assert result.get("meta_synced") is True
    dom = crud_read(_meta_brain(workspace_root), "$2/DOM:mi_proyecto")
    assert dom["entries"], "DOM:mi_proyecto must be synced even without OBJ"
    assert dom["entries"][0]["value"].get("last_event") == "brain.reconcile"


def test_reconcile_updates_existing_obj_entry(workspace_root: Path, governor_ctx) -> None:
    """With a seeded ``OBJ:onboard`` (no literal ``OBJ:_``), reconcile resolves
    the first OBJ and updates it."""
    proj = _ws_and_project(workspace_root, governor_ctx)
    brain = proj / ARQUX_DIR / "brain.cortex"

    result = reconcile_brain(proj)

    assert result["reconciled"] is True, str(result["errors"])
    obj = crud_read(brain, "$3/OBJ:onboard")
    assert obj["entries"], "OBJ:onboard missing"
    assert obj["entries"][0]["value"].get("event") == "brain.reconcile"


def test_reconcile_after_project_restart(workspace_root: Path, governor_ctx) -> None:
    """Restart scenario: cycles wiped + fresh empty CYCLE-01 → DOM reflects
    ``open_cycles=1`` and ``blueprints_done=0``."""
    import shutil

    proj = _ws_and_project(workspace_root, governor_ctx)
    cycles = proj / ARQUX_DIR / "cycles"
    shutil.rmtree(cycles)
    (cycles / "CYCLE-01").mkdir(parents=True)

    result = reconcile_brain(proj)

    dom = crud_read(_meta_brain(workspace_root), "$2/DOM:mi_proyecto")
    assert dom["entries"], "DOM:mi_proyecto missing after reconcile"
    attrs = dom["entries"][0]["value"]
    assert attrs.get("open_cycles") == "1", str(attrs)
    assert attrs.get("blueprints_done") == "0", str(attrs)
    assert result["metrics"]["open_cycles"] == 1


# ---------------------------------------------------------------------------
# T-010: reconcile_brain must not overwrite the meta-brain FCS what
# ---------------------------------------------------------------------------


def test_reconcile_workspace_preserves_meta_fcs(workspace_root: Path, governor_ctx) -> None:
    """Workspace-context reconcile refreshes the timestamp but keeps the
    existing meta-brain FCS:current what (focus_create_only semantics)."""
    _ws_and_project(workspace_root, governor_ctx)
    meta = _meta_brain(workspace_root)

    result = reconcile_brain(workspace_root)

    assert result["reconciled"] is True, str(result["errors"])
    fcs = crud_read(meta, "$3/FCS:current")
    assert fcs["entries"], "FCS:current missing in meta-brain"
    val = fcs["entries"][0]["value"]
    assert val["what"] == "Workspace initialized"
    assert val["event"] == "brain.reconcile"


def test_reconcile_workspace_creates_fcs_when_absent(workspace_root: Path, governor_ctx) -> None:
    """Workspace-context reconcile writes the generic FCS only when absent."""
    _ws_and_project(workspace_root, governor_ctx)
    meta = _meta_brain(workspace_root)

    text = meta.read_text(encoding="utf-8")
    text = text.replace(
        'FCS:current{name:"current", what:"Workspace initialized", priority:"medium", status:"current", survive:"work", updated:"<timestamp>"}',
        "",
    )
    meta.write_text(text, encoding="utf-8")
    assert not crud_read(meta, "$3/FCS:current")["entries"]

    result = reconcile_brain(workspace_root)

    assert result["reconciled"] is True, str(result["errors"])
    fcs = crud_read(meta, "$3/FCS:current")
    assert fcs["entries"], "reconcile must create FCS:current when absent"
    assert "Reconciliacion completada" in fcs["entries"][0]["value"].get("what", "")


# ---------------------------------------------------------------------------
# T-015: reconcile_brain must not overwrite the project brain OBJ goal
# ---------------------------------------------------------------------------


def test_reconcile_project_preserves_obj_goal(workspace_root: Path, governor_ctx) -> None:
    """Project-context reconcile refreshes success/updated/event but keeps
    the operator-authored OBJ goal."""
    proj = _ws_and_project(workspace_root, governor_ctx)
    brain = proj / ARQUX_DIR / "brain.cortex"

    crud_update(
        str(brain),
        "$3/OBJ:onboard",
        set_={"goal": "Operator-authored objective: keep me"},
        force=True,
    )

    result = reconcile_brain(proj)

    assert result["reconciled"] is True, str(result["errors"])
    obj = crud_read(brain, "$3/OBJ:onboard")
    assert obj["entries"], "OBJ:onboard missing"
    val = obj["entries"][0]["value"]
    assert val["goal"] == "Operator-authored objective: keep me"
    assert "Mantener sincronia" not in val["goal"]
    assert val["event"] == "brain.reconcile"
    assert val["success"] == "synced"
    assert val.get("updated"), "reconcile must refresh updated"


def test_reconcile_project_creates_obj_when_absent(workspace_root: Path, governor_ctx) -> None:
    """Project-context reconcile writes the generic OBJ goal only when §3
    has no OBJ entry at all."""
    proj = _ws_and_project(workspace_root, governor_ctx)
    brain = proj / ARQUX_DIR / "brain.cortex"

    text = brain.read_text(encoding="utf-8")
    text = text.replace(
        'OBJ:onboard{name:"onboarding", goal:"Complete project onboarding: populate brain sections, open first cycle", status:"current", success:"brain valid and first cycle open", survive:"work"}',
        "",
    )
    brain.write_text(text, encoding="utf-8")
    assert not crud_read(brain, "$3/OBJ:*")["entries"]

    result = reconcile_brain(proj)

    assert result["reconciled"] is True, str(result["errors"])
    objs = crud_read(brain, "$3/OBJ:*")["entries"]
    assert objs, "reconcile must create a generic OBJ when absent"
    assert "Mantener sincronia" in objs[0]["value"].get("goal", "")
