"""Tests for PULSE hot-window sweep (T1) — brain canon retention policy."""

from __future__ import annotations

import time


def _bootstrap_project(tmp_path, name: str = "sweep-test"):
    """Create a workspace + project with a cycle for testing."""
    from arqux.handlers.cycle import create_cycle
    from arqux.handlers.project import init_project
    from arqux.handlers.workspace import init_workspace

    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(path=str(ws))
    proj = ws / name
    proj.mkdir()
    init_project(name=name, path=str(proj))
    create_cycle(name="CYCLE-SWP", path=str(proj))
    return proj


def _iso_days_ago(days: int) -> str:
    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400)
    )


def _add_aud(proj, eid: str, *, kind: str = "note", date: str | None = None,
             ses_ref: str | None = None):
    """Insert an AUD entry directly (custom date/kind), bypassing append."""
    from arqux.pulse import _brain_cortex_path, _now_iso
    from arqux.state import crud_add

    brain = _brain_cortex_path(proj)
    value = {
        "date": date or _now_iso(),
        "event": eid,
        "task": "-",
        "kind": kind,
        "agent": "test",
        "result": f"payload {eid}",
        "evidence": f"payload {eid}",
    }
    if ses_ref:
        value["ses_ref"] = ses_ref
    crud_add(
        brain, "$11", "AUD", eid.replace("-", "_"), value,
        create_section=True, section_title="PULSE", force=True,
    )


def _aud_ids(proj) -> list[str]:
    from arqux.pulse import read_pulse_from_brain

    return [e["id"] for e in read_pulse_from_brain(proj, limit=None)]


def _fixture_closed_history(proj, n_notes: int = 45):
    """anchor -> n_notes (closed session) -> anchor -> live notes.

    Entries between the two anchors are sweep candidates; the tail after
    the last anchor is the live (exempt) window.
    """
    _add_aud(proj, "E-0001", kind="session")
    for i in range(n_notes):
        _add_aud(proj, f"E-{i + 2:04d}", kind="note")
    _add_aud(proj, f"E-{n_notes + 2:04d}", kind="session")
    _add_aud(proj, f"E-{n_notes + 3:04d}", kind="note")  # live tail
    _add_aud(proj, f"E-{n_notes + 4:04d}", kind="note")  # live tail


# ---------------------------------------------------------------------------
# sweep_pulse_window — window bounds
# ---------------------------------------------------------------------------


def test_sweep_prunes_beyond_count_window(tmp_path) -> None:
    """Entries ranked beyond PULSE_KEEP_COUNT are pruned even when young."""
    from arqux.pulse import PULSE_KEEP_COUNT, sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _fixture_closed_history(proj, n_notes=45)

    result = sweep_pulse_window(proj)
    assert result["swept"] is True
    assert result["pruned"] > 0

    remaining = _aud_ids(proj)
    # anchors + live tail + the newest ~K notes survive
    anchors = [i for i in remaining if i in ("E-0001", "E-0047")]
    assert len(anchors) == 2
    live = [i for i in remaining if i in ("E-0048", "E-0049")]
    assert len(live) == 2
    notes_left = [i for i in remaining if i.startswith("E-") and i not in anchors + live]
    assert len(notes_left) <= PULSE_KEEP_COUNT


def test_sweep_prunes_beyond_age_window(tmp_path) -> None:
    """Entries older than PULSE_KEEP_DAYS are pruned even inside rank K."""
    from arqux.pulse import PULSE_KEEP_DAYS, sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _add_aud(proj, "E-0001", kind="session")
    # 10 notes: first 5 old (>T days), last 5 young — all within rank K
    for i in range(10):
        date = _iso_days_ago(PULSE_KEEP_DAYS + 2) if i < 5 else None
        _add_aud(proj, f"E-{i + 2:04d}", kind="note", date=date)
    _add_aud(proj, "E-0012", kind="session")

    result = sweep_pulse_window(proj)
    assert result["swept"] is True

    remaining = set(_aud_ids(proj))
    for i in range(5):
        assert f"E-{i + 2:04d}" not in remaining  # old ones gone
    for i in range(5, 10):
        assert f"E-{i + 2:04d}" in remaining  # young ones kept


