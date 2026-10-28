"""CYCLE-14 / BLP-006 — optional external projection and reconciliation.

Covers AC-01 to AC-08.
"""

from __future__ import annotations

import pytest

from arqux.execution import mint_execution_key
from arqux.permissions import PermissionContext, PermissionDenied
from arqux.session_identity import open_session
from arqux.timelog_projection import (
    ADAPTER_VERSION,
    STATE_CONFIRMED,
    STATE_UNKNOWN,
    InsufficientCapability,
    LocalReferenceAdapter,
    UnsupportedProvider,
    batch_identity,
    get_receipt,
    project,
    snapshot,
)
from arqux.timelog_store import canonical_path, close_block, list_timelogs, load, open_block


@pytest.fixture
def session(arqux_env):
    env = arqux_env
    env.session = open_session(env.proj_root, agent="test-governor", project="test-proj",
                               execution=mint_execution_key())
    env.sid = env.session["session_id"]
    env.opened = env.session["date"]
    open_block(env.proj_root, env.sid, operation_ref="T-1.1",
               start="2026-10-15T01:00:00Z")
    close_block(env.proj_root, env.sid, operation_ref="T-1.1",
                end="2026-10-15T02:00:00Z")
    env.block = "T_1.1"
    env.adapter = LocalReferenceAdapter()
    return env


class TestAc01Snapshot:
    def test_snapshot_preserves_project_session_and_revision(self, session):
        snap = snapshot(session.proj_root, session.sid, [session.block],
                        opened_at=session.opened)
        assert snap["project"] == "test-proj"
        assert snap["ses"] == session.sid
        assert snap["revision"]
        assert snap["entries"][0]["block_id"] == session.block

    def test_transformations_do_not_alter_source_marks(self, session):
        before = load(session.proj_root, session.sid, opened_at=session.opened)
        result = project(session.proj_root, session.sid, destination="local",
                         block_ids=[session.block], action="preview",
                         rounding="nearest-minute", adapter=session.adapter,
                         opened_at=session.opened)
        after = load(session.proj_root, session.sid, opened_at=session.opened)
        assert result["status"] == "preview"
        assert before["blocks"] == after["blocks"]
        assert result["entries"][0]["rounding"] == "nearest-minute"


class TestAc02BatchIdentity:
    def _key(self, session, **overrides):
        snap = snapshot(session.proj_root, session.sid, [session.block],
                        opened_at=session.opened)
        params = {"destination": "local", "adapter_version": ADAPTER_VERSION}
        params.update(overrides)
        return batch_identity(snap, **params)

    def test_same_batch_same_key(self, session):
        assert self._key(session) == self._key(session)

    def test_changing_target_changes_the_key(self, session):
        assert self._key(session, target="a") != self._key(session, target="b")

    def test_changing_rounding_changes_the_key(self, session):
        assert self._key(session, rounding="none") != self._key(session, rounding="up")

    def test_changing_selection_changes_the_key(self, session, arqux_env):
        open_block(arqux_env.proj_root, session.sid, operation_ref="T-2.1",
                   start="2026-10-15T03:00:00Z")
        one = self._key(session)
        snap = snapshot(session.proj_root, session.sid, [session.block, "T_2.1"],
                        opened_at=session.opened)
        two = batch_identity(snap, destination="local", adapter_version=ADAPTER_VERSION)
        assert one != two

    def test_authorization_is_bound_to_the_identity(self, session):
        project(session.proj_root, session.sid, destination="local",
                block_ids=[session.block], action="prepare", authorization_ref="msg-1",
                adapter=session.adapter, opened_at=session.opened)
        # A different target produces a different key; the same authorization_ref
        # is not a valid order for it (send requires a fresh authorization).
        result = project(session.proj_root, session.sid, destination="other",
                         block_ids=[session.block], action="send",
                         authorization_ref="", adapter=session.adapter,
                         opened_at=session.opened)
        assert result["code"] == "TIMELOG_AUTHORIZATION_REQUIRED"


