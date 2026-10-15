"""CYCLE-14 / BLP-001 — real SES identity and per-execution isolation.

Covers AC-01 to AC-04 (opening, naming, STANDBY, concurrency).
"""

from __future__ import annotations

import os
import threading

import pytest

from arqux.constants import ROLE_GOVERNOR
from arqux.execution import (
    ENV_STRICT_EXECUTION,
    bind_execution_key,
    current_execution_key,
    mint_execution_key,
    reset_execution_key,
    set_process_execution_key,
)
from arqux.permissions import PermissionContext
from arqux.session_identity import (
    SESSION_ID_RE,
    get_session,
    list_sessions,
    next_session_id,
    open_session,
    reopen_session,
    timelog_name,
    timelog_path,
)


def _bind(project: str, scope: str = "CYCLE-TEST", *, key: str | None = None,
          agent: str = "test-governor", blp: str | None = None,
          intent: str = "new", session_ref: str | None = None, ws=None,
          bind: bool = True):
    """Bind a context and call session.context.set.

    ``bind=False`` simulates a caller the transport never bound, which is the
    only way to reach ``SESSION_BINDING_REQUIRED``.
    """
    from arqux.handlers.session import context_set

    token = bind_execution_key(key or mint_execution_key()) if bind else bind_execution_key(None)
    try:
        return context_set(project=project, scope=scope, blp=blp, intent=intent,
                           session_ref=session_ref, path=str(ws), ctx=None)
    finally:
        if token is not None:
            reset_execution_key(token)


@pytest.fixture(autouse=True)
def _isolated_process_key():
    set_process_execution_key(None)
    yield
    set_process_execution_key(None)


class TestExecutionKey:
    def test_env_key_wins(self, monkeypatch):
        monkeypatch.setenv("ARQUX_EXECUTION_KEY", "exec-env")
        assert current_execution_key() == "exec-env"

    def test_context_key_overrides_process(self):
        token = bind_execution_key("exec-ctx")
        try:
            assert current_execution_key() == "exec-ctx"
        finally:
            reset_execution_key(token)

    def test_process_default_is_stable(self):
        first = current_execution_key()
        assert first and current_execution_key() == first

    def test_implicit_process_key_is_not_authoritative(self, monkeypatch):
        from arqux.execution import authoritative_execution_key

        bind_execution_key(None)
        set_process_execution_key(None)
        assert current_execution_key()          # readable, still resolves
        assert authoritative_execution_key() is None

    def test_strict_mode_rejects_keyless_caller(self, monkeypatch):
        from arqux.execution import authoritative_execution_key

        monkeypatch.setenv(ENV_STRICT_EXECUTION, "1")
        bind_execution_key(None)
        set_process_execution_key(None)
        assert authoritative_execution_key() is None


class TestAc01OpeningIsUniqueAndIdempotent:
    def test_open_creates_one_entry_with_original_start(self, arqux_env):
        key = mint_execution_key()
        session = open_session(arqux_env.proj_root, agent="test-governor",
                               project="test-proj", execution=key, scope="CYCLE-TEST")
        assert SESSION_ID_RE.match(session["session_id"])
        assert session["state"] == "open"
        assert session["date"].endswith("Z")

    def test_repeating_the_binding_does_not_create_a_second_ses(self, arqux_env):
        key = mint_execution_key()
        first = open_session(arqux_env.proj_root, agent="test-governor",
                             project="test-proj", execution=key)
        second = open_session(arqux_env.proj_root, agent="test-governor",
                              project="test-proj", execution=key)
        assert first["session_id"] == second["session_id"]
        assert first["date"] == second["date"]
        assert len(list_sessions(arqux_env.proj_root)) == 1

    def test_handler_binding_is_idempotent(self, arqux_env):
        key = mint_execution_key()
        first = _bind("test-proj", key=key, ws=arqux_env.ws_root)
        second = _bind("test-proj", key=key, ws=arqux_env.ws_root)
        assert first.fields["session_ref"] == second.fields["session_ref"]
        assert first.fields["opened_at"] == second.fields["opened_at"]


class TestAc02Name:
    def test_name_derives_from_id_and_original_start(self):
        assert timelog_name("SES001", "2026-10-14T23:02:57Z") == "SES001_20261014_230257.cortex"

    def test_name_keeps_more_than_three_digits(self):
        assert timelog_name("SES1234", "2026-10-14T23:02:57Z") == "SES1234_20261014_230257.cortex"

    def test_resume_does_not_rename(self, arqux_env):
        key = mint_execution_key()
        opened = open_session(arqux_env.proj_root, agent="test-governor",
                              project="test-proj", execution=key)
        sid, name = opened["session_id"], opened["timelog"]
        from arqux.session_identity import close_session

        close_session(arqux_env.proj_root, sid, agent="test-governor", summary="done")
        reopened = reopen_session(arqux_env.proj_root, sid, execution=mint_execution_key(),
                                  agent="test-governor")
        assert reopened["session_id"] == sid
        assert reopened["timelog"] == name
        assert reopened["date"] == opened["date"]
        assert timelog_path(arqux_env.proj_root, sid, opened["date"]).name == name

    def test_handler_reports_the_planned_timelog(self, arqux_env):
        result = _bind("test-proj", ws=arqux_env.ws_root)
        sid = result.fields["session_ref"]
        assert result.fields["timelog"] == timelog_name(sid, result.fields["opened_at"])


