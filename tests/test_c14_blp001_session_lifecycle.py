"""CYCLE-14 / BLP-001 — resume, close, membership and compaction.

Covers AC-02, AC-03, AC-05, AC-06 and AC-07.
"""

from __future__ import annotations

import re

import pytest

from arqux.execution import bind_execution_key, mint_execution_key, reset_execution_key
from arqux.permissions import PermissionContext
from arqux.pulse import (
    append_pulse_to_brain,
    compact_session_pulse,
    next_pulse_event_id,
    read_pulse_from_brain,
)
from arqux.session_identity import (
    current_session_ref,
    get_session,
    list_sessions,
    open_session,
)

from .test_c14_blp001_session_identity import _bind


@pytest.fixture
def bound(arqux_env):
    """Bind an execution and open its session; return (key, session_id, env)."""
    key = mint_execution_key()
    token = bind_execution_key(key)
    session = open_session(arqux_env.proj_root, agent="test-governor",
                           project="test-proj", execution=key, scope="CYCLE-TEST")
    arqux_env.key, arqux_env.token = key, token
    arqux_env.session_id = session["session_id"]
    yield arqux_env
    reset_execution_key(token)


def _ctx(key: str, agent: str = "test-governor") -> PermissionContext:
    return PermissionContext(agent_id=agent, role="governor", execution_key=key)


def _evidence(project_root, ses_ref: str | None, *, n: int, tag: str, agent="test-governor") -> None:
    for i in range(n):
        append_pulse_to_brain(
            project_root, event_id=next_pulse_event_id(project_root), task_id="T-1.1",
            kind="note", agent=agent, payload=f"{tag}-{i}", ses_ref=ses_ref,
        )


class TestAc05ReadsStayReadOnlyAndUnambiguous:
    def test_resume_does_not_write(self, bound):
        from arqux.handlers.session import resume

        before = list_sessions(bound.proj_root), read_pulse_from_brain(bound.proj_root, limit=None)
        result = resume(path=str(bound.proj_root), ctx=_ctx(bound.key))
        assert result.fields["session_ref"] == bound.session_id
        assert result.fields["state"] == "open"
        after = list_sessions(bound.proj_root), read_pulse_from_brain(bound.proj_root, limit=None)
        assert before == after

    def test_status_does_not_write(self, bound):
        from arqux.handlers.session import status

        before = read_pulse_from_brain(bound.proj_root, limit=None)
        result = status(path=str(bound.proj_root), ctx=_ctx(bound.key))
        assert result.fields["session_ref"] == bound.session_id
        assert read_pulse_from_brain(bound.proj_root, limit=None) == before

    def test_ambiguous_selection_is_rejected_with_alternatives(self, arqux_env):
        from arqux.handlers.session import resume
        from arqux.session_identity import SESSION_SECTION, SESSION_SIGIL, brain_path
        from arqux.state import crud_add

        a = open_session(arqux_env.proj_root, agent="test-governor",
                         project="test-proj", execution=mint_execution_key(),
                         scope="CYCLE-A")
        # Room model: a second open session cannot be opened, but legacy brains
        # still carry the residue this test protects against.
        value = {k: v for k, v in a.items() if k != "session_id"}
        crud_add(brain_path(arqux_env.proj_root), SESSION_SECTION, SESSION_SIGIL,
                 "SES002", value, create_section=True, force=True)
        b = {"session_id": "SES002"}
        result = resume(path=str(arqux_env.proj_root),
                        ctx=PermissionContext(agent_id="test-governor", role="governor",
                                              execution_key="exec-unbound"))
        assert result.fields["code"] == "SESSION_AMBIGUOUS"
        alternatives = " ".join(result.fields["alternatives"])
        assert a["session_id"] in alternatives and b["session_id"] in alternatives

    def test_explicit_reference_wins_over_a_newer_close(self, arqux_env):
        from arqux.handlers.session import resume, status

        first_key = mint_execution_key()
        token = bind_execution_key(first_key)
        try:
            first = open_session(arqux_env.proj_root, agent="test-governor",
                                 project="test-proj", execution=first_key)
            from arqux.session_identity import close_session

            close_session(arqux_env.proj_root, first["session_id"],
                          agent="test-governor", summary="older")
            second = open_session(arqux_env.proj_root, agent="test-governor",
                                  project="test-proj", execution=mint_execution_key())
            from arqux.session_identity import close_session as close2

            close2(arqux_env.proj_root, second["session_id"], agent="test-governor",
                   summary="newer")
            result = resume(session_ref=first["session_id"],
                            path=str(arqux_env.proj_root), ctx=_ctx("exec-unbound"))
            assert result.fields["session_ref"] == first["session_id"]
            assert result.fields["summary"] == "older"
            meta = status(session_ref=second["session_id"],
                          path=str(arqux_env.proj_root), ctx=_ctx("exec-unbound"))
            assert meta.fields["summary"] == "newer"
        finally:
            reset_execution_key(token)

    def test_unknown_reference_is_rejected(self, bound):
        from arqux.handlers.session import resume

        result = resume(session_ref="SES999", path=str(bound.proj_root), ctx=_ctx(bound.key))
        assert result.fields["code"] == "SESSION_NOT_FOUND"

    def test_legacy_brain_keeps_the_previous_selection(self, arqux_env):
        from arqux.handlers.session import close, resume, status

        for text in ("first", "second"):
            close(summary=text, path=str(arqux_env.proj_root), ctx=_ctx(mint_execution_key()))
        assert list_sessions(arqux_env.proj_root) == []
        result = resume(path=str(arqux_env.proj_root), ctx=_ctx("exec-unbound"))
        assert result.fields["source"] == "pulse_legacy"
        assert result.fields["summary"] == "second"
        assert status(path=str(arqux_env.proj_root), ctx=_ctx("exec-unbound")).fields[
            "summary"
        ] == "second"


