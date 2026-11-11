"""loop.* handlers — autonomous loop commands (BLP-023).

Registry lives in the project brain §LOOPS; the execution trail is
appended to the session timelog by :func:`arqux.loops.log_event`.
State transitions go through these commands only — never direct edits.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .. import loops as loops_mod
from ..core.state._crud import crud_add, crud_update
from ..cortex_out import CortexOUT


def _brain(path: str | Path) -> Path:
    return Path(path) / ".arqux" / "brain.cortex"


def _find(path, name) -> dict | None:
    return next((l for l in loops_mod.load_loops(_brain(path)) if l["name"] == name), None)


def _set(path, name, fields: dict) -> dict:
    return crud_update(_brain(path), f"LOOP:{name}", set_=fields, force=True)


def loop_register(path: str, name: str, phases: list | None = None,
                  recurrence: str = "on_bootstrap", max_stall: str = "60",
                  expected_duration: str = "", owner: str = "",
                  session: str = "", next_: str = "", checkpoint: str = "",
                  content: str | None = None, ctx: Any = None) -> Any:
    for text in (next_, checkpoint):
        err = loops_mod.validate_loop_text(text)
        if err:
            return CortexOUT.error(err, code="INVALID_ARGS")
    if not name:
        return CortexOUT.error("name is required", code="INVALID_ARGS")
    if _find(path, name):
        return CortexOUT.error(f"loop {name!r} already registered", code="ALREADY_EXISTS")
    res = crud_add(
        _brain(path), "$18", "LOOP", name,
        {"state": "armed", "index": "0", "retries": "0",
         "phases": phases or [], "recurrence": recurrence,
         "max_stall": str(max_stall or "60"),
         "expected_duration": str(expected_duration or ""),
         "next": loops_mod._sanitize(next_), "checkpoint": loops_mod._sanitize(checkpoint),
         "owner": owner, "session": session,
         "claimed_by": "", "claim_ts": "0",
         "created": f"{time.time():.0f}", "last_run": "0", "last_activity": "0"},
        create_section=True, force=True,
    )
    if "error" in res:
        return CortexOUT.error(str(res["error"]), code="WRITE_FAILED")
    return CortexOUT.work(f"loop.register ok name={name}", name=name, state="armed")


def loop_list(path: str, ctx: Any = None) -> Any:
    loops = [l for l in loops_mod.load_loops(_brain(path)) if l.get("state") != "removed"]
    return CortexOUT.work(
        f"loop.list ok total={len(loops)}",
        loops=[{"name": l["name"], "state": l.get("state"), "index": l.get("index"),
                "recurrence": l.get("recurrence"), "next": l.get("next", ""),
                "last_activity": l.get("last_activity", "")} for l in loops],
        total=len(loops),
    )


def _claim_check(loop: dict, claimant: str) -> Any | None:
    """Reject mutations from an execution that doesn't hold the lease."""
    if loops_mod._claimed_by_other(loop, claimant, time.time()):
        return CortexOUT.error(
            f"loop {loop['name']!r} claimed by {loop['claimed_by']!r}",
            code="CLAIMED_BY_OTHER")
    return None


def _transition(path, name, want: str | tuple, fields: dict, event: str,
                detail: str = "", claimant: str = "") -> Any:
    loop = _find(path, name)
    if not loop:
        return CortexOUT.error(f"loop {name!r} not found", code="NOT_FOUND")
    states = (want,) if isinstance(want, str) else want
    if loop.get("state") not in states:
        return CortexOUT.error(
            f"loop {name!r} is {loop.get('state')}, expected {'|'.join(states)}",
            code="INVALID_STATE")
    err = _claim_check(loop, claimant)
    if err:
        return err
    res = _set(path, name, fields)
    if "error" in res:
        return CortexOUT.error(str(res["error"]), code="WRITE_FAILED")
    loops_mod.log_event(path, loop.get("session", ""), name, event, detail)
    return CortexOUT.work(f"loop.{event} ok name={name}", name=name, **fields)


def loop_activate(path: str, name: str, claimant: str = "", ctx: Any = None) -> Any:
    now = f"{time.time():.0f}"
    return _transition(path, name, ("armed", "paused", "stalled"),
                       {"state": "active", "last_activity": now, "retries": "0"},
                       "activate", claimant=claimant)


def loop_deactivate(path: str, name: str, claimant: str = "", ctx: Any = None) -> Any:
    return _transition(path, name, "active", {"state": "paused"}, "deactivate",
                       claimant=claimant)


def loop_advance(path: str, name: str, checkpoint: str = "",
                 next_: str = "", claimant: str = "", ctx: Any = None) -> Any:
    err = loops_mod.validate_loop_text(checkpoint) or loops_mod.validate_loop_text(next_)
    if err:
        return CortexOUT.error(err, code="INVALID_ARGS")
    loop = _find(path, name)
    if not loop:
        return CortexOUT.error(f"loop {name!r} not found", code="NOT_FOUND")
    if loop.get("state") != "active":
        return CortexOUT.error(
            f"loop {name!r} is {loop.get('state')}, expected active",
            code="INVALID_STATE")
    err = _claim_check(loop, claimant)
    if err:
        return err
    now = f"{time.time():.0f}"
    idx = int(loop.get("index") or 0) + 1
    fields = {"index": str(idx), "checkpoint": loops_mod._sanitize(checkpoint),
              "next": loops_mod._sanitize(next_), "last_run": now, "last_activity": now}
    res = _set(path, name, fields)
    if "error" in res:
        return CortexOUT.error(str(res["error"]), code="WRITE_FAILED")
    loops_mod.log_event(path, loop.get("session", ""), name, "advance",
                checkpoint or f"index={idx}")
    return CortexOUT.work(f"loop.advance ok name={name} index={idx}",
                          name=name, index=str(idx))


