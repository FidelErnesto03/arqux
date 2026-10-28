"""Real session identity entries in the project brain (CYCLE-14 / BLP-001).

Before this module the ArqUX session was not an object: ``session.close``
minted a PULSE event id (``E-XXXX``) and wrote the ``SES:`` summary as its
payload, so the *only* thing that identified a session was a position in a flat
event list. ``resume``/``status`` took the last entry and ``session.pulse.compact``
pruned everything between the two last session entries.

A session now has an identity of its own: an ``SESxxx`` entry in ``$4 SESSIONS``
of the project brain, carrying its own original UTC start, the execution it
belongs to, and the timelog file name derived from both. The PULSE ``SES:`` line
is retained as a summary payload, but it is no longer the identity.

Guarantees:

* Monotonic ``SESxxx`` allocation under an exclusive file lock — an atomic
  replace is not enough to exclude concurrent updates.
* Idempotent opening: repeating the same binding for the same execution returns
  the same session, with the same id and the same original start.
* Reentry re-attaches: returning to a context that already has an open session
  for the same ``(agent, project, scope)`` reuses it instead of stacking a
  second one. Only two or more open sessions for that same context are
  ambiguous, and are reported so the caller can decide.
* Renaming on resume is impossible by construction: the name is computed once
  from the original start and stored on the entry.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .concurrency import file_lock, reentrant_file_lock
from .constants import ARQUX_DIR, BRAIN_CORTEX
from .state import crud_add, crud_list, crud_update, find_project_root

SESSION_SECTION = "$4"
SESSION_SIGIL = "SES"
SESSION_ID_RE = re.compile(r"^SES(\d{3,})$")
SESSION_LOCK = ".sessions.lock"
# Brain-wide exclusion. Every read-modify-write of brain.cortex (crud_add /
# crud_update rewrite the whole file) must hold it, or two processes that
# overlap between read and write silently drop the loser's write. The session
# lock only orders *identity allocation*; it does not protect the file.
# Sidecar next to the artifact itself: brain.cortex -> brain.cortex.lock.
# The CRUD read-modify-write takes the same path, so the two exclusions are one.
BRAIN_LOCK_SUFFIX = ".lock"
TIMELOG_DIR = "timelog"


def brain_path(project_root: Path | str) -> Path:
    """Resolve ``<project>/.arqux/brain.cortex`` for *project_root*.

    A path that already points at a ``.arqux`` directory must not get a second
    one: that fallback created ``.arqux/.arqux/brain.cortex.lock``, the nested
    tree the doctor reports as FAIL (BLP-009 guard, residual path).
    """
    root = find_project_root(start=str(project_root))
    if root is not None:
        return root / "brain.cortex"
    base = Path(project_root)
    if base.name == ARQUX_DIR:
        return base / BRAIN_CORTEX
    return base / ".arqux" / "brain.cortex"


def lock_path(project_root: Path | str) -> Path:
    """Path of the exclusive lock guarding session identity allocation."""
    return brain_path(project_root).parent / SESSION_LOCK


def brain_lock_path(project_root: Path | str) -> Path:
    """Path of the brain-wide write lock shared by every brain writer."""
    return brain_path(project_root).with_name(brain_path(project_root).name + BRAIN_LOCK_SUFFIX)


@contextmanager
def brain_lock(project_root: Path | str) -> Iterator[None]:
    """Reentrant brain-wide write lock (see ``concurrency.reentrant_file_lock``)."""
    with reentrant_file_lock(brain_lock_path(project_root)):
        yield


def now_utc() -> str:
    """Current UTC timestamp in the brain's ISO-8601 ``Z`` form."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def timestamp_slug(opened_at: str) -> str:
    """``2026-10-14T23:02:57Z`` -> ``20261014_230257``."""
    digits = re.sub(r"[^0-9]", "", opened_at)
    return f"{digits[0:8]}_{digits[8:14]}" if len(digits) >= 14 else digits


def timelog_name(session_id: str, opened_at: str) -> str:
    """Canonical timelog file name: ``SESXXX_yyyymmdd_hhmiss.cortex``.

    Derived from the session id and the *original* UTC start. Numbers wider than
    three digits are never truncated.
    """
    return f"{session_id}_{timestamp_slug(opened_at)}.cortex"


def timelog_path(project_root: Path | str, session_id: str, opened_at: str) -> Path:
    """Planned durable location of the session's timelog (BLP-002 creates it)."""
    return brain_path(project_root).parent / TIMELOG_DIR / timelog_name(session_id, opened_at)


def _is_session_id(name: str) -> bool:
    return bool(SESSION_ID_RE.match(name or ""))


