"""BLP-022 — write-integrity pre-write gate.

Phase 1 exercises the single reusable gate in ``arqux.timelog_capture`` in
isolation: ``require_bound_session`` (invariante A),
``require_writable_destination`` (invariante B) and ``require_open_cycle``
(invariante C). Each has a negative path (typed rejection, no mutation) and a
positive path. Later phases add the end-to-end, hash-identical guarantees.
"""

from __future__ import annotations

import re
from pathlib import Path

from arqux import timelog_capture as tc
from arqux.execution import (
    authoritative_execution_key,
    bind_execution_key,
    reset_execution_key,
)
from arqux.session_identity import close_session, open_session

# --- Fixtures/text ----------------------------------------------------------

# A Level-1 (BEHAVIORAL) identity contract: declares level 1 in $0.1 and must
# admit no live-state sigil (E023).
LEVEL1_IDENTITY = (
    "$0\n\n"
    "# ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata\n\n"
    "$0.1: ARQUX METADATA\n\n"
    'ARQX:artifact{level:1, name:"alfred", usage:"identity", kind:"native"}\n\n'
    "$1: IDENTITY\n\n"
    'IDN:alfred{name:"Alfred", status:"current"}\n\n'
    "$2: AXIOMS\n\n"
    'AXM:architect_first{name:"architect_first", body:"x", status:"current"}\n'
)

# A Level-3 (BRAIN) artifact: the legitimate home of live-state entries.
LEVEL3_BRAIN = (
    "$0\n\n"
    "# ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata\n\n"
    "$0.1: ARQUX METADATA\n\n"
    'ARQX:artifact{level:3, name:"brain", usage:"state", kind:"native"}\n'
)


def _arqux_dir(arqux_env) -> Path:
    """The project's ``.arqux/`` directory — what handlers pass as root."""
    return arqux_env.proj_root / ".arqux"


def _open_bound_session(arqux_env) -> str:
    session = open_session(
        _arqux_dir(arqux_env),
        agent="test-governor",
        project="test-proj",
        execution=authoritative_execution_key(),
        scope=arqux_env.cycle_id,
    )
    return session["session_id"]


def _open_foreign_session(arqux_env) -> str:
    """A session bound to *another* execution — this one is not the owner."""
    session = open_session(
        _arqux_dir(arqux_env),
        agent="someone-else",
        project="test-proj",
        execution="exec-foreign-key",
    )
    return session["session_id"]


# --- Invariante A — sesión vinculada ---------------------------------------


def test_session_unbound_rejects_with_remediation(arqux_env):
    """With session identity present and none bound, the gate rejects with a
    typed, actionable code."""
    _open_foreign_session(arqux_env)
    token = bind_execution_key(None)
    try:
        rejection = tc.require_bound_session(
            _arqux_dir(arqux_env), None, action="task.claim"
        )
    finally:
        reset_execution_key(token)

    assert rejection is not None
    assert rejection["code"] == "SESSION_UNBOUND"
    # The exact remediation command is present (T-1.2 / R-04).
    assert "session.context_set(project, scope)" in rejection["message"]
    assert rejection["remediation"] == tc.SESSION_BIND_REMEDIATION


def test_session_unbound_does_not_mutate_state(arqux_env):
    """A rejection is read-only: the brain is byte-identical afterwards."""
    _open_foreign_session(arqux_env)
    brain = _arqux_dir(arqux_env) / "brain.cortex"
    before = brain.read_bytes()

    token = bind_execution_key(None)
    try:
        tc.require_bound_session(_arqux_dir(arqux_env), None, action="task.claim")
    finally:
        reset_execution_key(token)

    assert brain.read_bytes() == before


def test_session_bound_and_open_accepted(arqux_env):
    """With an open session bound to this execution the gate is satisfied."""
    _open_bound_session(arqux_env)
    assert tc.require_bound_session(
        _arqux_dir(arqux_env), None, action="task.claim"
    ) is None


def test_session_bound_but_closed_rejects(arqux_env):
    """A closed session is not a valid precondition for a new write."""
    sid = _open_bound_session(arqux_env)
    close_session(_arqux_dir(arqux_env), sid, agent="test-governor", summary="done")

    rejection = tc.require_bound_session(
        _arqux_dir(arqux_env), None, action="task.claim"
    )
    assert rejection is not None
    assert rejection["code"] == "SESSION_UNBOUND"


