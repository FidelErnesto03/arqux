"""`timelog` module — read, correct and purge a session's timelog (BLP-004).

Handlers:
    timelog.query   — read-only view of a session (or an explicit multisession view)
    timelog.review  — authorized correction: writes a revision with reason
    timelog.purge   — authorized preview/archive/summarize/delete of a selection

Query never writes. Review and purge require the user's explicit authorization
reference; purge previews by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import timelog_control, timelog_store
from ..cortex_out import CortexOUT
from ..execution import authoritative_execution_key
from ..permissions import PermissionContext
from ..session_identity import find_session_for_execution, get_session
from ..state import find_project_root


def _resolve_session(root: Path, session_ref: str | None,
                     ctx: PermissionContext | None) -> tuple[dict[str, Any] | None, dict | None]:
    """The session this call is about: explicit reference, else this execution's."""
    if session_ref:
        session = get_session(root, session_ref)
        if session is None:
            return None, {"code": "SESSION_NOT_FOUND",
                          "message": f"session {session_ref!r} not found in this project"}
        return session, None
    execution = (ctx.execution_key if ctx else None) or authoritative_execution_key()
    if execution:
        session = find_session_for_execution(root, execution, state=None)
        if session is not None:
            return session, None
    return None, {"code": "SESSION_BINDING_REQUIRED",
                  "message": ("no session bound to this execution — pass session_ref "
                              "explicitly; the latest session is never selected implicitly")}


def _root(project: str | None, path: str | None) -> Path | None:
    return find_project_root(start=path)


