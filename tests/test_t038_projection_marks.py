"""T-038 — native projection marks (PRJ / $4: PROJECTIONS) in the session timelog.

The native timelog must answer "has this block already been projected, and as
what?" from the file alone. Closes issue
2026-10-22-design-gap-no-native-projection-marks-in-arqux-t.
"""

from __future__ import annotations

import pytest

from arqux.execution import mint_execution_key
from arqux.session_identity import open_session
from arqux.timelog_control import query, review
from arqux.timelog_projection import (
    STATE_CONFIRMED,
    STATE_SENT,
    STATE_UNKNOWN,
    LocalReferenceAdapter,
    project,
)
from arqux.timelog_store import canonical_path, close_block, load, open_block


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


def _send(session, *, destination="local", agent="alfred", adapter=None):
    return project(session.proj_root, session.sid, destination=destination,
                   block_ids=[session.block], action="send", authorization_ref="msg-1",
                   adapter=adapter or session.adapter, agent=agent,
                   opened_at=session.opened)


class TestAc01Schema:
    def test_prj_is_declared_and_the_section_is_present(self, session):
        _send(session)
        text = canonical_path(session.proj_root, session.sid, session.opened).read_text()
        assert "$0: TIMLOG LOCAL GLOSSARY" in text
        assert "PRJ" in text and "projection" in text
        assert "$4: PROJECTIONS" in text
        assert text.index("$0") < text.index("$4")

    def test_official_reader_accepts_the_extended_schema(self, session):
        from arqux.state import cortex_read

        _send(session)
        path = canonical_path(session.proj_root, session.sid, session.opened)
        doc = cortex_read(str(path))
        ids = [s["id"] for s in doc["sections"]]
        assert ids == ["$0", "$1", "$2", "$3", "$4"], ids

    def test_round_trip_is_lossless_with_a_mark(self, session):
        from arqux.timelog_store import _parse, _serialize

        _send(session)
        path = canonical_path(session.proj_root, session.sid, session.opened)
        original = path.read_text(encoding="utf-8")
        once = _serialize(_parse(original))
        twice = _serialize(_parse(once))
        assert once == twice, "the serializer is not deterministic"
        assert "PRJ:" in once

    def test_load_exposes_the_projections_key(self, session):
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        assert document["projections"] == {}


class TestAc02MarkContent:
    def test_send_writes_destination_remote_and_origin(self, session):
        _send(session, destination="local", agent="alfred")
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        marks = list(document["projections"].values())
        assert len(marks) == 1
        mark = marks[0]
        assert mark["operation"] == "timelog.project"
        assert mark["destination"] == "local"
        assert mark["remote"].startswith("local-")
        assert mark["state"] == STATE_CONFIRMED
        assert mark["blocks"].startswith(f"{session.block}@")
        assert mark["agent"] == "alfred"
        assert mark["projected_at"]

    def test_mark_records_the_projected_interval(self, session):
        _send(session)
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        mark = next(iter(document["projections"].values()))
        assert mark["start"] == "2026-10-15T01:00:00Z"
        assert mark["end"] == "2026-10-15T02:00:00Z"
        assert mark["minutes"] == "60"

    def test_mark_carries_no_secrets(self, session):
        _send(session)
        text = canonical_path(session.proj_root, session.sid, session.opened).read_text()
        assert "token" not in text and "api_key" not in text and "secret" not in text.lower()


class TestAc03Atomicity:
    def test_mark_is_persisted_before_the_network(self, session):
        seen: dict[str, object] = {}

        class PeekAdapter(LocalReferenceAdapter):
            def send(self, batch, key):
                document = load(session.proj_root, session.sid, opened_at=session.opened)
                seen["marks"] = dict(document["projections"])
                return super().send(batch, key)

        _send(session, adapter=PeekAdapter())
        marks = seen.get("marks") or {}
        assert marks, "no native mark existed before dispatch"
        mark = next(iter(marks.values()))
        assert mark["state"] == STATE_SENT

    def test_failed_send_still_leaves_a_mark(self, session):
        adapter = LocalReferenceAdapter()
        adapter._fail_send = True
        result = _send(session, adapter=adapter)
        assert result["state"] == STATE_UNKNOWN
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        mark = next(iter(document["projections"].values()))
        assert mark["state"] == STATE_UNKNOWN
        assert mark["remote"] == ""


class TestAc04PluralMarks:
    def test_two_providers_produce_two_marks_without_overwrite(self, session):
        _send(session, destination="local")
        _send(session, destination="other")
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        marks = list(document["projections"].values())
        assert len(marks) == 2
        assert {m["destination"] for m in marks} == {"local", "other"}

    def test_repeating_the_same_batch_does_not_add_a_mark(self, session):
        _send(session)
        _send(session)
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        assert len(document["projections"]) == 1


class TestAc05Query:
    def test_query_exposes_the_projection_registry(self, session):
        _send(session, destination="local")
        result = query(session.proj_root, session.sid, opened_at=session.opened)
        assert len(result["projections"]) == 1
        mark = result["projections"][0]
        assert mark["destination"] == "local"
        assert mark["block_ids"] == [session.block]
        assert mark["interval"]["minutes"] == "60"

    def test_block_entry_reports_where_it_was_projected(self, session):
        _send(session, destination="local")
        result = query(session.proj_root, session.sid, opened_at=session.opened)
        block = result["blocks"][0]
        assert [p["destination"] for p in block["projections"]] == ["local"]

    def test_query_is_read_only_with_marks_present(self, session):
        _send(session)
        path = canonical_path(session.proj_root, session.sid, session.opened)
        before = path.read_text()
        query(session.proj_root, session.sid, opened_at=session.opened)
        assert path.read_text() == before


class TestAc06Review:
    def test_review_of_a_projected_block_marks_it_stale(self, session):
        _send(session)
        review(session.proj_root, session.sid, block_id=session.block,
               changes={"end": "2026-10-15T02:30:00Z"}, reason="fix",
               authorization_ref="msg-2", opened_at=session.opened)
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        mark = next(iter(document["projections"].values()))
        assert mark["status"] == "stale"

    def test_review_of_an_unrelated_block_leaves_the_mark_untouched(self, session):
        _send(session)
        open_block(session.proj_root, session.sid, operation_ref="T-2.1",
                   start="2026-10-15T03:00:00Z")
        review(session.proj_root, session.sid, block_id="T_2.1",
               changes={"end": "2026-10-15T04:00:00Z"}, reason="fix",
               authorization_ref="msg-2", opened_at=session.opened)
        document = load(session.proj_root, session.sid, opened_at=session.opened)
        mark = next(iter(document["projections"].values()))
        assert mark["status"] != "stale"
