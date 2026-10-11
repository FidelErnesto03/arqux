"""BLP-006: `cycle.reopen` reverses a close.

`cycle.close` was terminal; a premature close could only be undone out of
band. The sanctioned reversal reopens a closed cycle, clears `closed_at`, and
refuses to reopen a cycle that is not closed.
"""

from __future__ import annotations

from pathlib import Path

from arqux.handlers.cycle import (
    _read_cycle_manifest,
    close_cycle,
    create_cycle,
    reopen_cycle,
    synthesize_cycle,
)
from arqux.handlers.project import init_project
from arqux.handlers.workspace import init_workspace
from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test-governor", role="governor")

_SYNTH = (
    "$1:{scope: test}$2:{Inside: a, Outside: b}$3:{CYC-OBJ-1: obj}"
    "$4:{Directriz: d}$5:{No risks}$6:{CP-01: check}$7:{metric: m}"
    "$8:{No constraints}$9:{No decisions}"
)


def _project(tmp_path: Path) -> Path:
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()
    init_workspace(path=str(ws_root), ctx=_CONTEXT)
    init_project(name="test-proj", path=str(proj_root), ctx=_CONTEXT)
    return proj_root


def test_reopen_cycle_flips_closed_back_to_open(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    cycle_id = create_cycle(name="CYCLE-T", path=str(proj), ctx=_CONTEXT).fields["cycle_id"]
    synthesize_cycle(cycle_id=cycle_id, content=_SYNTH, path=str(proj), ctx=_CONTEXT)
    close_cycle(cycle_id, path=str(proj), ctx=_CONTEXT)

    cdir = proj / ".arqux" / "cycles" / cycle_id
    assert _read_cycle_manifest(cdir).get("status") == "closed"

    reopen_cycle(cycle_id, path=str(proj), ctx=_CONTEXT)

    fm = _read_cycle_manifest(cdir)
    # reconcile_cycle derives the manifest status ("active"/"draft"); the
    # invariant that matters is that the cycle is no longer closed.
    assert fm.get("status") != "closed"
    assert fm.get("closed_at") is None


def test_reopen_cycle_refuses_a_non_closed_cycle(tmp_path: Path) -> None:
    proj = _project(tmp_path)
    cycle_id = create_cycle(name="CYCLE-T2", path=str(proj), ctx=_CONTEXT).fields["cycle_id"]

    out = reopen_cycle(cycle_id, path=str(proj), ctx=_CONTEXT)

    assert out.fields.get("code") == "INVALID_STATE", f"unexpected: {out}"