class TestAc07CloseAndProjectSwitch:
    def test_close_requires_the_session_holder(self, arqux_env):
        """Room model: solo quien sostiene la sala puede cerrarla."""
        from arqux.handlers.session import close

        key_a, key_b = mint_execution_key(), mint_execution_key()
        token_a = bind_execution_key(key_a)
        try:
            a = open_session(arqux_env.proj_root, agent="test-governor",
                             project="test-proj", execution=key_a, scope="CYCLE-A")
        finally:
            reset_execution_key(token_a)

        open_session(arqux_env.proj_root, agent="test-governor", project="test-proj",
                     execution=key_b, intent="resumed", session_ref=a["session_id"])

        result = close(summary="done by A", path=str(arqux_env.proj_root), ctx=_ctx(key_a))
        assert result.profile == "OUT-ERROR", result
        assert get_session(arqux_env.proj_root, a["session_id"])["state"] == "open"

    def test_close_emits_evidence_with_explicit_membership(self, bound):
        from arqux.handlers.session import close

        result = close(summary="closing", blps="BLP-001", path=str(bound.proj_root),
                       ctx=_ctx(bound.key))
        events = read_pulse_from_brain(bound.proj_root, limit=None)
        mine = [e for e in events if e["id"] == result.fields["event_id"]]
        assert mine and mine[0]["ses_ref"] == bound.session_id

    def test_close_resumed_keeps_original_identity(self, arqux_env):
        from arqux.handlers.session import close

        key = mint_execution_key()
        token = bind_execution_key(key)
        try:
            first = _bind("test-proj", key=key, ws=arqux_env.ws_root)
            sid = first.fields["session_ref"]
            close(summary="first pass", path=str(arqux_env.proj_root), ctx=_ctx(key))
            again = _bind("test-proj", key=mint_execution_key(), ws=arqux_env.ws_root,
                          intent="resumed", session_ref=sid)
            assert again.fields["session_ref"] == sid
            assert again.fields["opened_at"] == first.fields["opened_at"]
            assert again.fields["timelog"] == first.fields["timelog"]
        finally:
            reset_execution_key(token)

    def test_resumed_without_reference_is_rejected(self, bound):
        result = _bind("test-proj", ws=bound.ws_root, intent="resumed")
        assert result.fields["code"] == "SESSION_SELECTION_REQUIRED"

    def test_identity_switch_preserves_membership(self, arqux_env):
        from arqux.handlers.identity.switch import switch

        key = mint_execution_key()
        token = bind_execution_key(key)
        try:
            opened = _bind("test-proj", key=key, ws=arqux_env.ws_root)
            sid = opened.fields["session_ref"]
            result = switch(agent_id="alfred", path=str(arqux_env.proj_root),
                            ctx=PermissionContext(agent_id="test-governor", role="governor",
                                                  execution_key=key))
            assert result.profile != "OUT-ERROR", result.fields
            context = (arqux_env.ws_root / ".arqux" / "context.cortex").read_text()
            assert f'ses:"{sid}"' in context
            assert get_session(arqux_env.proj_root, sid)["agent"] == "alfred"
        finally:
            reset_execution_key(token)

    def test_legacy_sessions_stay_readable_after_migration(self, arqux_env):
        from arqux.handlers.session import close, resume

        close(summary="legacy", path=str(arqux_env.proj_root), ctx=_ctx(mint_execution_key()))
        _bind("test-proj", ws=arqux_env.ws_root)
        result = resume(path=str(arqux_env.proj_root),
                        ctx=_ctx("exec-unbound", agent="test-governor"))
        # A real session now exists: the legacy payload is still readable by
        # event id, and the real identity takes over as the current answer.
        assert result.fields["session_ref"].startswith("SES")


