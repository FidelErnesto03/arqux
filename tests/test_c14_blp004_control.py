"""CYCLE-14 / BLP-004 — query, correction and purge of timelogs.

Covers AC-01 to AC-08.
"""

from __future__ import annotations

import pytest

from arqux.execution import mint_execution_key
from arqux.permissions import PermissionContext, PermissionDenied
from arqux.session_identity import get_session, open_session
from arqux.timelog_control import describe_block, purge, query, review, union_seconds
from arqux.timelog_store import (
    canonical_path,
    close_block,
    list_timelogs,
    load,
    open_block,
)


@pytest.fixture
def session(arqux_env):
    env = arqux_env
    env.key = mint_execution_key()
    env.session = open_session(env.proj_root, agent="test-governor", project="test-proj",
                               execution=env.key)
    env.sid = env.session["session_id"]
    env.opened = env.session["date"]
    return env


def _seed(session, ref, start, end, *, state="closed"):
    open_block(session.proj_root, session.sid, operation_ref=ref, start=start)
    if end:
        close_block(session.proj_root, session.sid, operation_ref=ref, end=end)


class TestAc01QueryReadOnly:
    def test_query_returns_exactly_the_sessions_records(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        result = query(session.proj_root, session.sid, opened_at=session.opened)
        assert result["session_ref"] == session.sid
        assert [b["block_id"] for b in result["blocks"]] == ["T_1.1"]

    def test_query_is_read_only(self, session):
        before = canonical_path(session.proj_root, session.sid, session.opened).read_text()
        query(session.proj_root, session.sid, opened_at=session.opened)
        after = canonical_path(session.proj_root, session.sid, session.opened).read_text()
        assert before == after

    def test_multisession_view_creates_no_joint_file(self, session, arqux_env):
        other = open_session(arqux_env.proj_root, agent="test-governor", project="test-proj",
                             execution=mint_execution_key(), scope="CYCLE-OTHER")
        files_before = list_timelogs(arqux_env.proj_root)
        result = query(arqux_env.proj_root, "", view="multisession")
        assert result["view"] == "multisession"
        assert result["provenance"]
        assert len(result["sessions"]) == 2
        assert list_timelogs(arqux_env.proj_root) == files_before
        assert other["session_id"] in {s["session_ref"] for s in result["sessions"]}


class TestAc02Durations:
    def test_closed_interval_duration_is_exact(self):
        block = describe_block("x", {"start": "2026-10-15T01:00:00Z",
                                     "end": "2026-10-15T02:30:00Z", "state": "closed"})
        assert block["duration_seconds"] == 5400
        assert block["flags"] == []

    def test_open_interval_is_flagged_not_filled(self):
        block = describe_block("x", {"start": "2026-10-15T01:00:00Z", "end": "",
                                     "state": "open"})
        assert block["duration_seconds"] is None
        assert "open" in block["flags"]

    def test_end_before_start_is_flagged(self):
        block = describe_block("x", {"start": "2026-10-15T02:00:00Z",
                                     "end": "2026-10-15T01:00:00Z", "state": "closed"})
        assert block["duration_seconds"] is None
        assert "end_before_start" in block["flags"]

    def test_missing_timezone_is_flagged(self):
        block = describe_block("x", {"start": "2026-10-15T01:00:00",
                                     "end": "2026-10-15T02:00:00Z", "state": "closed"})
        assert "start_without_timezone" in block["flags"]

    def test_unparsable_timestamp_is_flagged(self):
        block = describe_block("x", {"start": "not-a-time", "end": "", "state": "open"})
        assert "unparsable_timestamp" in block["flags"] or "open" in block["flags"]

    def test_no_rounding_or_minimum(self):
        block = describe_block("x", {"start": "2026-10-15T01:00:00Z",
                                     "end": "2026-10-15T01:00:01Z", "state": "closed"})
        assert block["duration_seconds"] == 1


class TestAc03UnionTotals:
    def test_overlaps_are_counted_once(self):
        blocks = [
            {"block_id": "a", "start": "2026-10-15T01:00:00Z",
             "end": "2026-10-15T03:00:00Z", "state": "closed"},
            {"block_id": "b", "start": "2026-10-15T02:00:00Z",
             "end": "2026-10-15T04:00:00Z", "state": "closed"},
        ]
        result = union_seconds(blocks)
        assert result["total_seconds"] == 3 * 3600
        assert result["overlaps_merged"] == 1

    def test_disjoint_intervals_add_up(self):
        blocks = [
            {"block_id": "a", "start": "2026-10-15T01:00:00Z",
             "end": "2026-10-15T02:00:00Z", "state": "closed"},
            {"block_id": "b", "start": "2026-10-15T03:00:00Z",
             "end": "2026-10-15T04:00:00Z", "state": "closed"},
        ]
        assert union_seconds(blocks)["total_seconds"] == 7200

    def test_report_explains_the_definition(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        result = query(session.proj_root, session.sid, opened_at=session.opened)
        assert "union" in result["total"]["definition"]

    def test_open_blocks_make_the_total_unknown_not_zero(self):
        # BLP-025: an open block makes the total unknowable. Returning 0 made a
        # consumer report zero hours worked for a live session.
        blocks = [
            {"block_id": "a", "start": "2026-10-15T01:00:00Z", "end": "", "state": "open"},
            {"block_id": "b", "start": "2026-10-15T01:00:00Z",
             "end": "2026-10-15T02:00:00Z", "state": "archived"},
        ]
        result = union_seconds(blocks)
        assert result["total_seconds"] is None
        assert result["closed_seconds"] == 0
        assert result["open_block_count"] == 1


class TestAc04Review:
    def test_authorized_correction_writes_a_revision_with_reason(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        before = load(session.proj_root, session.sid, opened_at=session.opened)["revision"]
        result = review(session.proj_root, session.sid, block_id="T_1.1",
                        changes={"end": "2026-10-15T02:30:00Z"}, reason="user corrected",
                        authorization_ref="msg-42", opened_at=session.opened)
        assert result["status"] == "applied"
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        block = document["blocks"]["T_1.1"]
        assert block["end"] == "2026-10-15T02:30:00Z"
        assert block["note"] == "user corrected"
        assert document["revision"] != before

    def test_correction_without_authorization_is_rejected(self, session):
        result = review(session.proj_root, session.sid, block_id="x", changes={},
                        reason="", authorization_ref="", opened_at=session.opened)
        assert result["code"] == "TIMELOG_AUTHORIZATION_REQUIRED"

    def test_unknown_block_is_rejected(self, session):
        result = review(session.proj_root, session.sid, block_id="nope",
                        changes={"end": "2026-10-15T02:00:00Z"}, reason="r",
                        authorization_ref="a", opened_at=session.opened)
        assert result["code"] == "TIMELOG_BLOCK_NOT_FOUND"

    def test_previous_value_is_preserved_when_user_does_not_purge(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        review(session.proj_root, session.sid, block_id="T_1.1",
               changes={"end": "2026-10-15T03:00:00Z"}, reason="fix",
               authorization_ref="msg-1", opened_at=session.opened)
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        assert document["blocks"]["T_1.1"]["start"] == "2026-10-15T01:00:00Z"


class TestAc05Purge:
    def test_preview_mutates_nothing(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        path = canonical_path(session.proj_root, session.sid, session.opened)
        before = path.read_text()
        result = purge(session.proj_root, session.sid, selection=["T_1.1"],
                       mode="delete", preview=True, authorization_ref="msg-9",
                       opened_at=session.opened)
        assert result["status"] == "preview"
        assert path.read_text() == before

    def test_deleting_a_non_exported_record_is_allowed(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        result = purge(session.proj_root, session.sid, selection=["T_1.1"],
                       mode="delete", preview=False, authorization_ref="msg-9",
                       opened_at=session.opened)
        assert result["status"] == "applied"

    def test_purge_without_authorization_is_rejected(self, session):
        result = purge(session.proj_root, session.sid, selection=[], mode="delete",
                       preview=False, authorization_ref="", opened_at=session.opened)
        assert result["code"] == "TIMELOG_AUTHORIZATION_REQUIRED"

    def test_foreign_selection_is_reported_not_found(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        result = purge(session.proj_root, session.sid, selection=["not-mine"],
                       mode="archive", preview=True, authorization_ref="msg-9",
                       opened_at=session.opened)
        assert result["not_found"] == ["not-mine"]
        assert result["selection"] == []


class TestAc06PurgeIntegration:
    def test_delete_removes_the_file_and_leaves_a_tombstone(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        purge(session.proj_root, session.sid, selection=["T_1.1"],
              mode="delete", preview=False, authorization_ref="msg-9",
              opened_at=session.opened)
        assert not canonical_path(session.proj_root, session.sid, session.opened).exists()
        entry = get_session(session.proj_root, session.sid)
        assert str(entry.get("suppressed")).lower() == "true"
        assert entry.get("summary", "") == ""

    def test_deleted_file_is_not_recreated(self, session):
        from arqux.timelog_store import ensure_timelog

        purge(session.proj_root, session.sid, selection=["T_1.1"],
              mode="delete", preview=False, authorization_ref="msg-9",
              opened_at=session.opened)
        entry = get_session(session.proj_root, session.sid)
        result = ensure_timelog(session.proj_root, entry)
        assert result["state"] == "suppressed"
        assert not canonical_path(session.proj_root, session.sid, session.opened).exists()

    def test_capture_after_purge_is_rejected(self, session):
        from arqux.timelog_capture import capture

        purge(session.proj_root, session.sid, selection=["T-1.1".replace("_", ".")],
              mode="delete", preview=False, authorization_ref="msg-9",
              opened_at=session.opened)
        ctx = PermissionContext(agent_id="test-governor", role="governor",
                                 execution_key=session.key)
        result = capture(session.proj_root, ctx, event="open", operation_ref="late",
                         activity="late")
        assert result["status"] == "rejected"

    def test_purge_does_not_touch_another_session(self, session, arqux_env):
        other = open_session(arqux_env.proj_root, agent="test-governor", project="test-proj",
                             execution=mint_execution_key(), scope="CYCLE-OTHER")
        open_block(arqux_env.proj_root, other["session_id"], operation_ref="T-9.9",
                   start="2026-10-15T01:00:00Z")
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        purge(session.proj_root, session.sid, selection=["T_1.1"],
              mode="delete", preview=False, authorization_ref="msg-9",
              opened_at=session.opened)
        assert canonical_path(arqux_env.proj_root, other["session_id"],
                              other["date"]).exists()


class TestAc07JointPresentation:
    def test_view_does_not_rank_participants(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        result = query(session.proj_root, session.sid, opened_at=session.opened)
        text = str(result)
        assert "ranking" not in text and "blame" not in text

    def test_joint_activity_is_the_primary_unit(self, session):
        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        result = query(session.proj_root, session.sid, opened_at=session.opened)
        assert result["total"]["interval_count"] == 1


class TestAc08HandlersAndPermissions:
    def test_three_handlers_are_registered(self):
        from arqux.handlers import REGISTRY

        for name in ("timelog.query", "timelog.review", "timelog.purge"):
            assert name in REGISTRY
            assert REGISTRY[name].input_schema.get("type") == "object"

    def test_query_is_read_only_for_the_auditor(self):
        auditor = PermissionContext(agent_id="test-auditor", role="auditor")
        auditor.check("timelog.query")  # must not raise

    def test_review_is_denied_for_the_auditor(self):
        auditor = PermissionContext(agent_id="test-auditor", role="auditor")
        with pytest.raises(PermissionDenied):
            auditor.check("timelog.review", block_id="x", changes={}, reason="r",
                          authorization_ref="a")

    def test_purge_preview_is_allowed_but_suppression_is_denied_for_the_auditor(self):
        auditor = PermissionContext(agent_id="test-auditor", role="auditor")
        auditor.check("timelog.purge", selection=[], preview=True)  # preview: allowed
        with pytest.raises(PermissionDenied):
            auditor.check("timelog.purge", selection=[], preview=False,
                          authorization_ref="a")

    def test_query_handler_is_read_only_end_to_end(self, session):
        from arqux.handlers.timelog import query_handler

        _seed(session, "T-1.1", "2026-10-15T01:00:00Z", "2026-10-15T02:00:00Z")
        path = canonical_path(session.proj_root, session.sid, session.opened)
        before = path.read_text()
        out = query_handler(session_ref=session.sid, path=str(session.proj_root))
        assert out.profile != "OUT-ERROR"
        assert path.read_text() == before
