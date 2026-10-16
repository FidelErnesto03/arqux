"""`session` module — session handoff between agents.

Handlers:
    session.close           — generate a portable SES entry in brain PULSE
    session.resume          — read the last SES and restore context
    session.status          — read SES metadata without restoring full context
    session.context.set     — set the session context pointer (project + scope)
    session.context.get     — read the current context pointer

SES entries are stored in the brain's PULSE section as evidence-like
entries with kind="session". Each SES is self-contained and < 2KB.
"""

from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..constants import ARQUX_DIR, BRAIN_CORTEX, is_name_component
from ..cortex_out import CortexOUT
from ..execution import authoritative_execution_key
from ..permissions import PermissionContext
from ..pulse import read_pulse_from_brain, record_pulse
from ..session_identity import (
    close_session,
    current_session_ref,
    get_session,
    list_sessions,
    open_session,
    timelog_path,
)
from ..state import find_project_root, find_workspace_root


def close(
    summary: str,
    blps: str | None = None,
    tasks: str | None = None,
    decisions: str | None = None,
    gaps: str | None = None,
    session_ref: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Close the session and write its portable summary to brain PULSE.

    The session that gets closed is the one this execution is bound to (or the
    explicit ``session_ref``); the global pointer and the newest event of the
    project are never used to pick someone else's session.

    Args:
        summary: Short human-readable summary of what was accomplished.
        blps: Comma-separated list of active blueprint IDs (e.g. "BLP-006,BLP-007").
        tasks: Comma-separated list of pending task IDs (e.g. "T-002,T-003").
        decisions: Comma-separated list of key decisions made.
        gaps: Comma-separated list of detected gaps or pending items.
        session_ref: Explicit ``SESxxx`` to close. Defaults to this execution's.
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
                        activity="session")

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

    # Trigger pulse.compact after SES write
    compact_result: dict = {}
    try:
        from ..pulse import compact_session_pulse
        compact_result = compact_session_pulse(
            root,
            session_id=event_id,
            agent_id=agent,
            ses_ref=ses_ref or None,
        )
    except Exception:
        pass

    return CortexOUT.work(
        "session.close ok",
        event_id=event_id,
        session_ref=ses_ref,
        agent=agent,
        size_bytes=len(ses_payload),
        summary=summary,
        compact=compact_result,
        lifecycle=lifecycle,
        warnings=warnings,
    )


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
            "session.status ok",
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


def _resolve_project_from_meta_brain(ws_root: Path, project_name: str) -> Path | None:
    """Look up a project's absolute root path from meta-brain.cortex.

    Reads the workspace meta-brain, finds the DOM entry matching *project_name*,
    and returns the resolved absolute path.
    """
    meta_brain_path = ws_root / "meta-brain.cortex"
    if not meta_brain_path.exists():
        return None

    try:
        raw = meta_brain_path.read_text(encoding="utf-8")
        # Find DOM:<name>{... path="VALUE" ... name="PROJECT_NAME" ...}
        # or DOM:<name>{... name="PROJECT_NAME" ... path="VALUE" ...}
        import re as _re
        # Look for DOM entry where name matches project_name (case-insensitive)
        pattern = (
            rf'DOM:\w+\s*{{\s*'
            rf'(?:[^}}]*?path:"([^"]*)"[^}}]*?name:"{_re.escape(project_name)}"'
            rf'|[^}}]*?name:"{_re.escape(project_name)}"[^}}]*?path:"([^"]*)"'
            rf')[^}}]*?}}'
        )
        m = _re.search(pattern, raw, _re.IGNORECASE)
        if m:
            rel_path = m.group(1) or m.group(2)
            if rel_path:
                resolved = (ws_root.parent / rel_path).resolve()
                if resolved.exists():
                    return resolved
    except Exception:
        pass

    # Fallback: try to find the project as a subdirectory of workspace
    candidate = ws_root.parent / project_name
    if (candidate / ARQUX_DIR / BRAIN_CORTEX).exists():
        return candidate
    return None

