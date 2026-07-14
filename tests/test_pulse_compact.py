"""Tests for pulse.compact — BLP-013 compactación de PULSE."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap_project(tmp_path, name: str = "compact-test"):
    """Create a workspace + project with a cycle for testing."""
    from arqux.handlers.cycle import create_cycle, mature_cycle
    from arqux.handlers.project import init_project
    from arqux.handlers.workspace import init_workspace

    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(path=str(ws))
    proj = ws / name
    proj.mkdir()
    init_project(name=name, path=str(proj))
    create_cycle(name="CYCLE-CPT", path=str(proj))
    mature_cycle(path=str(proj))
    return proj


def _add_pulses(proj, count: int, start_id: int = 1, *, kind: str = "note", agent: str = "test"):
    """Add N PULSE entries and return their event IDs."""
    from arqux.pulse import append_pulse_to_brain
    ids = []
    for i in range(count):
        eid = f"E-{start_id + i:04d}"
        append_pulse_to_brain(
            proj, event_id=eid, task_id=f"T-{start_id + i:03d}",
            kind=kind, agent=agent, payload=f"pulse {i}",
        )
        ids.append(eid)
    return ids


def _add_ses(proj, event_id: str, agent: str = "test"):
    """Add a SES entry (kind=session) to the brain."""
    from arqux.pulse import append_pulse_to_brain
    append_pulse_to_brain(
        proj, event_id=event_id, task_id="-",
        kind="session", agent=agent, payload="SES payload",
    )


# ---------------------------------------------------------------------------
# compact_session_pulse — skip < 5 entries
# ---------------------------------------------------------------------------


def test_compact_skip_few_entries(tmp_path) -> None:
    """compact_session_pulse skips when < 5 entries exist."""
    from arqux.pulse import compact_session_pulse

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 3, kind="note")
    _add_ses(proj, "E-0004")

    result = compact_session_pulse(proj, session_id="E-0004", agent_id="test")
    assert result.get("skip") is True
    assert result.get("entry_count") == 3


# ---------------------------------------------------------------------------
# compact_session_pulse — dry_run
# ---------------------------------------------------------------------------


def test_compact_dry_run(tmp_path) -> None:
    """compact_session_pulse dry_run reports without modifying."""
    from arqux.pulse import compact_session_pulse, read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 7, kind="note")
    _add_ses(proj, "E-0008")

    # Dry run
    result = compact_session_pulse(proj, session_id="E-0008", agent_id="test", dry_run=True)
    assert result.get("dry_run") is True
    assert result.get("entry_count") == 7
    assert "entries_to_prune" in result
    assert result.get("ses_preserved") is True
    assert len(result["entries_to_prune"]) == 7

    # Verify brain unchanged — all entries still there
    events = read_pulse_from_brain(proj, limit=100)
    assert len(events) == 8  # 7 notes + 1 SES


# ---------------------------------------------------------------------------
# compact_session_pulse — SES preserved
# ---------------------------------------------------------------------------


def test_compact_ses_preserved(tmp_path) -> None:
    """SES entries are NEVER pruned during compaction."""
    from arqux.pulse import compact_session_pulse, read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 3, kind="note")  # between SES-1 and SES-2
    _add_ses(proj, "E-0004")  # first SES
    _add_pulses(proj, 6, start_id=5, kind="task_complete")
    _add_ses(proj, "E-0011")  # second SES (the one we compact)

    result = compact_session_pulse(proj, session_id="E-0011", agent_id="test")
    assert result.get("compacted") is True
    assert result.get("pruned") == 6  # 6 task_complete entries pruned

    # Verify SES entries still exist
    events = read_pulse_from_brain(proj, limit=100)
    ses_entries = [e for e in events if e.get("kind") == "session"]
    assert len(ses_entries) == 2
    assert ses_entries[0]["id"] == "E-0004"
    assert ses_entries[1]["id"] == "E-0011"


# ---------------------------------------------------------------------------
# compact_session_pulse — idempotencia
# ---------------------------------------------------------------------------


def test_compact_idempotent(tmp_path) -> None:
    """compact_session_pulse is idempotent — second call skips."""
    from arqux.pulse import compact_session_pulse

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 6, kind="note")
    _add_ses(proj, "E-0007")

    # First call compacts
    result1 = compact_session_pulse(proj, session_id="E-0007", agent_id="test")
    assert result1.get("compacted") is True
    assert result1.get("pruned") == 6

    # Second call skips (LNG already exists)
    result2 = compact_session_pulse(proj, session_id="E-0007", agent_id="test")
    assert result2.get("skip") is True
    assert "already compacted" in result2.get("reason", "")


# ---------------------------------------------------------------------------
# compact_session_pulse — LNG written to §7
# ---------------------------------------------------------------------------


def test_compact_lng_written(tmp_path) -> None:
    """After compaction, LNG entry exists in brain §7."""
    from arqux.pulse import compact_session_pulse
    from arqux.state import crud_read

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 5, kind="task_complete")
    _add_pulses(proj, 3, start_id=6, kind="decision")
    _add_ses(proj, "E-0009")

    result = compact_session_pulse(proj, session_id="E-0009", agent_id="test")
    assert result.get("compacted") is True

    brain_path = proj / ".arqux" / "brain.cortex"
    lng = crud_read(brain_path, "$7/LNG:session_E_0009")
    assert len(lng.get("entries", [])) == 1
    val = lng["entries"][0]["value"]
    assert val["type"] == "session"
    assert val["entry_count"] == 8
    assert "task_complete:5" in val["summary"]
    assert "decision:3" in val["summary"]


# ---------------------------------------------------------------------------
# compact_session_pulse — meta-evento AUD
# ---------------------------------------------------------------------------


def test_compact_meta_event(tmp_path) -> None:
    """Compaction registers a meta-event AUD in PULSE."""
    from arqux.pulse import compact_session_pulse, read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 6, kind="note")
    _add_ses(proj, "E-0007")

    result = compact_session_pulse(proj, session_id="E-0007", agent_id="test")
    assert result.get("compacted") is True
    meta_id = result["meta_event"]

    # Verify meta-event exists
    events = read_pulse_from_brain(proj, limit=100)
    meta = [e for e in events if e.get("kind") == "pulse_compact"]
    assert len(meta) == 1
    assert meta[0]["id"] == meta_id
    assert "pulse.compact ok" in meta[0]["payload"]


# ---------------------------------------------------------------------------
# compact_session_pulse — error: brain not found
# ---------------------------------------------------------------------------


def test_compact_brain_not_found(tmp_path) -> None:
    """compact_session_pulse returns error when brain doesn't exist."""
    from arqux.pulse import compact_session_pulse

    result = compact_session_pulse(tmp_path / "nowhere", session_id="E-0001", agent_id="test")
    assert "error" in result


