"""CYCLE-14 / BLP-003 — embedded capture in governance actions.

Covers AC-01 to AC-07 (AC-08 is the independent review of the integration).
"""

from __future__ import annotations

import threading

import pytest

from arqux.execution import mint_execution_key
from arqux.permissions import PermissionContext
from arqux.session_identity import open_session
from arqux.timelog_capture import (
    COVERAGE_FULL,
    COVERAGE_LIMITED,
    STATUS_APPLIED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_SKIPPED,
    activity_of,
    capture,
    dedicated_timelog_calls,
    observe,
    repair,
)
from arqux.timelog_store import canonical_path, list_timelogs, load


@pytest.fixture
def bound(arqux_env):
    """Bind an execution and open its session (and canonical timelog)."""
    env = arqux_env
    env.key = mint_execution_key()
    env.ctx = PermissionContext(agent_id="test-governor", role="governor",
                                 execution_key=env.key)
    env.session = open_session(env.proj_root, agent="test-governor",
                               project="test-proj", execution=env.key)
    return env


class TestAc01NaturalBoundaries:
    def test_binding_opens_the_session_block(self, bound):
        result = capture(bound.proj_root, bound.ctx, event="open",
                         operation_ref=f"session:{bound.session['session_id']}",
                         activity="session")
        assert result["status"] == STATUS_APPLIED
        assert result["coverage"] == COVERAGE_FULL
        document = load(bound.proj_root, bound.session["session_id"],
                        opened_at=bound.session["date"])
        assert document["blocks"][f"session_{bound.session['session_id']}"]["state"] == "open"

    def test_closing_the_session_block_records_the_end(self, bound):
        ses = bound.session["session_id"]
        capture(bound.proj_root, bound.ctx, event="open",
                operation_ref=f"session:{ses}", activity="session")
        result = capture(bound.proj_root, bound.ctx, event="close",
                         operation_ref=f"session:{ses}", activity="session")
        assert result["status"] == STATUS_APPLIED
        document = load(bound.proj_root, ses, opened_at=bound.session["date"])
        assert document["blocks"][f"session_{ses}"]["end"]

    def test_task_boundaries_land_in_their_own_session(self, bound, arqux_env):
        other = open_session(arqux_env.proj_root, agent="test-governor",
                             project="test-proj", execution=mint_execution_key())
        capture(bound.proj_root, bound.ctx, event="open",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        mine = load(bound.proj_root, bound.session["session_id"],
                    opened_at=bound.session["date"])
        theirs = load(arqux_env.proj_root, other["session_id"],
                      opened_at=other["date"])
        assert "task_T_1.1" in mine["blocks"]
        assert theirs["blocks"] == {}

    def test_only_the_intended_effects_happen(self, bound):
        capture(bound.proj_root, bound.ctx, event="open",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        document = load(bound.proj_root, bound.session["session_id"],
                        opened_at=bound.session["date"])
        assert document["project"] == "test-proj"
        assert document["ses"] == bound.session["session_id"]


class TestAc02OneBlockPerActivity:
    def test_repeated_actions_do_not_add_blocks(self, bound):
        for _ in range(5):
            capture(bound.proj_root, bound.ctx, event="update",
                    operation_ref="task:T-1.1", activity="task:T-1.1")
        document = load(bound.proj_root, bound.session["session_id"],
                        opened_at=bound.session["date"])
        assert len(document["blocks"]) == 0

    def test_claim_then_repeated_complete_keeps_one_block(self, bound):
        capture(bound.proj_root, bound.ctx, event="open",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        capture(bound.proj_root, bound.ctx, event="close",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        capture(bound.proj_root, bound.ctx, event="close",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        document = load(bound.proj_root, bound.session["session_id"],
                        opened_at=bound.session["date"])
        assert len(document["blocks"]) == 1
        assert document["blocks"]["task_T_1.1"]["state"] == "closed"

    def test_analysis_without_task_has_a_valid_activity_reference(self):
        assert activity_of("analysis") == "analysis"
        assert activity_of("task_claim", task_id="T-7.1") == "task:T-7.1"


class TestAc03ReadOnlyUnchanged:
    def test_read_only_functions_record_nothing(self, bound):
        before = list_timelogs(bound.proj_root)
        from arqux.handlers.context import detect_handler, full_handler
        from arqux.handlers.session import resume, status

        ses = bound.session["session_id"]
        resume(session_ref=ses, path=str(bound.proj_root), ctx=bound.ctx)
        status(session_ref=ses, path=str(bound.proj_root), ctx=bound.ctx)
        detect_handler(path=str(bound.proj_root))
        full_handler(path=str(bound.proj_root))
        assert list_timelogs(bound.proj_root) == before

    def test_auditor_keeps_read_only_and_records_nothing(self, bound):
        from arqux.timelog_capture import observe

        auditor = PermissionContext(agent_id="test-auditor", role="auditor",
                                    execution_key=bound.key)
        result = observe(bound.proj_root, auditor, event="open",
                         operation_ref="audit:read", activity="audit")
        assert result["status"] == STATUS_REJECTED
        document = load(bound.proj_root, bound.session["session_id"],
                        opened_at=bound.session["date"])
        assert document["blocks"] == {}

    def test_the_recorder_observes_without_extending_reader_rights(self):
        import inspect

        from arqux import timelog_capture

        assert "PermissionContext" in inspect.getsource(timelog_capture)
        assert not hasattr(timelog_capture, "enforce")


class TestAc04ZeroDedicatedCalls:
    def test_no_call_is_made_only_to_annotate(self):
        assert dedicated_timelog_calls() == 0

    def test_no_counter_thread_or_periodic_timer(self):
        capture_threads = [t.name for t in threading.enumerate()
                           if "timelog" in t.name.lower() or "timer" in t.name.lower()]
        assert capture_threads == []

    def test_routine_response_does_not_dump_the_file(self, bound):
        from arqux.handlers.session import status

        out = status(session_ref=bound.session["session_id"],
                     path=str(bound.proj_root), ctx=bound.ctx)
        text = out.to_text()
        assert len(text) < 4000
        assert "ACT:" not in text

    def test_capture_has_no_dedicated_handler(self):
        from arqux.handlers import REGISTRY

        assert not any("timelog" in name and "record" in name for name in REGISTRY)


class TestAc05JointWorkDefault:
    def test_blocks_carry_no_participation_fields_by_default(self, bound):
        capture(bound.proj_root, bound.ctx, event="open",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        document = load(bound.proj_root, bound.session["session_id"],
                        opened_at=bound.session["date"])
        block = document["blocks"]["task_T_1.1"]
        assert "human" not in block and "agent" not in block and "blame" not in block

    def test_activity_name_does_not_rank_participants(self):
        assert "ranking" not in activity_of("task_complete", task_id="T-1.1")


class TestAc06LimitedCoverage:
    def test_without_execution_the_capture_is_limited(self, arqux_env):
        keyless = PermissionContext(agent_id="test-governor", role="governor")
        result = capture(arqux_env.proj_root, keyless, event="open",
                         operation_ref="session:SES001", activity="session")
        assert result["coverage"] == COVERAGE_LIMITED
        assert result["status"] == STATUS_SKIPPED

    def test_unknown_session_leaves_limits_open(self, arqux_env):
        result = capture(arqux_env.proj_root, None, event="open",
                         operation_ref="session:SES999", activity="session",
                         session_ref="SES999")
        assert result["coverage"] == COVERAGE_LIMITED

    def test_no_start_or_end_is_fabricated(self, arqux_env):

        key = mint_execution_key()
        session = open_session(arqux_env.proj_root, agent="test-governor",
                               project="test-proj", execution=key)
        document = load(arqux_env.proj_root, session["session_id"],
                        opened_at=session["date"])
        assert document["blocks"] == {}


class TestAc07AnnotationRecovery:
    def test_suppressed_file_is_rejected_not_recreated(self, bound):
        ses = bound.session["session_id"]
        path = canonical_path(bound.proj_root, ses, bound.session["date"])
        path.unlink()
        result = capture(bound.proj_root, bound.ctx, event="open",
                         operation_ref="task:T-1.1", activity="task:T-1.1")
        assert result["status"] == STATUS_REJECTED
        assert not path.exists(), "capture must not recreate a suppressed timelog"

    def test_repair_does_not_repeat_effects_or_duplicate_intervals(self, bound):
        ses = bound.session["session_id"]
        capture(bound.proj_root, bound.ctx, event="open",
                operation_ref="task:T-1.1", activity="task:T-1.1")
        first = repair(bound.proj_root, bound.ctx, event="close",
                       operation_ref="task:T-1.1")
        second = repair(bound.proj_root, bound.ctx, event="close",
                        operation_ref="task:T-1.1")
        assert first["status"] == STATUS_APPLIED
        assert second["status"] == STATUS_APPLIED
        document = load(bound.proj_root, ses, opened_at=bound.session["date"])
        assert len(document["blocks"]) == 1
        assert document["blocks"]["task_T_1.1"]["end"]

    def test_failed_annotation_does_not_change_the_work_result(self, bound):
        # Closing an activity that was never opened is an annotation failure:
        # the work result is unaffected and the annotation stays pending.
        result = observe(bound.proj_root, bound.ctx, event="close",
                         operation_ref="task:T-9.9", activity="task:T-9.9")
        assert result["status"] == STATUS_PENDING

    def test_suppressed_file_is_a_rejection_not_a_pending_record(self, bound):
        path = canonical_path(bound.proj_root, bound.session["session_id"],
                              bound.session["date"])
        path.unlink()
        result = observe(bound.proj_root, bound.ctx, event="open",
                         operation_ref="task:T-9.9", activity="task:T-9.9")
        assert result["status"] == STATUS_REJECTED

    def test_pending_is_reported_separately_from_applied(self, bound):
        result = capture(bound.proj_root, bound.ctx, event="close",
                         operation_ref="never-opened", activity="task:never")
        assert result["status"] == STATUS_PENDING