CONTEXT_CORTEX = "context.cortex"
CONTEXTS_DIR = "contexts"


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

    # Phase 2: resolve target project from meta-brain
    project_root = _resolve_project_from_meta_brain(ws_root, project)
    if project_root is None:
        return CortexOUT.error(
            f"project {project!r} not found — is it registered in meta-brain?",
            code="NOT_FOUND",
        )

    # Phase 3: validate target project has a brain.cortex
    project_brain = project_root / ARQUX_DIR / BRAIN_CORTEX
    if not project_brain.exists():
        return CortexOUT.error(
            f"project {project!r} not found (no brain.cortex at {project_brain})",
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
    blp_part = f' blp="{_escape_ses_value(blp)}"' if blp else ""
    entry = (
        f'CTX:{agent} project="{_escape_ses_value(project)}"'
        f' scope="{_escape_ses_value(scope)}"{blp_part}'
        f' agent="{_escape_ses_value(agent)}"'
        f' ses="{session_id}"'
        f' project_root="{_escape_ses_value(str(project_root))}"'
    )
    document = f"$0\n\n$1: CURRENT\n{entry}\n"
    _write_context(ws_root, execution, document)
    (ws_root / CONTEXT_CORTEX).write_text(document, encoding="utf-8")

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
        warnings=[w for w in (unbound_warning(lifecycle, action="session.context_set"),) if w],
    )


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


def _write_context(ws_root: Path, execution: str | None, document: str) -> Path:
    """Persist *document* under this execution's own context file."""
    target = ws_root / CONTEXT_CORTEX
    slug = _execution_slug(execution)
    if slug:
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
    if not context_path.exists():
        return CortexOUT.error("no context set", code="NOT_FOUND")

    raw = context_path.read_text(encoding="utf-8")
    result: dict[str, str] = {}

    # Parse CTX:{agent_id} key="val" pairs
    m = re.search(r"CTX:(\S+)\s+(.+)", raw)
    if m:
        result["agent"] = m.group(1)
        pairs = m.group(2)
        for pair in re.findall(r'(\w+)="([^"]*)"', pairs):
            result[pair[0]] = pair[1]

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

    # 3. Load identity.
    identity_content = ""
    identity_source = ""
    for base, source in (
        (ws_root / "identities", "workspace"),
        (_IDENTITIES_DIR, "package"),
    ):
        candidate = base / f"{agent_id}.cortex"
        if candidate.exists():
            try:
                identity_content = candidate.read_text(encoding="utf-8")
                identity_source = source
                break
            except OSError:
                pass

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
        "identity": identity_content,
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
    """Build a project-level bootstrap (legacy, no workspace found)."""
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

    # 5. Load identity.
    identity_content = ""
    identity_source = ""
    for base, source in (
        (project_arqux / "identities", "project"),
        (_IDENTITIES_DIR, "package"),
    ):
        candidate = base / f"{agent_id}.cortex"
        if candidate.exists():
            try:
                identity_content = candidate.read_text(encoding="utf-8")
                identity_source = source
                break
            except OSError:
                pass

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
        "identity": identity_content,
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

    workspace_arqux = find_workspace_root(start=start)

    if workspace_arqux:
        # Workspace found — workspace-level bootstrap, no project binding.
        return _bootstrap_workspace(workspace_arqux, start, agent_id, ctx)

    project_arqux = find_project_root(start=start)
    if project_arqux:
        # No workspace, only project — legacy project-level bootstrap.
        return _bootstrap_project(project_arqux, start, agent_id, ctx)

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
            "— it becomes the handoff filename handoffs/<id>.cortex and the HOF 'to' field",
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

    # Build CORTEX handoff payload.
    handoff_lines = [
        "$0",
        "",
        "$1: HANDOFF",
        "",
        f'HOF:handoff{{from:"{agent_id}", to:"{target_agent}", project:"{project_name}", summary:"{summary}", blps:"{blps}", tasks:"{tasks}"}}',
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

    # Write handoff file.
    handoffs_dir = root / "handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    handoff_path = handoffs_dir / f"{target_agent}.cortex"
    handoff_path.write_text(handoff_cortex, encoding="utf-8")

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
        handoff_path=str(handoff_path),
        dry_run=False,
    )