# --- Invariante B — destino admite la entrada ------------------------------


def test_identity_destination_rejects_live_state_sigil(tmp_path):
    """A Level-1 identity contract cannot hold LNG/FCS/OBJ/SES/WRK (E023)."""
    identity = tmp_path / "alfred.cortex"
    identity.write_text(LEVEL1_IDENTITY, encoding="utf-8")

    rejection = tc.require_writable_destination(
        identity, "LNG", action="identity.record"
    )
    assert rejection is not None
    assert rejection["code"] == "DESTINATION_NOT_ALLOWED"


def test_brain_destination_allows_live_state_sigil(tmp_path):
    """A Level-3 brain is the rightful home of a live-state entry."""
    brain = tmp_path / "brain.cortex"
    brain.write_text(LEVEL3_BRAIN, encoding="utf-8")

    assert tc.require_writable_destination(
        brain, "LNG", action="identity.record"
    ) is None


def test_identity_destination_allows_axiom(tmp_path):
    """A Level-1 contract *does* admit its own contract sigils (AXM/LIM)."""
    identity = tmp_path / "alfred.cortex"
    identity.write_text(LEVEL1_IDENTITY, encoding="utf-8")

    assert tc.require_writable_destination(
        identity, "AXM", action="identity.record"
    ) is None


def test_undeclared_level_is_not_judged(tmp_path):
    """No declared level → the gate declines to judge (never invents one)."""
    artifact = tmp_path / "unknown.cortex"
    artifact.write_text("$0\n\n(nothing declared)\n", encoding="utf-8")

    assert tc.require_writable_destination(
        artifact, "LNG", action="identity.record"
    ) is None


# --- Invariante C — ciclo abierto ------------------------------------------


def _write_manifest(root: Path, cycle: str, status: str) -> None:
    cycle_dir = root / "cycles" / cycle
    cycle_dir.mkdir(parents=True, exist_ok=True)
    (cycle_dir / "MANIFEST.md").write_text(
        f'---\ncycle: "{cycle}"\nstatus: {status}\n---\n\n# {cycle}\n',
        encoding="utf-8",
    )


def test_cycle_closed_rejects(tmp_path):
    """A closed cycle cannot receive new governance state."""
    _write_manifest(tmp_path, "CYCLE-14", "closed")

    rejection = tc.require_open_cycle(
        tmp_path, "CYCLE-14", action="blueprint.synthesize"
    )
    assert rejection is not None
    assert rejection["code"] == "CYCLE_CLOSED"


def test_cycle_open_accepted(tmp_path):
    """An open cycle admits the write."""
    _write_manifest(tmp_path, "CYCLE-12", "current")

    assert tc.require_open_cycle(
        tmp_path, "CYCLE-12", action="blueprint.synthesize"
    ) is None


def test_missing_cycle_not_judged(tmp_path):
    """A cycle with no MANIFEST declares nothing to contradict."""
    assert tc.require_open_cycle(
        tmp_path, "CYCLE-99", action="blueprint.synthesize"
    ) is None


# --- T-1.2 — un solo mensaje, un solo comando ------------------------------


def test_unbound_warning_shares_remediation(arqux_env):
    """The legacy warning and the new gate surface the same command."""
    warning = tc.unbound_warning(
        {"status": "skipped", "reason": "no session bound to this execution"},
        action="task.claim",
    )
    assert warning is not None
    assert tc.SESSION_BIND_REMEDIATION in warning


# --- Fase 2 — invariante A en los writers ----------------------------------


def _task_file(arqux_env, task_id: str) -> Path:
    return next((_arqux_dir(arqux_env) / "cycles").glob(f"*/tasks/{task_id}.cortex"))