class TestAc06MembershipAndCompaction:
    def test_new_pulses_carry_membership(self, bound):
        _evidence(bound.proj_root, bound.session_id, n=2, tag="mine")
        assert current_session_ref(bound.proj_root, bound.key) == bound.session_id
        mine = read_pulse_from_brain(bound.proj_root, limit=None, ses_ref=bound.session_id)
        assert len(mine) == 2

    def test_compaction_prunes_only_its_own_membership(self, arqux_env):
        key = mint_execution_key()
        token = bind_execution_key(key)
        try:
            from tests.conftest import rotate_session

            mine = open_session(arqux_env.proj_root, agent="test-governor",
                                project="test-proj", execution=key, scope="CYCLE-A")
            _evidence(arqux_env.proj_root, mine["session_id"], n=6, tag="mine")
            theirs = rotate_session(arqux_env.proj_root, scope="CYCLE-B")
            _evidence(arqux_env.proj_root, theirs["session_id"], n=6, tag="theirs")
            _evidence(arqux_env.proj_root, None, n=6, tag="legacy")

            ses_event = append_pulse_to_brain(
                arqux_env.proj_root, event_id=next_pulse_event_id(arqux_env.proj_root),
                task_id="-", kind="session", agent="test-governor", payload="SES:closing",
                ses_ref=mine["session_id"],
            )
            event_id = ses_event.split("id=")[1].split()[0]

            result = compact_session_pulse(arqux_env.proj_root, session_id=event_id,
                                           agent_id="test-governor",
                                           ses_ref=mine["session_id"])
            assert result["selection"] == "membership"
            assert result["pruned"] == 6
            remaining = read_pulse_from_brain(arqux_env.proj_root, limit=None)
            assert len([e for e in remaining if e["payload"].startswith("mine")]) == 0
            assert len([e for e in remaining if e["payload"].startswith("theirs")]) == 6
            assert len([e for e in remaining if e["payload"].startswith("legacy")]) == 6
        finally:
            reset_execution_key(token)

    def test_compaction_keeps_the_session_identity_entry(self, arqux_env):
        key = mint_execution_key()
        token = bind_execution_key(key)
        try:
            session = open_session(arqux_env.proj_root, agent="test-governor",
                                   project="test-proj", execution=key)
            _evidence(arqux_env.proj_root, session["session_id"], n=6, tag="mine")
            event_id = next_pulse_event_id(arqux_env.proj_root)
            append_pulse_to_brain(arqux_env.proj_root, event_id=event_id, task_id="-",
                                  kind="session", agent="test-governor", payload="SES:x",
                                  ses_ref=session["session_id"])
            compact_session_pulse(arqux_env.proj_root, session_id=event_id,
                                  agent_id="test-governor", ses_ref=session["session_id"])
            assert get_session(arqux_env.proj_root, session["session_id"]) is not None
            assert get_session(arqux_env.proj_root, session["session_id"])["state"] == "open"
        finally:
            reset_execution_key(token)

    def test_legacy_pulses_are_never_silently_assigned(self, arqux_env):
        key = mint_execution_key()
        token = bind_execution_key(key)
        try:
            session = open_session(arqux_env.proj_root, agent="test-governor",
                                   project="test-proj", execution=key)
            _evidence(arqux_env.proj_root, None, n=6, tag="legacy")
            event_id = next_pulse_event_id(arqux_env.proj_root)
            append_pulse_to_brain(arqux_env.proj_root, event_id=event_id, task_id="-",
                                  kind="session", agent="test-governor", payload="SES:x",
                                  ses_ref=session["session_id"])
            result = compact_session_pulse(arqux_env.proj_root, session_id=event_id,
                                           agent_id="test-governor",
                                           ses_ref=session["session_id"])
            assert result["skip"] and "0 entries" in result["reason"]
            assert len([e for e in read_pulse_from_brain(arqux_env.proj_root, limit=None)
                        if e["payload"].startswith("legacy")]) == 6
        finally:
            reset_execution_key(token)