def loop_complete(path: str, name: str, summary: str = "",
                  claimant: str = "", ctx: Any = None) -> Any:
    return _transition(path, name, "active",
                       {"state": "done", "last_activity": f"{time.time():.0f}",
                        "claimed_by": "", "claim_ts": "0"},
                       "complete", summary, claimant=claimant)


def loop_remove(path: str, name: str, claimant: str = "", ctx: Any = None) -> Any:
    # Tombstone per V-06: removal is a state, never a physical delete, so a
    # concurrent advance cannot resurrect the entry.
    return _transition(path, name, ("armed", "paused", "stalled", "done"),
                       {"state": "removed"}, "remove", claimant=claimant)


def loop_wake(path: str, name: str, checkpoint: str = "", ctx: Any = None) -> Any:
    loop = _find(path, name)
    if not loop:
        return CortexOUT.error(f"loop {name!r} not found", code="NOT_FOUND")
    target = loops_mod.write_wake(path, name, reason="manual",
                          checkpoint=checkpoint or loop.get("checkpoint", ""))
    if not target:
        return CortexOUT.error("could not write wake", code="WRITE_FAILED")
    loops_mod.log_event(path, loop.get("session", ""), name, "wake", "manual")
    return CortexOUT.work(f"loop.wake ok name={name}", name=name)


def loop_suggest(path: str, name: str = "", ctx: Any = None) -> Any:
    """Suggest a recurrence for a loop (or the active ones) based on the
    observed execution pattern — read-only."""
    loops = [l for l in loops_mod.load_loops(_brain(path)) if l.get("state") != "removed"]
    if name:
        loops = [l for l in loops if l["name"] == name]
        if not loops:
            return CortexOUT.error(f"loop {name!r} not found", code="NOT_FOUND")
    suggestions = []
    for l in loops:
        rec = l.get("recurrence", "on_bootstrap")
        phases = l.get("phases") or []
        if len(phases) > 1:
            sugg = ("multi-phase work — keep on_bootstrap so every governed "
                    "entry resumes it; add expected_duration per phase for "
                    "accurate stall detection")
        elif rec == "on_heartbeat":
            sugg = ("heartbeat-driven — keep on_heartbeat; it only fires on "
                    "watch ticks, never on bootstrap")
        else:
            sugg = ("single-shot — on_bootstrap until complete; consider "
                    "cooldown:1h if it should not re-fire every call")
        suggestions.append({"name": l["name"], "current": rec, "suggestion": sugg})
    return CortexOUT.work(f"loop.suggest ok total={len(suggestions)}",
                          suggestions=suggestions)


handler_schemas: list[dict[str, Any]] = [
    {"name": "loop.register", "fn": loop_register,
     "description": "Register an autonomous loop in the brain §LOOPS registry (state armed). phases[] + recurrence (on_bootstrap|every_bootstrap|cooldown:<n>h|on_heartbeat) + max_stall(<n>m) declare the cycle.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"}, "name": {"type": "string"},
         "phases": {"type": "array", "items": {"type": "string"}},
         "recurrence": {"type": "string"}, "max_stall": {"type": "string"},
         "expected_duration": {"type": "string"}, "owner": {"type": "string"},
         "session": {"type": "string"}, "next_": {"type": "string"},
         "checkpoint": {"type": "string"}, "content": {"type": "string"}},
         "required": ["name"]}},
    {"name": "loop.list", "fn": loop_list,
     "description": "List registered loops (name, state, recurrence, next) — tombstoned entries excluded.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "loop.activate", "fn": loop_activate,
     "description": "Arm a registered loop for dispatch (armed|paused|stalled → active; retries reset).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "name": {"type": "string"}, "claimant": {"type": "string"}}, "required": ["name"]}},
    {"name": "loop.deactivate", "fn": loop_deactivate,
     "description": "Silence an active loop (→ paused) without removing it.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "name": {"type": "string"}, "claimant": {"type": "string"}}, "required": ["name"]}},
    {"name": "loop.advance", "fn": loop_advance,
     "description": "Advance the loop to the next phase: index+1, checkpoint persisted in §LOOPS, progress event appended to the session timelog.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"}, "name": {"type": "string"},
         "checkpoint": {"type": "string"}, "next_": {"type": "string"},
         "claimant": {"type": "string"}},
         "required": ["name"]}},
    {"name": "loop.complete", "fn": loop_complete,
     "description": "Close an active loop (→ done); the dispatcher stops signalling it.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "name": {"type": "string"}, "summary": {"type": "string"}, "claimant": {"type": "string"}}, "required": ["name"]}},
    {"name": "loop.remove", "fn": loop_remove,
     "description": "Eliminate a loop from the registry (tombstone; requires deactivate first if active).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "name": {"type": "string"}, "claimant": {"type": "string"}}, "required": ["name"]}},
    {"name": "loop.wake", "fn": loop_wake,
     "description": "Manually queue a WAKE for a loop — the next governed call surfaces it as pending_loop.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "name": {"type": "string"}, "checkpoint": {"type": "string"}}, "required": ["name"]}},
    {"name": "loop.suggest", "fn": loop_suggest,
     "description": "Suggest a recurrence for a loop (or all) based on its execution pattern — read-only.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "name": {"type": "string"}}, "required": ["path"]}},
]
