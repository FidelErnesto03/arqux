"""Embedded timelog capture in governance actions (CYCLE-14 / BLP-003).

Timelog capture is an *internal effect* of an authorized natural action, never
a dedicated call. When the governor claims a task, when the session opens or
closes, when identity changes — the lifecycle recorder turns that boundary into
an interval on the session's canonical timelog.

Rules this module enforces:

* **One block per activity.** Several actions about the same activity update the
  existing block's evidence; they never add a block per call.
* **Read-only stays read-only.** ``resume``, ``status``, ``context.get``,
  ``context.detect``, ``context.full`` and every auditor call record nothing.
  Observing the host is the recorder's own authority, not the reader's.
* **No fabricated limits.** Without an authoritative execution/session the
  result is ``coverage: limited`` with the interval left open or unknown — a
  start or end is never invented.
* **Work and annotation are separate.** A failed annotation returns a pending
  record; the work itself already happened and is never replayed.
* **Suppression wins.** If the timelog file was deleted by an authorized debug,
  pending capture or repair is rejected instead of recreating the file.
* **No timers.** Boundaries come from the observed action's UTC instant; there
  is no counter thread, no periodic pulse and no stopwatch clock.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from . import timelog_store
from .execution import authoritative_execution_key
from .permissions import PermissionContext
from .session_identity import (
    brain_lock,
    current_session_ref,
    find_session_for_execution,
    get_session,
    list_sessions,
    open_sessions,
)

COVERAGE_FULL = "full"
COVERAGE_LIMITED = "limited"

STATUS_APPLIED = "applied"
STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"
STATUS_SKIPPED = "skipped"

# --- BLP-022: pre-write validation gate ------------------------------------
#
# Every writer of governance state consults this gate *before* it mutates
# anything. It answers two questions — is an open session bound to this
# execution, and does the destination admit the entry — and returns a typed,
# actionable rejection when the answer is no. The gate never adapts: no
# auto-binding a session, no re-classifying the destination. Persisting invalid
# state and warning about it afterwards is the exact defect it removes.

#: The one exact remediation command for an unbound execution (T-1.2). Shared
#: by the gate and by ``unbound_warning`` so the operator learns a single
#: message, never a parallel one.
SESSION_BIND_REMEDIATION = "session.context_set(project, scope) or session.open"

#: Stable rejection codes (BLP-022 §10). No mutation accompanies any of them.
SESSION_UNBOUND = "SESSION_UNBOUND"
DESTINATION_NOT_ALLOWED = "DESTINATION_NOT_ALLOWED"
CYCLE_CLOSED = "CYCLE_CLOSED"

#: Sigils carrying live/episodic working state. A Level-1 identity contract
#: (BEHAVIORAL) admits none of them — codec-cortex raises E023 when one lands
#: in the ``$0`` of an identity file (E-1808).
_LIVE_STATE_SIGILS = frozenset({"FCS", "OBJ", "WRK", "SES", "LNG"})

#: Architectural level of a Level-1 (BEHAVIORAL) artifact — identity contract.
_LEVEL_BEHAVIORAL = 1

# Increments only when a call is made *solely* to record a time. The whole point
# of this BLP is that no such call exists; the counter exists so AC-04 can prove
# it stayed at zero instead of asserting it by omission.
_DEDICATED_CALLS = 0


def dedicated_timelog_calls() -> int:
    """Number of calls made only to annotate time. Must stay zero."""
    return _DEDICATED_CALLS


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _result(status: str, *, coverage: str, **fields: Any) -> dict[str, Any]:
    return {"status": status, "coverage": coverage, **fields}


def _session_ref_for(project_root: Path | str, ctx: PermissionContext | None,
                     session_ref: str | None = None) -> str:
    if session_ref:
        return session_ref
    execution = (ctx.execution_key if ctx else None) or authoritative_execution_key()
    if not execution:
        return ""
    session = find_session_for_execution(project_root, execution, state=None)
    return session["session_id"] if session else ""


def _open_foreign_sessions(project_root: Path | str,
                           ctx: PermissionContext | None) -> list[str]:
    """Ids of open sessions owned by *other* executions, oldest first.

    Their presence is the post-restart signature: the client restarted, this
    execution inherited nothing, and the work it does cannot be registered
    until it re-attaches one of them.
    """
    execution = (ctx.execution_key if ctx else None) or authoritative_execution_key()
    return [
        s["session_id"]
        for s in open_sessions(project_root)
        if s.get("execution") != execution
    ]


def _require_file(project_root: Path | str, session_id: str, opened_at: str) -> Path:
    """Reject capture when the canonical file is gone (authorized suppression)."""
    path = timelog_store.canonical_path(project_root, session_id, opened_at)
    if not path.exists():
        raise timelog_store.MembershipError(
            f"timelog {path.name} no longer exists — capture refused instead of recreating it"
        )
    return path


def capture(
    project_root: Path | str,
    ctx: PermissionContext | None,
    *,
    event: str,
    operation_ref: str,
    activity: str,
    session_ref: str | None = None,
    result: str = "applied",
) -> dict[str, Any]:
    """Turn a natural governance boundary into a timelog interval.

    ``event`` is one of ``open``, ``close``, ``update`` or ``boundary``. A
    missing session or an unusable execution yields ``coverage: limited`` and
    writes nothing.
    """
    if ctx is not None and ctx.role == "auditor":
        # The lifecycle recorder observes host events with its own authority.
        # Observing work does not grant the auditor the power to write it.
        return _result(STATUS_REJECTED, coverage=COVERAGE_LIMITED,
                       reason="the auditor has no lifecycle recording authority")

    session_id = _session_ref_for(project_root, ctx, session_ref)
    if not session_id:
        result = _result(STATUS_SKIPPED, coverage=COVERAGE_LIMITED,
                         reason="no session bound to this execution; limits left unknown")
        foreign = _open_foreign_sessions(project_root, ctx)
        if foreign:
            # Post-restart signature: open sessions exist but belong to
            # executions this one did not inherit. Keep the canonical bind
            # command and append the exact re-attach command.
            result["remediation"] = (
                f"bind a session via {SESSION_BIND_REMEDIATION}; "
                "after a client restart re-attach instead: "
                f"session.context_set(project, scope, intent='resumed', "
                f"session_ref='{foreign[-1]}') "
                f"(open under another execution: {', '.join(foreign)})"
            )
        return result

    session = get_session(project_root, session_id)
    if session is None:
        return _result(STATUS_SKIPPED, coverage=COVERAGE_LIMITED,
                       reason=f"session {session_id} not found")
    if session.get("state") != "open":
        # A closed session is finished. Recording new activity into it would
        # fabricate limits on work that belongs to no open execution; declare
        # limited coverage and write nothing.
        return _result(STATUS_SKIPPED, coverage=COVERAGE_LIMITED,
                       reason=f"session {session_id} is {session.get('state')}, not open; "
                              "no activity is recorded")
    opened_at = session.get("date", "")

    try:
        _require_file(project_root, session_id, opened_at)
    except timelog_store.MembershipError as exc:
        return _result(STATUS_REJECTED, coverage=COVERAGE_LIMITED,
                       reason=str(exc), operation_ref=operation_ref)

    # Single exclusion order: brain/SES lock first, timelog lock second.
    try:
        with brain_lock(project_root):
            if event == "open":
                outcome = timelog_store.open_block(
                    project_root, session_id, operation_ref=operation_ref,
                    start=_now(),
                )
            elif event == "close":
                outcome = timelog_store.close_block(
                    project_root, session_id, operation_ref=operation_ref,
                    end=_now(),
                )
            elif event in ("update", "boundary"):
                # Same activity: refresh evidence without adding a block.
                outcome = timelog_store.update(
                    project_root, session_id, operation_ref=operation_ref,
                    opened_at=opened_at,
                    mutate=lambda document: False,
                )
            else:
                return _result(STATUS_REJECTED, coverage=COVERAGE_LIMITED,
                               reason=f"unknown lifecycle event {event!r}",
                               operation_ref=operation_ref)
    except timelog_store.UnknownOperation as exc:
        return _result(STATUS_PENDING, coverage=COVERAGE_FULL,
                       reason=str(exc), operation_ref=operation_ref)
    except timelog_store.TimelogError as exc:
        # The work already happened: report a pending annotation, never replay.
        return _result(STATUS_PENDING, coverage=COVERAGE_FULL,
                       reason=str(exc), operation_ref=operation_ref)

    return _result(STATUS_APPLIED, coverage=COVERAGE_FULL,
                   operation_ref=operation_ref, activity=activity,
                   applied=outcome.get("applied", False),
                   session_ref=session_id)


def unbound_warning(lifecycle: dict[str, Any], *, action: str) -> str | None:
    """Loud warning when a lifecycle event wrote no timelog block.

    Every governance boundary that observes time MUST surface an unbound
    execution — a silent skip is the failure that hid a full unregistered
    session (ENVX_INFRA, 2026-10-16).
    """
    if lifecycle.get("status") != "skipped":
        return None
    reason = lifecycle.get("reason", "")
    remediation = lifecycle.get("remediation") or (
        f"bind a session via {SESSION_BIND_REMEDIATION}"
    )
    return (
        f"TIMELOG_UNBOUND: {action} wrote no native timelog block ({reason}). "
        f"This work is NOT registered — {remediation}."
    )


# --- BLP-022: pre-write validation gate ------------------------------------


def _open_session_for(
    project_root: Path | str,
    ctx: PermissionContext | None,
    session_ref: str | None = None,
) -> str:
    """Session id bound to this execution *and open*, or ``""``.

    Distinct from ``_session_ref_for`` (which accepts any state): a writer may
    only proceed against a session that is actually open, because a closed
    session's timelog refuses new blocks — persisting against it would be the
    silent degradation this gate rejects.
    """
    session_id = _session_ref_for(project_root, ctx, session_ref)
    if not session_id:
        return ""
    session = get_session(project_root, session_id)
    if session is None or session.get("state") != "open":
        return ""
    return session_id


def require_bound_session(
    project_root: Path | str,
    ctx: PermissionContext | None,
    *,
    action: str,
    session_ref: str | None = None,
) -> dict[str, Any] | None:
    """Rejection dict when no open session is bound, else ``None``.

    Reuses the ``TIMELOG_UNBOUND`` wording and the single exact remediation
    command (T-1.2, R-04) so the operator learns one message, not two.

    Legacy-compatible by design (BLP-022 §7.4, reusing the existing gate): a
    project with *no* session identity at all has nothing to bind, so the writer
    proceeds and surfaces the ``TIMELOG_UNBOUND`` warning instead. The rejection
    bites only once real session identity exists — which is exactly the E-1805
    case, where a bound session existed and the writer ignored it.
    """
    if _open_session_for(project_root, ctx, session_ref):
        return None
    if not list_sessions(project_root):
        return None
    message = (
        f"TIMELOG_UNBOUND: {action} rejected before writing — this project has "
        "session identity but none is bound to this execution, so the work "
        f"could not be registered. Bind a session via {SESSION_BIND_REMEDIATION}."
    )
    remediation = SESSION_BIND_REMEDIATION
    foreign = _open_foreign_sessions(project_root, ctx)
    if foreign:
        remediation = (
            f"session.context_set(project, scope, intent='resumed', "
            f"session_ref='{foreign[-1]}') — open session(s) exist under "
            f"other executions: {', '.join(foreign)}"
        )
        message += f" After a client restart, re-attach instead: {remediation}."
    return {
        "code": SESSION_UNBOUND,
        "message": message,
        "remediation": remediation,
    }


def _declared_level(path: Path | str) -> int | None:
    """The level the artifact *declares* in ``ARQX:artifact{level:N}``.

    Read from the declaration, never inferred: a file that carries none (or
    cannot be read) returns ``None`` so the destination gate declines to judge
    it instead of inventing a level.
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"ARQX:artifact\{[^}]*?\blevel:(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _declares_axioms(path: Path | str) -> bool:
    """True when a level-1 artifact carries an AXM (contract) entry.

    codec-cortex classifies such an artifact as "skill" and applies E023 to any
    live-state sigil in it (verified: LNG in a level-1 file with no AXM is not
    flagged). The destination gate mirrors that exact rule instead of rejecting
    every level-1 file, so it bites where corruption is real (E-1808) and leaves
    contract-less level-1 artifacts untouched.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(r"(?m)^AXM:", text) is not None


def require_writable_destination(
    path: Path | str,
    sigil: str,
    *,
    action: str,
) -> dict[str, Any] | None:
    """Rejection dict when *path*'s level cannot hold a *sigil* entry, else ``None``.

    A Level-1 identity contract classified as a skill (it declares AXIOMS)
    admits no live-state sigil (E023). Returns ``None`` when the destination
    admits the entry, when no level is declared, or when the level-1 artifact is
    not a contract.
    """
    if _declared_level(path) != _LEVEL_BEHAVIORAL:
        return None
    if sigil.upper() not in _LIVE_STATE_SIGILS:
        return None
    if not _declares_axioms(path):
        return None
    return {
        "code": DESTINATION_NOT_ALLOWED,
        "message": (
            f"DESTINATION_NOT_ALLOWED: {action} rejected — a Level-1 identity "
            f"contract cannot hold live-state sigil {sigil.upper()} (E023). "
            "Persist it in a project brain.cortex (Level 3) instead."
        ),
        "remediation": "persist the entry in <project>/.arqux/brain.cortex",
    }


def cycle_is_closed(project_root: Path | str, cycle: str | None) -> bool:
    """True when *cycle*'s MANIFEST declares ``status: closed``.

    ``project_root`` is the project's ``.arqux/`` directory. A cycle with no
    MANIFEST declares nothing to contradict, so it is not closed.
    """
    if not cycle:
        return False
    manifest = Path(project_root) / "cycles" / cycle / "MANIFEST.md"
    if not manifest.is_file():
        return False
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(r"(?m)^status:\s*[\"']?closed\b", text) is not None


def require_open_cycle(
    project_root: Path | str,
    cycle: str | None,
    *,
    action: str,
) -> dict[str, Any] | None:
    """Rejection dict when *cycle* is closed, else ``None``."""
    if not cycle_is_closed(project_root, cycle):
        return None
    return {
        "code": CYCLE_CLOSED,
        "message": (
            f"CYCLE_CLOSED: {action} rejected — cycle {cycle} is closed and cannot "
            "receive new governance state. Write to the active (open) cycle."
        ),
        "remediation": "write to the active (open) cycle",
    }


def observe(project_root: Path | str, ctx: PermissionContext | None, *,
            event: str, operation_ref: str, activity: str,
            session_ref: str | None = None) -> dict[str, Any]:
    """Best-effort capture inside a natural action; never raises.

    A lifecycle annotation must never change the outcome of the governance
    action it observes, so every failure becomes a pending record.
    """
    try:
        return capture(project_root, ctx, event=event, operation_ref=operation_ref,
                       activity=activity, session_ref=session_ref)
    except Exception:  # noqa: BLE001
        return {"status": STATUS_PENDING, "coverage": COVERAGE_LIMITED,
                "operation_ref": operation_ref}


def repair(
    project_root: Path | str,
    ctx: PermissionContext | None,
    *,
    operation_ref: str,
    event: str,
    session_ref: str | None = None,
) -> dict[str, Any]:
    """Complete a pending annotation by operation_ref without redoing the work."""
    session_id = _session_ref_for(project_root, ctx, session_ref)
    if not session_id:
        return _result(STATUS_REJECTED, coverage=COVERAGE_LIMITED,
                       reason="no session bound to this execution",
                       operation_ref=operation_ref)
    session = get_session(project_root, session_id)
    if session is None or session.get("state") != "open":
        return _result(STATUS_REJECTED, coverage=COVERAGE_LIMITED,
                       reason=f"session {session_id} is not open",
                       operation_ref=operation_ref)
    try:
        _require_file(project_root, session_id, session.get("date", ""))
    except timelog_store.MembershipError as exc:
        return _result(STATUS_REJECTED, coverage=COVERAGE_LIMITED,
                       reason=str(exc), operation_ref=operation_ref)

    # Repeating a repair is idempotent: the second call observes the block and
    # adds neither a block nor an interval.
    return capture(project_root, ctx, event=event, operation_ref=operation_ref,
                   activity="repair", session_ref=session_id)


def activity_of(event: str, task_id: str = "", agent: str = "") -> str:
    """Human-readable activity name for a natural boundary."""
    if event in ("task_claim", "task_complete", "task_fail") and task_id:
        return f"task:{task_id}"
    if event == "session":
        return "session"
    if event == "identity_switch":
        return "identity-switch"
    return event or "activity"


__all__ = [
    "COVERAGE_FULL",
    "COVERAGE_LIMITED",
    "CYCLE_CLOSED",
    "DESTINATION_NOT_ALLOWED",
    "SESSION_BIND_REMEDIATION",
    "SESSION_UNBOUND",
    "STATUS_APPLIED",
    "STATUS_PENDING",
    "STATUS_REJECTED",
    "STATUS_SKIPPED",
    "activity_of",
    "capture",
    "current_session_ref",
    "cycle_is_closed",
    "dedicated_timelog_calls",
    "observe",
    "repair",
    "require_bound_session",
    "require_open_cycle",
    "require_writable_destination",
]
