"""arqux loop-watch — the autonomous-loop watch daemon (BLP-023).

An OS process under our own control (started via ``arqux serve`` or
standalone). Each tick it:

1. Writes its own heartbeat (``.arqux/loops/.watch``) — a dead watch is
   itself detectable (V-02).
2. Scans the brain §LOOPS registry for ``active`` loops whose
   ``last_activity`` exceeded the phase budget (``expected_duration`` or
   ``max_stall``) → queues a ``WAKE`` and increments ``retries``.
3. When ``retries`` exceeds ``max_retries`` (default 3) → marks the loop
   ``stalled`` (no infinite resurrection) and logs the event to the
   session timelog.

The system degrades gracefully without the watch: dispatch on bootstrap
still surfaces due/stalled loops.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import loops as loops_mod
from .core.state._crud import crud_update

DEFAULT_MAX_RETRIES = 3


def _watch_file(project_root: str | Path) -> Path:
    return Path(project_root) / ".arqux" / "loops" / ".watch"


def tick(project_root: str | Path, *, now: float | None = None) -> dict:
    """One watch cycle. Returns a summary dict (also used by tests)."""
    now = time.time() if now is None else now
    brain = Path(project_root) / ".arqux" / "brain.cortex"
    summary = {"scanned": 0, "wakes": [], "stalled": [], "errors": []}

    try:
        wf = _watch_file(project_root)
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(f"watch_last_tick:{now:.0f}\n", encoding="utf-8")
    except OSError as exc:
        summary["errors"].append(f"watch heartbeat: {exc}")

    for loop in loops_mod.load_loops(brain):
        if loop.get("state") != "active":
            continue
        summary["scanned"] += 1
        name = loop["name"]
        if not loops_mod.is_stalled(loop, now):
            # Heartbeat-recurrent loops fire only via watch ticks (H-03):
            # no other caller passes on_heartbeat=True.
            if loop.get("recurrence") == "on_heartbeat":
                wake = Path(project_root) / ".arqux" / "loops" / f"{name}.wake"
                if not wake.exists() and loops_mod.write_wake(
                        project_root, name, reason="due",
                        checkpoint=loop.get("checkpoint", "")):
                    summary["wakes"].append(name)
            continue
        try:
            retries = int(loop.get("retries") or 0)
            max_retries = int(loop.get("max_retries") or DEFAULT_MAX_RETRIES)
        except (TypeError, ValueError):
            retries, max_retries = 0, DEFAULT_MAX_RETRIES

        if retries >= max_retries:
            res = crud_update(brain, f"LOOP:{name}",
                              set_={"state": "stalled"}, force=True)
            if "error" in res:
                summary["errors"].append(f"{name}: {res['error']}")
            else:
                loops_mod.log_event(project_root, loop.get("session", ""), name,
                            "stalled", f"retries exhausted ({retries})")
                summary["stalled"].append(name)
            continue

        wake = Path(project_root) / ".arqux" / "loops" / f"{name}.wake"
        if wake.exists():
            continue  # a pending wake is already queued — don't spam
        # Backoff: re-wake only after retries * 2 ticks worth of time.
        try:
            last_wake = float(loop.get("last_wake") or 0)
        except (TypeError, ValueError):
            last_wake = 0.0
        if now - last_wake < retries * 120:
            continue

        if loops_mod.write_wake(project_root, name, reason="stall",
                        checkpoint=loop.get("checkpoint", "")):
            crud_update(brain, f"LOOP:{name}",
                        set_={"retries": str(retries + 1),
                              "last_wake": f"{now:.0f}"}, force=True)
            loops_mod.log_event(project_root, loop.get("session", ""), name, "stall",
                        f"retry {retries + 1}/{max_retries}")
            summary["wakes"].append(name)
    return summary


def run(project_root: str | Path, *, interval: float = 60.0,
        once: bool = False) -> int:
    """Watch loop. ``once=True`` performs a single tick (tests/manual)."""
    if once:
        s = tick(project_root)
        print(f"loop-watch tick scanned={s['scanned']} "
              f"wakes={s['wakes']} stalled={s['stalled']} "
              f"errors={len(s['errors'])}")
        return 0 if not s["errors"] else 1
    while True:
        tick(project_root)
        time.sleep(interval)
