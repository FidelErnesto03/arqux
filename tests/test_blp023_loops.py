"""BLP-023 — autonomous loops: registry, dispatcher, WAKE mailbox, watch."""
from __future__ import annotations

import time

import pytest

from arqux import loops as loops_mod
from arqux.handlers.loops import (
    loop_activate,
    loop_advance,
    loop_complete,
    loop_deactivate,
    loop_list,
    loop_register,
    loop_remove,
    loop_wake,
)
from arqux.loop_watch import tick

BRAIN = """\
$1: FOCUS

FCS:primary{what:"test", status:"current"}

$2: OBJECTIVES

OBJ:goals{goal:"test", status:"current"}

$5: WORKING MEMORY

WRK:current{obj:"test"}
"""


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".arqux").mkdir()
    (tmp_path / ".arqux" / "brain.cortex").write_text(BRAIN, encoding="utf-8")
    return tmp_path


@pytest.fixture
def registered(proj):
    loop_register(path=str(proj), name="demo",
                  phases=["a", "b"], session="SES001")
    return proj / ".arqux" / "brain.cortex"


def _text(out):
    return str(out)


# --- CA-1: register armed; not surfaced until activate ----------------------

def test_register_creates_armed_and_dispatcher_ignores(registered, proj):
    loops = loops_mod.load_loops(registered)
    assert loops[0]["name"] == "demo" and loops[0]["state"] == "armed"
    assert loops_mod.dispatch_pending_loops(registered) is None


def test_register_rejects_duplicate(registered, proj):
    out = loop_register(path=str(proj), name="demo")
    assert "ALREADY_EXISTS" in _text(out)


def test_register_rejects_control_chars(proj):
    out = loop_register(path=str(proj), name="bad", next_="bad\x07text")
    assert "INVALID_ARGS" in _text(out)


# --- CA-2/3/4: activate → pending_loop; deactivate silences; advance --------

def test_activate_then_dispatch_returns_pending(registered, proj):
    loop_activate(path=str(proj), name="demo")
    pl = loops_mod.dispatch_pending_loops(registered)
    assert pl["loop"] == "demo" and pl["phase"] == "a" and pl["reason"] == "due"


def test_deactivate_silences(registered, proj):
    loop_activate(path=str(proj), name="demo")
    loop_deactivate(path=str(proj), name="demo")
    assert loops_mod.dispatch_pending_loops(registered) is None
    loop_activate(path=str(proj), name="demo")
    assert loops_mod.dispatch_pending_loops(registered)["loop"] == "demo"


def test_advance_persists_checkpoint_and_timelog(registered, proj):
    (proj / ".arqux" / "timelog").mkdir()
    (proj / ".arqux" / "timelog" / "SES001_x.cortex").write_text("$1: PULSE\n")
    loop_activate(path=str(proj), name="demo")
    out = loop_advance(path=str(proj), name="demo",
                       checkpoint="phase a done", next_="run b")
    assert "index=1" in _text(out)
    loop = _find(proj, "demo")
    assert loop["index"] == "1" and loop["checkpoint"] == "phase a done"
    tl = (proj / ".arqux" / "timelog" / "SES001_x.cortex").read_text()
    assert 'LOOP:demo{event:"advance"' in tl


# --- CA-4 complete / CA-9 remove ---------------------------------------------

def test_complete_stops_signal(registered, proj):
    loop_activate(path=str(proj), name="demo")
    loop_complete(path=str(proj), name="demo")
    assert loops_mod.dispatch_pending_loops(registered) is None


def test_remove_tombstone_and_requires_deactivate(registered, proj):
    out = loop_remove(path=str(proj), name="demo")
    assert "INVALID_STATE" not in _text(out)  # armed → allowed
    assert _find(proj, "demo") is None or _find(proj, "demo")["state"] == "removed"
    out = loop_register(path=str(proj), name="d2")
    loop_activate(path=str(proj), name="d2")
    out = loop_remove(path=str(proj), name="d2")
    assert "INVALID_STATE" in _text(out)


# --- CA-5 cooldown -----------------------------------------------------------

def test_cooldown_respects_last_run(registered, proj):
    from arqux.core.state._crud import crud_update
    loop_activate(path=str(proj), name="demo")
    crud_update(registered, "LOOP:demo",
                set_={"recurrence": "cooldown:2h",
                      "last_run": f"{time.time():.0f}"}, force=True)
    assert loops_mod.dispatch_pending_loops(registered) is None
    crud_update(registered, "LOOP:demo",
                set_={"last_run": f"{time.time() - 3 * 3600:.0f}"}, force=True)
    assert loops_mod.dispatch_pending_loops(registered)["loop"] == "demo"


