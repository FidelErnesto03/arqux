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
