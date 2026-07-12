"""Tests for arqux.pulse — pulse entries and handoff operations."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# next_pulse_event_id — pure logic, no file I/O
# ---------------------------------------------------------------------------


def test_next_pulse_event_id_first(tmp_path) -> None:
    """next_pulse_event_id returns E-0001 for empty / nonexistent brain."""
    from arqux.pulse import next_pulse_event_id

    assert next_pulse_event_id(tmp_path) == "E-0001"


# ---------------------------------------------------------------------------
# read_pulse_from_brain — edge cases
# ---------------------------------------------------------------------------


def test_read_pulse_from_brain_nonexistent(tmp_path) -> None:
    """read_pulse_from_brain returns [] when brain does not exist."""
    from arqux.pulse import read_pulse_from_brain

    assert read_pulse_from_brain(tmp_path / "nowhere") == []


# ---------------------------------------------------------------------------
# read_handoffs — edge cases
# ---------------------------------------------------------------------------


def test_read_handoffs_nonexistent(tmp_path) -> None:
    """read_handoffs returns [] when brain does not exist."""
    from arqux.pulse import read_handoffs

    assert read_handoffs(tmp_path / "nowhere") == []


# ---------------------------------------------------------------------------
# _parse_pulse_line — pure parsing logic
# ---------------------------------------------------------------------------


def test_parse_pulse_line_valid() -> None:
    """_parse_pulse_line parses a valid pulse line."""
    from arqux.pulse import _parse_pulse_line

    result = _parse_pulse_line(
        "- [2026-07-11T14:52:25Z] id=E-0001 task=T-001 kind=task_complete agent=jarvis :: done"
    )
    assert result is not None
    assert result["ts"] == "2026-07-11T14:52:25Z"
    assert result["id"] == "E-0001"
    assert result["task"] == "T-001"
    assert result["kind"] == "task_complete"
    assert result["agent"] == "jarvis"
    assert result["payload"] == "done"


def test_parse_pulse_line_with_cycle() -> None:
    """_parse_pulse_line parses a line with cycle field."""
    from arqux.pulse import _parse_pulse_line

    result = _parse_pulse_line(
        "- [2026-07-11T14:52:25Z] id=E-0002 task=T-002 kind=task_start cycle=CYCLE-01 agent=bob :: starting"
    )
    assert result is not None
    assert result["cycle"] == "CYCLE-01"
    assert result["agent"] == "bob"


def test_parse_pulse_line_invalid() -> None:
    """_parse_pulse_line returns None for invalid lines."""
    from arqux.pulse import _parse_pulse_line

    assert _parse_pulse_line("") is None
    assert _parse_pulse_line("not a pulse line") is None
    assert _parse_pulse_line("- [] id=E-0001 task=T-001 kind=x agent=y :: z") is None


def test_append_pulse_to_brain(tmp_path) -> None:
    """append_pulse_to_brain writes an entry and next_pulse_event_id advances."""
    from arqux.handlers.workspace import init_workspace
    from arqux.handlers.project import init_project
    from arqux.handlers.cycle import create_cycle, mature_cycle
    from arqux.pulse import next_pulse_event_id, append_pulse_to_brain, read_pulse_from_brain

    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(path=str(ws))
    proj = ws / "proj"
    proj.mkdir()
    init_project(name="pulse-test", path=str(proj))
    create_cycle(name="CYCLE-PULSE", path=str(proj))
    mature_cycle(path=str(proj))

    eid = next_pulse_event_id(proj)
    assert eid == "E-0001"

    append_pulse_to_brain(proj, event_id=eid, task_id="T-TEST", kind="note", agent="test", payload="hello")
    events = read_pulse_from_brain(proj)
    assert len(events) >= 1
    assert events[0]["id"] == "E-0001"
    assert events[0]["payload"] == "hello"

    eid2 = next_pulse_event_id(proj)
    assert eid2 == "E-0002"