# ---------------------------------------------------------------------------
# compact_session_pulse — error: SES not found
# ---------------------------------------------------------------------------


def test_compact_ses_not_found(tmp_path) -> None:
    """compact_session_pulse returns error when SES doesn't exist."""
    from arqux.pulse import compact_session_pulse

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 5, kind="note")

    result = compact_session_pulse(proj, session_id="E-9999", agent_id="test")
    assert "error" in result
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# compact_session_pulse — first session (no previous SES)
# ---------------------------------------------------------------------------


def test_compact_first_session(tmp_path) -> None:
    """First session (no previous SES) compacts all entries up to that SES."""
    from arqux.pulse import compact_session_pulse

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 8, kind="note")
    _add_ses(proj, "E-0009")

    result = compact_session_pulse(proj, session_id="E-0009", agent_id="test")
    assert result.get("compacted") is True
    assert result.get("pruned") == 8  # all 8 notes before the SES


# ---------------------------------------------------------------------------
# _prune_pulse_entries — unit tests
# ---------------------------------------------------------------------------


def test_prune_empty(tmp_path) -> None:
    """_prune_pulse_entries with empty list returns 0."""
    from arqux.pulse import _prune_pulse_entries

    proj = _bootstrap_project(tmp_path)
    brain_path = proj / ".arqux" / "brain.cortex"
    result = _prune_pulse_entries(brain_path, [])
    assert result["pruned"] == 0


def test_prune_dry_run(tmp_path) -> None:
    """_prune_pulse_entries dry_run reports without modifying."""
    from arqux.pulse import _prune_pulse_entries, read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 3, kind="note")
    brain_path = proj / ".arqux" / "brain.cortex"

    result = _prune_pulse_entries(brain_path, ["E-0001", "E-0002"], dry_run=True)
    assert result.get("dry_run") is True
    assert result.get("would_prune") == 2

    # Verify nothing was actually deleted
    events = read_pulse_from_brain(proj, limit=100)
    assert len(events) == 3


