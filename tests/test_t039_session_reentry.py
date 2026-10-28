"""Política de sesión abierta (Arquitecto, 2026-10-28).

Una sesión NO cerrada significa que el trabajo no terminó: si alguien apagó la
máquina sin cerrar, la sesión sigue viva y se puede retomar. La sesión conserva
su fecha de inicio; las actividades registran internamente sus propias fechas.

Para abrir una sesión NUEVA sobre el mismo proyecto es obligatorio cerrar la que
está abierta o retomarla, y el sistema presenta ambas alternativas.

Esta política reemplaza el contrato anterior de T-039 (re-adhesión automática
por contexto) y la expiración en la frontera de día.
"""

from __future__ import annotations

import pytest

from arqux.execution import mint_execution_key
from arqux.handlers.session import context_set
from arqux.permissions import PermissionContext
from arqux.session_identity import (
    SessionOpenExists,
    brain_path,
    close_session,
    get_session,
    list_sessions,
    open_session,
    open_sessions,
)
from arqux.state import crud_update


def _open(env, *, execution=None, agent="test-governor", scope="CYCLE-A"):
    return open_session(env.proj_root, agent=agent, project="test-proj",
                        execution=execution or mint_execution_key(), scope=scope)


def _ctx(key):
    return PermissionContext(agent_id="test-governor", role="governor",
                             execution_key=key)


class TestResumeAnyOpenSession:
    def test_another_execution_can_resume_the_open_session(self, env):
        first = _open(env)
        resumed = open_session(env.proj_root, agent="test-governor", project="test-proj",
                               execution=mint_execution_key(), scope="CYCLE-B",
                               intent="resumed", session_ref=first["session_id"])

        assert resumed["session_id"] == first["session_id"]
        assert resumed["date"] == first["date"]
        assert resumed["timelog"] == first["timelog"]

    def test_resume_repoints_the_execution_without_touching_the_start(self, env):
        first = _open(env)
        key = mint_execution_key()
        open_session(env.proj_root, agent="test-governor", project="test-proj",
                     execution=key, intent="resumed", session_ref=first["session_id"])

        stored = get_session(env.proj_root, first["session_id"])
        assert stored["execution"] == key
        assert stored["date"] == first["date"]

    def test_a_session_from_yesterday_is_still_resumable(self, env):
        first = _open(env)
        crud_update(brain_path(env.proj_root), f"$4/SES:{first['session_id']}",
                    set_={"date": "2026-10-20T09:00:00Z"}, force=True)

        resumed = open_session(env.proj_root, agent="test-governor", project="test-proj",
                               execution=mint_execution_key(), intent="resumed",
                               session_ref=first["session_id"])
        assert resumed["state"] == "open"
        assert resumed["date"] == "2026-10-20T09:00:00Z"

    def test_same_execution_stays_idempotent(self, env):
        key = mint_execution_key()
        first = _open(env, execution=key)
        again = _open(env, execution=key)
        assert again["session_id"] == first["session_id"]
        assert len(list_sessions(env.proj_root)) == 1


class TestNewSessionRequiresClosingOrResuming:
    def test_new_session_is_refused_while_one_is_open(self, env):
        first = _open(env)
        with pytest.raises(SessionOpenExists) as exc:
            _open(env, scope="CYCLE-B")

        ids = [s["session_id"] for s in exc.value.alternatives]
        assert ids == [first["session_id"]]
        assert len(open_sessions(env.proj_root)) == 1

    def test_a_different_scope_does_not_open_a_second_session(self, env):
        _open(env, scope="CYCLE-A")
        with pytest.raises(SessionOpenExists):
            _open(env, scope="CYCLE-B")

    def test_after_closing_a_new_session_is_allowed(self, env):
        first = _open(env)
        close_session(env.proj_root, first["session_id"], agent="test-governor",
                      summary="trabajo terminado")

        second = _open(env, scope="CYCLE-B")
        assert second["session_id"] != first["session_id"]
        assert second["state"] == "open"

    def test_legacy_residue_lists_every_open_session(self, env):
        first = _open(env)
        base = get_session(env.proj_root, first["session_id"])
        crud_update(brain_path(env.proj_root), f"$4/SES:{first['session_id']}",
                    set_={}, force=True)
        from arqux.session_identity import SESSION_SECTION, SESSION_SIGIL
        from arqux.state import crud_add

        value = {k: v for k, v in base.items() if k != "session_id"}
        crud_add(brain_path(env.proj_root), SESSION_SECTION, SESSION_SIGIL, "SES002",
                 value, create_section=True, force=True)

        with pytest.raises(SessionOpenExists) as exc:
            _open(env, scope="CYCLE-Z")
        assert {s["session_id"] for s in exc.value.alternatives} == {"SES001", "SES002"}


class TestHandlerPresentsAlternatives:
    def test_context_set_returns_both_commands(self, env):
        key = mint_execution_key()
        first = _open(env, execution=key)

        out = context_set(project="test-proj", scope="CYCLE-B",
                          path=str(env.ws_root), ctx=_ctx(mint_execution_key()))

        assert out.profile == "OUT-ERROR"
        assert out.fields["code"] == "SESSION_OPEN_EXISTS"
        alt = out.fields["alternatives"][0]
        assert f"session_ref='{first['session_id']}'" in alt
        assert "intent='resumed'" in alt
        assert "session.close" in alt

    def test_resuming_through_the_handler_works(self, env):
        key = mint_execution_key()
        first = _open(env, execution=key)

        out = context_set(project="test-proj", scope="CYCLE-A", intent="resumed",
                          session_ref=first["session_id"],
                          path=str(env.ws_root), ctx=_ctx(mint_execution_key()))
        assert out.profile == "OUT-WORK", out
        assert out.fields["session_ref"] == first["session_id"]


@pytest.fixture
def env(arqux_env):
    arqux_env.key = mint_execution_key()
    return arqux_env