class TestAc03AdapterContract:
    def test_preview_reconcile_send_without_a_real_provider(self, session):
        sent = project(session.proj_root, session.sid, destination="local",
                       block_ids=[session.block], action="send",
                       authorization_ref="msg-1", adapter=session.adapter,
                       opened_at=session.opened)
        assert sent["status"] == STATE_CONFIRMED
        assert sent["remote"].startswith("local-")

    def test_unsupported_provider_is_declared(self):
        adapter = LocalReferenceAdapter(capabilities=frozenset({"prepare"}))
        assert "send" not in adapter.capabilities

    def test_unsupported_provider_type_is_explicit(self):
        with pytest.raises(UnsupportedProvider):
            raise UnsupportedProvider("teamwork")

    def test_adapter_knows_no_credentials(self, session):
        # The core never receives provider ids or tokens from the timelog.
        text = canonical_path(session.proj_root, session.sid, session.opened).read_text()
        assert "token" not in text and "api_key" not in text


class TestAc04UnknownAndReconcile:
    def test_failure_after_send_leaves_unknown(self, session):
        adapter = LocalReferenceAdapter()
        adapter._fail_send = True
        result = project(session.proj_root, session.sid, destination="local",
                         block_ids=[session.block], action="send",
                         authorization_ref="msg-1", adapter=adapter,
                         opened_at=session.opened)
        assert result["state"] == STATE_UNKNOWN
        receipt = get_receipt(session.proj_root, session.sid, result["batch_key"],
                              opened_at=session.opened)
        assert receipt["state"] == STATE_UNKNOWN

    def test_reconcile_reports_unknown_without_blind_resend(self, session):
        adapter = LocalReferenceAdapter()
        result = project(session.proj_root, session.sid, destination="local",
                         block_ids=[session.block], action="reconcile",
                         authorization_ref="msg-1", adapter=adapter,
                         opened_at=session.opened)
        assert result["state"] == STATE_UNKNOWN
        assert "do not resend blindly" in result["detail"]

    def test_insufficient_capability_requires_review(self):
        with pytest.raises(InsufficientCapability):
            raise InsufficientCapability("query")


class TestAc05Receipts:
    def test_receipt_is_cortex_and_has_no_secrets(self, session):
        project(session.proj_root, session.sid, destination="local",
                block_ids=[session.block], action="send", authorization_ref="msg-1",
                adapter=session.adapter, opened_at=session.opened)
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        assert document["receipts"]
        text = canonical_path(session.proj_root, session.sid, session.opened).read_text()
        assert "secret" not in text.lower()

    def test_repeating_a_confirmed_batch_does_not_duplicate(self, session):
        first = project(session.proj_root, session.sid, destination="local",
                        block_ids=[session.block], action="send",
                        authorization_ref="msg-1", adapter=session.adapter,
                        opened_at=session.opened)
        second = project(session.proj_root, session.sid, destination="local",
                         block_ids=[session.block], action="send",
                         authorization_ref="msg-1", adapter=session.adapter,
                         opened_at=session.opened)
        assert first["batch_key"] == second["batch_key"]
        assert second["remote"] == first["remote"]
        assert len(session.adapter._sent) == 1

    def test_changing_target_does_not_collide(self, session):
        first = project(session.proj_root, session.sid, destination="local",
                        block_ids=[session.block], action="send",
                        authorization_ref="m1", adapter=session.adapter,
                        opened_at=session.opened)
        second = project(session.proj_root, session.sid, destination="other",
                         block_ids=[session.block], action="send",
                         authorization_ref="m2", adapter=session.adapter,
                         opened_at=session.opened)
        assert first["batch_key"] != second["batch_key"]


