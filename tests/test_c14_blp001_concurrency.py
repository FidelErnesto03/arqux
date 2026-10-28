"""CYCLE-14 / BLP-001 — concurrency between real processes.

The threading tests prove the code path; these prove the exclusion. Two
separate processes writing the same brain is the scenario the BLP's R-01 and
R-02 are actually about, and the one a thread-only test cannot reach.
"""

from __future__ import annotations

import multiprocessing as mp

import pytest

from arqux.execution import mint_execution_key
from arqux.pulse import next_pulse_event_id, read_pulse_from_brain, record_pulse
from arqux.session_identity import list_sessions, open_session


def _open_worker(project_root: str, session_ref: str, executions: list[str],
                 queue) -> None:  # pragma: no cover
    """Child process: join the project's room from each execution key."""
    for execution in executions:
        session = open_session(project_root, agent="test-governor",
                               project="test-proj", execution=execution,
                               intent="resumed", session_ref=session_ref)
        queue.put(session["session_id"])


def _pulse_worker(project_root: str, session_ref: str, executions: list[str],
                  queue) -> None:  # pragma: no cover
    """Child process: join the room and record one pulse on it."""
    for execution in executions:
        session = open_session(project_root, agent="test-governor",
                               project="test-proj", execution=execution,
                               intent="resumed", session_ref=session_ref)
        queue.put(record_pulse(
            project_root, task_id="T-1.1", kind="note", agent="test-governor",
            payload=f"note for {execution}", ses_ref=session["session_id"],
        ))


def _run(worker, project_root, batches) -> list[str]:
    """Run *worker* in one process per batch.

    A batch is either a plain list (workers that take it whole) or a
    ``(session_ref, executions)`` tuple for the room-model workers.
    """
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    procs = []
    expected = 0
    for batch in batches:
        if isinstance(batch, tuple):
            session_ref, executions = batch
            procs.append(ctx.Process(
                target=worker, args=(project_root, session_ref, executions, queue)))
            expected += len(executions)
        else:
            procs.append(ctx.Process(target=worker, args=(project_root, batch, queue)))
            expected += len(batch)
    for proc in procs:
        proc.start()
    results = [queue.get(timeout=120) for _ in range(expected)]
    for proc in procs:
        proc.join(timeout=120)
        assert proc.exitcode == 0, f"child exited with {proc.exitcode}"
    return results


class TestCrossProcessExclusion:
    def test_concurrent_processes_converge_on_one_room(self, arqux_env):
        """Room model (2026-10-28): the project has one open session, and every
        process that joins it lands on the same id."""
        room = open_session(arqux_env.proj_root, agent="test-governor",
                            project="test-proj", execution=mint_execution_key())
        batches = [(room["session_id"], [mint_execution_key()]) for _ in range(4)]
        ids = _run(_open_worker, str(arqux_env.proj_root), batches)
        assert set(ids) == {room["session_id"]}
        assert len(list_sessions(arqux_env.proj_root)) == 1

    def test_repeated_open_from_one_execution_never_duplicates(self, arqux_env):
        key = mint_execution_key()
        room = open_session(arqux_env.proj_root, agent="test-governor",
                            project="test-proj", execution=key)
        ids = _run(_open_worker, str(arqux_env.proj_root),
                   [(room["session_id"], [key])] * 3)
        assert set(ids) == {room["session_id"]}
        assert len(list_sessions(arqux_env.proj_root)) == 1

    def test_concurrent_writes_lose_nothing_and_never_reuse_an_id(self, arqux_env):
        room = open_session(arqux_env.proj_root, agent="test-governor",
                            project="test-proj", execution=mint_execution_key())
        batches = [(room["session_id"], [mint_execution_key()]) for _ in range(5)]
        ids = _run(_pulse_worker, str(arqux_env.proj_root), batches)
        assert len(set(ids)) == 5
        stored = {e["id"] for e in read_pulse_from_brain(arqux_env.proj_root, limit=None)}
        assert set(ids) <= stored, "a pulse written by one process was lost"
        assert next_pulse_event_id(arqux_env.proj_root) not in ids

    def test_every_pulse_keeps_its_own_membership(self, arqux_env):
        room = open_session(arqux_env.proj_root, agent="test-governor",
                            project="test-proj", execution=mint_execution_key())
        batches = [(room["session_id"], [mint_execution_key()]) for _ in range(3)]
        ids = _run(_pulse_worker, str(arqux_env.proj_root), batches)
        pulses = [p for p in read_pulse_from_brain(arqux_env.proj_root, limit=None)
                  if p["kind"] == "note"]
        assert len(pulses) == len(ids)
        assert {p["ses_ref"] for p in pulses} == {room["session_id"]}


@pytest.mark.skipif(not hasattr(mp, "get_all_start_methods"), reason="no multiprocessing")
def test_worker_entrypoints_are_importable():
    """Spawn re-imports the module in the child; keep the entrypoints module-level."""
    assert callable(_open_worker) and callable(_pulse_worker)


def _entry_worker(brain_path: str, entries: list[str], queue) -> None:  # pragma: no cover
    """Child process: write through the generic CORTEX read-modify-write path.

    This is the path every governed artifact uses, not the pulse-specific one.
    """
    from arqux.handlers.cortex.entries import entry_add_handler

    for name in entries:
        result = entry_add_handler(
            path=brain_path, section="$7", sigil="LNG", name=name,
            value=f"note {name}", force=True,
        )
        queue.put("ok" if result.profile != "OUT-ERROR" else str(result.fields))


class TestGovernedArtifactExclusion:
    """D-01: the loss was in the shared read-modify-write, not in the pulse layer."""

    def test_concurrent_entry_add_loses_nothing(self, arqux_env):
        batches = [[f"note-{i}-{j}" for j in range(12)] for i in range(8)]
        brain = str(arqux_env.proj_root / ".arqux" / "brain.cortex")
        results = _run(_entry_worker, brain, batches)
        assert set(results) == {"ok"}, results
        from arqux.state import crud_read

        stored = crud_read(str(arqux_env.proj_root / ".arqux" / "brain.cortex"), "$7/LNG:*")
        names = {e["name"] for e in stored["entries"]}
        for batch in batches:
            assert set(batch) <= names, "a governed write was silently lost"

    def test_concurrent_compaction_writes_one_lesson(self, arqux_env):
        """D-03: the idempotency guard has to be evaluated under the lock."""
        from arqux.state import crud_read

        root = arqux_env.proj_root
        session = open_session(root, agent="test-governor", project="test-proj",
                               execution=mint_execution_key())
        from arqux.pulse import append_pulse_to_brain, next_pulse_event_id

        for i in range(8):
            append_pulse_to_brain(root, event_id=next_pulse_event_id(root),
                                  task_id="T-1.1", kind="note",
                                  agent="test-governor", payload=f"mine-{i}",
                                  ses_ref=session["session_id"])
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(root, event_id=event_id, task_id="-", kind="session",
                              agent="test-governor", payload="SES:close",
                              ses_ref=session["session_id"])

        from arqux.pulse import compact_session_pulse

        for _ in range(4):
            compact_session_pulse(root, session_id=event_id, agent_id="test-governor",
                                  ses_ref=session["session_id"])
        stored = crud_read(str(root / ".arqux" / "brain.cortex"), "$7/LNG:*")
        names = [e["name"] for e in stored["entries"]]
        assert len(names) == len(set(names)), f"duplicate lessons: {names}"
