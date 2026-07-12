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
from pathlib import Path
from typing import Any

from ..constants import ARQUX_DIR, BRAIN_CORTEX
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..pulse import append_pulse_to_brain, next_pulse_event_id, read_pulse_from_brain
from ..state import find_project_root, find_workspace_root


def close(
    summary: str,
    blps: str | None = None,
    tasks: str | None = None,
    decisions: str | None = None,
    gaps: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Close the current session and write a portable SES entry to brain PULSE.

    Args:
        summary: Short human-readable summary of what was accomplished.
        blps: Comma-separated list of active blueprint IDs (e.g. "BLP-006,BLP-007").
        tasks: Comma-separated list of pending task IDs (e.g. "T-002,T-003").
        decisions: Comma-separated list of key decisions made.
        gaps: Comma-separated list of detected gaps or pending items.
        path: Path to project root. Defaults to cwd.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    agent = (ctx or PermissionContext.from_env()).agent_id

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
    )

    if len(ses_payload) > 2048:
        return CortexOUT.error(
            f"SES exceeds 2KB ({len(ses_payload)} bytes). Prioritize critical info.",
            code="SES_TOO_LARGE",
        )

    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root,
        event_id=event_id,
        task_id="-",
        kind="session",
        agent=agent,
        payload=ses_payload,
    )

    return CortexOUT.work(
        "session.close ok",
        event_id=event_id,
        agent=agent,
        size_bytes=len(ses_payload),
        summary=summary,
    )


def resume(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read the last SES entry from brain PULSE and return the context."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

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
    )


