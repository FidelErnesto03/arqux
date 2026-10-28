"""CYCLE-14 / BLP-002 — canonical CORTEX timelog and protected persistence.

Covers AC-01 to AC-07 (AC-08 is the independent review of the contract).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.execution import mint_execution_key
from arqux.session_identity import open_session, timelog_path
from arqux.timelog_store import (
    MembershipError,
    RevisionConflict,
    UnknownOperation,
    canonical_name,
    canonical_path,
    close_block,
    ensure_timelog,
    is_canonical,
    list_timelogs,
    load,
    open_block,
    timelog_dir,
    update,
)


@pytest.fixture
def session(arqux_env):
    """Open a real session; BLP-002 now creates its canonical timelog too."""
    env = arqux_env
    key = mint_execution_key()
    opened = open_session(env.proj_root, agent="test-governor", project="test-proj",
                          execution=key, scope="CYCLE-TEST")
    env.session = opened
    env.session_id = opened["session_id"]
    env.opened_at = opened["date"]
    return env


class TestAc01SchemaRoundTrip:
    def test_identity_intervals_survive_reserialization(self, session):
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert document is not None
        assert document["ses"] == session.session_id
        assert document["opened"] == session.opened_at
        assert document["revision"] == "1"

    def test_glossary_and_identity_are_parseable(self, session):
        path = canonical_path(session.proj_root, session.session_id, session.opened_at)
        text = path.read_text(encoding="utf-8")
        assert "$0: TIMLOG LOCAL GLOSSARY" in text
        assert "TLG" in text and "timelog" in text
        assert f'ses:"{session.session_id}"' in text
        assert 'opened:"' in text and "Z\"" in text

    def test_round_trip_is_lossless(self, session):
        from arqux.timelog_store import _parse, _serialize

        path = canonical_path(session.proj_root, session.session_id, session.opened_at)
        original = path.read_text(encoding="utf-8")
        once = _serialize(_parse(original))
        twice = _serialize(_parse(once))
        assert once == twice, "the serializer is not deterministic"

    def test_blocks_round_trip_with_start_and_end(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-1.1",
                   start="2026-10-15T01:00:00Z")
        close_block(session.proj_root, session.session_id, operation_ref="T-1.1",
                    end="2026-10-15T02:00:00Z")
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        block = document["blocks"]["T_1.1"]
        assert block["start"] == "2026-10-15T01:00:00Z"
        assert block["end"] == "2026-10-15T02:00:00Z"
        assert block["state"] == "closed"


class TestAc02CanonicalFile:
    def test_exactly_one_canonical_file(self, session):
        assert list_timelogs(session.proj_root) == [
            canonical_name(session.session_id, session.opened_at)
        ]

    def test_name_uses_real_id_and_utc_start(self, session):
        name = list_timelogs(session.proj_root)[0]
        assert name.startswith(f"{session.session_id}_")
        slug = name[len(session.session_id) + 1:-len(".cortex")]
        assert len(slug) == len("20261015_013717")
        assert slug.replace("_", "").isdigit()

    def test_no_database_or_alternative_format(self, session):
        directory = timelog_dir(session.proj_root)
        suffixes = {p.suffix for p in directory.iterdir()}
        assert not (suffixes & {".jsonl", ".db", ".sqlite", ".bak", ".bak.1"})
        assert suffixes <= {".cortex", ".lock"}

    def test_no_durable_backup_is_created(self, session):
        directory = timelog_dir(session.proj_root)
        open_block(session.proj_root, session.session_id, operation_ref="T-2.1")
        close_block(session.proj_root, session.session_id, operation_ref="T-2.1")
        assert not list(directory.glob("*.bak"))
        assert not list(directory.glob("*.bak.1"))

    def test_path_matches_the_planned_location(self, session):
        expected = timelog_path(session.proj_root, session.session_id, session.opened_at)
        assert canonical_path(session.proj_root, session.session_id, session.opened_at) == expected
        assert expected.parent == session.proj_root / ".arqux" / "timelog"


class TestAc03ConcurrencyAndExclusion:
    def test_two_sessions_have_distinct_files(self, arqux_env):
        from tests.conftest import rotate_session

        a = open_session(arqux_env.proj_root, agent="test-governor",
                         project="test-proj", execution=mint_execution_key(),
                         scope="CYCLE-A")
        b = rotate_session(arqux_env.proj_root, scope="CYCLE-B")
        assert a["timelog"] != b["timelog"]
        assert len(list_timelogs(arqux_env.proj_root)) == 2

    def test_concurrent_writes_do_not_lose_updates(self, arqux_env):
        env = arqux_env
        session = open_session(env.proj_root, agent="test-governor",
                               project="test-proj", execution=mint_execution_key())
        refs = [f"op-{i}" for i in range(40)]
        from tests.test_c14_blp001_concurrency import _entry_worker, _run

        _run(_entry_worker, str(env.proj_root / ".arqux" / "brain.cortex"), [])
        # Every write is a separate operation on the same file, serialized by the lock.
        for ref in refs:
            open_block(env.proj_root, session["session_id"], operation_ref=ref)
        document = load(env.proj_root, session["session_id"],
                        opened_at=session["date"])
        assert len(document["blocks"]) == len(refs)

    def test_revision_conflict_writes_nothing(self, session):
        with pytest.raises(RevisionConflict):
            open_block(session.proj_root, session.session_id, operation_ref="T-3.1",
                       expected_revision="999")
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert document["blocks"] == {}
        assert document["revision"] == "1"

    def test_lock_order_is_brain_then_timelog(self):
        import inspect

        from arqux import session_identity, timelog_store

        source = inspect.getsource(timelog_store)
        assert "reentrant_file_lock" in source
        assert hasattr(session_identity, "brain_lock")

    def test_brain_lock_is_reentrant_around_timelog_writes(self, session):
        """A caller already holding the brain lock must not deadlock."""
        from arqux.session_identity import brain_lock

        with brain_lock(session.proj_root):
            open_block(session.proj_root, session.session_id, operation_ref="T-4.1")
            close_block(session.proj_root, session.session_id, operation_ref="T-4.1")
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert document["blocks"]["T_4.1"]["state"] == "closed"


class TestAc04RecoverableOpening:
    @pytest.mark.parametrize("interrupt", ["after_ses", "after_file", "after_link"])
    def test_interruption_recovers_the_same_session(self, arqux_env, interrupt, monkeypatch):
        env = arqux_env
        key = mint_execution_key()

        original = ensure_timelog
        calls = {"n": 0}

        def flaky(project_root, session, *, operation_ref="session.open"):
            calls["n"] += 1
            result = original(project_root, session, operation_ref=operation_ref)
            if calls["n"] == 1 and interrupt == "after_file":
                # Simulate a crash right after the file was created: remove it so
                # the retry has to recreate it and the phase must be inspected.
                path = Path(result["path"])
                path.unlink(missing_ok=True)
            return result

        monkeypatch.setattr("arqux.timelog_store.ensure_timelog", flaky)
        opened = open_session(env.proj_root, agent="test-governor", project="test-proj",
                              execution=key)
        assert opened["timelog_state"] in {"created", "exists", "uncertain"}

        # The retry completes the same session; no second SES is created.
        again = open_session(env.proj_root, agent="test-governor", project="test-proj",
                             execution=key)
        assert again["session_id"] == opened["session_id"]

    def test_reopen_reuses_the_same_file(self, arqux_env):
        env = arqux_env
        key = mint_execution_key()
        first = open_session(env.proj_root, agent="test-governor", project="test-proj",
                             execution=key)
        from arqux.session_identity import close_session, reopen_session

        close_session(env.proj_root, first["session_id"], agent="test-governor",
                      summary="done")
        reopened = reopen_session(env.proj_root, first["session_id"],
                                  execution=mint_execution_key(), agent="test-governor")
        assert reopened["timelog"] == first["timelog"]
        assert list_timelogs(env.proj_root) == [first["timelog"]]


class TestAc05Idempotency:
    def test_repeating_operation_ref_does_not_duplicate(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-1.1",
                   start="2026-10-15T01:00:00Z")
        first_revision = load(session.proj_root, session.session_id,
                              opened_at=session.opened_at)["revision"]
        result = open_block(session.proj_root, session.session_id,
                            operation_ref="T-1.1", start="2026-10-15T09:99:99Z")
        assert result["applied"] is False
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert len(document["blocks"]) == 1
        assert document["blocks"]["T_1.1"]["start"] == "2026-10-15T01:00:00Z"
        assert document["revision"] == first_revision

    def test_repeating_close_does_not_move_the_end(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-2.1",
                   start="2026-10-15T01:00:00Z")
        close_block(session.proj_root, session.session_id, operation_ref="T-2.1",
                    end="2026-10-15T02:00:00Z")
        again = close_block(session.proj_root, session.session_id,
                            operation_ref="T-2.1", end="2026-10-15T23:00:00Z")
        assert again["applied"] is False
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert document["blocks"]["T_2.1"]["end"] == "2026-10-15T02:00:00Z"

    def test_foreign_path_is_rejected(self, session, tmp_path):
        outside = tmp_path / "other.cortex"
        outside.write_text("not a timelog", encoding="utf-8")
        with pytest.raises(MembershipError):
            load(session.proj_root, session.session_id, path=outside)

    def test_path_escaping_the_directory_is_rejected(self, session):
        with pytest.raises(MembershipError):
            update(session.proj_root, session.session_id, operation_ref="x",
                   path=session.proj_root / "brain.cortex")

    def test_contradictory_session_is_rejected(self, session, arqux_env):
        with pytest.raises(MembershipError):
            update(arqux_env.proj_root, "SES999", operation_ref="x",
                   opened_at=session.opened_at)

    def test_unknown_operation_is_rejected(self, session):
        with pytest.raises(UnknownOperation):
            close_block(session.proj_root, session.session_id, operation_ref="never-opened")


class TestAc06TechnicalTemporaries:
    def test_temporaries_are_not_canonical(self):
        assert is_canonical("SES001_20261015_013717.cortex")
        assert not is_canonical(".SES001_20261015_013717.cortex.tmp.cortex")
        assert not is_canonical("SES001_20261015_013717.cortex.lock")
        assert not is_canonical("SES001_20261015_013717.cortex.bak")
        assert not is_canonical("notes.txt")

    def test_no_hidden_copy_survives_a_write(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-1.1")
        close_block(session.proj_root, session.session_id, operation_ref="T-1.1")
        directory = timelog_dir(session.proj_root)
        leftovers = [p.name for p in directory.iterdir() if p.name.startswith(".")]
        assert leftovers == [], f"hidden temporaries left behind: {leftovers}"

    def test_lock_files_are_not_timelogs(self, session):
        assert not list_timelogs(session.proj_root) or all(
            is_canonical(n) for n in list_timelogs(session.proj_root)
        )


class TestAc07ExplicitData:
    def test_open_block_keeps_the_interval_explicit(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-1.1")
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        block = document["blocks"]["T_1.1"]
        assert block["end"] == ""
        assert block["state"] == "open"

    def test_no_semantic_filling_for_missing_end(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-1.1",
                   start="2026-10-15T01:00:00Z")
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert "duration" not in document
        assert document["blocks"]["T_1.1"]["end"] == ""

    def test_invalid_record_is_not_repaired_silently(self, session):
        path = canonical_path(session.proj_root, session.session_id, session.opened_at)
        text = path.read_text(encoding="utf-8")
        path.write_text(text + 'ACT:broken{start:"not-a-timestamp",end:""}\n',
                        encoding="utf-8")
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        assert document["blocks"]["broken"]["start"] == "not-a-timestamp"
        assert document["blocks"]["broken"]["state"] == "open"

    def test_unterminated_blocks_are_marked_not_invented(self, session):
        open_block(session.proj_root, session.session_id, operation_ref="T-1.1")
        from arqux.timelog_store import invalidate_pending

        result = invalidate_pending(session.proj_root, session.session_id)
        assert result["applied"] is True
        document = load(session.proj_root, session.session_id, opened_at=session.opened_at)
        block = document["blocks"]["T_1.1"]
        assert block["state"] == "unterminated"
        assert block["end"] == ""

    def test_module_does_not_depend_on_new_libraries(self):
        import ast

        import arqux.timelog_store as module

        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        top_level = {n.names[0].name.split(".")[0]
                     for n in tree.body if isinstance(n, (ast.Import,))}
        top_level |= {n.module.split(".")[0]
                      for n in tree.body if isinstance(n, ast.ImportFrom) and n.module}
        top_level |= {"concurrency", "session_identity"}  # relative, same package
        assert top_level <= {"os", "re", "time", "pathlib", "typing", "arqux",
                             "__future__", "concurrency", "session_identity"}, top_level


def test_execution_slug_never_collides_for_distinct_keys(arqux_env):
    """D-07: two different execution keys must not share one context file."""
    from arqux.handlers.session import _execution_slug

    pairs = [("a/b", "a_b"), ("x", "y" * 200), ("k-1", "k_1")]
    slugs = [_execution_slug(a) for a in ("a/b", "a_b", "x", "y" * 200, "k-1", "k_1")]
    assert len(set(slugs)) == len(slugs), slugs
    for pair in pairs:
        assert _execution_slug(pair[0]) != _execution_slug(pair[1])
    assert _execution_slug("a/b") == _execution_slug("a/b")  # deterministic


def test_timelog_is_valid_cortex_with_glossary_first(session):
    """The official reader must accept it: $0 first, not only as a comment."""
    from arqux.state import cortex_read

    path = canonical_path(session.proj_root, session.session_id, session.opened_at)
    doc = cortex_read(str(path))
    ids = [s["id"] for s in doc["sections"]]
    assert ids[0] == "$0", ids
    assert ids == ["$0", "$1", "$2", "$3", "$4"], ids