def list_sessions(project_root: Path | str) -> list[dict[str, Any]]:
    """All real session entries of the project, oldest id first."""
    path = brain_path(project_root)
    if not path.exists():
        return []
    try:
        result = crud_list(path, sigil=SESSION_SIGIL)
    except Exception:
        return []
    sessions = []
    for entry in result.get("entries", []):
        name = entry.get("name") or ""
        if not _is_session_id(name):
            continue  # legacy agent-binding entries keep their own shape
        value = entry.get("value")
        value = value if isinstance(value, dict) else {}
        sessions.append({"session_id": name, **value})
    sessions.sort(key=lambda s: int(SESSION_ID_RE.match(s["session_id"]).group(1)))
    return sessions


def get_session(project_root: Path | str, session_id: str) -> dict[str, Any] | None:
    """Return one session entry by id, or ``None``."""
    if not _is_session_id(session_id or ""):
        return None
    for session in list_sessions(project_root):
        if session["session_id"] == session_id:
            return session
    return None


def next_session_id(project_root: Path | str) -> str:
    """Allocate the next ``SESxxx`` id. Callers must hold the lock."""
    highest = 0
    for session in list_sessions(project_root):
        highest = max(highest, int(SESSION_ID_RE.match(session["session_id"]).group(1)))
    return f"SES{highest + 1:03d}"


def find_session_for_execution(
    project_root: Path | str,
    execution: str,
    *,
    state: str | None = "open",
) -> dict[str, Any] | None:
    """The session bound to *execution*, ignoring any global context pointer."""
    if not execution:
        return None
    for session in reversed(list_sessions(project_root)):
        if session.get("execution") != execution:
            continue
        if state is not None and session.get("state") != state:
            continue
        return session
    return None


def open_sessions(project_root: Path | str, execution: str | None = None) -> list[dict[str, Any]]:
    """Open sessions, optionally restricted to one execution."""
    return [
        s
        for s in list_sessions(project_root)
        if s.get("state") == "open" and (execution is None or s.get("execution") == execution)
    ]


class ReentryAmbiguous(Exception):
    """More than one open session describes the same working context.

    Re-attaching is a decision the lifecycle cannot make alone: two (or more)
    open sessions for the same ``(agent, project, scope)`` mean either the
    caller picks one or a previous one is closed. The handler turns this into a
    question instead of silently stacking a third session.
    """

    code = "SESSION_REENTRY_AMBIGUOUS"

    def __init__(self, alternatives: list[dict[str, Any]]) -> None:
        super().__init__(self.code)
        self.alternatives = alternatives


def _compatible_open_sessions(
    project_root: Path | str, *, agent: str, project: str, scope: str
) -> list[dict[str, Any]]:
    """Open sessions that describe the *same* working context.

    Compatibility is the full ``(agent, project, scope)`` triple: a different
    agent or a different scope is a different context — a legitimate candidate
    for its own session — not an ambiguity.
    """
    return [
        s
        for s in open_sessions(project_root)
        if s.get("agent") == agent
        and s.get("project") == project
        and s.get("scope", "") == (scope or "")
    ]


# --- Day-boundary expiry (policy: Architect 2026-10-23) ----------------------
#
# An open session expires at each day's 00:00 unless it is active and in use
# by the user at that moment — i.e. bound to the *current* execution. Open
# sessions owned by foreign executions (zombie bindings left by client
# restarts) are auto-closed on the next lifecycle touch.


def _is_expired(session: dict[str, Any], execution: str, *,
                now: datetime | None = None) -> bool:
    """True when *session* crossed the day boundary under a foreign execution."""
    if session.get("state") != "open":
        return False
    if (session.get("execution") or "") == execution:
        return False
    opened = session.get("date") or ""
    try:
        opened_dt = datetime.fromisoformat(opened.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return False
    midnight = (now or datetime.now()).astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0)
    return opened_dt < midnight


def expire_stale_sessions(project_root: Path | str, execution: str, *,
                          agent: str) -> list[str]:
    """Close open sessions that crossed 00:00 owned by other executions.

    Caller MUST hold the brain lock. Returns the ids of expired sessions.
    """
    expired: list[str] = []
    for session in list_sessions(project_root):
        if not _is_expired(session, execution):
            continue
        _close_locked(
            project_root, session["session_id"], agent=agent,
            summary=(
                "auto-expired at day boundary — session open since "
                f"{session.get('date', '?')} under foreign execution "
                f"{session.get('execution', '?')} (policy: sessions close at "
                "00:00 unless active and in use)"
            ),
            gaps="auto-expired zombie session",
        )
        expired.append(session["session_id"])
    return expired