# --- CA-6: stall → WAKE → next call resurfaces -------------------------------

def test_stall_generates_wake_and_dispatch_resurfaces(registered, proj):
    from arqux.core.state._crud import crud_update
    loop_activate(path=str(proj), name="demo")
    crud_update(registered, "LOOP:demo",
                set_={"last_activity": f"{time.time() - 7200:.0f}",
                      "checkpoint": "mid phase a"}, force=True)
    summary = tick(proj, now=time.time())
    assert "demo" in summary["wakes"]
    pl = loops_mod.dispatch_pending_loops(registered)
    assert pl["loop"] == "demo" and pl["reason"] == "stall"
    assert pl["checkpoint"] == "mid phase a"


# --- CA-7: retries exhausted → stalled ---------------------------------------

def test_retries_exhausted_marks_stalled(registered, proj):
    from arqux.core.state._crud import crud_update
    loop_activate(path=str(proj), name="demo")
    crud_update(registered, "LOOP:demo",
                set_={"last_activity": "1", "retries": "3"}, force=True)
    summary = tick(proj)
    assert "demo" in summary["stalled"]
    assert _find(proj, "demo")["state"] == "stalled"


# --- CA-8: WAKE drains once --------------------------------------------------

def test_wake_drains_once(registered, proj):
    loops_mod.write_wake(proj, "demo", reason="manual", checkpoint="c")
    assert len(loops_mod.drain_wakes(proj)) == 1
    assert loops_mod.drain_wakes(proj) == []


def test_manual_wake_via_handler(registered, proj):
    loop_activate(path=str(proj), name="demo")
    loop_wake(path=str(proj), name="demo", checkpoint="go")
    pl = loops_mod.dispatch_pending_loops(registered)
    assert pl["reason"] == "manual" and pl["checkpoint"] == "go"


# --- CA-12: malformed WAKE → quarantine --------------------------------------

def test_malformed_wake_quarantined(registered, proj):
    d = proj / ".arqux" / "loops"
    d.mkdir()
    (d / "bad.wake").write_text("not a wake entry")
    assert loops_mod.drain_wakes(proj) == []
    assert (d / ".bad" / "bad.wake").exists()


# --- CA-10: no loops dir / no section → nothing breaks ------------------------

def test_dispatch_clean_without_registry(proj):
    assert loops_mod.dispatch_pending_loops(proj / ".arqux" / "brain.cortex") is None
    assert loops_mod.drain_wakes(proj) == []


# --- CA-11: fail-silent -------------------------------------------------------

def test_dispatch_never_raises(tmp_path):
    brain = tmp_path / ".arqux" / "brain.cortex"
    brain.parent.mkdir()
    brain.write_text("garbage {{{ LOOP:x{")
    assert loops_mod.dispatch_pending_loops(brain) is None


# --- CA-13: per-phase expected_duration ---------------------------------------

def test_phase_budget_uses_expected_duration(proj):
    from arqux.core.state._crud import crud_update
    loop_register(path=str(proj), name="long",
                  phases=["suite"], expected_duration="240")
    brain = proj / ".arqux" / "brain.cortex"
    loop_activate(path=str(proj), name="long")
    crud_update(brain, "LOOP:long",
                set_={"last_activity": f"{time.time() - 7200:.0f}"}, force=True)
    # 2h old but budget is 4h → not stalled
    assert not loops_mod.is_stalled(_find(proj, "long"), time.time())
    crud_update(brain, "LOOP:long",
                set_={"last_activity": f"{time.time() - 5 * 3600:.0f}"}, force=True)
    assert loops_mod.is_stalled(_find(proj, "long"), time.time())


# --- Legacy fallback -----------------------------------------------------------

def test_legacy_wrk_current_fallback(proj):
    brain = proj / ".arqux" / "brain.cortex"
    brain.write_text(
        BRAIN + '\nWRK:current{loop:"old", phase:"B", next:"go"}\n',
        encoding="utf-8")
    pl = loops_mod.dispatch_pending_loops(brain)
    assert pl["loop"] == "old" and pl["reason"] == "legacy"


def test_legacy_done_phase_silent(proj):
    brain = proj / ".arqux" / "brain.cortex"
    brain.write_text(
        BRAIN + '\nWRK:current{loop:"old", phase:"done", next:"x"}\n',
        encoding="utf-8")
    assert loops_mod.dispatch_pending_loops(brain) is None


