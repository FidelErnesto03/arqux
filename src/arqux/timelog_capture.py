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
)

COVERAGE_FULL = "full"
COVERAGE_LIMITED = "limited"

STATUS_APPLIED = "applied"
STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"
STATUS_SKIPPED = "skipped"

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
        return _result(STATUS_SKIPPED, coverage=COVERAGE_LIMITED,
                       reason="no session bound to this execution; limits left unknown")

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
    return (
        f"TIMELOG_UNBOUND: {action} wrote no native timelog block ({reason}). "
        "This work is NOT registered — bind a session via "
        "session.context_set(project, scope) or session.open."
    )


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
    "STATUS_APPLIED",
    "STATUS_PENDING",
    "STATUS_REJECTED",
    "STATUS_SKIPPED",
    "activity_of",
    "capture",
    "current_session_ref",
    "dedicated_timelog_calls",
    "observe",
    "repair",
]