def open_session(
    project_root: Path | str,
    *,
    agent: str,
    project: str,
    execution: str,
    scope: str = "",
    blp: str = "",
    intent: str = "new",
    session_ref: str | None = None,
) -> dict[str, Any]:
    """Create — or recover — the real session for this execution.

    ``intent`` is ``new`` (default) or ``resumed``. ``resumed`` requires an
    unambiguous ``session_ref``; it re-attaches that session without changing
    its id or its original start. When no ``session_ref`` is given, an already
    open session bound to this execution is returned unchanged (AC-01).
    """
    path = brain_path(project_root)

    if intent == "resumed":
        if not session_ref:
            raise ValueError("SESSION_SELECTION_REQUIRED")
        existing = get_session(project_root, session_ref)
        if existing is None:
            raise ValueError("SESSION_NOT_FOUND")
        if existing.get("state") == "open":
            owner = existing.get("execution") or ""
            if owner and owner != execution:
                if not _is_expired(existing, execution):
                    # The session belongs to a live execution. Re-attaching it
                    # would silently move another execution's work here; an
                    # explicit instruction must name the session to close.
                    raise PermissionError(
                        f"session {session_ref} is open under execution {owner}"
                    )
                # Day-boundary expiry: the foreign session already crossed
                # 00:00 — close it, then the normal reopen path applies.
                with file_lock(lock_path(project_root)), brain_lock(project_root):
                    expire_stale_sessions(project_root, execution, agent=agent)
            else:
                return _bind(project_root, existing, execution=execution,
                             agent=agent, scope=scope, blp=blp)
        else:
            return _bind(project_root, existing, execution=execution, agent=agent,
                         scope=scope, blp=blp)
        return reopen_session(
            project_root,
            session_ref,
            execution=execution,
            agent=agent,
            scope=scope,
            blp=blp,
        )

    with file_lock(lock_path(project_root)), brain_lock(project_root):
        expire_stale_sessions(project_root, execution, agent=agent)
        current = find_session_for_execution(project_root, execution)
        if current is not None:
            return current  # idempotent: same id, same original start

        # Reentry contract (T-039): returning to a context that already has an
        # open session for this exact (agent, project, scope) re-attaches it
        # instead of silently stacking a new SES. Only genuine ambiguity — two
        # or more open sessions for the same context — is handed back so the
        # caller can decide.
        compatible = _compatible_open_sessions(
            project_root, agent=agent, project=project, scope=scope
        )
        if len(compatible) > 1:
            raise ReentryAmbiguous(sorted(compatible, key=lambda s: s["session_id"]))
        if len(compatible) == 1:
            return _bind(project_root, compatible[0], execution=execution,
                         agent=agent, scope=scope, blp=blp)

        session_id = next_session_id(project_root)
        opened_at = now_utc()
        value = {
            "date": opened_at,
            "state": "open",
            "agent": agent,
            "project": project,
            "execution": execution,
            "intent": intent,
            "scope": scope,
            "blp": blp,
            "timelog": timelog_name(session_id, opened_at),
            "intervals": f"[{opened_at}/]",
            "closed": "",
            # CODEC SES contract requires input/output/outcome non-empty.
            # An open session honestly reports itself in flight; close()
            # rewrites output/outcome with the real result.
            "input": f"{intent}:{project}/{scope}",
            "output": "in_progress",
            "outcome": "open",
            "summary": "",
            "blps": "",
            "tasks": "",
            "decisions": "",
            "gaps": "",
            "lng_count": "0",
            "event": "",
        }
        crud_add(path, SESSION_SECTION, SESSION_SIGIL, session_id, value,
                     create_section=True, force=True)

        # Second file: the canonical timelog (BLP-002). Opening is deliberately
        # not atomic across the two files; the phase is recorded so a retry can
        # complete the same session instead of opening a second one.
        from .timelog_store import ensure_timelog

        timelog = ensure_timelog(project_root, {"session_id": session_id, **value},
                                   operation_ref="session.open")
        value["timelog_state"] = timelog.get("state", "unknown")
        crud_update(path, f"{SESSION_SECTION}/{SESSION_SIGIL}:{session_id}",
                    set_={"timelog_state": value["timelog_state"],
                          "timelog": timelog.get("timelog", "")}, force=True)
        # ``timelog`` is the canonical file name (stable, comparable with the
        # field persisted on the entry); the full location is ``timelog_path``.
        return {"session_id": session_id, **value,
                "timelog": timelog.get("timelog", ""),
                "timelog_path": timelog.get("path", ""),
                "timelog_state": timelog.get("state", "unknown")}


def _bind(
    project_root: Path | str,
    session: dict[str, Any],
    *,
    execution: str,
    agent: str,
    scope: str,
    blp: str,
) -> dict[str, Any]:
    """Re-point an existing session at the current execution/agent."""
    updates = {"execution": execution, "agent": agent}
    if scope:
        updates["scope"] = scope
    if blp:
        updates["blp"] = blp
    with brain_lock(project_root):
        crud_update(brain_path(project_root),
                    f"{SESSION_SECTION}/{SESSION_SIGIL}:{session['session_id']}",
                    set_=updates, force=True)
    return {**session, **updates}


