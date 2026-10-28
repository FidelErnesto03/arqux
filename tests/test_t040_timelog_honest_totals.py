"""CYCLE-12 / BLP-025 — the timelog answers "how much so far" by itself.

Issue 2026-10-26: an open session returned ``duration_seconds: None`` and
``total_seconds: 0``. Zero and unknown are different answers, and the number
given to the Architect was computed outside the MCP with the system clock.
These tests pin the contract: the server stamps the heartbeat, computes the
elapsed window, returns ``null`` for an unknowable total, and serializes
nested structures as JSON.
"""

from __future__ import annotations

import json
import time

import pytest

from arqux.cortex_out import CortexOUT
from arqux.execution import mint_execution_key
from arqux.session_identity import open_session
from arqux.timelog_capture import capture
from arqux.timelog_control import describe_block, summary, union_seconds
from arqux.timelog_store import close_block, load, open_block, touch


@pytest.fixture
def session(arqux_env):
    env = arqux_env
    env.key = mint_execution_key()
    env.session = open_session(env.proj_root, agent="test-governor", project="test-proj",
                               execution=env.key)
    env.sid = env.session["session_id"]
    env.opened = env.session["date"]
    return env


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class TestHeartbeat:
    def test_open_block_carries_last_activity(self, session):
        open_block(session.proj_root, session.sid, operation_ref="session",
                   start="2026-10-15T01:00:00Z")
        block = load(session.proj_root, session.sid,
                     opened_at=session.opened)["blocks"]["session"]
        assert block["last_activity"] == "2026-10-15T01:00:00Z"

    def test_touch_moves_the_heartbeat(self, session):
        open_block(session.proj_root, session.sid, operation_ref="session",
                   start="2026-10-15T01:00:00Z")
        touch(session.proj_root, session.sid, at="2026-10-15T03:30:00Z",
              opened_at=session.opened)
        block = load(session.proj_root, session.sid,
                     opened_at=session.opened)["blocks"]["session"]
        assert block["last_activity"] == "2026-10-15T03:30:00Z"

    def test_governance_boundary_stamps_the_heartbeat(self, session):
        open_block(session.proj_root, session.sid, operation_ref="session",
                   start="2026-10-15T01:00:00Z")
        capture(session.proj_root, None, event="boundary", operation_ref="session",
                activity="session", session_ref=session.sid)
        block = load(session.proj_root, session.sid,
                     opened_at=session.opened)["blocks"]["session"]
        assert block["last_activity"] and block["last_activity"] != "2026-10-15T01:00:00Z"

    def test_checkpoint_stamps_the_heartbeat(self, session):
        from arqux.handlers.cortex.checkpoint import checkpoint_handler
        from arqux.permissions import PermissionContext

        open_block(session.proj_root, session.sid, operation_ref="session",
                   start="2026-10-15T01:00:00Z")
        ctx = PermissionContext(agent_id="test-governor", role="governor",
                                execution_key=session.key)
        checkpoint_handler(content="fcs:seguir; obj:probar", path=str(session.proj_root),
                           ctx=ctx)
        block = load(session.proj_root, session.sid,
                     opened_at=session.opened)["blocks"]["session"]
        assert block["last_activity"] and block["last_activity"] != "2026-10-15T01:00:00Z"


class TestHonestTotals:
    def test_open_block_exposes_server_elapsed_as_window(self):
        described = describe_block("x", {"start": "2026-10-15T01:00:00Z",
                                         "end": "", "state": "open",
                                         "last_activity": "2026-10-15T01:05:00Z"})
        assert described["duration_seconds"] is None
        assert described["elapsed_seconds"] is not None
        assert described["elapsed_seconds"] > 0
        assert described["elapsed_is_window"] is True
        assert described["as_of"]
        assert described["last_activity"] == "2026-10-15T01:05:00Z"

    def test_total_is_null_while_a_block_is_open(self):
        blocks = [
            {"block_id": "a", "start": _now_iso(), "end": "", "state": "open"},
            {"block_id": "b", "start": "2026-10-15T01:00:00Z",
             "end": "2026-10-15T02:00:00Z", "state": "closed"},
        ]
        result = union_seconds(blocks)
        assert result["total_seconds"] is None
        assert result["closed_seconds"] == 3600
        assert result["open_block_count"] == 1
        assert result["as_of"]

    def test_closed_timelog_still_reports_a_number(self):
        result = union_seconds([
            {"block_id": "a", "start": "2026-10-15T01:00:00Z",
             "end": "2026-10-15T02:00:00Z", "state": "closed"},
        ])
        assert result["total_seconds"] == 3600
        assert result["open_block_count"] == 0


