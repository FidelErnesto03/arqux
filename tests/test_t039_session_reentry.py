"""T-039 — session reentry contract: re-attach by default, ask on ambiguity.

Returning to a project that already has an open session for the same
``(agent, project, scope)`` must re-attach it instead of silently stacking a new
``SES``. Only two or more open sessions for that same context are ambiguous, and
are handed back as a question. Closes issue
2026-10-22-reingreso-a-contexto-con-sesi-n-abierta-debe-ret.
"""

from __future__ import annotations

import pytest

from arqux.execution import mint_execution_key
from arqux.session_identity import (
    SESSION_SECTION,
    SESSION_SIGIL,
    ReentryAmbiguous,
    brain_path,
    get_session,
    list_sessions,
    open_session,
    open_sessions,
)
from arqux.state import crud_add


def _open(arqux_env, *, execution=None, agent="test-governor", scope="CYCLE-A"):
    return open_session(arqux_env.proj_root, agent=agent, project="test-proj",
                        execution=execution or mint_execution_key(), scope=scope)


def _duplicate_open(arqux_env, session_id: str, new_id: str) -> None:
    """Recreate a second OPEN session with the same context (legacy residue).

    This is the shape the fix removes: two open sessions for one context, as the
    repeated Kiro reconnections produced before the contract existed.
    """
    base = get_session(arqux_env.proj_root, session_id)
    value = {k: v for k, v in base.items() if k != "session_id"}
    crud_add(brain_path(arqux_env.proj_root), SESSION_SECTION, SESSION_SIGIL, new_id,
             value, create_section=True, force=True)


def _ambiguous_pair(arqux_env) -> dict:
    first = _open(arqux_env)
    _duplicate_open(arqux_env, first["session_id"], "SES002")
    return first


class TestAc01ReentryReattaches:
    def test_new_execution_same_context_reuses_the_open_session(self, arqux_env):
        first = _open(arqux_env)
        again = _open(arqux_env)
        assert again["session_id"] == first["session_id"]
        assert again["date"] == first["date"]
        assert again["timelog"] == first["timelog"]
        assert len(list_sessions(arqux_env.proj_root)) == 1

    def test_reattach_repoints_the_execution_without_renaming(self, arqux_env):
        first = _open(arqux_env)
        key = mint_execution_key()
        again = _open(arqux_env, execution=key)
        assert again["session_id"] == first["session_id"]
        assert get_session(arqux_env.proj_root, first["session_id"])["execution"] == key

    def test_same_execution_stays_idempotent(self, arqux_env):
        key = mint_execution_key()
        a = _open(arqux_env, execution=key)
        b = _open(arqux_env, execution=key)
        assert a["session_id"] == b["session_id"]

    def test_distinct_scope_opens_a_second_session(self, arqux_env):
        a = _open(arqux_env, scope="CYCLE-A")
        b = _open(arqux_env, scope="CYCLE-B")
        assert a["session_id"] != b["session_id"]

    def test_distinct_agent_opens_a_second_session(self, arqux_env):
        a = _open(arqux_env, agent="test-governor")
        b = _open(arqux_env, agent="test-executor")
        assert a["session_id"] != b["session_id"]


class TestAc02NoStacking:
    def test_repeated_reentry_leaves_one_open_session_per_context(self, arqux_env):
        for _ in range(3):
            _open(arqux_env)
        opens = open_sessions(arqux_env.proj_root)
        assert len(opens) == 1

    def test_reattach_leaves_the_bound_session_open(self, arqux_env):
        first = _open(arqux_env)
        _open(arqux_env)
        assert get_session(arqux_env.proj_root, first["session_id"])["state"] == "open"