class TestAuditFindings:
    """Regresiones de la auditoría independiente de Heimdall (T-5.1)."""

    def test_close_does_not_adopt_another_execution_session(self, arqux_env):
        """H-01: con una sola sesión abierta, un cierre ajeno la robaba."""
        from arqux.handlers.session import close

        theirs = open_session(arqux_env.proj_root, agent="test-governor",
                              project="test-proj", execution=mint_execution_key())
        result = close(summary="not mine", path=str(arqux_env.proj_root),
                       ctx=_ctx("exec-someone-else"))
        assert result.fields["code"] == "SESSION_BINDING_REQUIRED"
        assert get_session(arqux_env.proj_root, theirs["session_id"])["state"] == "open"
        assert get_session(arqux_env.proj_root, theirs["session_id"])["summary"] == ""

    def test_identity_switch_does_not_hijack_a_foreign_session(self, arqux_env):
        """H-02: identity.switch tomaba la sesión del puntero global."""
        from arqux.handlers.identity.switch import switch

        owner = mint_execution_key()
        token = bind_execution_key(owner)
        try:
            mine = open_session(arqux_env.proj_root, agent="test-governor",
                                project="test-proj", execution=owner, scope="CYCLE-A")
            _bind("test-proj", key=owner, ws=arqux_env.ws_root)
            switch("alfred", path=str(arqux_env.proj_root),
                   ctx=PermissionContext(agent_id="test-governor", role="governor",
                                         execution_key=owner))
            after = get_session(arqux_env.proj_root, mine["session_id"])
            assert after["execution"] == owner
            assert len(list_sessions(arqux_env.proj_root)) == 1
        finally:
            reset_execution_key(token)

    def test_pulse_compact_handler_accepts_membership(self, arqux_env):
        """H-04: el esquema MCP anunciaba ses_ref pero la firma lo rechazaba."""
        from arqux.handlers.session import pulse_compact

        session = open_session(arqux_env.proj_root, agent="test-governor",
                               project="test-proj", execution=mint_execution_key())
        _evidence(arqux_env.proj_root, session["session_id"], n=6, tag="mine")
        _evidence(arqux_env.proj_root, None, n=6, tag="legacy")
        event_id = next_pulse_event_id(arqux_env.proj_root)
        append_pulse_to_brain(arqux_env.proj_root, event_id=event_id, task_id="-",
                              kind="session", agent="test-governor", payload="SES:x",
                              ses_ref=session["session_id"])
        result = pulse_compact(event_id, ses_ref=session["session_id"],
                               path=str(arqux_env.proj_root), ctx=_ctx("exec-x"))
        assert result.profile != "OUT-ERROR", result.fields
        remaining = read_pulse_from_brain(arqux_env.proj_root, limit=None)
        assert len([e for e in remaining if e["payload"].startswith("legacy")]) == 6

    def test_compaction_refuses_a_foreign_session_event(self, arqux_env):
        """H-07: compactar el evento de cierre de otra sesión."""
        from arqux.pulse import compact_session_pulse
        from tests.conftest import rotate_session

        mine = open_session(arqux_env.proj_root, agent="test-governor",
                            project="test-proj", execution=mint_execution_key(),
                            scope="CYCLE-A")
        _evidence(arqux_env.proj_root, mine["session_id"], n=6, tag="mine")
        theirs = rotate_session(arqux_env.proj_root, scope="CYCLE-B")
        event_id = next_pulse_event_id(arqux_env.proj_root)
        append_pulse_to_brain(arqux_env.proj_root, event_id=event_id, task_id="-",
                              kind="session", agent="test-governor", payload="SES:x",
                              ses_ref=theirs["session_id"])
        result = compact_session_pulse(arqux_env.proj_root, session_id=event_id,
                                       agent_id="test-governor",
                                       ses_ref=mine["session_id"])
        assert "error" in result and theirs["session_id"] in result["error"]
        assert len([e for e in read_pulse_from_brain(arqux_env.proj_root, limit=None)
                    if e["payload"].startswith("mine")]) == 6

    def test_context_is_recorded_per_execution(self, arqux_env):
        """H-08: el puntero global era un único asiento."""
        from arqux.handlers.session import context_get

        key_a, key_b = mint_execution_key(), mint_execution_key()
        token_a, token_b = bind_execution_key(key_a), bind_execution_key(key_b)
        try:
            a = _bind("test-proj", key=key_a, ws=arqux_env.ws_root, scope="CYCLE-A")
            b = _bind("test-proj", key=key_b, ws=arqux_env.ws_root, scope="CYCLE-B",
                      intent="resumed", session_ref=a.fields["session_ref"])
            assert a.fields["session_ref"] == b.fields["session_ref"]
            assert context_get(path=str(arqux_env.ws_root),
                               ctx=_ctx(key_a)).fields["scope"] == "CYCLE-A"
            assert context_get(path=str(arqux_env.ws_root),
                               ctx=_ctx(key_b)).fields["scope"] == "CYCLE-B"
        finally:
            reset_execution_key(token_b)
            reset_execution_key(token_a)

    def test_implicit_process_key_cannot_open_a_session(self, arqux_env, monkeypatch):
        """H-05: la clave de proceso no es un vínculo de ejecución."""
        from arqux.execution import set_process_execution_key

        bind_execution_key(None)
        set_process_execution_key("exec-process-default")
        monkeypatch.setattr("arqux.handlers.session.PermissionContext.from_env",
                            classmethod(lambda cls, project_root=None: PermissionContext(
                                agent_id="test-governor", role="governor",
                                execution_key=current_process_key())))
        result = _bind("test-proj", ws=arqux_env.ws_root, bind=False)
        assert result.fields["code"] == "SESSION_BINDING_REQUIRED"
        assert list_sessions(arqux_env.proj_root) == []