def query_handler(
    session_ref: str | None = None,
    view: str = "session",
    limit: int | None = None,
    offset: int = 0,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read-only view of a session's timelog."""
    root = _root(None, path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    if view == "multisession":
        result = timelog_control.query(root, "", view="multisession", limit=limit, offset=offset)
        return CortexOUT.work("timelog.query ok view=multisession", **result)
    session, error = _resolve_session(root, session_ref, ctx)
    if error:
        return CortexOUT.error(error["message"], code=error["code"])
    result = timelog_control.query(root, session["session_id"], view="session",
                                   opened_at=session.get("date"), limit=limit, offset=offset)
    if result.get("error"):
        return CortexOUT.error(result["error"], code=result.get("code", "TIMELOG_ERROR"))
    return CortexOUT.work("timelog.query ok", **result)


def summary_handler(
    period: str = "day",
    session_ref: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Aggregate the record by day, session or project (read-only)."""
    root = _root(None, path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    session, error = _resolve_session(root, session_ref, ctx)
    if error and period == "session":
        return CortexOUT.error(error["message"], code=error["code"])
    result = timelog_control.summary(
        root, (session or {}).get("session_id", ""), period=period,
    )
    if result.get("error"):
        return CortexOUT.error(result["error"], code=result.get("code", "TIMELOG_ERROR"))
    return CortexOUT.work(f"timelog.summary {period}", **result)


def review_handler(
    block_id: str,
    changes: dict[str, Any],
    reason: str,
    authorization_ref: str,
    session_ref: str | None = None,
    expected_revision: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Authorized correction of one activity block."""
    root = _root(None, path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    session, error = _resolve_session(root, session_ref, ctx)
    if error:
        return CortexOUT.error(error["message"], code=error["code"])
    result = timelog_control.review(
        root, session["session_id"], block_id=block_id, changes=changes or {},
        reason=reason, authorization_ref=authorization_ref,
        expected_revision=expected_revision, opened_at=session.get("date"),
    )
    if result.get("error"):
        return CortexOUT.error(result["error"], code=result.get("code", "TIMELOG_ERROR"))
    return CortexOUT.work(f"timelog.review {result.get('status')}", **result)


def purge_handler(
    selection: list[str],
    authorization_ref: str,
    mode: str = "delete",
    preview: bool = True,
    session_ref: str | None = None,
    expected_revision: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Preview (default) or apply an archive/summarize/delete of an exact selection."""
    root = _root(None, path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    session, error = _resolve_session(root, session_ref, ctx)
    if error:
        return CortexOUT.error(error["message"], code=error["code"])
    result = timelog_control.purge(
        root, session["session_id"], selection=list(selection or []), mode=mode,
        preview=preview, authorization_ref=authorization_ref,
        expected_revision=expected_revision, opened_at=session.get("date"),
    )
    if result.get("error"):
        return CortexOUT.error(result["error"], code=result.get("code", "TIMELOG_ERROR"))
    return CortexOUT.work(f"timelog.purge {result.get('status')}", **result)


def project_handler(
    destination: str,
    block_ids: list[str],
    action: str = "preview",
    authorization_ref: str = "",
    session_ref: str | None = None,
    expected_revision: str | None = None,
    rounding: str = "none",
    units: str = "seconds",
    account: str = "",
    target: str = "",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Optional external projection of a timelog batch (BLP-006).

    ``preview`` reads; ``prepare`` persists the batch identity; ``send`` requires
    an authorization bound to that identity; ``reconcile`` records the remote
    outcome. Projecting never purges the local origin.
    """
    from .. import timelog_projection

    root = _root(None, path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    session, error = _resolve_session(root, session_ref, ctx)
    if error:
        return CortexOUT.error(error["message"], code=error["code"])
    try:
        result = timelog_projection.project(
            root, session["session_id"], destination=destination,
            block_ids=list(block_ids or []), action=action,
            authorization_ref=authorization_ref, expected_revision=expected_revision,
            rounding=rounding, units=units, account=account, target=target,
            agent=(ctx.agent_id if ctx else ""),
            opened_at=session.get("date"),
        )
    except timelog_projection.InsufficientCapability as exc:
        return CortexOUT.error(str(exc), code="TIMELOG_CAPABILITY_MISSING")
    except timelog_projection.UnsupportedProvider as exc:
        return CortexOUT.error(str(exc), code="TIMELOG_PROVIDER_UNSUPPORTED")
    except timelog_store.UnknownOperation as exc:
        return CortexOUT.error(str(exc), code="TIMELOG_BLOCK_NOT_FOUND")
    except timelog_store.TimelogError as exc:
        return CortexOUT.error(str(exc), code=exc.code)
    if result.get("error"):
        return CortexOUT.error(result["error"], code=result.get("code", "TIMELOG_ERROR"))
    return CortexOUT.work(f"timelog.project {result.get('status')}", **result)


handler_schemas = [
    {
        "name": "timelog.query",
        "fn": query_handler,
        "description": ("Read-only view of a session's timelog: activity blocks with UTC "
                        "durations, integrity flags and a union total. A multisession view "
                        "keeps provenance and creates no joint file."),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_ref": {"type": "string", "description": "Explicit SESxxx reference."},
                "view": {"type": "string", "enum": ["session", "multisession"],
                         "default": "session"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer", "default": 0},
                "path": {"type": "string", "description": "Project root. Defaults to cwd."},
            },
        },
    },
    {
        "name": "timelog.project",
        "fn": project_handler,
        "description": ("Optional external projection of a timelog batch. preview is "
                        "read-only; prepare persists the batch identity; send requires an "
                        "authorization bound to that identity; reconcile records the remote "
                        "outcome. A crash between send and receipt leaves the result unknown. "
                        "Projecting never purges the local origin."),
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string"},
                "block_ids": {"type": "array", "items": {"type": "string"}},
                "action": {"type": "string",
                           "enum": ["preview", "prepare", "send", "reconcile"],
                           "default": "preview"},
                "authorization_ref": {"type": "string"},
                "session_ref": {"type": "string"},
                "expected_revision": {"type": "string"},
                "rounding": {"type": "string", "default": "none"},
                "units": {"type": "string", "default": "seconds"},
                "account": {"type": "string"},
                "target": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["destination", "block_ids"],
        },
    },
    {
        "name": "timelog.summary",
        "fn": summary_handler,
        "description": ("Read-only aggregate of the native record by period: day (blocks "
                        "starting today), session (this session) or project (every canonical "
                        "file). Totals use the union rule and are null while a block is open; "
                        "open_elapsed_seconds is a window, not productive time."),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["day", "session", "project"],
                           "default": "day"},
                "session_ref": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "timelog.review",
        "fn": review_handler,
        "description": ("Authorized correction of one activity block. Writes a revision "
                        "with a reason and the user's authorization reference and marks "
                        "previously projected receipts stale; it never edits a remote copy."),
        "input_schema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string"},
                "changes": {"type": "object", "description": "Fields to change (start/end/state)."},
                "reason": {"type": "string"},
                "authorization_ref": {"type": "string",
                                      "description": "The user's explicit instruction reference."},
                "session_ref": {"type": "string"},
                "expected_revision": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["block_id", "changes", "reason", "authorization_ref"],
        },
    },
    {
        "name": "timelog.purge",
        "fn": purge_handler,
        "description": ("Authorized archive/summarize/delete of an exact selection. "
                        "preview=true (default) mutates nothing. Deleting removes the "
                        "canonical file and its auxiliaries and leaves a content-free "
                        "tombstone; the deleted content is never recreated."),
        "input_schema": {
            "type": "object",
            "properties": {
                "selection": {"type": "array", "items": {"type": "string"},
                              "description": "Exact block ids to affect."},
                "authorization_ref": {"type": "string"},
                "mode": {"type": "string", "enum": ["archive", "summarize", "delete"],
                         "default": "delete"},
                "preview": {"type": "boolean", "default": True},
                "session_ref": {"type": "string"},
                "expected_revision": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["selection", "authorization_ref"],
        },
    },
]

__all__ = ["handler_schemas", "query_handler", "summary_handler", "review_handler",
           "purge_handler", "project_handler"]