class TestAc03AmbiguityAsks:
    def test_two_open_sessions_for_one_context_are_ambiguous(self, arqux_env):
        _ambiguous_pair(arqux_env)
        with pytest.raises(ReentryAmbiguous) as exc:
            _open(arqux_env)
        assert [s["session_id"] for s in exc.value.alternatives] == ["SES001", "SES002"]

    def test_ambiguity_does_not_stack_a_third_session(self, arqux_env):
        _ambiguous_pair(arqux_env)
        with pytest.raises(ReentryAmbiguous):
            _open(arqux_env)
        assert len(list_sessions(arqux_env.proj_root)) == 2

    def test_handler_returns_a_structured_question(self, arqux_env):
        from arqux.handlers.session import context_set
        from arqux.permissions import PermissionContext

        _ambiguous_pair(arqux_env)
        ctx = PermissionContext(agent_id="test-governor", role="governor",
                                execution_key=mint_execution_key())
        result = context_set(project="test-proj", scope="CYCLE-A",
                             path=str(arqux_env.ws_root), ctx=ctx)
        assert result.fields["code"] == "SESSION_REENTRY_AMBIGUOUS"
        joined = " ".join(result.fields["alternatives"])
        assert "SES001" in joined and "SES002" in joined
        assert len(list_sessions(arqux_env.proj_root)) == 2

    def test_a_single_open_session_is_not_ambiguous(self, arqux_env):
        first = _open(arqux_env)
        again = _open(arqux_env)
        assert again["session_id"] == first["session_id"]


def _age_session(proj_root, sid, days=2):
    """Rewrite a session's opened date into the past (day-boundary fixture)."""
    import datetime as _dt

    from arqux.session_identity import brain_path
    brain = brain_path(proj_root)
    text = brain.read_text(encoding="utf-8")
    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
           ).strftime("%Y-%m-%dT%H:%M:%SZ")
    import re as _re
    # Replace only this session's date field.
    pattern = _re.compile(rf"(SES:{sid}\{{date:\")([^\"]+)")
    brain.write_text(pattern.sub(rf"\g<1>{old}", text), encoding="utf-8")


def test_expired_foreign_session_auto_closes_on_next_touch(arqux_env):
    """Policy: sessions expire at 00:00 unless bound to the user's execution."""
    from arqux.execution import mint_execution_key
    from arqux.session_identity import get_session, open_session

    foreign = open_session(arqux_env.proj_root, agent="test-governor",
                           project="test-proj",
                           execution=mint_execution_key(), scope="CYCLE-A")
    _age_session(arqux_env.proj_root, foreign["session_id"])

    new = open_session(arqux_env.proj_root, agent="test-governor",
                       project="test-proj",
                       execution=mint_execution_key(), scope="CYCLE-A")
    assert new["session_id"] != foreign["session_id"]
    assert get_session(arqux_env.proj_root, foreign["session_id"])["state"] == "closed"


def test_own_session_survives_day_boundary(arqux_env):
    """The session bound to THIS execution never expires — 'active and in use'."""
    from arqux.execution import mint_execution_key
    from arqux.session_identity import get_session, open_session

    key = mint_execution_key()
    mine = open_session(arqux_env.proj_root, agent="test-governor",
                        project="test-proj", execution=key, scope="CYCLE-A")
    _age_session(arqux_env.proj_root, mine["session_id"])

    again = open_session(arqux_env.proj_root, agent="test-governor",
                         project="test-proj", execution=key, scope="CYCLE-A")
    assert again["session_id"] == mine["session_id"]
    assert get_session(arqux_env.proj_root, mine["session_id"])["state"] == "open"


def test_fresh_foreign_session_does_not_expire(arqux_env):
    """A foreign session opened TODAY is still live — expiry needs the 00:00 crossing."""
    from arqux.execution import mint_execution_key
    from arqux.session_identity import get_session, open_session

    foreign = open_session(arqux_env.proj_root, agent="test-governor",
                           project="test-proj",
                           execution=mint_execution_key(), scope="CYCLE-A")
    # Today's foreign session is re-attached (T-039 contract), never closed.
    adopted = open_session(arqux_env.proj_root, agent="test-governor",
                           project="test-proj",
                           execution=mint_execution_key(), scope="CYCLE-A")
    assert adopted["session_id"] == foreign["session_id"]
    assert get_session(arqux_env.proj_root, foreign["session_id"])["state"] == "open"