def test_sweep_exempts_session_anchors(tmp_path) -> None:
    """kind:session anchors are never pruned regardless of age/rank."""
    from arqux.pulse import sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _add_aud(proj, "E-0001", kind="session", date=_iso_days_ago(30))
    for i in range(45):
        _add_aud(proj, f"E-{i + 2:04d}", kind="note", date=_iso_days_ago(30))
    _add_aud(proj, "E-0047", kind="session", date=_iso_days_ago(30))

    result = sweep_pulse_window(proj)
    assert result["swept"] is True
    remaining = set(_aud_ids(proj))
    assert "E-0001" in remaining
    assert "E-0047" in remaining


def test_sweep_exempts_live_tail(tmp_path) -> None:
    """Entries after the last session anchor (open session) never prune."""
    from arqux.pulse import sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _add_aud(proj, "E-0001", kind="session")
    for i in range(45):
        _add_aud(proj, f"E-{i + 2:04d}", kind="note", date=_iso_days_ago(30))
    _add_aud(proj, "E-0047", kind="session")
    # live tail: many old entries still exempt (open session = retomable)
    for i in range(30):
        _add_aud(proj, f"E-{i + 48:04d}", kind="note", date=_iso_days_ago(30))

    result = sweep_pulse_window(proj)
    assert result["swept"] is True
    remaining = set(_aud_ids(proj))
    for i in range(30):
        assert f"E-{i + 48:04d}" in remaining


def test_sweep_nothing_outside_window(tmp_path) -> None:
    """Few young entries inside the window -> skip, no mutation."""
    from arqux.pulse import sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _add_aud(proj, "E-0001", kind="session")
    for i in range(5):
        _add_aud(proj, f"E-{i + 2:04d}", kind="note")

    result = sweep_pulse_window(proj)
    assert result.get("skip") is True or result.get("swept") is False
    assert len(_aud_ids(proj)) == 6


# ---------------------------------------------------------------------------
# Archive consolidation + idempotency
# ---------------------------------------------------------------------------


def test_sweep_writes_rolling_lng_archive(tmp_path) -> None:
    """Pruned events consolidate into LNG:pulse_sweep with required fields."""
    from arqux.pulse import sweep_pulse_window
    from arqux.state import crud_read

    proj = _bootstrap_project(tmp_path)
    _fixture_closed_history(proj, n_notes=45)

    result = sweep_pulse_window(proj)
    assert result["swept"] is True

    brain = proj / ".arqux" / "brain.cortex"
    found = crud_read(brain, "$8/LNG:pulse_sweep")
    entries = found.get("entries", [])
    assert entries, "LNG:pulse_sweep missing"
    val = entries[0]["value"]
    for field in ("cause", "lesson", "prevention", "total_pruned", "sweeps"):
        assert field in val
    assert val["total_pruned"] == result["pruned"]


def test_sweep_second_run_is_idempotent(tmp_path) -> None:
    """A second sweep finds nothing outside the window."""
    from arqux.pulse import sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _fixture_closed_history(proj, n_notes=45)

    first = sweep_pulse_window(proj)
    assert first["swept"] is True
    second = sweep_pulse_window(proj)
    assert second.get("skip") is True or second.get("pruned", 0) == 0


def test_sweep_dry_run_does_not_mutate(tmp_path) -> None:
    """dry_run reports candidates without writing."""
    from arqux.pulse import sweep_pulse_window

    proj = _bootstrap_project(tmp_path)
    _fixture_closed_history(proj, n_notes=45)
    before = _aud_ids(proj)

    result = sweep_pulse_window(proj, dry_run=True)
    assert result["dry_run"] is True
    assert result["would_prune"] > 0
    assert _aud_ids(proj) == before