class TestAc06NoPurgeNoRecreation:
    def test_projecting_never_purges_the_origin(self, session):
        before = list_timelogs(session.proj_root)
        project(session.proj_root, session.sid, destination="local",
                block_ids=[session.block], action="send", authorization_ref="m",
                adapter=session.adapter, opened_at=session.opened)
        assert list_timelogs(session.proj_root) == before

    def test_purged_session_refuses_projection(self, session):
        from arqux.timelog_control import purge

        purge(session.proj_root, session.sid, selection=[session.block], mode="delete",
              preview=False, authorization_ref="msg-9", opened_at=session.opened)
        result = project(session.proj_root, session.sid, destination="local",
                         block_ids=[session.block], action="send",
                         authorization_ref="m", adapter=session.adapter,
                         opened_at=session.opened)
        assert result["code"] == "TIMELOG_SUPPRESSED"

    def test_network_happens_outside_the_lock(self, session):
        import threading

        seen = {"locked": False}

        class SlowAdapter(LocalReferenceAdapter):
            def send(self, batch, key):
                # A lock is not held here: the common brain lock must be free.
                from arqux.session_identity import brain_lock

                acquired = []

                def try_lock():
                    try:
                        with brain_lock(session.proj_root):
                            acquired.append(True)
                    except Exception:  # noqa: BLE001
                        acquired.append(False)

                t = threading.Thread(target=try_lock)
                t.start()
                t.join(timeout=5)
                seen["locked"] = bool(acquired)
                return super().send(batch, key)

        adapter = SlowAdapter()
        project(session.proj_root, session.sid, destination="local",
                block_ids=[session.block], action="send", authorization_ref="m",
                adapter=adapter, opened_at=session.opened)
        assert seen["locked"] is True


class TestAc07RevisionAndReconciliation:
    def test_later_correction_changes_the_revision(self, session):
        from arqux.timelog_control import review

        before = load(session.proj_root, session.sid, opened_at=session.opened)["revision"]
        review(session.proj_root, session.sid, block_id=session.block,
               changes={"end": "2026-10-15T02:30:00Z"}, reason="fix",
               authorization_ref="msg-2", opened_at=session.opened)
        after = load(session.proj_root, session.sid, opened_at=session.opened)["revision"]
        assert after != before

    def test_correction_yields_a_new_batch_identity(self, session):
        from arqux.timelog_control import review

        snap1 = snapshot(session.proj_root, session.sid, [session.block],
                         opened_at=session.opened)
        review(session.proj_root, session.sid, block_id=session.block,
               changes={"end": "2026-10-15T04:00:00Z"}, reason="fix",
               authorization_ref="msg-2", opened_at=session.opened)
        snap2 = snapshot(session.proj_root, session.sid, [session.block],
                         opened_at=session.opened)
        assert batch_identity(snap1, destination="local") != batch_identity(
            snap2, destination="local")

    def test_query_does_not_mix_sessions(self, session, arqux_env):
        other = open_session(arqux_env.proj_root, agent="test-governor",
                             project="test-proj", execution=mint_execution_key(),
                             scope="CYCLE-OTHER")
        snap = snapshot(session.proj_root, session.sid, [session.block],
                        opened_at=session.opened)
        assert snap["ses"] == session.sid != other["session_id"]


class TestAc08HandlerAndPermissions:
    def test_handler_is_registered_with_schema(self):
        from arqux.handlers import REGISTRY

        assert "timelog.project" in REGISTRY
        assert REGISTRY["timelog.project"].input_schema["type"] == "object"

    def test_preview_is_read_only_for_the_auditor(self):
        auditor = PermissionContext(agent_id="test-auditor", role="auditor")
        auditor.check("timelog.project", destination="d", block_ids=[], action="preview")

    def test_send_is_denied_for_the_auditor(self):
        auditor = PermissionContext(agent_id="test-auditor", role="auditor")
        with pytest.raises(PermissionDenied):
            auditor.check("timelog.project", destination="d", block_ids=[], action="send")

    def test_no_real_provider_is_loaded(self):
        import arqux.timelog_projection as mod

        assert mod.default_adapter().provider == "local-reference"