def reopen_session(
    project_root: Path | str,
    session_ref: str,
    *,
    execution: str,
    agent: str,
    scope: str = "",
    blp: str = "",
) -> dict[str, Any]:
    """Reopen a closed session by adding an interval, never changing its identity.

    The original ``date`` and the timelog name are preserved: a resumed session
    keeps the file name it was given at opening (AC-02).
    """
    with brain_lock(project_root):
        # Read and write under the same lock: reading first and writing after
        # loses the interval another process appended in between.
        session = get_session(project_root, session_ref)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")

        opened_at = now_utc()
        intervals = session.get("intervals") or ""
        intervals = (f"{intervals}[{opened_at}/]" if intervals.startswith("[")
                     else f"[{opened_at}/]")
        updates = {"state": "open", "intervals": intervals, "closed": "",
                   "execution": execution, "agent": agent,
                   # Keep the SES entry codec-complete across the reopen:
                   # legacy entries may lack input/output/outcome.
                   "input": session.get("input") or
                            f"{session.get('intent', 'resumed')}:{session.get('project', '')}/{session.get('scope', '')}",
                   "output": "in_progress",
                   "outcome": "open"}
        if scope:
            updates["scope"] = scope
        if blp:
            updates["blp"] = blp
        crud_update(
            brain_path(project_root),
            f"{SESSION_SECTION}/{SESSION_SIGIL}:{session_ref}",
            set_=updates,
            force=True,
        )
    return {**session, **updates}


def _close_open_interval(intervals: str, closed_at: str) -> str:
    """Close the trailing open interval, keeping the ``[start/end]`` notation.

    ``[start/]`` -> ``[start/end]`` and ``[a/b][c/]`` -> ``[a/b][c/end]``. The
    open marker is one character, so slicing it off by two used to eat the
    timestamp as well.
    """
    if not intervals.endswith("/]"):
        return intervals
    return f"{intervals[:-2]}/{closed_at}]"


def close_session(
    project_root: Path | str,
    session_ref: str,
    *,
    agent: str,
    summary: str,
    blps: str = "",
    tasks: str = "",
    decisions: str = "",
    gaps: str = "",
    lng_count: int = 0,
    event: str = "",
) -> dict[str, Any]:
    """Close the original session entry and emit its close evidence."""
    # Read and write under one lock: reading first loses intervals another
    # process appended in between, and the clobbering close loses the interval
    # it never saw.
    with brain_lock(project_root):
        return _close_locked(
            project_root, session_ref, agent=agent, summary=summary, blps=blps,
            tasks=tasks, decisions=decisions, gaps=gaps, lng_count=lng_count,
            event=event,
        )


def _close_locked(
    project_root: Path | str,
    session_ref: str,
    *,
    agent: str,
    summary: str,
    blps: str = "",
    tasks: str = "",
    decisions: str = "",
    gaps: str = "",
    lng_count: int = 0,
    event: str = "",
) -> dict[str, Any]:
    """Close the session. Caller holds the brain lock."""
    session = get_session(project_root, session_ref)
    if session is None:
        raise ValueError("SESSION_NOT_FOUND")

    closed_at = now_utc()
    intervals = _close_open_interval(session.get("intervals") or "", closed_at)

    updates = {
        "state": "closed",
        "closed": closed_at,
        "intervals": intervals,
        "summary": summary,
        # CODEC SES contract: output/outcome carry the episode result.
        # Also repairs legacy entries that predate the fields.
        "input": session.get("input") or
                 f"{session.get('intent', 'new')}:{session.get('project', '')}/{session.get('scope', '')}",
        "output": summary or "session closed without summary",
        "outcome": "closed",
        "blps": blps,
        "tasks": tasks,
        "decisions": decisions,
        "gaps": gaps,
        "lng_count": str(lng_count),
    }
    if event:
        updates["event"] = event
    crud_update(
        brain_path(project_root),
        f"{SESSION_SECTION}/{SESSION_SIGIL}:{session_ref}",
        set_=updates,
        force=True,
    )
    return {**session, **updates}


def current_session_ref(project_root: Path | str, execution: str | None) -> str:
    """Session id bound to *execution*, or ``""`` when there is none.

    Used by evidence writers to label new pulses with their session
    membership. Returns an empty string rather than guessing: an unlabelled
    pulse is never attributed later.
    """
    if not execution:
        return ""
    session = find_session_for_execution(project_root, execution, state=None)
    return session["session_id"] if session else ""
