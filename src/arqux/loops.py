"""Autonomous loop registry + dispatcher (BLP-023).

Concurrency model (multi-session, same project): writes are serialised by
the brain file lock; *delivery* is made exclusive by a lease —
``claimed_by``/``claim_ts`` stamped on the loop entry when a caller
surfaces it. A fresh claim by another execution defers the candidate;
the lease expires after ``CLAIM_TTL_S`` so a dead claimant never blocks
resurrection. Wake-file draining uses an O_EXCL claim marker so two
processes cannot consume the same signal.

Loops are declared in the project brain under a ``LOOPS`` section as
``LOOP:<name>{...}`` entries. The brain holds ONLY the registry
(declaration, state, checkpoint); the execution trail (advance, stall,
resume, pause, complete, remove) is appended to the session timelog —
never to the brain.

The universal dispatcher (:func:`dispatch_pending_loops`) is invoked at
every governed entry point (session bootstrap, heartbeat, identity
switch). It is strictly fail-silent: it never raises and its output is
annexed to the caller's response, never masking it (V-01).

A stalled active loop (``now - last_activity`` beyond the phase budget or
``max_stall``) produces a ``WAKE`` file under ``.arqux/loops/`` written
atomically (tmp + rename); the next governed call drains the mailbox and
re-surfaces the loop with ``reason="stall"`` (V-03).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

LOOPS_TITLE = "LOOPS"
LOOP_STATES = ("armed", "active", "paused", "stalled", "done", "removed")
_MAX_TEXT = 500
CLAIM_TTL_S = 600        # a surfaced claim must be renewed (advance/etc.) in 10 min
_WAKE_CLAIM_TTL_S = 120  # stale drain-claim markers self-heal

_LOOP_RE = re.compile(r"LOOP:([\w.-]+)\{([^}]*)\}", re.DOTALL)
_FIELD_RE = re.compile(r'(\w+):"([^"]*)"')
_LIST_RE = re.compile(r"phases:\[([^\]]*)\]")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ---------------------------------------------------------------------------
# Parsing / selection
# ---------------------------------------------------------------------------

def _fields(body: str) -> dict[str, str]:
    out = dict(_FIELD_RE.findall(body))
    m = _LIST_RE.search(body)
    if m:
        out["phases"] = [p.strip().strip('"') for p in m.group(1).split(",") if p.strip()]
    elif isinstance(out.get("phases"), str):
        # Writer serialises lists as "a, b" — accept both bracket and CSV forms.
        out["phases"] = [p.strip() for p in out["phases"].split(",") if p.strip()]
    return out


def load_loops(brain_path: str | Path) -> list[dict]:
    """Parse all ``LOOP:`` entries from the brain text (read-only, tolerant)."""
    try:
        text = Path(brain_path).read_text(encoding="utf-8")
    except OSError:
        return []
    loops = []
    for m in _LOOP_RE.finditer(text):
        f = _fields(m.group(2))
        f["name"] = m.group(1)
        loops.append(f)
    return loops


def _cooldown_hours(rec: str) -> float | None:
    m = re.fullmatch(r"cooldown:(\d+(?:\.\d+)?)h?", rec.strip())
    return float(m.group(1)) if m else None


def _phase_budget_minutes(loop: dict) -> float:
    """Stall budget: per-phase expected_duration wins over global max_stall (V-05)."""
    dur = loop.get("expected_duration", "")
    if dur:
        try:
            mins = float(re.sub(r"\D.*", "", dur)) or 0.0
            if mins:
                return mins
        except (TypeError, ValueError):
            pass
    try:
        return float(re.sub(r"\D.*", "", loop.get("max_stall", "60")) or 60.0) or 60.0
    except (TypeError, ValueError):
        return 60.0


def _is_due(loop: dict, now: float, on_heartbeat: bool) -> bool:
    if loop.get("state") != "active":
        return False
    rec = (loop.get("recurrence") or "on_bootstrap").strip()
    if rec == "on_heartbeat" and not on_heartbeat:
        return False
    cd = _cooldown_hours(rec)
    if cd is not None:
        try:
            last = float(loop.get("last_run") or 0)
        except (TypeError, ValueError):
            last = 0.0
        if now - last < cd * 3600:
            return False
    return True


def is_stalled(loop: dict, now: float) -> bool:
    if loop.get("state") != "active":
        return False
    try:
        last = float(loop.get("last_activity") or 0)
    except (TypeError, ValueError):
        last = 0.0
    if not last:
        return False
    return now - last > _phase_budget_minutes(loop) * 60


def phase_name(loop: dict) -> str:
    phases = loop.get("phases") or []
    idx = int(loop.get("index") or 0)
    if isinstance(phases, list) and 0 <= idx < len(phases):
        return str(phases[idx])
    return f"phase-{idx}"


# ---------------------------------------------------------------------------
# WAKE mailbox (.arqux/loops/) — atomic write, idempotent drain (V-03)
# ---------------------------------------------------------------------------

def _loops_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".arqux" / "loops"


def write_wake(project_root: str | Path, name: str, *, reason: str,
               checkpoint: str = "") -> Path | None:
    """Atomically queue a wake signal for *name* (tmp + rename)."""
    try:
        d = _loops_dir(project_root)
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"{name}.wake"
        tmp = d / f".{name}.wake.tmp"
        safe_cp = _sanitize(checkpoint)
        tmp.write_text(
            f'WAKE:{name}{{reason:"{reason}", checkpoint:"{safe_cp}", '
            f'ts:"{time.time():.0f}"}}\n',
            encoding="utf-8",
        )
        tmp.replace(target)
        return target
    except OSError:
        return None


def drain_wakes(project_root: str | Path) -> list[dict]:
    """Read and remove every WAKE entry exactly once; corrupt files are
    quarantined under ``.arqux/loops/.bad/`` and never abort the drain."""
    d = _loops_dir(project_root)
    out: list[dict] = []
    try:
        files = sorted(d.glob("*.wake"))
    except OSError:
        return out
    for f in files:
        # Atomic claim (O_EXCL): only one concurrent process consumes a
        # wake; stale markers self-heal after _WAKE_CLAIM_TTL_S.
        marker = d / f".{f.name}.claim"
        try:
            os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            try:
                if time.time() - marker.stat().st_mtime < _WAKE_CLAIM_TTL_S:
                    continue
                marker.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        try:
            text = f.read_text(encoding="utf-8")
            m = re.search(r"WAKE:([\w.-]+)\{([^}]*)\}", text)
            if m:
                out.append({"loop": m.group(1), **_fields(m.group(2))})
            else:
                raise ValueError("malformed")
            f.unlink(missing_ok=True)
            # Consume only the surfaced wake: further files keep their
            # signals alive for the next governed call (Heimdall H-01).
            break
        except (OSError, ValueError):
            try:
                bad = d / ".bad"
                bad.mkdir(exist_ok=True)
                f.replace(bad / f.name)
            except OSError:
                pass
        finally:
            marker.unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------------------
# Universal dispatcher — fail-silent, annexed output (V-01)
# ---------------------------------------------------------------------------

def _claim_fresh(loop: dict, now: float) -> bool:
    try:
        ts = float(loop.get("claim_ts") or 0)
    except (TypeError, ValueError):
        return False
    return bool(loop.get("claimed_by")) and ts > 0 and now - ts < CLAIM_TTL_S


def _claimed_by_other(loop: dict, claimant: str, now: float) -> bool:
    return _claim_fresh(loop, now) and loop.get("claimed_by") != claimant


def _stamp_claim(brain_path: Path, name: str, claimant: str) -> None:
    """Mark the loop as surfaced to *claimant* (lease, CLAIM_TTL_S)."""
    if not claimant:
        return
    try:
        from .core.state._crud import crud_update
        crud_update(Path(brain_path), f"LOOP:{name}",
                    set_={"claimed_by": claimant,
                          "claim_ts": f"{time.time():.0f}"}, force=True)
    except Exception:  # noqa: BLE001 — stamping is best-effort
        pass


def dispatch_pending_loops(brain_path: str | Path, *,
                           on_heartbeat: bool = False,
                           claimant: str = "") -> dict | None:
    """Surface the pending autonomous loop for the caller's response.

    Order: drained WAKE entries first (stall/manual), then due ``active``
    loops by recurrence, then the legacy ``WRK:current{loop,phase,next}``
    fallback when no §LOOPS registry exists. Never raises (V-01).

    *claimant* (typically the execution id) makes delivery exclusive: a
    loop surfaced to one execution is deferred for others until the lease
    expires — same-project multi-session cannot double-dispatch it.
    """
    try:
        brain_path = Path(brain_path)
        project_root = brain_path.parent.parent
        now = time.time()

        loops = [l for l in load_loops(brain_path) if l.get("state") != "removed"]

        # Inline stall detection: even without the watch daemon, a governed
        # call still notices a dead loop and queues its own wake.
        for loop in loops:
            if is_stalled(loop, now):
                write_wake(project_root, loop["name"], reason="stall",
                           checkpoint=loop.get("checkpoint", ""))

        wakes = drain_wakes(project_root)
        if wakes:
            w = wakes[0]
            loop = next((l for l in loops if l["name"] == w["loop"]), None) or {}
            if not (loop and _claimed_by_other(loop, claimant, now)):
                _stamp_claim(brain_path, w["loop"], claimant)
                return {"loop": w["loop"], "phase": phase_name(loop) if loop else "",
                        "next": loop.get("next", ""), "reason": w.get("reason", "manual"),
                        "checkpoint": w.get("checkpoint", ""),
                        "watch": _watch_status(project_root, now)}
            # Surfaced for the claimant only — the consumed signal is safe:
            # the loop stays 'active' and re-surfaces for its owner via due.

        for loop in loops:
            if (_is_due(loop, now, on_heartbeat)
                    and not _claimed_by_other(loop, claimant, now)):
                _stamp_claim(brain_path, loop["name"], claimant)
                return {"loop": loop["name"], "phase": phase_name(loop),
                        "next": loop.get("next", ""), "reason": "due",
                        "checkpoint": loop.get("checkpoint", ""),
                        "watch": _watch_status(project_root, now)}

        return _legacy_pending_loop(brain_path)
    except Exception:  # noqa: BLE001 — fail-silent by contract (V-01)
        return None


def _watch_status(project_root: Path, now: float) -> str:
    """Report the watch daemon liveness (V-02): alive / stale / absent."""
    try:
        tick_file = _loops_dir(project_root) / ".watch"
        text = tick_file.read_text(encoding="utf-8")
        m = re.search(r"watch_last_tick:(\d+)", text)
        if not m:
            return "stale"
        return "alive" if now - int(m.group(1)) < 600 else "stale"
    except OSError:
        return "absent"


def _legacy_pending_loop(brain_path: Path) -> dict | None:
    """Pre-BLP-023 fallback: WRK:current{loop,phase,next} in the brain."""
    try:
        text = brain_path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Several WRK:current entries may coexist — take the first declaring a loop.
    fields: dict = {}
    for m in re.finditer(r"WRK:current\{([^}]*)\}", text):
        f = dict(_FIELD_RE.findall(m.group(1)))
        if f.get("loop"):
            fields = f
            break
    if not fields:
        return None
    loop, phase = fields.get("loop", ""), fields.get("phase", "")
    if not loop or not phase:
        return None
    if phase.casefold().startswith(("done", "h-", "complet")):
        return None
    return {"loop": loop, "phase": phase, "next": fields.get("next", ""),
            "reason": "legacy", "checkpoint": ""}


# ---------------------------------------------------------------------------
# Schema validation (V-04) + timelog trail
# ---------------------------------------------------------------------------

def _sanitize(text: str) -> str:
    return _CTRL_RE.sub("", str(text))[:_MAX_TEXT]


def validate_loop_text(text: str) -> str | None:
    """Return an error string if *text* violates the schema bounds (V-04)."""
    if _CTRL_RE.search(text or ""):
        return "control characters not allowed in loop fields"
    if len(text or "") > _MAX_TEXT:
        return f"field exceeds {_MAX_TEXT} chars"
    return None


def log_event(project_root: str | Path, session: str, loop: str,
              event: str, detail: str = "") -> None:
    """Append a loop progress event to the session timelog — never the
    brain. Tolerates missing timelog silently (trail is best-effort)."""
    if not session:
        return
    tdir = Path(project_root) / ".arqux" / "timelog"
    try:
        files = sorted(tdir.glob(f"{session}_*.cortex"))
    except OSError:
        return
    if not files:
        return
    try:
        with files[-1].open("a", encoding="utf-8") as fh:
            fh.write(
                f'\nLOOP:{loop}{{event:"{event}", detail:"{_sanitize(detail)}", '
                f'ts:"{time.time():.0f}"}}\n'
            )
    except OSError:
        pass
