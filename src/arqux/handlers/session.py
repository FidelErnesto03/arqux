"""`session` module — session handoff between agents.

Handlers:
    session.close           — generate a portable SES entry in brain SESSIONS
    session.resume          — read the last SES and restore context
    session.status          — read SES metadata without restoring full context
    session.context.set     — set the session context pointer (project + scope)
    session.context.get     — read the current context pointer

SES entries are stored in the brain's SESSIONS section (title-resolved)
with kind="session". Each SES is self-contained and < 2KB.
"""

from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..constants import ARQUX_DIR, BRAIN_CORTEX, META_BRAIN_CORTEX, is_name_component
from ..cortex_out import CortexOUT
from ..execution import authoritative_execution_key
from ..loops import dispatch_pending_loops
from ..permissions import PermissionContext
from ..pulse import read_pulse_from_brain, record_pulse
from ..session_identity import (
    ReentryAmbiguous,
    SessionOpenExists,
    close_session,
    current_session_ref,
    get_session,
    list_sessions,
    open_session,
    timelog_path,
)
from ..state import (
    find_project_root,
    find_project_root_with_source,
    find_workspace_root,
)


def close(
    summary: str,
    blps: str | None = None,
    tasks: str | None = None,
    decisions: str | None = None,
    gaps: str | None = None,
    session_ref: str | None = None,
    orphan: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Close the session and write its portable summary to brain PULSE.

    The session that gets closed is the one this execution is bound to (or the
    explicit ``session_ref``); the global pointer and the newest event of the
    project are never used to pick someone else's session.

    ``orphan=True`` covers the unbound-execution case (issue
    2026-11-18-session-context-set-resuelven-el-proyecto-equivocado): when
    this execution never bound a session, the summary is recorded as a
    ``session_orphan`` PULSE event instead of being rejected — the work is
    real and deserves a trace even without a session to close. External
    evidence belongs in *summary* (e.g. NEX request_ids).

    Args:
        summary: Short human-readable summary of what was accomplished.
        blps: Comma-separated list of active blueprint IDs (e.g. "BLP-006,BLP-007").
        tasks: Comma-separated list of pending task IDs (e.g. "T-002,T-003").
        decisions: Comma-separated list of key decisions made.
        gaps: Comma-separated list of detected gaps or pending items.
        session_ref: Explicit ``SESxxx`` to close. Defaults to this execution's.
        orphan: Record the summary as evidence without closing a session
            (requires SESSION_BINDING_REQUIRED, i.e. no session bound).
        path: Path to project root. Defaults to cwd.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    agent = (ctx or PermissionContext.from_env()).agent_id
    execution = _authoritative_execution(ctx)

    blps_list = _parse_csv(blps)
    tasks_list = _parse_csv(tasks)
    decisions_list = _parse_csv(decisions)
    gaps_list = _parse_csv(gaps)

    ses_payload = _build_ses(
        summary=summary,
        blps=blps_list,
        tasks=tasks_list,
        decisions=decisions_list,
        gaps=gaps_list,
        agent=agent,
    )

    if len(ses_payload) > 2048:
        return CortexOUT.error(
            f"SES exceeds 2KB ({len(ses_payload)} bytes). Prioritize critical info.",
            code="SES_TOO_LARGE",
        )

    session, error = _read_session(root, session_ref, execution, for_mutation=True)
    if error:
        # Orphan close: the execution never bound a session but the work is
        # real — record the summary as a session_orphan PULSE event so it is
        # not lost (issue 2026-11-18). Only for SESSION_BINDING_REQUIRED —
        # an explicit but missing session_ref keeps its hard error.
        if orphan and error.get("code") == "SESSION_BINDING_REQUIRED":
            event_id = record_pulse(
                root,
                task_id="-",
                kind="session_orphan",
                agent=agent,
                payload=f"[session.close orphan] {ses_payload}",
            )
            return CortexOUT.work(
                f"session.close ok orphan (no bound session — summary recorded "
                f"as {event_id})",
                orphan=True,
                event_id=event_id,
                agent=agent,
            )
        return CortexOUT.error(error["message"], code=error["code"],
                               **{k: v for k, v in error.items() if k not in ("code", "message")})

    ses_ref = session["session_id"] if session else ""
    event_id = record_pulse(
        root,
        task_id="-",
        kind="session",
        agent=agent,
        payload=ses_payload,
        ses_ref=ses_ref or None,
    )

    # CYCLE-14 / BLP-003: the close is a natural boundary of the session block.
    # It must be captured while the session is still OPEN — after close_session
    # the recorder refuses to touch a closed session (and the block would be
    # left open).
    from ..timelog_capture import observe

    lifecycle = observe(root, ctx, event="close",
                        operation_ref=f"session:{ses_ref or 'legacy'}",
                        activity="session", session_ref=ses_ref or None)

    # Gate: a silent lifecycle skip means the session's work was never
    # registered in the native timelog. Surface it loudly — in the result
    # and in the audit trail — instead of degrading quietly.
    warnings: list[str] = []
    if lifecycle.get("status") == "skipped":
        reason = lifecycle.get("reason", "")
        warnings.append(
            "TIMELOG_UNBOUND: session.close wrote no native timelog block "
            f"({reason}). This session's work is NOT registered — bind a "
            "session via session.context_set(project, scope) or session.open "
            "before closing."
        )
        with suppress(Exception):
            record_pulse(
                root,
                task_id="-",
                kind="timelog_unbound",
                agent=agent,
                payload=f"[timelog] close without bound session: {reason}",
                ses_ref=ses_ref or None,
            )

    if session is not None:
        close_session(
            root,
            ses_ref,
            agent=agent,
            summary=summary,
            blps=",".join(blps_list),
            tasks=",".join(tasks_list),
            decisions=",".join(decisions_list),
            gaps=",".join(gaps_list),
            lng_count=len(blps_list) + len(tasks_list) + len(decisions_list) + len(gaps_list),
            event=event_id,
        )

    # CYCLE-12 / BLP-027: closing used to compact this session's pulse trail
    # into a single LNG census, erasing the per-turn record (SES015,
    # 2026-10-28: five checkpoints became "checkpoint:5"). Consolidating
    # evidence is the Architect's decision, so the close only reports what it
    # leaves behind; session.pulse.compact stays as the explicit operation.
    pulse_events = 0
    if ses_ref:
        with suppress(Exception):
            from ..pulse import read_pulse_from_brain

            pulse_events = sum(
                1 for e in read_pulse_from_brain(root, ses_ref=ses_ref, limit=10_000)
                if e.get("id") != event_id
            )

    fields: dict[str, Any] = {
        "event_id": event_id,
        "session_ref": ses_ref,
        "agent": agent,
        "size_bytes": len(ses_payload),
        "summary": summary,
        "pulse_events": pulse_events,
        "lifecycle": lifecycle,
        "warnings": warnings,
    }
    if pulse_events:
        fields["hint"] = (
            f"{pulse_events} pulse event(s) from this session are left "
            f"uncompacted; consolidate them with "
            f"session.pulse.compact(session_id='{event_id}', ses_ref='{ses_ref}') "
            "if you want the census instead of the trail"
        )
    return CortexOUT.work("session.close ok", **fields)


def pulse_compact(
    session_id: str,
    *,
    ses_ref: str | None = None,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Compact pulse entries for a session. BLP-013 handler.

    With ``ses_ref`` the selection is by membership, never by position.
    """
    from ..pulse import compact_session_pulse
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    agent = (ctx or PermissionContext.from_env()).agent_id
    result = compact_session_pulse(root, session_id=session_id, agent_id=agent,
                                   dry_run=dry_run, ses_ref=ses_ref)
    if result.get("error"):
        return CortexOUT.error(result["error"], code="COMPACT_ERROR")
    if result.get("skip"):
        return CortexOUT.work(f"pulse.compact skip {result.get('reason','')}", entry_count=result.get("entry_count", 0), dry_run=dry_run)
    if result.get("dry_run"):
        return CortexOUT.work("pulse.compact dry_run ok", entry_count=result.get("entry_count", 0), entries_to_prune=result.get("entries_to_prune", []), dry_run=True)
    return CortexOUT.work("pulse.compact ok", pruned=result.get("pruned", 0), entry_count=result.get("entry_count", 0), lng_name=result.get("lng_name", ""), meta_event=result.get("meta_event", ""), dry_run=False)


def pulse_gc(
    *,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Explicit sweep of legacy brain-PULSE entries (compatibility path).

    Canonical pulse events live in the session timelog ``$5 EVENTS`` and are
    append-only — this handler only ever touches residual AUD entries still
    held in a legacy brain PULSE section, pruning those outside the window
    (rank > PULSE_KEEP_COUNT or age > PULSE_KEEP_DAYS) into the rolling
    ``LNG:pulse_sweep`` archive. The write path never sweeps.
    """
    from ..pulse import sweep_pulse_window
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    result = sweep_pulse_window(root, dry_run=dry_run)
    if result.get("error"):
        return CortexOUT.error(result["error"], code="SWEEP_ERROR")
    if result.get("dry_run"):
        return CortexOUT.work(
            "session.pulse.gc dry_run ok",
            aud_total=result.get("aud_total", 0),
            would_prune=result.get("would_prune", 0),
            keep_count=result.get("keep_count", 0),
            keep_days=result.get("keep_days", 0),
            dry_run=True,
        )
    if result.get("skip"):
        return CortexOUT.work(
            f"session.pulse.gc skip {result.get('reason', '')}",
            aud_total=result.get("aud_total", 0),
            dry_run=False,
        )
    return CortexOUT.work(
        "session.pulse.gc ok",
        pruned=result.get("pruned", 0),
        aud_total_before=result.get("aud_total_before", 0),
        batch=result.get("batch", ""),
        total_pruned=result.get("total_pruned", 0),
        dry_run=False,
    )


def checkpoint_context(
    content: str = "",
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Session-level wrapper for cortex.checkpoint."""
    from ..handlers.cortex.checkpoint import checkpoint_handler
    return checkpoint_handler(content=content, path=path, ctx=ctx)


def compact_context(
    content: str = "",
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Serialize current state and return WRK:full."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    brain_path = root / "brain.cortex"
    if not brain_path.exists():
        return CortexOUT.error("brain.cortex not found", code="NOT_FOUND")
    return CortexOUT.work("cortex.compact ok", wrk_full=content[:200])


def _read_session(
    root: Path,
    session_ref: str | None,
    execution: str | None,
    *,
    for_mutation: bool = False,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Select the session a call must act on. Never mutates.

    Resolution order:

    1. an explicit ``session_ref`` (a real ``SESxxx`` entry);
    2. the session bound to this execution;
    3. ``None`` — the brain has no real session identity at all, so the legacy
       PULSE ``SES:`` payload selection applies unchanged.

    A read may fall back to the project's only real session and says so in
    ``selected_by``. A mutation may not: adopting "the one open session" is how
    one execution ends up closing another one's work.
    """
    from ..session_identity import find_session_for_execution

    if session_ref:
        session = get_session(root, session_ref)
        if session is None:
            return None, {"code": "SESSION_NOT_FOUND",
                          "message": f"session {session_ref!r} not found in this project"}
        return session, None

    if execution:
        session = find_session_for_execution(root, execution, state=None)
        if session is not None:
            return session, None

    sessions = list_sessions(root)
    if not sessions:
        return None, None

    if not for_mutation and len(sessions) == 1:
        return sessions[0], None

    code = "SESSION_BINDING_REQUIRED" if for_mutation else "SESSION_AMBIGUOUS"
    message = (
        "this execution has no session of its own in this project — a mutation "
        "never adopts another execution's session; pass session_ref explicitly"
        if for_mutation else
        "several sessions exist in this project and none is bound to this "
        "execution — pass session_ref explicitly; the latest session is "
        "never selected implicitly"
    )
    return None, {"code": code, "message": message, "alternatives": _alternatives(sessions)}


def _alternatives(sessions: list[dict[str, Any]]) -> list[str]:
    return [
        f'{s["session_id"]} ({s.get("state", "?")}, {s.get("agent", "?")}, '
        f'opened {s.get("date", "?")})'
        for s in sessions[-10:]
    ]


def _selected_by(session_ref: str | None, execution: str | None,
                 session: dict[str, Any]) -> str:
    """How the session was picked — never silently implied."""
    if session_ref:
        return "explicit"
    if execution and session.get("execution") == execution:
        return "execution"
    return "single_session_project"


def _authoritative_execution(ctx: PermissionContext | None) -> str | None:
    """The execution key of *ctx*, but only when the transport supplied one.

    ``PermissionContext.execution_key`` already carries only authoritative keys
    (an implicit process key never populates it), so this is a straight read; it
    stays a function so the rule has one place to live.
    """
    if ctx is not None and ctx.execution_key:
        return ctx.execution_key
    return authoritative_execution_key()


def resume(
    session_ref: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read the session identified by ``session_ref`` (or this execution's) and
    return its context. Read-only: never writes and never reopens."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    execution = (ctx.execution_key if ctx else None) or authoritative_execution_key()
    session, error = _read_session(root, session_ref, execution)
    if error:
        return CortexOUT.error(error["message"], code=error["code"],
                               **{k: v for k, v in error.items() if k not in ("code", "message")})

    if session is not None:
        return CortexOUT.work(
            "session.resume ok",
            selected_by=_selected_by(session_ref, execution, session),
            session_ref=session["session_id"],
            state=session.get("state", ""),
            opened_at=session.get("date", ""),
            closed_at=session.get("closed", ""),
            timelog=session.get("timelog", ""),
            agent=session.get("agent", ""),
            project=session.get("project", ""),
            scope=session.get("scope", ""),
            blp=session.get("blp", ""),
            execution=session.get("execution", ""),
            summary=session.get("summary", ""),
            blps=_parse_csv(session.get("blps", "")),
            tasks=_parse_csv(session.get("tasks", "")),
            decisions=_parse_csv(session.get("decisions", "")),
            gaps=_parse_csv(session.get("gaps", "")),
            lng_count=int(session.get("lng_count", "0") or 0),
            source="session_identity",
        )

    events = read_pulse_from_brain(root, limit=10_000)
    ses_entries = [e for e in events if e.get("kind") == "session"]

    if not ses_entries:
        return CortexOUT.error("no previous session found", code="NOT_FOUND")

    last_ses = ses_entries[-1]
    payload = last_ses.get("payload", "")

    parsed = _parse_ses(payload)

    return CortexOUT.work(
        "session.resume ok",
        event_id=last_ses.get("id", "?"),
        ts=last_ses.get("ts", ""),
        agent=last_ses.get("agent", ""),
        summary=parsed.get("summary", ""),
        blps=parsed.get("blps", []),
        tasks=parsed.get("tasks", []),
        decisions=parsed.get("decisions", []),
        gaps=parsed.get("gaps", []),
        lng_count=parsed.get("lng_count", 0),
        source="pulse_legacy",
    )


def status(
    session_ref: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read session metadata without restoring full context. Read-only."""
    root, resolution = find_project_root_with_source(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Issue 2026-11-18 (session resuelta contra el proyecto equivocado): a
    # project resolved through the SHARED workspace pointer may belong to a
    # different execution entirely — surface it instead of answering as if
    # the binding were certain.
    shared_pointer_warning = (
        "project resolved from the shared workspace pointer (WRK:current), "
        "not from this execution — the answer may describe another execution's "
        "project; bind your own via session.context_set(project, scope)"
    )

    execution = (ctx.execution_key if ctx else None) or authoritative_execution_key()
    session, error = _read_session(root, session_ref, execution)
    if error:
        return CortexOUT.error(error["message"], code=error["code"],
                               project_resolution=resolution,
                               **{k: v for k, v in error.items() if k not in ("code", "message")})

    if session is not None:
        return CortexOUT.work(
            "session.status ok",
            project_resolution=resolution,
            warnings=[shared_pointer_warning] if resolution == "shared_pointer" else [],
            selected_by=_selected_by(session_ref, execution, session),
            session_ref=session["session_id"],
            state=session.get("state", ""),
            opened_at=session.get("date", ""),
            closed_at=session.get("closed", ""),
            timelog=session.get("timelog", ""),
            agent=session.get("agent", ""),
            project=session.get("project", ""),
            scope=session.get("scope", ""),
            execution=session.get("execution", ""),
            summary=session.get("summary", ""),
            blp_count=len(_parse_csv(session.get("blps", ""))),
            task_count=len(_parse_csv(session.get("tasks", ""))),
            decision_count=len(_parse_csv(session.get("decisions", ""))),
            gap_count=len(_parse_csv(session.get("gaps", ""))),
            lng_count=int(session.get("lng_count", "0") or 0),
            source="session_identity",
        )

    events = read_pulse_from_brain(root, limit=10_000)
    ses_entries = [e for e in events if e.get("kind") == "session"]

    if not ses_entries:
        return CortexOUT.error("no previous session found", code="NOT_FOUND")

    last_ses = ses_entries[-1]
    payload = last_ses.get("payload", "")
    parsed = _parse_ses(payload)

    return CortexOUT.work(
        "session.status ok",
        project_resolution=resolution,
        warnings=[shared_pointer_warning] if resolution == "shared_pointer" else [],
        event_id=last_ses.get("id", "?"),
        ts=last_ses.get("ts", ""),
        agent=last_ses.get("agent", ""),
        summary=parsed.get("summary", ""),
        blp_count=len(parsed.get("blps", [])),
        task_count=len(parsed.get("tasks", [])),
        decision_count=len(parsed.get("decisions", [])),
        gap_count=len(parsed.get("gaps", [])),
        lng_count=parsed.get("lng_count", 0),
        source="pulse_legacy",
    )


def _is_project_root(path: Path) -> bool:
    return (path / ARQUX_DIR / BRAIN_CORTEX).is_file()


def _resolve_project_from_meta_brain(ws_root: Path, project_name: str) -> Path | None:
    """Resolve a project root from workspace meta-brain or filesystem.

    Distinguishes workspace container (``ws_root``) from project roots
    (subdirs with ``.arqux/brain.cortex``). Never returns the workspace root
    as a project.
    """
    meta_brain_path = ws_root / "meta-brain.cortex"
    workspace_base = ws_root.parent
    wanted = project_name.casefold()

    # 1) Meta-brain DOM entries (authoritative registry), but only if they
    # point to an actual project root.
    if meta_brain_path.exists():
        try:
            raw = meta_brain_path.read_text(encoding="utf-8")
            dom_re = re.compile(r'DOM:\w+\s*\{([^}]*)\}', re.IGNORECASE)
            for dm in dom_re.finditer(raw):
                body = dm.group(1)
                name_m = re.search(r'name:"([^"]*)"', body)
                path_m = re.search(r'path:"([^"]*)"', body)
                if not name_m or not path_m:
                    continue
                if name_m.group(1).casefold() != wanted:
                    continue
                rel_path = path_m.group(1).strip()
                if not rel_path:
                    continue
                resolved = (workspace_base / rel_path).resolve()
                # Common misconfiguration: path "." points at workspace base.
                if resolved == workspace_base and _is_project_root(workspace_base / project_name):
                    return (workspace_base / project_name).resolve()
                if _is_project_root(resolved):
                    return resolved
        except Exception:
            pass

    # 2) Direct subdirectory by exact/common names.
    for candidate_name in (project_name, project_name.upper(), project_name.lower()):
        candidate = (workspace_base / candidate_name).resolve()
        if _is_project_root(candidate):
            return candidate

    # 3) Case-insensitive directory scan (ergonomic fallback).
    try:
        for child in workspace_base.iterdir():
            if not child.is_dir():
                continue
            if child.name.casefold() == wanted and _is_project_root(child):
                return child.resolve()
    except OSError:
        pass
    return None

CONTEXT_CORTEX = "context.cortex"
CONTEXTS_DIR = "contexts"

#: $0 glossary declaring the CTX sigil so context.cortex is machine-readable
#: for CODEC-CORTEX (verify, gc, render). Previously written with an empty
#: glossary and a non-canonical ``CTX:agent key="val"`` line that the codec
#: could not parse (issue 2026-10-18-higiene-workspace-t-032-arqux-context-cortex-pun).
_CONTEXT_GLOSSARY = (
    "$0\n"
    "$0:format{cortex:1.0, encoding:UTF-8}\n\n"
    "# -- $0: SESSION CONTEXT GLOSSARY --\n"
    "# Sigil | Name    | Type  | Risk | Cognitive Layer | Description\n"
    "# CTX   | context | attrs | B    | Working         | "
    "Session context pointer (execution->project/scope/session binding)\n"
    "# ARQX  | artifact | attrs | B   | Semantic        | "
    "ArqUX artifact metadata\n"
    "CTX:ctx_contract{type:\"attrs\", weight:\"M\", focus:\"value\", "
    "fields:\"value:any?\", desc:\"ArqUX CTX entry\", open:true}\n"
    "ARQX:arqx_contract{type:\"attrs\", weight:\"M\", focus:\"value\", "
    "fields:\"value:any?\", desc:\"ArqUX ARQX entry\", open:true}\n"
)


def _context_document(
    *,
    agent: str,
    project: str,
    scope: str,
    blp: str = "",
    ses: str = "",
    project_root: str = "",
) -> str:
    """Build a canonical context.cortex document: declared CTX sigil + attrs entry."""
    fields = [
        ("name", "context"),
        ("project", project),
        ("scope", scope),
    ]
    if blp:
        fields.append(("blp", blp))
    fields.append(("agent", agent))
    if ses:
        fields.append(("ses", ses))
    fields.append(("project_root", project_root))
    attrs = ",".join(f'{k}:"{_escape_ses_value(v)}"' for k, v in fields)
    return (
        f"{_CONTEXT_GLOSSARY}\n$1: CURRENT\nCTX:{agent}{{{attrs}}}\n\n"
        "$19: ARQUX METADATA\n\n"
        'ARQX:artifact{level:0, name:"context", usage:"state", kind:"native"}\n'
    )


def context_set(
    project: str,
    scope: str,
    blp: str | None = None,
    intent: str = "new",
    session_ref: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Set the current session context pointer and open/attach the real session.

    This is the natural mutating binding action, so it is where a session
    becomes real (CYCLE-14 / BLP-001). It locates the workspace from *path*
    (or CWD), resolves the target project from meta-brain.cortex, validates it
    has a brain.cortex, opens or re-attaches the session identity bound to this
    execution, and stores a lightweight context entry in the workspace's
    ``.arqux/context.cortex``.

    Args:
        intent: ``new`` (default) opens or recovers this execution's session;
            ``resumed`` re-attaches ``session_ref`` without changing its id or
            its original start.
        session_ref: explicit ``SESxxx`` reference, required by ``resumed``.
    """
    # Phase 1: locate workspace (from path or CWD)
    ws_root = find_workspace_root(start=path)
    if ws_root is None:
        return CortexOUT.error("no workspace root found", code="NOT_FOUND")

    # BLP-fix (T-004 / Heimdall audit): never silently fall back to the
    # default governor identity (alfred) when an explicit context agent is
    # available. Respect ctx.agent_id; only fall back to from_env when
    # no context is supplied, and surface the chosen identity instead of
    # masking it.
    if ctx is not None:
        agent = ctx.agent_id
        execution = _authoritative_execution(ctx)
    else:
        ctx_env = PermissionContext.from_env(project_root=ws_root)
        agent = ctx_env.agent_id
        execution = authoritative_execution_key()

    # Phase 2: resolve target project (workspace container != project root).
    project_root = _resolve_project_from_meta_brain(ws_root, project)
    if project_root is None:
        project_root_hint = (ws_root.parent / project).resolve()
        return CortexOUT.error(
            f"project {project!r} not found from workspace {ws_root.parent} "
            f"(expected a project root with {ARQUX_DIR}/{BRAIN_CORTEX}, e.g. {project_root_hint}; "
            "workspace root is a container, not a governed project). "
            "Register the project in meta-brain/projects registry or pass the workspace root as path.",
            code="NOT_FOUND",
        )

    # Phase 3: validate target project has a brain.cortex
    project_brain = project_root / ARQUX_DIR / BRAIN_CORTEX
    if not project_brain.exists():
        return CortexOUT.error(
            f"project {project!r} resolved to {project_root} but has no {ARQUX_DIR}/{BRAIN_CORTEX} "
            "(governed project root required; workspace container is not valid here)",
            code="NOT_FOUND",
        )

    # Phase 4: open or re-attach the real session for this execution.
    # Without an unambiguous execution binding the newest global session is
    # never borrowed: the call is rejected instead (AC-03).
    if not execution:
        return CortexOUT.error(
            "no execution binding available for session identity — start the MCP "
            "transport (or set ARQUX_EXECUTION_KEY) so the session can be tied to "
            "this execution instead of the workspace's latest session",
            code="SESSION_BINDING_REQUIRED",
        )
    try:
        session = open_session(
            project_root,
            agent=agent,
            project=project,
            execution=execution,
            scope=scope,
            blp=blp or "",
            intent=intent,
            session_ref=session_ref,
        )
    except PermissionError as exc:
        return CortexOUT.error(str(exc), code="SESSION_IN_USE")
    except SessionOpenExists as exc:
        # Policy (Architect, 2026-10-28): an open session means the work is not
        # finished. A new session on the same project requires closing that one
        # or resuming it — present both commands, never decide for the user.
        alternatives = [
            (
                f'{s["session_id"]} ({s.get("state", "?")}, {s.get("agent", "?")}, '
                f'scope {s.get("scope", "") or "-"}, opened {s.get("date", "?")}) — '
                f"resume: session.context_set(project, scope, intent='resumed', "
                f"session_ref='{s['session_id']}') | "
                f"close: session.close(session_ref='{s['session_id']}', summary='...')"
            )
            for s in exc.alternatives
        ]
        return CortexOUT.error(
            "SESSION_OPEN_EXISTS: this project already has an open session. An "
            "open session means the work is not finished: resume it, or close it "
            "before opening a new one.",
            code="SESSION_OPEN_EXISTS",
            alternatives=alternatives,
        )
    except ReentryAmbiguous as exc:
        alternatives = [
            f'{s["session_id"]} ({s.get("state", "?")}, {s.get("agent", "?")}, '
            f'scope {s.get("scope", "") or "-"}, opened {s.get("date", "?")})'
            for s in exc.alternatives
        ]
        return CortexOUT.error(
            "SESSION_REENTRY_AMBIGUOUS: more than one open session matches this "
            "context (agent/project/scope). Decide explicitly — resume one, open "
            "a new one, or close the previous one; no third session is stacked.",
            code="SESSION_REENTRY_AMBIGUOUS",
            alternatives=alternatives,
        )
    except ValueError as exc:
        code = str(exc)
        message = {
            "SESSION_SELECTION_REQUIRED": (
                "intent='resumed' requires an explicit session_ref (SESxxx); the "
                "latest session of the project is never selected implicitly"
            ),
            "SESSION_NOT_FOUND": f"session {session_ref!r} not found in this project",
        }.get(code, code)
        return CortexOUT.error(message, code=code)

    session_id = session["session_id"]

    # Phase 5: write the context. The per-execution file is the real record —
    # two executions of the same agent in one workspace must not overwrite each
    # other. The single workspace slot is kept for callers that predate it.
    document = _context_document(
        agent=agent,
        project=project,
        scope=scope,
        blp=blp or "",
        ses=session_id,
        project_root=str(project_root),
    )
    _write_context(ws_root, execution, document)
    # Canon (GRADIENT-12): the workspace context pointer lives in meta-brain
    # ACTIVE_CONTEXT as WRK:current — context.cortex is retired. The
    # per-execution file above remains the multi-execution record.
    try:
        from ..core.state._crud import crud_section_id_for_title
        from ..state import _now_iso, crud_add, crud_read, crud_update
        meta_brain = ws_root / META_BRAIN_CORTEX
        if meta_brain.exists():
            ac = crud_section_id_for_title(meta_brain, "ACTIVE_CONTEXT", fallback="$7")
            wrk_attrs = {
                "name": "workspace", "agent": agent, "project": project,
                "scope": scope, "blp": blp or "", "ses": session_id,
                "project_root": str(project_root), "updated": _now_iso(),
            }
            if crud_read(str(meta_brain), f"{ac}/WRK:current").get("entries"):
                crud_update(str(meta_brain), f"{ac}/WRK:current", set_=wrk_attrs, force=True)
            else:
                crud_add(str(meta_brain), ac, "WRK", "current", wrk_attrs,
                         create_section=True, force=True)
    except Exception:
        pass

    header = f"⬡ {agent} | {project} | {scope}"
    if blp:
        header += f" | {blp}"

    # CYCLE-14 / BLP-003: binding to a project opens the session block.
    from ..timelog_capture import observe, unbound_warning

    lifecycle = observe(project_root, ctx, event="open",
                        operation_ref=f"session:{session_id}", activity="session")

    return CortexOUT.work(
        "session.context.set ok",
        header=header,
        project=project,
        scope=scope,
        blp=blp or "",
        agent=agent,
        session_ref=session_id,
        opened_at=session.get("date", ""),
        timelog=session.get("timelog", ""),
        timelog_path=str(timelog_path(project_root, session_id, session.get("date", ""))),
        execution=execution,
        lifecycle=lifecycle,
        pending_loop=dispatch_pending_loops(project_brain, claimant=execution),
        warnings=[w for w in (unbound_warning(lifecycle, action="session.context_set"),) if w],
    )


def _pending_autonomous_loop(brain_path: Path) -> dict[str, str] | None:
    """Surface an unfinished autonomous loop declared in ``WRK:current``.

    Kept for backward compatibility (BLP-020 tests); the live dispatcher is
    :func:`arqux.loops.dispatch_pending_loops` (BLP-023).
    """
    from ..loops import _legacy_pending_loop

    found = _legacy_pending_loop(Path(brain_path))
    if not found:
        return None
    return {"loop": found["loop"], "phase": found["phase"],
            "next": found.get("next", "")}


def _execution_slug(execution: str | None) -> str:
    """Filesystem-safe, collision-free name for an execution key.

    The key comes from the environment or the transport. Sanitising alone is not
    enough: ``a/b`` and ``a_b`` would both become ``a_b`` and two different
    executions would share one context file. A short digest of the *full* key
    disambiguates them, and truncation can no longer merge two long keys.
    """
    if not execution:
        return ""
    import hashlib

    readable = re.sub(r"[^A-Za-z0-9._-]", "_", execution).strip("._")[:64] or "exec"
    digest = hashlib.sha256(execution.encode("utf-8")).hexdigest()[:12]
    return f"{readable}-{digest}"


def _context_file(ws_root: Path, execution: str | None) -> Path:
    """This execution's context file.

    The workspace slot is a fallback only for workspaces that predate
    per-execution contexts. Once any execution has its own file, reading
    another execution's slot would hand it that execution's scope and session.
    """
    slug = _execution_slug(execution)
    if slug:
        scoped = ws_root / CONTEXTS_DIR / f"{slug}.cortex"
        if scoped.exists():
            return scoped
    contexts = ws_root / CONTEXTS_DIR
    if slug and contexts.exists() and any(contexts.glob("*.cortex")):
        return ws_root / CONTEXTS_DIR / f"{slug}.cortex"  # absent: no context yet
    return ws_root / CONTEXT_CORTEX


def _write_context(ws_root: Path, execution: str | None, document: str) -> Path | None:
    """Persist *document* under this execution's own context file.

    GRADIENT-12: without an execution slug there is no file to write — the
    retired shared ``context.cortex`` slot is no longer recreated; the
    meta-brain ``WRK:current`` update the caller performs right after is
    the canonical shared pointer. Returns the written path or ``None``.
    """
    slug = _execution_slug(execution)
    if not slug:
        return None
    target = ws_root / CONTEXTS_DIR / f"{slug}.cortex"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    return target


def context_get(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read the current context pointer.

    Prefers this execution's own context file and falls back to the workspace
    slot written by callers that predate it. Read-only.
    """
    ws_root = find_workspace_root(start=path)
    if ws_root is None:
        return CortexOUT.error("no workspace root found", code="NOT_FOUND")

    execution = (ctx.execution_key if ctx else None) or authoritative_execution_key()
    context_path = _context_file(ws_root, execution)

    raw = ""
    result: dict[str, str] = {}
    if context_path.exists():
        raw = context_path.read_text(encoding="utf-8")
    elif context_path == ws_root / CONTEXT_CORTEX:
        # Canon (GRADIENT-12): the retired global slot's replacement is
        # meta-brain ACTIVE_CONTEXT (WRK:current). It applies ONLY when the
        # resolution actually chose the global slot — when per-execution
        # contexts exist, a missing scoped file must NOT leak another
        # execution's pointer (N-06).
        meta_brain = ws_root / META_BRAIN_CORTEX
        if meta_brain.exists():
            try:
                from ..core.state._crud import crud_section_id_for_title
                from ..state import crud_read
                ac = crud_section_id_for_title(meta_brain, "ACTIVE_CONTEXT", fallback="$7")
                ents = crud_read(str(meta_brain), f"{ac}/WRK:current").get("entries", [])
                if ents:
                    val = ents[0].get("value") or {}
                    if isinstance(val, dict):
                        result = {k: str(v) for k, v in val.items() if v is not None}
            except Exception:
                result = {}
        if not result:
            return CortexOUT.error("no context set", code="NOT_FOUND")
    else:
        return CortexOUT.error("no context set", code="NOT_FOUND")

    # Canonical CTX:{agent_id}{k:"v"} entry; fall back to the pre-canonical
    # CTX:{agent_id} k="v" line still found in older context files.
    # The $0 glossary declares ``CTX:ctx_contract{...}`` — a *_contract
    # sigil is a declaration, never the live entry, so it is skipped.
    entry_match = None
    for m in re.finditer(r"CTX:([^\s{]+)\{([^}]*)\}", raw):
        if m.group(1).endswith("_contract"):
            continue
        entry_match = m
        break
    if entry_match is not None:
        m = entry_match
        result["agent"] = m.group(1)
        for key, val in re.findall(r'(\w+):"([^"]*)"', m.group(2)):
            result[key] = val
    else:
        for m in re.finditer(r"CTX:(\S+)\s+(.+)", raw):
            agent_name = m.group(1)
            if "{" in agent_name or agent_name.endswith("_contract"):
                continue
            result["agent"] = agent_name
            pairs = m.group(2)
            for pair in re.findall(r'(\w+)="([^"]*)"', pairs):
                result[pair[0]] = pair[1]
            break

    if not result:
        return CortexOUT.error("invalid context format", code="PARSE_ERROR")

    header = (
        f"⬡ {result.get('agent', '?')}"
        f" | {result.get('project', '?')}"
        f" | {result.get('scope', '?')}"
    )
    if result.get("blp"):
        header += f" | {result['blp']}"

    return CortexOUT.work(
        "session.context.get ok",
        header=header,
        **result,
    )


# --- SES format helpers -----------------------------------------------------

SES_TEMPLATE = (
    "SES:{ts} agent={agent} "
    'summary="{summary}" '
    "blps=[{blps}] "
    "tasks=[{tasks}] "
    "decisions=[{decisions}] "
    "gaps=[{gaps}] "
    "lng_count={lng_count}"
)


def _build_ses(
    summary: str,
    blps: list[str],
    tasks: list[str],
    decisions: list[str],
    gaps: list[str],
    agent: str = "",
) -> str:
    """Build a compact SES string (< 2KB)."""
    import time

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return SES_TEMPLATE.format(
        ts=ts,
        agent=agent,
        summary=_escape_ses_value(summary),
        blps=",".join(blps) if blps else "-",
        tasks=",".join(tasks) if tasks else "-",
        decisions=",".join(decisions) if decisions else "-",
        gaps=",".join(gaps) if gaps else "-",
        lng_count=len(blps) + len(tasks) + len(decisions) + len(gaps),
    )


def _parse_ses(payload: str) -> dict[str, Any]:
    """Parse a SES string back into structured data."""
    result: dict[str, Any] = {
        "summary": "",
        "blps": [],
        "tasks": [],
        "decisions": [],
        "gaps": [],
        "lng_count": 0,
    }

    m = re.search(r'summary="([^"]*)"', payload)
    if m:
        result["summary"] = m.group(1)

    for field in ("blps", "tasks", "decisions", "gaps"):
        m = re.search(rf"{field}=\[([^\]]*)\]", payload)
        if m:
            raw = m.group(1)
            result[field] = [x.strip() for x in raw.split(",") if x.strip() and x.strip() != "-"]

    m = re.search(r"lng_count=(\d+)", payload)
    if m:
        result["lng_count"] = int(m.group(1))

    return result


def _parse_csv(value: str | None) -> list[str]:
    """Parse a comma-separated string into a list."""
    if not value or not value.strip():
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def _escape_ses_value(value: str) -> str:
    """Escape a value for safe embedding in a SES string."""
    return value.replace('"', "'").replace("\n", " ")


# ---------------------------------------------------------------------------
# session.bootstrap (BLP-008)
# ---------------------------------------------------------------------------


def _resolve_bootstrap_scope(start: Path) -> tuple[str, Path] | None:
    """Nearest ``.arqux/`` at or above *start*, classified project vs workspace.

    A ``.arqux/`` holding ``brain.cortex`` is a governed project; one holding
    only ``meta-brain.cortex`` is a workspace. The CLOSEST ancestor wins, so
    an explicit path inside a project binds that project even when a
    workspace encloses it — the workspace level is reached only from
    genuinely workspace-level paths (issue: session-bootstrap-resolves-upward;
    previously find_workspace_root ran first and every project path inside a
    workspace resolved to the workspace).
    """
    cursor = start
    # Path already inside a .arqux/ directory (BC-6 parity with
    # find_project_root: never double-nest).
    if cursor.name == ARQUX_DIR:
        if (cursor / BRAIN_CORTEX).exists():
            return ("project", cursor)
        if (cursor / META_BRAIN_CORTEX).exists():
            return ("workspace", cursor)
        return None
    while True:
        candidate = cursor / ARQUX_DIR
        if (candidate / BRAIN_CORTEX).exists():
            return ("project", candidate)
        if (candidate / META_BRAIN_CORTEX).exists():
            return ("workspace", candidate)
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


#: Cap on entry heads included in the bootstrap identity contract summary.
_IDENTITY_SUMMARY_CAP = 100

#: Head of a CORTEX entry — ``SIGIL:name`` at line start.
_IDENTITY_ENTRY_RE = re.compile(r"(?m)^([A-Z][A-Z0-9]{1,11}):([^\s{:]+)")


def _identity_summary(content: str) -> dict[str, list[str]]:
    """sigil → entry names — a bounded contract summary of an identity file.

    GSIG glossary declarations are schema, not contract, and are skipped.
    """
    summary: dict[str, list[str]] = {}
    count = 0
    for m in _IDENTITY_ENTRY_RE.finditer(content):
        sigil, name = m.group(1), m.group(2)
        if sigil == "GSIG":
            continue
        names = summary.setdefault(sigil, [])
        if name not in names:
            names.append(name)
            count += 1
            if count >= _IDENTITY_SUMMARY_CAP:
                break
    return summary


def _identity_reference(
    agent_id: str,
    bases: list[tuple[Path, str]],
) -> tuple[dict[str, Any], str]:
    """Bounded identity reference for the bootstrap ``cortex_context``.

    The bootstrap payload used to embed the whole ``<agent>.cortex`` file as
    escaped text — several KB per call (issue: session-bootstrap-embeds).
    The reference carries just enough to locate and gauge the contract:
    resolved ``path``, ``source`` and a sigil → entry-names ``contracts``
    summary. Returns ``(reference, source)``; ``source`` is "" when no
    identity file resolved under *bases*.
    """
    for base, source in bases:
        candidate = base / f"{agent_id}.cortex"
        if not candidate.exists():
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        return {
            "agent_id": agent_id,
            "source": source,
            "path": str(candidate),
            "contracts": _identity_summary(content),
        }, source
    return {
        "agent_id": agent_id,
        "source": None,
        "path": None,
        "contracts": {},
    }, ""


def _list_projects_from_meta(ws_root: Path) -> list[dict[str, str]]:
    """Extract project DOM entries from the workspace meta-brain.cortex."""
    meta_path = ws_root / "meta-brain.cortex"
    if not meta_path.exists():
        return []
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return []
    projects: list[dict[str, str]] = []
    for m in re.finditer(
        r'DOM:(\w+)\s*\{[^}]*?(?:name:"([^"]*)"[^}]*?path:"([^"]*)"'
        r'|[^}]*?path:"([^"]*)"[^}]*?name:"([^"]*)")[^}]*?\}',
        text,
    ):
        name = m.group(2) or m.group(5) or m.group(1)
        path_rel = m.group(3) or m.group(4) or ""
        projects.append({"name": name, "path": path_rel})
    # Fallback: scan subdirectories with .arqux/brain.cortex
    if not projects:
        for child in sorted(ws_root.parent.iterdir()):
            if (child / ARQUX_DIR / BRAIN_CORTEX).exists():
                projects.append({"name": child.name, "path": child.name})
    return projects


def _bootstrap_workspace(
    ws_root: Path,
    start: Path,
    agent_id: str,
    ctx: PermissionContext | None,
) -> CortexOUT:
    """Build a workspace-level bootstrap (no project auto-binding)."""
    from ..constants import IDENTITIES_DIR as _IDENTITIES_DIR

    # 1. List projects from meta-brain.
    projects = _list_projects_from_meta(ws_root)
    project_names = [p["name"] for p in projects]

    # 2. List skills.
    skills_dir = ws_root / "skills"
    skills: list[str] = []
    if skills_dir.exists():
        for f in sorted(skills_dir.iterdir()):
            if f.is_file() and f.name.endswith(".skill.md"):
                skills.append(f.stem.removesuffix(".skill"))

    # 3. Resolve the identity contract as a REFERENCE (agent_id + path +
    # contract summary) — embedding the raw file cost several KB per call
    # (issue: session-bootstrap-embeds).
    identity_ref, identity_source = _identity_reference(
        agent_id,
        [
            (ws_root / "identities", "workspace"),
            (_IDENTITIES_DIR, "package"),
        ],
    )

    # 4. Build cortex_context (workspace-level, no project/cycle binding).
    cortex_context: dict[str, Any] = {
        "found": True,
        "kind": "workspace",
        "start": str(start),
        "arqux_path": str(ws_root),
        "project": None,
        "project_path": None,
        "governor": None,
        "cycle": None,
        "cycles": [],
        "projects": project_names,
        "agents": [],
        "skills": skills,
        "brain": {},
        "identity": identity_ref,
        "identity_source": identity_source,
        "agent_id": agent_id,
    }

    # 5. Build workspace dashboard.
    dashboard_parts: list[str] = []
    dashboard_parts.append("# Session Bootstrap — Workspace")
    dashboard_parts.append("")
    dashboard_parts.append("**STANDBY** — no project auto-selected.")
    dashboard_parts.append(f"**Workspace:** `{ws_root.parent}`")
    dashboard_parts.append(f"**Agent:** `{agent_id}`")
    dashboard_parts.append("")
    dashboard_parts.append("## Available Projects")
    if projects:
        for p in projects:
            dashboard_parts.append(f"- `{p['name']}`")
    else:
        dashboard_parts.append("_No projects registered._")
    dashboard_parts.append("")
    dashboard_parts.append("## Skills Available")
    if skills:
        for s in skills:
            dashboard_parts.append(f"- `{s}`")
    else:
        dashboard_parts.append("_No skills installed._")
    dashboard_parts.append("")
    dashboard_parts.append("## Identity")
    dashboard_parts.append(f"Source: `{identity_source or 'none'}`")
    dashboard_parts.append("")
    dashboard_parts.append(
        "**Choose a project** with `session.context.set` "
        "or `project.status` to begin working."
    )

    hcortex_dashboard = "\n".join(dashboard_parts)

    # PULSE.
    _record_bootstrap_pulse(ws_root, ctx, agent_id=agent_id, project="")

    return CortexOUT.work(
        f"session.bootstrap ok kind=workspace projects={len(projects)} "
        f"skills={len(skills)}",
        found=True,
        kind="workspace",
        start=str(start),
        agent_id=agent_id,
        cortex_context=cortex_context,
        hcortex_dashboard=hcortex_dashboard,
        warnings=[
            "TIMELOG_UNBOUND: bootstrap at workspace level binds no session — "
            "no timelog is recording. When the Architect names a project, call "
            "session.context_set(project, scope) to open the SES before work starts."
        ],
    )


def _bootstrap_project(
    project_arqux: Path,
    start: Path,
    agent_id: str,
    ctx: PermissionContext | None,
) -> CortexOUT:
    """Build a project-level bootstrap.

    Fires when the start path resolves to a project ``.arqux/`` — either a
    standalone project or one nested inside a workspace (the project wins
    over its enclosing workspace; issue: session-bootstrap-resolves-upward).
    """
    from ..constants import CYCLES_DIR as _CYCLES_DIR
    from ..constants import IDENTITIES_DIR as _IDENTITIES_DIR
    from ..state import read_brain as _read_brain

    project_root_parent = project_arqux.parent

    # 1. Read brain.
    fm, sections, raw = _read_brain(project_root_parent)
    project_name = fm.get("project", "") or project_root_parent.name
    governor = fm.get("governor", "")

    # 2. List cycles (no auto-selection).
    cycles_base = project_arqux / _CYCLES_DIR
    cycles: list[dict[str, Any]] = []
    if cycles_base.exists():
        for cdir in sorted(cycles_base.iterdir()):
            if not cdir.is_dir():
                continue
            manifest = cdir / "MANIFEST.md"
            cycle_status = ""
            if manifest.exists():
                try:
                    mf_text = manifest.read_text(encoding="utf-8")
                    m = re.search(r"status:\s*[\"']?(\w+)", mf_text)
                    if m:
                        cycle_status = m.group(1)
                except OSError:
                    pass
            cycles.append({"id": cdir.name, "status": cycle_status})

    # 3. Parse bound agents from SESSIONS.
    agents: list[dict[str, str]] = []
    sessions_text = sections.get("SESSIONS", "")
    for line in sessions_text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        m = re.search(r"agent=([^\s]+)", line)
        if m:
            agents.append({"agent_id": m.group(1), "raw": line})

    # 4. List skills.
    skills_dir = project_arqux / "skills"
    skills: list[str] = []
    if skills_dir.exists():
        for f in sorted(skills_dir.iterdir()):
            if f.is_file() and f.name.endswith(".skill.md"):
                skills.append(f.stem.removesuffix(".skill"))

    # 5. Resolve the identity contract as a REFERENCE (bounded payload —
    # issue: session-bootstrap-embeds). Identity contracts live at
    # workspace level (AXM:identity_loading), so an enclosing workspace's
    # identities dir is consulted between the project's and the package's.
    identity_bases: list[tuple[Path, str]] = [
        (project_arqux / "identities", "project"),
    ]
    enclosing_ws = find_workspace_root(start=project_root_parent)
    if enclosing_ws is not None:
        identity_bases.append((enclosing_ws / "identities", "workspace"))
    identity_bases.append((_IDENTITIES_DIR, "package"))
    identity_ref, identity_source = _identity_reference(agent_id, identity_bases)

    # Build canal-I cortex_context dict.
    cortex_context: dict[str, Any] = {
        "found": True,
        "kind": "project",
        "start": str(start),
        "arqux_path": str(project_arqux),
        "project": project_name,
        "project_path": str(project_root_parent),
        "governor": governor,
        "cycle": None,
        "cycles": cycles,
        "projects": [project_name],
        "agents": agents,
        "skills": skills,
        "brain": {
            "focus": sections.get("FOCUS", ""),
            "objectives": sections.get("OBJECTIVES", ""),
            "active_context": sections.get("ACTIVE_CONTEXT", ""),
            "lessons": sections.get("LESSONS", ""),
            "risks": sections.get("RISKS", ""),
        },
        "identity": identity_ref,
        "identity_source": identity_source,
        "agent_id": agent_id,
    }

    # Build canal-E hcortex_dashboard markdown.
    dashboard_parts: list[str] = []
    dashboard_parts.append(f"# Session Bootstrap — {project_name}")
    dashboard_parts.append("")
    dashboard_parts.append("**STANDBY** — no cycle auto-selected.")
    dashboard_parts.append(f"**Project:** `{project_name}`")
    dashboard_parts.append(f"**Path:** `{project_root_parent}`")
    dashboard_parts.append(f"**Governor:** `{governor or '(unset)'}`")
    dashboard_parts.append(f"**Agent:** `{agent_id}` (identity: `{identity_source or 'none'}`)")
    dashboard_parts.append("")
    dashboard_parts.append("## Cycles")
    if cycles:
        for c in cycles:
            dashboard_parts.append(
                f"- `{c['id']}` — status: `{c.get('status', '?')}`"
            )
    else:
        dashboard_parts.append("_No cycles yet._")
    dashboard_parts.append("")
    dashboard_parts.append("## Bound Agents")
    if agents:
        for a in agents:
            dashboard_parts.append(f"- `{a['agent_id']}`")
    else:
        dashboard_parts.append("_No agents bound._")
    dashboard_parts.append("")
    dashboard_parts.append("## Skills Available")
    if skills:
        for s in skills:
            dashboard_parts.append(f"- `{s}`")
    else:
        dashboard_parts.append("_No skills installed._")
    dashboard_parts.append("")
    dashboard_parts.append("## Brain Focus")
    focus = sections.get("FOCUS", "").strip()
    dashboard_parts.append(focus if focus else "_(no focus set)_")
    dashboard_parts.append("")

    hcortex_dashboard = "\n".join(dashboard_parts)

    # PULSE.
    _record_bootstrap_pulse(project_arqux, ctx, agent_id=agent_id, project=project_name)

    return CortexOUT.work(
        f"session.bootstrap ok kind=project project={project_name} "
        f"cycles={len(cycles)} agents={len(agents)} skills={len(skills)}",
        found=True,
        kind="project",
        start=str(start),
        agent_id=agent_id,
        cortex_context=cortex_context,
        hcortex_dashboard=hcortex_dashboard,
    )


def bootstrap(
    path: str | None = None,
    *,
    agent_id: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Bootstrap a session — workspace-first, no project/cycle auto-binding.

    AXM:standby_first — the session begins in STANDBY. The bootstrap
    presents the workspace dashboard and available projects without
    auto-selecting any.

    Returns TWO outputs:
    - ``cortex_context`` (dict, canal I): machine-readable context.
    - ``hcortex_dashboard`` (str, canal E): markdown dashboard.

    If no ``.arqux/`` is found, returns an informative message.
    """
    import os as _os
    from pathlib import Path as _Path

    start = _Path(path or _os.getcwd()).resolve()

    # The authenticated context is authoritative.  An explicit agent_id is
    # presentation-only input and must not be allowed to impersonate another
    # identity (BLP-002).
    authenticated_agent = (ctx or PermissionContext.from_env()).agent_id or "alfred"
    if agent_id and agent_id.casefold() != authenticated_agent.casefold():
        return CortexOUT.error(
            f"requested agent_id={agent_id!r} does not match authenticated agent={authenticated_agent!r}",
            code="IDENTITY_MISMATCH",
        )
    agent_id = authenticated_agent.casefold()

    # Nearest .arqux wins: a path inside a governed project bootstraps THAT
    # project context; only a genuinely workspace-level path (or one inside
    # the workspace but outside every project) binds the workspace level.
    resolved = _resolve_bootstrap_scope(start)
    if resolved is not None:
        kind, arqux_root = resolved
        if kind == "project":
            return _bootstrap_project(arqux_root, start, agent_id, ctx)
        return _bootstrap_workspace(arqux_root, start, agent_id, ctx)

    # No .arqux/ found — informative message, NOT an error.
    return CortexOUT.work(
        f"session.bootstrap ok found=false start={start}",
        found=False,
        kind=None,
        start=str(start),
        cortex_context={"found": False, "start": str(start)},
        hcortex_dashboard=(
            f"# Session Bootstrap\n\n"
            f"**Status:** No `.arqux/` directory found.\n\n"
            f"**Start path:** `{start}`\n\n"
            f"To bootstrap a session, initialise a workspace first:\n\n"
            f"```\n"
            f"arqux workspace init\n"
            f"arqux project init --name <project-name>\n"
            f"```\n"
        ),
        agent_id=agent_id,
    )


def _record_bootstrap_pulse(
    arqux_root: Path,
    ctx: PermissionContext | None,
    *,
    agent_id: str,
    project: str,
) -> None:
    """Append a PULSE event for the bootstrap call (best-effort)."""
    try:
        agent = (ctx or PermissionContext.from_env()).agent_id
        record_pulse(
            arqux_root,
            task_id="-",
            kind="session_bootstrap",
            agent=agent,
            payload=f"[session.bootstrap] agent={agent_id} project={project}",
            ses_ref=current_session_ref(
                arqux_root, (ctx.execution_key if ctx else None) or authoritative_execution_key()
            ) or None,
        )
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# session.handoff (BLP-010)
# ---------------------------------------------------------------------------


def handoff(
    target_agent: str,
    *,
    content: str | None = None,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Serialize the current session context as CORTEX and write a handoff PULSE.

    BLP-010 meta-handler. Wraps:

    1. Read the current session context (identity, cycle, last pulse).
    2. Serialize it as a CORTEX string.
    3. Write a PULSE event for the outgoing session.
    4. Make the context accessible for the target agent (written to
       ``.arqux/handoffs/<target_agent>.cortex``).

    Args:
        target_agent: ID of the agent receiving the handoff.
        content: Optional CORTEX content with keys:
            ``target_agent, summary, blps, tasks``.
        dry_run: If True, report what would happen without writing.
        path: Path to project root.
        ctx: Permission context.
    """
    from ..cortex.parse_content import parse_content_entry

    # Merge content CORTEX.
    summary: str = ""
    blps: str = ""
    tasks: str = ""
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            target_agent = parsed.get("target_agent", target_agent)
            summary = parsed.get("summary", "")
            blps = parsed.get("blps", "")
            tasks = parsed.get("tasks", "")

    if not target_agent:
        return CortexOUT.error("target_agent is required", code="INVALID_ARGS")
    if not is_name_component(target_agent):
        return CortexOUT.error(
            f"target_agent must be a single agent id (slug), got {target_agent!r} "
            "— it becomes the HND:<to> entry name in brain ACTIVE_CONTEXT",
            code="INVALID_ARGS",
        )

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Read current context.
    from ..state import read_brain
    fm, sections, raw = read_brain(root.parent)
    project_name = fm.get("project", "") or root.parent.name
    # BLP-fix (T-004 / Heimdall audit): respect explicit ctx.agent_id;
    # never silently mask the active identity with the default fallback.
    agent_id = ctx.agent_id if ctx is not None else PermissionContext.from_env().agent_id

    # Build CORTEX handoff payload — the same shape migrated handoffs carry:
    # executable sigil declarations + $0:format (I001/G010) + $19 metadata.
    handoff_lines = [
        "$0",
        "",
        'HOF:hof_contract{type:"attrs", weight:"M", focus:"value", '
        'fields:"value:any?", desc:"ArqUX HOF entry", open:true}',
        'ARQX:arqx_contract{type:"attrs", weight:"M", focus:"value", '
        'fields:"value:any?", desc:"ArqUX ARQX entry", open:true}',
        "$0:format{cortex:1.0, encoding:UTF-8}",
        "",
        "$1: HANDOFF",
        "",
        'HOF:handoff{'
        f'from:"{_escape_ses_value(agent_id)}", '
        f'to:"{_escape_ses_value(target_agent)}", '
        f'project:"{_escape_ses_value(project_name)}", '
        f'summary:"{_escape_ses_value(summary)}", '
        f'blps:"{_escape_ses_value(blps)}", '
        f'tasks:"{_escape_ses_value(tasks)}"'
        '}',
        "",
        "$19: ARQUX METADATA",
        "",
        f'ARQX:artifact{{level:0, name:"handoff-{target_agent}", usage:"state", kind:"native"}}',
        "",
    ]
    handoff_cortex = "\n".join(handoff_lines)

    if dry_run:
        return CortexOUT.work(
            f"session.handoff dry_run from={agent_id} to={target_agent}",
            target_agent=target_agent,
            from_agent=agent_id,
            dry_run=True,
            handoff_cortex=handoff_cortex,
        )

    # Canon (GRADIENT-12): a pending handoff is state, not a file — it lives
    # as HND:<to> in the brain's ACTIVE_CONTEXT. The handoffs/ directory is
    # retired; the receiver finds the entry on bootstrap.
    # I002: HND:<to> is a fixed address. A second handoff to the same agent
    # must UPDATE the pending entry, never add a second one under the same
    # name — a duplicate blocks every later write to the brain with
    # I002_DUPLICATE_IDEA_ADDRESS (AXM:silent_corruption).
    brain_path = root / BRAIN_CORTEX
    handoff_ref = ""
    from ..core.state._crud import (
        cortex_verify,
        crud_read,
        crud_section_id_for_title,
        crud_update,
    )
    from ..state import _now_iso, crud_add
    handoff_attrs = {
        "date": _now_iso(), "from": agent_id, "to": target_agent,
        "project": project_name, "summary": summary, "blps": blps,
        "tasks": tasks,
    }
    try:
        ac = crud_section_id_for_title(brain_path, "ACTIVE_CONTEXT", fallback="$7")
        previous = (
            brain_path.read_text(encoding="utf-8")
            if brain_path.exists() else None
        )
        # AXM:silent_corruption — no ok before validating what was written.
        # Only NEW error diagnostics introduced by this write abort and roll
        # back: a brain that was already malformed before the handoff must
        # not make handoffs impossible (its errors are pre-existing state).
        def _error_codes(diags: list[str]) -> set[str]:
            return {
                d.split("] ", 1)[1].rsplit(" (line", 1)[0]
                for d in diags
                if d.startswith("[") and not d.startswith("[I")
            }

        before = cortex_verify(brain_path) if previous is not None else {"diagnostics": []}
        existing: dict | None = None
        with suppress(Exception):
            existing = crud_read(brain_path, f"{ac}/HND:{target_agent}")
        if existing and existing.get("entries"):
            crud_update(
                brain_path, f"{ac}/HND:{target_agent}",
                set_=handoff_attrs, force=True,
            )
        else:
            crud_add(
                brain_path, ac, "HND", target_agent, handoff_attrs,
                create_section=True, force=True,
            )
        # AXM:silent_corruption — validate after the write; roll back and
        # fail only when this write introduced NEW error diagnostics.
        verdict = cortex_verify(brain_path)
        new_errors = _error_codes(verdict.get("diagnostics", [])) - _error_codes(
            before.get("diagnostics", [])
        )
        if new_errors:
            if previous is not None:
                brain_path.write_text(previous, encoding="utf-8")
            return CortexOUT.error(
                "handoff write produced a malformed brain; reverted",
                code="WRITE_ERROR",
                diagnostics=sorted(new_errors),
            )
        handoff_ref = f"{ac}/HND:{target_agent}"
    except Exception as exc:
        return CortexOUT.error(f"handoff write failed: {exc}", code="WRITE_ERROR")

    # Write PULSE for outgoing session — telemetry never blocks the handoff.
    with suppress(Exception):
        record_pulse(
            root,
            task_id="-",
            kind="session_handoff",
            agent=agent_id,
            payload=f"[session.handoff] from={agent_id} to={target_agent} summary={summary[:60]}",
            ses_ref=current_session_ref(
                root, (ctx.execution_key if ctx else None) or authoritative_execution_key()
            ) or None,
        )

    return CortexOUT.work(
        f"session.handoff ok from={agent_id} to={target_agent}",
        target_agent=target_agent,
        from_agent=agent_id,
        handoff_ref=handoff_ref,
        dry_run=False,
    )


handler_schemas = [
    {"name": "session.close", "fn": close, "description": "Close the session bound to this execution (or the explicit session_ref) and write its portable summary to brain SESSIONS. Never closes the newest session of the project when it belongs to another execution.", "input_schema": {"type": "object", "properties": {"summary": {"type": "string", "description": "Short human-readable summary of what was accomplished."}, "blps": {"type": "string", "description": "Comma-separated active blueprint IDs (e.g. BLP-006,BLP-007)."}, "tasks": {"type": "string", "description": "Comma-separated pending task IDs."}, "decisions": {"type": "string", "description": "Comma-separated key decisions made."}, "gaps": {"type": "string", "description": "Comma-separated detected gaps or pending items."}, "session_ref": {"type": "string", "description": "Explicit SESxxx to close. Defaults to this execution's session."}, "orphan": {"type": "boolean", "default": False, "description": "Record summary as a session_orphan PULSE event when this execution never bound a session (work evidence without a session to close)."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["summary"]}},
    {"name": "session.resume", "fn": resume, "description": "Restore the context of a session. Read-only: selects by explicit session_ref, else the session bound to this execution, else rejects an ambiguous choice instead of taking the newest session. Brains without real session identity keep the legacy PULSE selection.", "input_schema": {"type": "object", "properties": {"session_ref": {"type": "string", "description": "Explicit SESxxx reference."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "session.status", "fn": status, "description": "Read session metadata without restoring full context. Read-only, same selection rules as session.resume.", "input_schema": {"type": "object", "properties": {"session_ref": {"type": "string", "description": "Explicit SESxxx reference."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "session.context.set", "fn": context_set, "description": "Set the current session context pointer (project + scope + optional BLP) and open or re-attach the real session bound to this execution. Validates project exists and returns the formatted header.", "input_schema": {"type": "object", "properties": {"project": {"type": "string", "description": "Project name (e.g. ARQUX)"}, "scope": {"type": "string", "description": "Scope within project (e.g. CYCLE-01)"}, "blp": {"type": "string", "description": "Optional active BLP ID (e.g. BLP-014)"}, "intent": {"type": "string", "enum": ["new", "resumed"], "default": "new", "description": "'new' opens or recovers this execution's session; 'resumed' re-attaches session_ref without changing its id or original start."}, "session_ref": {"type": "string", "description": "Explicit SESxxx reference; required when intent='resumed'."}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["project", "scope"]}},
    {"name": "session.context.get", "fn": context_get, "description": "Read the current context pointer and return the formatted header.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}}},
    {"name": "session.bootstrap", "fn": bootstrap, "description": "Bootstrap a session using the authenticated identity. An explicit agent_id must match the caller (BLP-002). Returns cortex_context (canal I) and hcortex_dashboard (canal E).", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Starting path. Defaults to cwd."}, "agent_id": {"type": "string", "description": "Optional identity selector; must match the authenticated caller."}}}},
    {"name": "session.handoff", "fn": handoff, "description": "Serialize the current session context as CORTEX and write a handoff PULSE for the target agent (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"target_agent": {"type": "string", "description": "ID of the agent receiving the handoff."}, "content": {"type": "string", "description": "CORTEX content with keys target_agent, summary, blps, tasks."}, "dry_run": {"type": "boolean", "default": False}, "path": {"type": "string"}}, "required": ["target_agent"]}},
    {"name": "session.pulse.compact", "fn": pulse_compact, "description": "Compact pulse entries for a session. With ses_ref, selection is by membership: only that session's events are summarized and concurrent or legacy events are never reassigned by position. Writes a consolidated LNG lesson; canonical timelog events are append-only and are never pruned.", "input_schema": {"type": "object", "properties": {"session_id": {"type": "string"}, "ses_ref": {"type": "string", "description": "Select by session membership instead of position."}, "dry_run": {"type": "boolean", "default": False}, "path": {"type": "string"}}, "required": ["session_id"]}},
    {"name": "session.pulse.gc", "fn": pulse_gc, "description": "Explicit sweep of residual brain-PULSE entries (legacy compatibility only): prunes AUD entries outside the window — rank>PULSE_KEEP_COUNT(20) or age>PULSE_KEEP_DAYS(5) — into the rolling LNG:pulse_sweep archive. Canonical session-timelog $5 EVENTS are append-only and are never swept; the write path never sweeps.", "input_schema": {"type": "object", "properties": {"dry_run": {"type": "boolean", "default": False}, "path": {"type": "string"}}}},
]