def current_process_key() -> str:
    from arqux.execution import current_execution_key

    return current_execution_key() or ""


class TestSecondAuditFindings:
    """Regresiones de la segunda auditoría independiente (H-03/N-01..N-08)."""

    def test_close_by_non_owner_is_explicit_but_logged(self, arqux_env):
        """H-06: un session_ref explícito es instrucción del operador, no robo."""
        from arqux.handlers.session import close

        theirs = open_session(arqux_env.proj_root, agent="test-governor",
                              project="test-proj", execution=mint_execution_key())
        result = close(summary="closed by explicit instruction",
                       session_ref=theirs["session_id"], path=str(arqux_env.proj_root),
                       ctx=_ctx("exec-other"))
        assert result.profile != "OUT-ERROR", result.fields
        assert get_session(arqux_env.proj_root, theirs["session_id"])["state"] == "closed"

    def test_resume_takes_over_the_room(self, arqux_env):
        """Policy 2026-10-28: una sesión abierta es retomable por diseño.

        H-06 rechazaba esto. La política vigente lo permite: si la máquina se
        apagó sin cerrar, el trabajo sigue pendiente y la sala es retomable.
        """
        owner = mint_execution_key()
        token = bind_execution_key(owner)
        try:
            theirs = open_session(arqux_env.proj_root, agent="test-governor",
                                  project="test-proj", execution=owner)
        finally:
            reset_execution_key(token)

        new_key = mint_execution_key()
        result = _bind("test-proj", ws=arqux_env.ws_root, key=new_key,
                       intent="resumed", session_ref=theirs["session_id"])
        assert result.profile == "OUT-WORK", result
        stored = get_session(arqux_env.proj_root, theirs["session_id"])
        assert stored["execution"] == new_key
        assert stored["date"] == theirs["date"]

    def test_close_keeps_interval_notation_readable(self, arqux_env):
        """N-02: cerrar una sesión corrompía la marca de intervalo."""
        from arqux.session_identity import close_session

        session = open_session(arqux_env.proj_root, agent="test-governor",
                               project="test-proj", execution=mint_execution_key())
        closed = close_session(arqux_env.proj_root, session["session_id"],
                               agent="test-governor", summary="done")
        intervals = closed["intervals"]
        assert intervals.startswith("[") and intervals.endswith("]")
        assert "/]" not in intervals
        assert intervals.count("[") == intervals.count("]") == 1

    def test_reopen_appends_without_losing_intervals(self, arqux_env):
        """N-03: lectura fuera del lock perdía intervalos en concurrencia."""
        from arqux.session_identity import close_session, reopen_session

        key = mint_execution_key()
        session = open_session(arqux_env.proj_root, agent="test-governor",
                               project="test-proj", execution=key)
        for _ in range(3):
            close_session(arqux_env.proj_root, session["session_id"],
                          agent="test-governor", summary="cycle")
            reopened = reopen_session(arqux_env.proj_root, session["session_id"],
                                      execution=key, agent="test-governor")
        assert reopened["intervals"].count("[") == 4

    def test_context_read_does_not_leak_another_execution(self, arqux_env):
        """N-06: context_get caía al slot global y filtraba scope ajeno."""
        from arqux.handlers.session import context_get

        key_a, key_b = mint_execution_key(), mint_execution_key()
        token_a, token_b = bind_execution_key(key_a), bind_execution_key(key_b)
        try:
            _bind("test-proj", key=key_a, ws=arqux_env.ws_root, scope="SCOPE-A")
            stranger = context_get(path=str(arqux_env.ws_root), ctx=_ctx(key_b))
            assert stranger.profile == "OUT-ERROR"
        finally:
            reset_execution_key(token_b)
            reset_execution_key(token_a)

    def test_legacy_workspace_slot_is_still_readable(self, arqux_env):
        """N-06 no puede romper los workspaces anteriores a los contextos por ejecución."""
        from arqux.handlers.session import CONTEXT_CORTEX, context_get
        from arqux.state import find_workspace_root

        arqux = find_workspace_root(start=str(arqux_env.ws_root))

        # A workspace whose only context is the pre-existing workspace slot,
        # with no per-execution file anywhere: the old behaviour must survive.
        (arqux / CONTEXT_CORTEX).write_text(
            '$0\n\n$1: CURRENT\n'
            'CTX:alfred project="test-proj" scope="CYCLE-01" agent="alfred" '
            f'project_root="{arqux_env.proj_root}"\n',
            encoding="utf-8",
        )
        assert context_get(path=str(arqux_env.ws_root),
                           ctx=_ctx("exec-unrelated")).fields["scope"] == "CYCLE-01"

    def test_context_document_is_canonical_and_self_describing(self, arqux_env):
        """context_set writes a glossary-declared CTX entry the codec can parse."""
        from arqux.handlers.session import CONTEXT_CORTEX, context_get

        key = mint_execution_key()
        _bind("test-proj", key=key, ws=arqux_env.ws_root, scope="CYCLE-CTX")
        document = (arqux_env.ws_root / ".arqux" / CONTEXT_CORTEX).read_text(
            encoding="utf-8")

        assert "# CTX " in document.split("$1")[0]
        entry_line = next(l for l in document.splitlines()
                          if l.startswith("CTX:"))
        assert re.fullmatch(r"CTX:[^\s{]+\{.*\}", entry_line)

        out = context_get(path=str(arqux_env.ws_root), ctx=_ctx(key))
        assert out.fields["scope"] == "CYCLE-CTX"
        assert out.fields["project"] == "test-proj"

    def test_identity_switch_does_not_copy_a_foreign_context(self, arqux_env):
        """N-04: switch escribía el contexto ajeno en el fichero propio."""
        from arqux.handlers.identity.switch import switch
        from arqux.handlers.session import CONTEXTS_DIR, _execution_slug
        from arqux.state import find_workspace_root

        arqux = find_workspace_root(start=str(arqux_env.ws_root))

        owner = mint_execution_key()
        token = bind_execution_key(owner)
        try:
            _bind("test-proj", key=owner, ws=arqux_env.ws_root, scope="SCOPE-A")
        finally:
            reset_execution_key(token)

        stranger = mint_execution_key()
        token = bind_execution_key(stranger)
        try:
            result = switch("alfred", path=str(arqux_env.proj_root),
                            ctx=PermissionContext(agent_id="test-governor", role="governor",
                                                  execution_key=stranger))
            assert result.fields["context_owned"] is False
            assert result.fields["session_rebound"] is False
            own_file = arqux / CONTEXTS_DIR / f"{_execution_slug(stranger)}.cortex"
            assert not own_file.exists()
            a_file = arqux / CONTEXTS_DIR / f"{_execution_slug(owner)}.cortex"
            assert 'scope:"SCOPE-A"' in a_file.read_text()
        finally:
            reset_execution_key(token)

    def test_execution_key_cannot_escape_the_contexts_directory(self, arqux_env):
        """N-08: la clave se usa como nombre de fichero."""
        from arqux.handlers.session import _execution_slug

        assert "/" not in _execution_slug("../../etc/passwd")
        assert ".." not in _execution_slug("../../etc/passwd")
        slug = _execution_slug("exec/../../x")
        assert "/" not in slug and slug != "exec____x"
        assert not slug.startswith(".")

    def test_compaction_of_an_unlabelled_close_is_refused(self, arqux_env):
        """H-07: un evento de cierre sin pertenencia no compacta por pertenencia."""
        from arqux.pulse import compact_session_pulse

        mine = open_session(arqux_env.proj_root, agent="test-governor",
                            project="test-proj", execution=mint_execution_key())
        _evidence(arqux_env.proj_root, mine["session_id"], n=6, tag="mine")
        event_id = next_pulse_event_id(arqux_env.proj_root)
        append_pulse_to_brain(arqux_env.proj_root, event_id=event_id, task_id="-",
                              kind="session", agent="test-governor", payload="SES:legacy")
        result = compact_session_pulse(arqux_env.proj_root, session_id=event_id,
                                       agent_id="test-governor",
                                       ses_ref=mine["session_id"])
        assert "error" in result
        assert len([e for e in read_pulse_from_brain(arqux_env.proj_root, limit=None)
                    if e["payload"].startswith("mine")]) == 6


