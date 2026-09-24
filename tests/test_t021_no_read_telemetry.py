"""Regression tests for T-021 — read handlers produce ZERO file writes.

Pre-T-021 every read-classified handler appended a generic
``kind="handler_call"`` AUD entry to brain.cortex on each call — a full
atomic rewrite of a ~300KB file per call plus persistent pulse
pollution.  T-021 removes that exhaustive telemetry: a read must not
touch the filesystem at all.

These tests snapshot the whole project tree (paths + content + mtimes),
invoke every read-classified handler through the REGISTRY dispatch path
(the same functions the MCP server calls), and assert the snapshot is
byte-for-byte identical afterwards.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from arqux.permissions import PermissionContext

_CONTEXT = PermissionContext(agent_id="test-governor", role="governor")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal workspace+project and return (ws_root, proj_root).

    ``session.close`` is called once during setup so the session read
    handlers have a real SES entry to read — all mutation happens BEFORE
    the snapshot.
    """
    from arqux.handlers.project import init_project
    from arqux.handlers.session import close as session_close
    from arqux.handlers.workspace import init_workspace

    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    proj_root = ws_root / "proj"
    proj_root.mkdir()

    init_workspace(path=str(ws_root), ctx=_CONTEXT)
    init_project(name="test-proj", path=str(proj_root), ctx=_CONTEXT)
    session_close(summary="bootstrap session for read tests", path=str(proj_root), ctx=_CONTEXT)
    return ws_root, proj_root


def _snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    """Map every file under *root* to (size, mtime_ns, sha1)."""
    snap: dict[str, tuple[int, int, str]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        data = p.read_bytes()
        snap[str(p.relative_to(root))] = (
            len(data),
            p.stat().st_mtime_ns,
            hashlib.sha1(data).hexdigest(),
        )
    return snap


def _read_calls(ws_root: Path, proj_root: Path) -> dict[str, dict]:
    """Kwargs for every read-classified handler (T-020 classification).

    Handlers that need a target that may not exist are called with a
    deliberately absent target — the NOT_FOUND path must stay write-free
    too.
    """
    brain = str(proj_root / ".arqux" / "brain.cortex")
    return {
        "blueprint.list": {"path": str(proj_root)},
        "blueprint.read": {"bp_id": "BLP-999", "path": str(proj_root)},
        "context.detect": {"path": str(proj_root)},
        "context.full": {"path": str(proj_root)},
        "cortex.entry.get": {"path": brain, "selector": "$6/AUD:*"},
        "cortex.entry.list": {"path": brain},
        "cortex.format": {"path": brain, "target": "hcortex"},
        "cortex.learn": {"path": str(proj_root)},
        "cortex.read": {"path": brain},
        "cortex.ref": {"sigil": "WRK"},
        "cortex.render": {"path": brain},
        "cortex.render.diagram": {"source": "@startuml\nA -> B\n@enduml"},
        "cortex.render.validate_file": {"path": brain},
        "cortex.verify": {"path": brain},
        "cycle.current": {"path": str(proj_root)},
        "cycle.list": {"path": str(proj_root)},
        "evidence.list": {"path": str(proj_root)},
        "evidence.read": {"event_id": "E-9999", "path": str(proj_root)},
        "handler.list": {"tier": "NANO"},
        "identity.get": {"path": str(proj_root)},
        "project.lessons": {"path": str(proj_root)},
        "project.status": {"path": str(proj_root)},
        "session.context.get": {"path": str(ws_root)},
        "session.resume": {"path": str(proj_root)},
        "session.status": {"path": str(proj_root)},
        "skill.list": {"path": str(proj_root)},
        "task.list": {"path": str(proj_root)},
        "task.read": {"task_id": "T-999", "path": str(proj_root)},
        "workspace.lessons": {"path": str(ws_root)},
        "workspace.status": {"path": str(ws_root)},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handler", sorted(_read_calls(Path("w"), Path("p")).keys()))
def test_read_handler_writes_nothing(tmp_path: Path, handler: str) -> None:
    """Each read-classified handler leaves the tree byte-for-byte identical.

    OUT-ERROR results are acceptable (missing task/blueprint/context) —
    the contract under test is ZERO file modification, not success.
    """
    from arqux.handlers import REGISTRY

    ws_root, proj_root = _bootstrap(tmp_path)
    before = _snapshot(ws_root)

    spec = REGISTRY[handler]
    kwargs = _read_calls(ws_root, proj_root)[handler]
    spec.fn(**kwargs, ctx=_CONTEXT)

    after = _snapshot(ws_root)
    assert before == after, (
        f"{handler} modified the filesystem: "
        f"{sorted(set(before) ^ set(after)) or [k for k in before if before[k] != after[k]]}"
    )


def test_repeat_read_calls_do_not_grow_brain(tmp_path: Path) -> None:
    """Repeated reads of the former telemetry emitters leave brain.cortex
    untouched — no per-call AUD entries, no atomic rewrites."""
    from arqux.blueprint.template import parse_blp_template
    from arqux.handlers import REGISTRY

    ws_root, proj_root = _bootstrap(tmp_path)
    brain = proj_root / ".arqux" / "brain.cortex"
    before_bytes = brain.read_bytes()
    before_mtime = brain.stat().st_mtime_ns

    calls = _read_calls(ws_root, proj_root)
    for _ in range(3):
        REGISTRY["context.detect"].fn(path=str(proj_root), ctx=_CONTEXT)
        REGISTRY["context.full"].fn(path=str(proj_root), ctx=_CONTEXT)
        REGISTRY["identity.get"].fn(path=str(proj_root), ctx=_CONTEXT)
        REGISTRY["cortex.format"].fn(**calls["cortex.format"], ctx=_CONTEXT)
        parse_blp_template(path=str(proj_root), ctx=_CONTEXT)

    assert brain.read_bytes() == before_bytes
    assert brain.stat().st_mtime_ns == before_mtime


def test_mutating_pulse_events_survive(tmp_path: Path) -> None:
    """Semantic pulse events on real mutations are governance evidence —
    session.close wrote a kind='session' SES entry during setup."""
    from arqux.pulse import read_pulse_from_brain

    _, proj_root = _bootstrap(tmp_path)
    events = read_pulse_from_brain(proj_root, limit=None)
    kinds = {e.get("kind") for e in events}
    assert "session" in kinds
    # The read calls themselves added nothing.
    assert "handler_call" not in kinds


def test_conditional_dry_run_writes_no_pulse(tmp_path: Path) -> None:
    """cortex.gc / cortex.patch / cortex.migrate in dry-run mode are reads
    in effect — they must not append pulse entries."""
    from arqux.handlers.cortex import gc_handler, migrate_handler, patch_handler
    from arqux.pulse import read_pulse_from_brain

    ws_root, proj_root = _bootstrap(tmp_path)
    brain = proj_root / ".arqux" / "brain.cortex"
    before = _snapshot(ws_root)

    # Dry-run invocations: preview only, zero writes.
    gc_handler(str(brain), dry_run=True, ctx=_CONTEXT)
    patch_handler(str(brain), content="$6/AUD:*{x:1}", dry_run=True, ctx=_CONTEXT)
    migrated = proj_root / ".arqux" / "_migrated_preview.cortex"
    migrate_handler(
        str(brain), str(migrated), "resigilar", dry_run=True, ctx=_CONTEXT
    )

    after = _snapshot(ws_root)
    assert before == after
    assert not migrated.exists()

    events = read_pulse_from_brain(proj_root, limit=None)
    assert not any(e.get("kind") in {"cortex_gc", "cortex_patch", "cortex_migrate"} for e in events)