class TestMachineReadable:
    def test_nested_structures_render_as_json(self):
        payload = {"sessions": [{"session_ref": "SES001", "total": {"closed_seconds": 60}}]}
        text = CortexOUT.work("ok", **payload).to_text()
        encoded = text.split("sessions=", 1)[1].rsplit(" ok", 1)[0]
        assert json.loads(encoded) == payload["sessions"]

    def test_flat_lists_keep_the_historical_form(self):
        assert CortexOUT._format_value(["a", "b"]) == "a,b"


class TestSummary:
    def test_summary_by_session(self, session):
        open_block(session.proj_root, session.sid, operation_ref="T-1.1",
                   start="2026-10-15T01:00:00Z")
        close_block(session.proj_root, session.sid, operation_ref="T-1.1",
                    end="2026-10-15T02:00:00Z")
        result = summary(session.proj_root, session.sid, period="session")
        assert result["period"] == "session"
        assert result["total"]["total_seconds"] == 3600
        assert result["window_vs_productive"]

    def test_summary_by_day_counts_blocks_started_today(self, session):
        open_block(session.proj_root, session.sid, operation_ref="today",
                   start=_now_iso())
        close_block(session.proj_root, session.sid, operation_ref="today",
                    end=_now_iso())
        open_block(session.proj_root, session.sid, operation_ref="old",
                   start="2026-10-15T01:00:00Z")
        close_block(session.proj_root, session.sid, operation_ref="old",
                    end="2026-10-15T02:00:00Z")
        result = summary(session.proj_root, session.sid, period="day")
        assert result["day"] == _now_iso()[:10]
        assert result["total"]["closed_seconds"] < 3600

    def test_summary_by_project_aggregates_sessions(self, session, arqux_env):
        open_block(session.proj_root, session.sid, operation_ref="a",
                   start="2026-10-15T01:00:00Z")
        close_block(session.proj_root, session.sid, operation_ref="a",
                    end="2026-10-15T02:00:00Z")
        from tests.conftest import rotate_session

        other = rotate_session(arqux_env.proj_root, scope="CYCLE-OTHER")
        open_block(arqux_env.proj_root, other["session_id"], operation_ref="b",
                   start="2026-10-16T01:00:00Z")
        close_block(arqux_env.proj_root, other["session_id"], operation_ref="b",
                    end="2026-10-16T02:00:00Z")
        result = summary(arqux_env.proj_root, session.sid, period="project")
        assert {s["session_ref"] for s in result["sessions"]} == {session.sid,
                                                                  other["session_id"]}
        assert result["total"]["closed_seconds"] == 7200

    def test_unknown_period_is_rejected(self, session):
        result = summary(session.proj_root, session.sid, period="year")
        assert result["code"] == "TIMELOG_INVALID_PERIOD"


class TestQueryThroughTheHandler:
    def test_multisession_handler_output_is_json(self, session):
        from arqux.handlers.timelog import query_handler

        open_block(session.proj_root, session.sid, operation_ref="session",
                   start=_now_iso())
        result = query_handler(view="multisession", path=str(session.proj_root),
                               ctx=None)
        assert result.profile == "OUT-WORK"
        text = result.to_text()
        encoded = text.split("sessions=", 1)[1].rsplit(" timelog.query ok", 1)[0]
        decoded = json.loads(encoded)
        assert decoded and decoded[0]["session_ref"] == session.sid
        assert decoded[0]["total"]["total_seconds"] is None

    def test_session_view_reports_open_elapsed(self, session):
        from arqux.handlers.timelog import query_handler

        open_block(session.proj_root, session.sid, operation_ref="session",
                   start=_now_iso())
        result = query_handler(view="session", session_ref=session.sid,
                               path=str(session.proj_root))
        blocks = result.fields["blocks"]
        assert blocks[0]["elapsed_seconds"] is not None
        assert result.fields["total"]["total_seconds"] is None
