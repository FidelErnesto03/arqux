"""Regression tests for T-016 — next_pulse_event_id scans the full trail.

next_pulse_event_id used to call read_pulse_from_brain with the default
limit=100, so once the PULSE trail exceeded 100 AUD entries the next id
was computed over the oldest 100 only and could duplicate an existing id.
"""

from __future__ import annotations

from pathlib import Path

from arqux.pulse import (
    append_pulse_to_brain,
    next_pulse_event_id,
    read_pulse_from_brain,
)


def _brain_with_pulses(tmp_path: Path, n: int) -> Path:
    """Create a minimal .arqux/brain.cortex with *n* AUD entries."""
    arqux = tmp_path / ".arqux"
    arqux.mkdir()
    (arqux / "brain.cortex").write_text("$0\n$6: PULSE\n", encoding="utf-8")
    for i in range(1, n + 1):
        append_pulse_to_brain(
            tmp_path,
            event_id=f"E-{i:04d}",
            task_id="T-001",
            kind="note",
            agent="test",
            payload=f"p{i}",
        )
    return tmp_path


def test_next_pulse_event_id_scans_full_trail(tmp_path: Path) -> None:
    """With >100 AUD entries the next id is max+1 over the FULL trail."""
    root = _brain_with_pulses(tmp_path, 110)

    assert next_pulse_event_id(root) == "E-0111"


def test_next_pulse_event_id_no_duplicate_beyond_100(tmp_path: Path) -> None:
    """The generated id does not collide with any existing AUD id."""
    root = _brain_with_pulses(tmp_path, 110)

    event_id = next_pulse_event_id(root)
    existing = {e["id"] for e in read_pulse_from_brain(root, limit=None)}
    assert event_id not in existing

    append_pulse_to_brain(
        root,
        event_id=event_id,
        task_id="T-001",
        kind="note",
        agent="test",
        payload="new",
    )
    ids = [e["id"] for e in read_pulse_from_brain(root, limit=None)]
    assert len(ids) == len(set(ids)) == 111