def status(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read SES metadata without restoring full context."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

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


def context_set(
    project: str,
    scope: str,
    blp: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Set the current session context pointer.

    Locates the workspace from *path* (or CWD), resolves the target project
    from meta-brain.cortex, validates it has a brain.cortex, and stores a
    lightweight context entry in the workspace's ``.arqux/context.cortex``.
    The context file is overwritten on each call (one context per workspace).
    """
    # Phase 1: locate workspace (from path or CWD)
    ws_root = find_workspace_root(start=path)
    if ws_root is None:
        return CortexOUT.error("no workspace root found", code="NOT_FOUND")

    agent = (ctx or PermissionContext.from_env()).agent_id

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

    # Phase 4: write context at workspace level (single source of truth)
    context_path = ws_root / CONTEXT_CORTEX
    blp_part = f' blp="{_escape_ses_value(blp)}"' if blp else ""
    entry = (
        f'CTX:{agent} project="{_escape_ses_value(project)}"'
        f' scope="{_escape_ses_value(scope)}"{blp_part}'
        f' agent="{_escape_ses_value(agent)}"'
        f' project_root="{_escape_ses_value(str(project_root))}"'
    )
    context_path.write_text(f"$0\n\n$1: CURRENT\n{entry}\n", encoding="utf-8")

    header = f"⬡ {agent} | {project} | {scope}"
    if blp:
        header += f" | {blp}"

    return CortexOUT.work(
        "session.context.set ok",
        header=header,
        project=project,
        scope=scope,
        blp=blp or "",
        agent=agent,
    )


def context_get(
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read the current context pointer from the workspace ``.arqux/context.cortex``."""
    ws_root = find_workspace_root(start=path)
    if ws_root is None:
        return CortexOUT.error("no workspace root found", code="NOT_FOUND")

    context_path = ws_root / CONTEXT_CORTEX
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


def bootstrap(
    path: str | None = None,
    *,
    agent_id: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Bootstrap a session by aggregating context, identity, cycle and brain.

    Wraps ``context.detect`` + ``identity.get`` + ``context.full`` +
    ``cycle.current`` + ``brain.cortex`` read into 1 call (BLP-008).

    Returns TWO outputs:

    - ``cortex_context`` (dict, canal I): machine-readable context for
      agent consumption.
    - ``hcortex_dashboard`` (str, canal E): markdown dashboard for the
      Architect.

    If no ``.arqux/`` is found, returns an informative message (not an
    error).
    """
    import os as _os
    from pathlib import Path as _Path
    from ..constants import IDENTITIES_DIR as _IDENTITIES_DIR, CYCLES_DIR as _CYCLES_DIR
    from ..state import read_brain as _read_brain

    start = _Path(path or _os.getcwd()).resolve()

    # Resolve agent_id (default: caller's agent_id, fallback to alfred).
    if not agent_id:
        agent_id = (ctx or PermissionContext.from_env()).agent_id or "alfred"

    project_arqux = find_project_root(start=start)
    workspace_arqux = find_workspace_root(start=start)

    if project_arqux is None and workspace_arqux is None:
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

    # We have at least a workspace — prefer project if available.
    arqux_root = project_arqux or workspace_arqux
    kind = "project" if project_arqux is not None else "workspace"
    project_root_parent = arqux_root.parent

    # 1. Read brain.
    fm, sections, raw = _read_brain(project_root_parent)
    project_name = fm.get("project", "") or project_root_parent.name
    governor = fm.get("governor", "")

    # 2. List cycles.
    cycles_base = arqux_root / _CYCLES_DIR
    cycles: list[dict[str, Any]] = []
    current_cycle: str | None = None
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
            if cycle_status in ("active", "ready") and current_cycle is None:
                current_cycle = cdir.name
    if current_cycle is None and cycles:
        current_cycle = cycles[-1]["id"]

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
    skills_dir = arqux_root / "skills"
    skills: list[str] = []
    if skills_dir.exists():
        for f in sorted(skills_dir.iterdir()):
            if f.is_file() and f.name.endswith(".skill.md"):
                skills.append(f.stem.removesuffix(".skill"))

    # 5. Load identity.
    identity_content = ""
    identity_source = ""
    for base, source in (
        (arqux_root / "identities", "project" if kind == "project" else "workspace"),
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
        "kind": kind,
        "start": str(start),
        "arqux_path": str(arqux_root),
        "project": project_name,
        "project_path": str(project_root_parent),
        "governor": governor,
        "cycle": current_cycle,
        "cycles": cycles,
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
    dashboard_parts.append(f"**Kind:** `{kind}`")
    dashboard_parts.append(f"**Architect path:** `{start}`")
    dashboard_parts.append(f"**Arqux path:** `{arqux_root}`")
    dashboard_parts.append(f"**Governor:** `{governor or '(unset)'}`")
    dashboard_parts.append(
        f"**Agent:** `{agent_id}` (identity source: `{identity_source or 'none'}`)"
    )
    dashboard_parts.append("")
    dashboard_parts.append("## Cycles")
    if cycles:
        for c in cycles:
            marker = " *(current)*" if c["id"] == current_cycle else ""
            dashboard_parts.append(
                f"- `{c['id']}` — status: `{c.get('status', '?')}`{marker}"
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
    _record_bootstrap_pulse(arqux_root, ctx, agent_id=agent_id, project=project_name)

    return CortexOUT.work(
        f"session.bootstrap ok kind={kind} project={project_name} "
        f"cycle={current_cycle} agents={len(agents)} skills={len(skills)}",
        found=True,
        kind=kind,
        start=str(start),
        agent_id=agent_id,
        cortex_context=cortex_context,
        hcortex_dashboard=hcortex_dashboard,
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
        event_id = next_pulse_event_id(arqux_root)
        append_pulse_to_brain(
            arqux_root,
            event_id=event_id,
            task_id="-",
            kind="session_bootstrap",
            agent=agent,
            payload=f"[session.bootstrap] agent={agent_id} project={project}",
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

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # Read current context.
    from ..state import read_brain
    fm, sections, raw = read_brain(root.parent)
    project_name = fm.get("project", "") or root.parent.name
    agent_id = (ctx or PermissionContext.from_env()).agent_id

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

    # Write PULSE for outgoing session.
    try:
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id="-",
            kind="session_handoff",
            agent=agent_id,
            payload=f"[session.handoff] from={agent_id} to={target_agent} summary={summary[:60]}",
        )
    except Exception:  # noqa: BLE001
        pass

    return CortexOUT.work(
        f"session.handoff ok from={agent_id} to={target_agent}",
        target_agent=target_agent,
        from_agent=agent_id,
        handoff_path=str(handoff_path),
        dry_run=False,
    )


handler_schemas = [
    dict(name="session.close", fn=close, description="Close the current session and write a portable SES entry to brain PULSE.", input_schema={"type": "object", "properties": {"summary": {"type": "string", "description": "Short human-readable summary of what was accomplished."}, "blps": {"type": "string", "description": "Comma-separated active blueprint IDs (e.g. BLP-006,BLP-007)."}, "tasks": {"type": "string", "description": "Comma-separated pending task IDs."}, "decisions": {"type": "string", "description": "Comma-separated key decisions made."}, "gaps": {"type": "string", "description": "Comma-separated detected gaps or pending items."}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["summary"]}),
    dict(name="session.resume", fn=resume, description="Read the last SES entry from brain PULSE and restore the context.", input_schema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}),
    dict(name="session.status", fn=status, description="Read SES metadata without restoring full context.", input_schema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}),
    dict(name="session.context.set", fn=context_set, description="Set the current session context pointer (project + scope + optional BLP). Validates project exists and returns the formatted header.", input_schema={"type": "object", "properties": {"project": {"type": "string", "description": "Project name (e.g. ARQUX)"}, "scope": {"type": "string", "description": "Scope within project (e.g. CYCLE-01)"}, "blp": {"type": "string", "description": "Optional active BLP ID (e.g. BLP-014)"}, "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}, "required": ["project", "scope"]}),
    dict(name="session.context.get", fn=context_get, description="Read the current context pointer and return the formatted header.", input_schema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."}}}),
    dict(name="session.bootstrap", fn=bootstrap, description="Bootstrap a session by aggregating context.detect + identity.get + context.full + cycle.current + brain.cortex read into 1 call (BLP-008). Returns cortex_context (canal I) and hcortex_dashboard (canal E).", input_schema={"type": "object", "properties": {"path": {"type": "string", "description": "Starting path. Defaults to cwd."}, "agent_id": {"type": "string", "description": "Agent ID for identity lookup. Defaults to caller's agent_id."}}}),
    dict(name="session.handoff", fn=handoff, description="Serialize the current session context as CORTEX and write a handoff PULSE for the target agent (BLP-010 meta-handler). Supports dry_run mode.", input_schema={"type": "object", "properties": {"target_agent": {"type": "string", "description": "ID of the agent receiving the handoff."}, "content": {"type": "string", "description": "CORTEX content with keys target_agent, summary, blps, tasks."}, "dry_run": {"type": "boolean", "default": False}, "path": {"type": "string"}}, "required": ["target_agent"]}),
]