class TestPruningMatchesTheEntryIdNotASubstring:
    """D-10: an id quoted inside a payload must not take its entry down."""

    def test_id_inside_a_payload_does_not_prune_that_entry(self, arqux_env):
        from arqux.pulse import (
            _prune_pulse_entries,
            append_pulse_to_brain,
            next_pulse_event_id,
        )
        from arqux.state import crud_read
        from arqux.timelog_store import brain_path

        root = arqux_env.proj_root
        session = open_session(root, agent="test-governor", project="test-proj",
                               execution=mint_execution_key())
        ses = session["session_id"]
        # First the entry that OWNS the id, then another that merely quotes it.
        first = next_pulse_event_id(root)
        append_pulse_to_brain(root, event_id=first, task_id="T-1.1", kind="note",
                              agent="test-governor", payload="original",
                              ses_ref=ses)
        quoted = next_pulse_event_id(root)
        append_pulse_to_brain(root, event_id=quoted, task_id="T-1.1", kind="note",
                              agent="test-governor",
                              payload=f"see {first} for context", ses_ref=ses)
        for _ in range(6):
            append_pulse_to_brain(root, event_id=next_pulse_event_id(root),
                                  task_id="T-1.1", kind="note",
                                  agent="test-governor", payload="mine", ses_ref=ses)

        brain = str(brain_path(root))
        _prune_pulse_entries(brain_path(root), [first])
        remaining = {e["name"] for e in crud_read(brain, "$6/AUD:*")["entries"]}
        # The entry that merely quotes the pruned id survives.
        assert quoted.replace("-", "_") in remaining, remaining
        assert first.replace("-", "_") not in remaining


class TestIdentitySwitchStateTransitions:
    """H-A: switching identity must not reopen a closed session."""

    def test_switch_does_not_reopen_a_closed_session(self, arqux_env):
        from arqux.handlers.identity.switch import switch
        from arqux.handlers.session import close, context_set

        key = mint_execution_key()
        token = bind_execution_key(key)
        try:
            ctx = PermissionContext(agent_id="test-governor", role="governor",
                                    execution_key=key)
            out = context_set(project="test-proj", scope="CYCLE-TEST",
                              path=str(arqux_env.ws_root), ctx=ctx)
            sid = out.fields["session_ref"]
            close(summary="done", path=str(arqux_env.proj_root), ctx=ctx)
            before = get_session(arqux_env.proj_root, sid)
            assert before["state"] == "closed"

            result = switch("alfred", path=str(arqux_env.proj_root), ctx=ctx)

            after = get_session(arqux_env.proj_root, sid)
            assert after["state"] == "closed"
            assert after["closed"] == before["closed"]
            assert result.fields["session_rebound"] is False
        finally:
            reset_execution_key(token)