def test_prune_matches_event_field_not_only_storage_name(tmp_path) -> None:
    """_prune_pulse_entries removes entries whose storage name differs.

    Regression: ``AUD:E_0301_0003{event:"E-0301"}`` — crud dedup suffixes the
    storage name while the event field keeps the canonical id. Matching only
    the storage name left the entry unprunable while LNG:pulse_sweep counters
    claimed it had been archived.
    """
    from arqux.pulse import _brain_cortex_path, _prune_pulse_entries
    from arqux.state import crud_add

    proj = _bootstrap_project(tmp_path)
    brain = _brain_cortex_path(proj)
    crud_add(
        brain, "$7", "AUD", "E_0301_0003",
        {"date": "2026-08-17T13:30:00Z", "event": "E-0301", "task": "-",
         "kind": "decision", "agent": "alfred",
         "result": "payload", "evidence": "payload"},
        create_section=True, force=True,
    )
    crud_add(
        brain, "$7", "AUD", "E_0302",
        {"date": "2026-08-17T13:31:00Z", "event": "E-0302", "task": "-",
         "kind": "note", "agent": "alfred",
         "result": "keep", "evidence": "keep"},
        create_section=True, force=True,
    )

    result = _prune_pulse_entries(brain, ["E-0301"])
    assert result["pruned"] == 1
    text = brain.read_text(encoding="utf-8")
    assert "E_0301_0003" not in text
    assert "E_0302" in text


def test_sweep_prunes_dedup_named_entry(tmp_path) -> None:
    """End-to-end: a dedup-named AUD outside the window is really removed."""
    from arqux.pulse import _brain_cortex_path, sweep_pulse_window
    from arqux.state import crud_add

    proj = _bootstrap_project(tmp_path)
    _add_aud(proj, "E-0001", kind="session")
    for i in range(44):
        _add_aud(proj, f"E-{i + 2:04d}", kind="note", date=_iso_days_ago(30))
    # Dedup-named candidate inside the closed window (before last anchor).
    brain = _brain_cortex_path(proj)
    crud_add(
        brain, "$11", "AUD", "E_0046_0009",
        {"date": _iso_days_ago(30), "event": "E-0046", "task": "-",
         "kind": "decision", "agent": "alfred",
         "result": "payload", "evidence": "payload"},
        create_section=True, section_title="PULSE", force=True,
    )
    _add_aud(proj, "E-0047", kind="session")
    _add_aud(proj, "E-0048", kind="note")
    _add_aud(proj, "E-0049", kind="note")

    result = sweep_pulse_window(proj)
    assert result["swept"] is True
    assert result["pruned"] == 45  # 44 notes + dedup entry

    text = brain.read_text(encoding="utf-8")
    assert "E_0046_0009" not in text
    assert "E-0046" not in _aud_ids(proj)
    # Anchors and live tail survive.
    remaining = set(_aud_ids(proj))
    assert "E-0001" in remaining and "E-0047" in remaining
    assert "E-0048" in remaining and "E-0049" in remaining


# ---------------------------------------------------------------------------
# Write-path auto trigger
# ---------------------------------------------------------------------------


def test_append_never_auto_sweeps(tmp_path) -> None:
    """Canon: the write path never prunes — events are append-only (T1 retired).

    Appending past the old PULSE_SWEEP_AT trigger leaves every legacy
    brain-PULSE entry intact; explicit ``session.pulse.gc`` remains the
    only sweep path.
    """
    from arqux.pulse import PULSE_SWEEP_AT, append_pulse_to_brain

    proj = _bootstrap_project(tmp_path)
    _add_aud(proj, "E-0001", kind="session")
    for i in range(PULSE_SWEEP_AT + 10):
        append_pulse_to_brain(
            proj, event_id=f"E-{i + 2:04d}", task_id="-",
            kind="note", agent="test", payload=f"note {i}",
        )
    append_pulse_to_brain(
        proj, event_id="E-9999", task_id="-",
        kind="session", agent="test", payload="session close",
    )

    from arqux.pulse import _aud_count, _brain_cortex_path

    remaining = _aud_count(_brain_cortex_path(proj))
    # Nothing pruned: all written entries survive (50 notes + 2 anchors).
    assert remaining == PULSE_SWEEP_AT + 12