handler_schemas = [
    {"name": "session.close", "fn": close, "description": "Close the session bound to this execution (or the explicit session_ref) and write its portable summary to brain PULSE. Never closes the newest session of the project when it belongs to another execution.", "input_schema": {"type": "object", "properties": {"summary": {"type": "string", "description": "Short human-readable summary of what was accomplished."}, "blps": {"type": "string", "description": "Comma-separated active blueprint IDs (e.g. BLP-006,BLP-007)."}, "tasks": {"type": "string", "description": "Comma-separated pending task IDs."}, "decisions": {"type": "string", "description": "Comma-separated key decisions made."}, "gaps": {"type": "string", "description": "Comma-separated detected gaps or pending items."}, "session_ref": {"type": "string", "description": "Explicit SESxxx to close. Defaults to this execution's session."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["summary"]}},
    {"name": "session.resume", "fn": resume, "description": "Restore the context of a session. Read-only: selects by explicit session_ref, else the session bound to this execution, else rejects an ambiguous choice instead of taking the newest session. Brains without real session identity keep the legacy PULSE selection.", "input_schema": {"type": "object", "properties": {"session_ref": {"type": "string", "description": "Explicit SESxxx reference."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "session.status", "fn": status, "description": "Read session metadata without restoring full context. Read-only, same selection rules as session.resume.", "input_schema": {"type": "object", "properties": {"session_ref": {"type": "string", "description": "Explicit SESxxx reference."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "session.context.set", "fn": context_set, "description": "Set the current session context pointer (project + scope + optional BLP) and open or re-attach the real session bound to this execution. Validates project exists and returns the formatted header.", "input_schema": {"type": "object", "properties": {"project": {"type": "string", "description": "Project name (e.g. ARQUX)"}, "scope": {"type": "string", "description": "Scope within project (e.g. CYCLE-01)"}, "blp": {"type": "string", "description": "Optional active BLP ID (e.g. BLP-014)"}, "intent": {"type": "string", "enum": ["new", "resumed"], "default": "new", "description": "'new' opens or recovers this execution's session; 'resumed' re-attaches session_ref without changing its id or original start."}, "session_ref": {"type": "string", "description": "Explicit SESxxx reference; required when intent='resumed'."}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["project", "scope"]}},
    {"name": "session.context.get", "fn": context_get, "description": "Read the current context pointer and return the formatted header.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}}},
    {"name": "session.bootstrap", "fn": bootstrap, "description": "Bootstrap a session using the authenticated identity. An explicit agent_id must match the caller (BLP-002). Returns cortex_context (canal I) and hcortex_dashboard (canal E).", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Starting path. Defaults to cwd."}, "agent_id": {"type": "string", "description": "Optional identity selector; must match the authenticated caller."}}}},
    {"name": "session.handoff", "fn": handoff, "description": "Serialize the current session context as CORTEX and write a handoff PULSE for the target agent (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"target_agent": {"type": "string", "description": "ID of the agent receiving the handoff."}, "content": {"type": "string", "description": "CORTEX content with keys target_agent, summary, blps, tasks."}, "dry_run": {"type": "boolean", "default": False}, "path": {"type": "string"}}, "required": ["target_agent"]}},
    {"name": "session.pulse.compact", "fn": pulse_compact, "description": "Compact pulse entries for a session. With ses_ref, selection is by membership: only that session's pulses are pruned and concurrent or legacy pulses are never reassigned by position. Writes a consolidated LNG lesson.", "input_schema": {"type": "object", "properties": {"session_id": {"type": "string"}, "ses_ref": {"type": "string", "description": "Select by session membership instead of position."}, "dry_run": {"type": "boolean", "default": False}, "path": {"type": "string"}}, "required": ["session_id"]}},
]