def test_unbound_writers_reject_when_session_identity_exists(arqux_env):
    """With session identity present but none bound, the writers refuse and
    leave the task untouched (invariante A / E-1805)."""
    from arqux.handlers.task import claim_task, complete_task, create_task

    _open_foreign_session(arqux_env)
    created = create_task(
        obj="probe", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx
    )
    tid = created.fields["task_id"]
    task_file = _task_file(arqux_env, tid)
    before = task_file.read_bytes()

    for writer in (claim_task, complete_task):
        result = writer(tid, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
        assert result.profile == "OUT-ERROR", result.to_text()
        assert result.fields["code"] == "SESSION_UNBOUND"
        assert "session.context_set(project, scope)" in result.message

    assert task_file.read_bytes() == before


def test_blueprint_writers_reject_before_mutating(arqux_env):
    """blueprint.claim/complete hit the gate before any transition is applied."""
    from arqux.handlers.blueprint.lifecycle import claim_blueprint
    from arqux.handlers.blueprint.review import complete_blueprint

    _open_foreign_session(arqux_env)
    for writer in (claim_blueprint, complete_blueprint):
        result = writer(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
        assert result.profile == "OUT-ERROR", result.to_text()
        assert result.fields["code"] == "SESSION_UNBOUND"


def test_legacy_project_without_sessions_allows_write(arqux_env):
    """Legacy carve-out (§7.4): no session identity → the write proceeds."""
    from arqux.handlers.task import claim_task, create_task

    created = create_task(
        obj="legacy probe", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx
    )
    tid = created.fields["task_id"]
    result = claim_task(tid, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert result.profile == "OUT-WORK", result.to_text()


def test_close_unbound_rejects(arqux_env):
    """session.close refuses to close a session not bound to this execution."""
    from arqux.handlers.session import close

    theirs = _open_foreign_session(arqux_env)
    result = close(summary="not mine", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert result.profile == "OUT-ERROR", result.to_text()
    assert result.fields["code"] == "SESSION_BINDING_REQUIRED"
    assert tc.get_session(_arqux_dir(arqux_env), theirs)["state"] == "open"


# --- Fase 3 — invariante B: destino de la lección --------------------------

# A Level-1 identity contract that declares its level and its glossary. It must
# survive identity.record untouched (E-1808).
LEVEL1_IDENTITY_WITH_GSIG = (
    "$0\n\n"
    "# ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata\n"
    'GSIG:IDN{name:"identity", type:"attrs", risk:"B", layer:"Semantic", description:"Agent identity descriptor"}\n'
    'GSIG:AXM{name:"axiom", type:"attrs", risk:"H", layer:"Prefrontal", description:"Non-negotiable principles"}\n'
    'GSIG:LIM{name:"limit", type:"attrs", risk:"M", layer:"Prefrontal", description:"Hard limits"}\n'
    'GSIG:DESC{name:"description", type:"attrs", risk:"B", layer:"Semantic", description:"Description"}\n\n'
    "$0.1: ARQUX METADATA\n\n"
    'ARQX:artifact{level:1, name:"alfred", usage:"identity", kind:"native"}\n\n'
    "$1: IDENTITY\n\n"
    'IDN:alfred{name:"Alfred", status:"current"}\n\n'
    "$2: AXIOMS\n\n"
    'AXM:architect_first{name:"architect_first", body:"x", status:"current"}\n'
)


def test_identity_destination_does_not_corrupt_a_level1_contract(tmp_path):
    """identity.record never writes live state into a Level-1 contract: the file
    stays byte-identical and keeps every GSIG (E-1808 / AC-05 / AC-06)."""
    from arqux.handlers.cortex.learning import record_lesson_handler_legacy

    ident = tmp_path / ".arqux" / "identities" / "alfred.cortex"
    ident.parent.mkdir(parents=True)
    ident.write_text(LEVEL1_IDENTITY_WITH_GSIG, encoding="utf-8")
    before = ident.read_text(encoding="utf-8")

    result = record_lesson_handler_legacy(
        lesson="Al escribir un artefacto...",
        kind="rule", cause="c", prevention="p",
        agent_id="alfred", path=str(tmp_path),
    )

    after = ident.read_text(encoding="utf-8")
    assert after == before, "the Level-1 contract was rewritten"
    assert len(re.findall(r"(?m)^GSIG:", after)) >= 4
    assert result.fields.get("destination") != "identity"


# --- Fase 4 — invariante C: ciclo de escritura -----------------------------


def _make_project(proj: Path) -> None:
    """A minimal project: ``.arqux/brain.cortex`` is what find_project_root needs."""
    arqux = proj / ".arqux"
    arqux.mkdir(exist_ok=True)
    (arqux / "brain.cortex").write_text(
        "$0\n\n$0.1: ARQUX METADATA\n\n"
        'ARQX:artifact{level:3, name:"brain", usage:"state", kind:"native"}\n\n'
        '$2: FOCUS\n\nFCS:current{what:"test", status:"current"}\n',
        encoding="utf-8",
    )


def _make_cycle(proj: Path, cycle: str, status: str) -> None:
    d = proj / ".arqux" / "cycles" / cycle
    d.mkdir(parents=True, exist_ok=True)
    (d / "MANIFEST.md").write_text(
        f'---\ncycle: "{cycle}"\nstatus: {status}\n---\n\n# {cycle}\n',
        encoding="utf-8",
    )


def _gov():
    from arqux.permissions import PermissionContext

    return PermissionContext(agent_id="test-governor", role="governor")


def test_synthesize_never_writes_to_a_closed_cycle(tmp_path):
    """An explicit cycle writes there and nowhere else (E-1816 / AC-07)."""
    from arqux.handlers.blueprint.synthesize import synthesize_blueprint

    _make_project(tmp_path)
    _make_cycle(tmp_path, "CYCLE-12", "current")
    _make_cycle(tmp_path, "CYCLE-14", "closed")

    result = synthesize_blueprint(
        "BLP-022", cycle="CYCLE-12", path=str(tmp_path), ctx=_gov()
    )
    assert result.profile == "OUT-WORK", result.to_text()
    base = tmp_path / ".arqux" / "cycles"
    assert (base / "CYCLE-12" / "blueprints" / "BLP-022.md").exists()
    assert not (base / "CYCLE-14" / "blueprints" / "BLP-022.md").exists()


def test_synthesize_refuses_a_closed_cycle_without_creating_a_file(tmp_path):
    """A closed cycle is refused before any file is created (AC-08)."""
    from arqux.handlers.blueprint.synthesize import synthesize_blueprint

    _make_project(tmp_path)
    _make_cycle(tmp_path, "CYCLE-14", "closed")

    result = synthesize_blueprint(
        "BLP-022", cycle="CYCLE-14", path=str(tmp_path), ctx=_gov()
    )
    assert result.profile == "OUT-ERROR", result.to_text()
    assert result.fields["code"] == "CYCLE_CLOSED"
    assert not (tmp_path / ".arqux" / "cycles" / "CYCLE-14" / "blueprints" / "BLP-022.md").exists()


# --- F6 — el rol efectivo sigue a la identidad activa -----------------------


def test_active_identity_role_follows_the_switch(arqux_env):
    """F6: tras cambiar a una identidad auditor, el rol efectivo es auditor y
    los handlers mutantes se rechazan aunque el default del transporte sea
    governor."""
    import pytest

    from arqux.handlers.identity.switch import switch
    from arqux.handlers.session import context_set
    from arqux.permissions import (
        PermissionContext,
        PermissionDenied,
        apply_active_identity_role,
        resolve_active_role,
    )

    # Un puntero de contexto debe existir; identity.switch lo actualiza, no lo crea.
    context_set(project="test-proj", scope=arqux_env.cycle_id,
                path=str(arqux_env.ws_root), ctx=arqux_env.gov_ctx)
    switch("heimdall", path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)

    # El puntero de contexto manda: la identidad activa es un auditor.
    assert resolve_active_role(path=str(arqux_env.ws_root)) == "auditor"

    # El default del transporte (governor) es sobrescrito por la identidad activa.
    ctx = PermissionContext(agent_id="heimdall", role="governor")
    apply_active_identity_role(ctx, handler="evidence.record", path=str(arqux_env.ws_root))
    assert ctx.role == "auditor"
    with pytest.raises(PermissionDenied):
        ctx.check("evidence.record")

    # El handler de control de rol sigue siendo invocable desde cualquier rol.
    control = PermissionContext(agent_id="heimdall", role="governor")
    apply_active_identity_role(control, handler="identity.switch", path=str(arqux_env.ws_root))
    assert control.role == "governor"
    control.check("identity.switch")  # no levanta


# --- F5 — el fallback de synthesize tampoco escribe en un ciclo cerrado ------


def test_synthesize_never_falls_back_into_a_closed_cycle(tmp_path):
    """F5: sin FCS y con el único ciclo cerrado, el fallback no debe escribir ahí."""
    from arqux.handlers.blueprint.synthesize import synthesize_blueprint

    _make_project(tmp_path)
    _make_cycle(tmp_path, "CYCLE-01", "closed")

    result = synthesize_blueprint("BLP-500", path=str(tmp_path), ctx=_gov())
    assert result.profile == "OUT-ERROR", result.to_text()
    assert result.fields["code"] == "CYCLE_CLOSED"
    assert not (tmp_path / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / "BLP-500.md").exists()


def test_synthesize_fallback_picks_the_open_cycle(tmp_path):
    """F5: el fallback elige el último ciclo ABIERTO, no el último por orden."""
    from arqux.handlers.blueprint.synthesize import synthesize_blueprint

    _make_project(tmp_path)
    _make_cycle(tmp_path, "CYCLE-01", "closed")
    _make_cycle(tmp_path, "CYCLE-02", "current")

    result = synthesize_blueprint("BLP-501", path=str(tmp_path), ctx=_gov())
    assert result.profile == "OUT-WORK", result.to_text()
    assert (tmp_path / ".arqux" / "cycles" / "CYCLE-02" / "blueprints" / "BLP-501.md").exists()
    assert not (tmp_path / ".arqux" / "cycles" / "CYCLE-01" / "blueprints" / "BLP-501.md").exists()


# --- F4 — no se reporta filed si la escritura al brain falla ----------------


def test_identity_record_rejects_when_no_destination_persists(tmp_path, monkeypatch):
    """F4: si la escritura al brain devuelve error, no se reporta filed; se
    rechaza con DESTINATION_NOT_ALLOWED en vez de un falso éxito."""
    from arqux.handlers.cortex import learning

    ident = tmp_path / ".arqux" / "identities" / "alfred.cortex"
    ident.parent.mkdir(parents=True)
    ident.write_text(LEVEL1_IDENTITY_WITH_GSIG, encoding="utf-8")
    (tmp_path / ".arqux" / "brain.cortex").write_text(LEVEL3_BRAIN, encoding="utf-8")

    monkeypatch.setattr(learning, "crud_add", lambda *a, **k: {"error": "boom"})

    result = learning.record_lesson_handler_legacy(
        lesson="destino fallido", kind="rule", cause="c", prevention="p",
        agent_id="alfred", path=str(tmp_path),
    )
    assert result.profile == "OUT-ERROR", result.to_text()
    assert result.fields["code"] == "DESTINATION_NOT_ALLOWED"


# --- T-037 — task.create tampoco escribe en un ciclo cerrado ----------------


def test_task_create_rejects_a_closed_cycle(tmp_path):
    """T-037: con solo un ciclo cerrado, task.create rechaza en vez de escribir."""
    from arqux.handlers.task import create_task

    _make_project(tmp_path)
    _make_cycle(tmp_path, "CYCLE-01", "closed")

    result = create_task(obj="x", path=str(tmp_path), ctx=_gov())
    assert result.profile == "OUT-ERROR", result.to_text()
    assert result.fields["code"] == "CYCLE_CLOSED"
    assert not (tmp_path / ".arqux" / "cycles" / "CYCLE-01" / "tasks").exists()


def test_task_create_prefers_the_open_cycle(tmp_path):
    """T-037: el fallback elige el ciclo abierto, nunca el cerrado."""
    from arqux.handlers.task import create_task

    _make_project(tmp_path)
    _make_cycle(tmp_path, "CYCLE-01", "closed")
    _make_cycle(tmp_path, "CYCLE-02", "current")

    result = create_task(obj="y", path=str(tmp_path), ctx=_gov())
    assert result.profile == "OUT-WORK", result.to_text()
    assert result.fields["cycle"] == "CYCLE-02"
    assert (tmp_path / ".arqux" / "cycles" / "CYCLE-02" / "tasks").exists()
    assert not (tmp_path / ".arqux" / "cycles" / "CYCLE-01" / "tasks").exists()