def _find(proj, name):
    return next((l for l in loops_mod.load_loops(proj / ".arqux" / "brain.cortex")
                 if l["name"] == name), None)


# --- Heimdall audit fixes -------------------------------------------------

def test_second_wake_survives_drain(registered, proj):
    """H-01: draining consumes only the surfaced wake; the rest keep their
    signal for the next governed call."""
    loop_activate(path=str(proj), name="demo")
    loops_mod.write_wake(proj, "demo", reason="stall", checkpoint="cp-a")
    loops_mod.write_wake(proj, "other", reason="manual", checkpoint="cp-b")
    out = loops_mod.dispatch_pending_loops(registered)
    assert out["loop"] == "demo"
    # 'other.wake' must still exist — its signal was not lost.
    assert (proj / ".arqux" / "loops" / "other.wake").exists()


def test_advance_rejects_non_active(registered, proj):
    """H-02: advance on a non-active entry (armed/paused/done/removed) is
    rejected — it must never write into a tombstone."""
    out = loop_advance(path=str(proj), name="demo", checkpoint="x")
    assert "INVALID_STATE" in str(out)
    loop_activate(path=str(proj), name="demo")
    loop_deactivate(path=str(proj), name="demo")
    out = loop_advance(path=str(proj), name="demo", checkpoint="x")
    assert "INVALID_STATE" in str(out)


def test_heartbeat_loop_fires_via_tick(registered, proj):
    """H-03: an on_heartbeat loop is unreachable via normal dispatch but the
    watch tick queues its 'due' wake."""
    from arqux.handlers.loops import _set
    _set(str(proj), "demo", {"recurrence": "on_heartbeat"})
    loop_activate(path=str(proj), name="demo")
    assert loops_mod.dispatch_pending_loops(registered) is None  # not due outside tick
    s = tick(proj)
    assert "demo" in s["wakes"]
    out = loops_mod.dispatch_pending_loops(registered)
    assert out["loop"] == "demo" and out["reason"] == "due"


def test_watch_status_reported(registered, proj):
    """H-04: the dispatcher reports watch liveness in its pending payload."""
    loop_activate(path=str(proj), name="demo")
    out = loops_mod.dispatch_pending_loops(registered)
    assert out["watch"] == "absent"
    tick(proj)
    out = loops_mod.dispatch_pending_loops(registered)
    assert out["watch"] == "alive"


# --- Multi-session concurrency (same project) ------------------------------

def test_claim_defers_second_execution(registered, proj):
    """Two executions on the same project: the loop surfaces to the first
    claimant only — no double dispatch while the lease is fresh."""
    loop_activate(path=str(proj), name="demo")
    out1 = loops_mod.dispatch_pending_loops(registered, claimant="exec-A")
    assert out1["loop"] == "demo"
    out2 = loops_mod.dispatch_pending_loops(registered, claimant="exec-B")
    assert out2 is None


def test_advance_rejected_for_non_claimant(registered, proj):
    """Mutations honour the lease: a second execution cannot advance a loop
    claimed by the first."""
    loop_activate(path=str(proj), name="demo")
    loops_mod.dispatch_pending_loops(registered, claimant="exec-A")
    out = loop_advance(path=str(proj), name="demo", claimant="exec-B")
    assert "CLAIMED_BY_OTHER" in str(out)
    out = loop_advance(path=str(proj), name="demo", claimant="exec-A")
    assert "index=1" in str(out)


def test_stale_claim_expires(registered, proj):
    """A dead claimant never blocks resurrection: the lease expires."""
    loop_activate(path=str(proj), name="demo")
    loops_mod.dispatch_pending_loops(registered, claimant="exec-A")
    from arqux.handlers.loops import _set
    _set(str(proj), "demo", {"claim_ts": str(int(time.time()) - 700)})
    out = loops_mod.dispatch_pending_loops(registered, claimant="exec-B")
    assert out["loop"] == "demo"


def test_wake_drain_claim_marker_skips(registered, proj):
    """A held .claim marker defers the drain without losing the signal —
    the concurrent case where two processes see the same file."""
    loop_activate(path=str(proj), name="demo")
    loops_mod.write_wake(proj, "demo", reason="stall")
    (proj / ".arqux" / "loops" / ".demo.wake.claim").write_text("held")
    assert loops_mod.drain_wakes(proj) == []
    assert (proj / ".arqux" / "loops" / "demo.wake").exists()


def test_loop_list(registered, proj):
    out = loop_list(path=str(proj))
    assert "total=1" in _text(out)