class TestAc03StandbyAndBindingRequired:
    def test_bootstrap_does_not_open_a_session(self, arqux_env):
        from arqux.handlers.session import bootstrap

        before = list_sessions(arqux_env.proj_root)
        bootstrap(path=str(arqux_env.proj_root),
                  ctx=PermissionContext(agent_id="test-governor", role=ROLE_GOVERNOR))
        assert list_sessions(arqux_env.proj_root) == before

    def test_workspace_context_get_opens_nothing(self, arqux_env):
        from arqux.handlers.session import context_get

        context_get(path=str(arqux_env.ws_root))
        assert list_sessions(arqux_env.proj_root) == []

    def test_missing_execution_binding_is_rejected(self, arqux_env, monkeypatch):
        monkeypatch.setenv(ENV_STRICT_EXECUTION, "1")
        set_process_execution_key(None)
        result = _bind("test-proj", ws=arqux_env.ws_root, bind=False)
        assert result.fields["code"] == "SESSION_BINDING_REQUIRED"
        assert list_sessions(arqux_env.proj_root) == []

    def test_rejection_does_not_borrow_another_execution_session(self, arqux_env, monkeypatch):
        other = _bind("test-proj", key=mint_execution_key(), ws=arqux_env.ws_root)
        monkeypatch.setenv(ENV_STRICT_EXECUTION, "1")
        set_process_execution_key(None)
        result = _bind("test-proj", ws=arqux_env.ws_root, bind=False)
        assert result.fields["code"] == "SESSION_BINDING_REQUIRED"
        assert get_session(arqux_env.proj_root, other.fields["session_ref"])["state"] == "open"


class TestAc04Concurrency:
    def test_two_executions_get_distinct_sessions(self, arqux_env):
        a = open_session(arqux_env.proj_root, agent="test-governor",
                         project="test-proj", execution=mint_execution_key())
        b = open_session(arqux_env.proj_root, agent="test-governor",
                         project="test-proj", execution=mint_execution_key())
        assert a["session_id"] != b["session_id"]

    def test_concurrent_open_allocates_unique_ids(self, arqux_env):
        results: list[str] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(4)

        def worker() -> None:
            try:
                barrier.wait(timeout=5)
                session = open_session(arqux_env.proj_root, agent="test-governor",
                                       project="test-proj", execution=mint_execution_key())
                results.append(session["session_id"])
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, errors
        assert len(results) == 4
        assert len(set(results)) == 4

    def test_concurrent_repeat_of_one_execution_keeps_one_ses(self, arqux_env):
        key = mint_execution_key()
        results: list[str] = []
        barrier = threading.Barrier(3)

        def worker() -> None:
            barrier.wait(timeout=5)
            session = open_session(arqux_env.proj_root, agent="test-governor",
                                   project="test-proj", execution=key)
            results.append(session["session_id"])

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(set(results)) == 1
        assert len(list_sessions(arqux_env.proj_root)) == 1

    def test_no_redirect_through_the_global_pointer(self, arqux_env):
        first = _bind("test-proj", key=mint_execution_key(), ws=arqux_env.ws_root)
        second = _bind("test-proj", key=mint_execution_key(), ws=arqux_env.ws_root)
        assert first.fields["session_ref"] != second.fields["session_ref"]
        context = (arqux_env.ws_root / ".arqux" / "context.cortex").read_text()
        assert f'ses="{second.fields["session_ref"]}"' in context
        assert get_session(arqux_env.proj_root, first.fields["session_ref"])["state"] == "open"


class TestNamespaceAllocation:
    def test_ids_are_monotonic(self, arqux_env):
        assert next_session_id(arqux_env.proj_root) == "SES001"
        open_session(arqux_env.proj_root, agent="test-governor",
                     project="test-proj", execution=mint_execution_key())
        assert next_session_id(arqux_env.proj_root) == "SES002"

    def test_legacy_agent_entries_are_not_sessions(self, arqux_env):
        from arqux.sessions import add_session_to_brain

        add_session_to_brain(arqux_env.proj_root, "test-governor", "governor")
        assert list_sessions(arqux_env.proj_root) == []
        assert next_session_id(arqux_env.proj_root) == "SES001"

    def test_lock_file_lives_under_arqux(self, arqux_env):
        from arqux.session_identity import lock_path

        assert lock_path(arqux_env.proj_root).parent == arqux_env.proj_root / ".arqux"
        assert not os.path.exists(os.environ.get("ARQUX_UNUSED", "/nonexistent"))