def test_prune_actual(tmp_path) -> None:
    """_prune_pulse_entries actually deletes entries."""
    from arqux.pulse import _prune_pulse_entries, read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 5, kind="note")
    brain_path = proj / ".arqux" / "brain.cortex"

    # Delete first 3
    result = _prune_pulse_entries(brain_path, ["E-0001", "E-0002", "E-0003"])
    assert result["pruned"] == 3
    assert result["errors"] == 0

    # Verify
    events = read_pulse_from_brain(proj, limit=100)
    assert len(events) == 2  # E-0004 and E-0005 remain
    remaining_ids = {e["id"] for e in events}
    assert remaining_ids == {"E-0004", "E-0005"}


# ---------------------------------------------------------------------------
# Integration: session.close → pulse.compact
# ---------------------------------------------------------------------------


def test_session_close_triggers_compact(tmp_path) -> None:
    """session.close automatically calls pulse.compact after writing SES."""
    from arqux.handlers.session import close
    from arqux.pulse import read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)

    # Add enough pulses for compaction (need > 5 for this session)
    from arqux.pulse import append_pulse_to_brain
    for i in range(7):
        eid = f"E-{i + 1:04d}"
        append_pulse_to_brain(
            proj, event_id=eid, task_id=f"T-{i:03d}",
            kind="note", agent="test", payload=f"pulse {i}",
        )

    # Close session — should trigger compact after SES
    result = close(
        summary="Integration test session",
        blps="BLP-013",
        path=str(proj),
    )

    assert "session.close ok" in result.message
    compact = result.fields.get("compact", {})
    # compact should have succeeded (7 entries > 5 threshold)
    assert compact.get("compacted") or compact.get("skip")

    # Verify meta-event exists
    events = read_pulse_from_brain(proj, limit=100)
    meta = [e for e in events if e.get("kind") == "pulse_compact"]
    assert len(meta) == 1


def test_session_close_compact_skip_few(tmp_path) -> None:
    """session.close compact skips when < 5 entries in session."""
    from arqux.handlers.session import close
    from arqux.pulse import read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)

    # Only 2 pulses
    from arqux.pulse import append_pulse_to_brain
    append_pulse_to_brain(
        proj, event_id="E-0001", task_id="T-001",
        kind="note", agent="test", payload="pulse 1",
    )
    append_pulse_to_brain(
        proj, event_id="E-0002", task_id="T-002",
        kind="note", agent="test", payload="pulse 2",
    )

    result = close(
        summary="Small session",
        path=str(proj),
    )

    compact = result.fields.get("compact", {})
    assert compact.get("skip") is True


# ---------------------------------------------------------------------------
# pulse.compact handler — direct invocation
# ---------------------------------------------------------------------------


def test_pulse_compact_handler_ok(tmp_path) -> None:
    """pulse.compact handler direct invocation works."""
    from arqux.handlers.session import pulse_compact

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 6, kind="note")
    _add_ses(proj, "E-0007")

    result = pulse_compact(session_id="E-0007", path=str(proj))
    assert "pulse.compact ok" in result.message
    assert result.fields.get("pruned") == 6


def test_pulse_compact_handler_skip(tmp_path) -> None:
    """pulse.compact handler skips with < 5 entries."""
    from arqux.handlers.session import pulse_compact

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 2, kind="note")
    _add_ses(proj, "E-0003")

    result = pulse_compact(session_id="E-0003", path=str(proj))
    assert "pulse.compact skip" in result.message


def test_pulse_compact_handler_dry_run(tmp_path) -> None:
    """pulse.compact handler dry_run reports without modifying."""
    from arqux.handlers.session import pulse_compact
    from arqux.pulse import read_pulse_from_brain

    proj = _bootstrap_project(tmp_path)
    _add_pulses(proj, 7, kind="note")
    _add_ses(proj, "E-0008")

    result = pulse_compact(session_id="E-0008", dry_run=True, path=str(proj))
    assert "pulse.compact dry_run" in result.message
    assert result.fields.get("dry_run") is True

    # Brain unchanged
    events = read_pulse_from_brain(proj, limit=100)
    assert len(events) == 8  # 7 notes + 1 SES


def test_pulse_compact_handler_no_project(tmp_path) -> None:
    """pulse.compact handler returns error without project."""
    from arqux.handlers.session import pulse_compact

    result = pulse_compact(session_id="E-0001", path=str(tmp_path))
    assert "no project" in result.message.lower()
