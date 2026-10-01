"""identity.switch handler (BLP-011).

Hot identity switch as a single atomic MCP call:

1. Validate the target identity exists (project → workspace → packaged).
2. Hydrate the full behavioral contract (composes ``identity.get`` logic).
3. Register the handoff record + PULSE audit (composes ``session.handoff``).
4. Update the active session context (``context.cortex`` — agent field) and
   return the ready-to-use HCORTEX header.

The agent NEVER touches governance files directly: every mutation happens
inside this handler. On ``IDENTITY_NOT_FOUND`` the available identities are
returned as actionable guidance (discovery without globbing the filesystem).
"""

from __future__ import annotations

import os
from pathlib import Path

from ...constants import IDENTITIES_DIR, OUT_ERROR
from ...cortex.parse_content import parse_content_entry
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root, find_workspace_root
from ..session import CONTEXT_CORTEX, _escape_ses_value, context_get, handoff
from .get import get_handler


def _available_identities(start: Path) -> list[str]:
    """Resolve the live identity list across the 3-level chain.

    Scans the same directories ``identity.get`` resolves: project,
    workspace, then packaged identities. Never hardcoded (BLP-011 §7).
    """
    found: set[str] = set()
    candidates: list[Path] = []

    project_arqux = find_project_root(start=start)
    if project_arqux is not None:
        candidates.append(project_arqux / "identities")

    workspace_arqux = find_workspace_root(start=start)
    if workspace_arqux is not None:
        candidates.append(workspace_arqux / "identities")

    candidates.append(IDENTITIES_DIR)

    for directory in candidates:
        if directory.is_dir():
            found.update(p.stem for p in directory.glob("*.cortex"))
    return sorted(found)


def switch(
    agent_id: str | None = None,
    *,
    content: str | None = None,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Switch the active agent identity in one atomic call.

    Args:
        agent_id: Target identity (case-insensitive).
        content: Optional CORTEX content with keys ``agent_id, summary,
            blps, tasks`` — parsed values override params (BLP-010).
        dry_run: If True, validate and report without mutating anything
            (no handoff, no context, no PULSE).
        path: Starting path for resolving the workspace/project root.
        ctx: Permission context (origin agent for PULSE audit).

    Returns ``OUT-WORK`` with ``agent_id``, ``from_agent``, ``header``,
    ``contract`` (raw CORTEX, canal I), ``available_identities`` and the
    mutation report (``handoff_path``, ``context_updated``).
    """
    # Merge content CORTEX (parsed values win — BLP-010 pattern).
    summary = ""
    blps = ""
    tasks = ""
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            agent_id = parsed.get("agent_id", agent_id)
            summary = parsed.get("summary", "")
            blps = parsed.get("blps", "")
            tasks = parsed.get("tasks", "")

    if not agent_id:
        return CortexOUT.error("agent_id is required", code="INVALID_ARGS")

    start = Path(path or os.getcwd()).resolve()
    available = _available_identities(start)
    canonical = agent_id.casefold()

    # Step 1+2 — existence + contract hydration (read-only composition).
    ident = get_handler(agent_id=canonical, path=str(start), ctx=ctx)
    if ident.profile == OUT_ERROR:
        return CortexOUT.error(
            f"identity not found for agent_id={agent_id!r}",
            code="IDENTITY_NOT_FOUND",
            agent_id=agent_id,
            available_identities=available,
        )
    contract = ident.fields.get("content", "")
    contract_source = ident.fields.get("source", "")

    from_agent = (
        ctx.agent_id if ctx is not None else PermissionContext.from_env().agent_id
    )

    # Read current session context (preserved across the switch).
    ctx_out = context_get(path=str(start), ctx=ctx)
    has_context = ctx_out.profile != OUT_ERROR
    current = ctx_out.fields if has_context else {}

    if dry_run:
        header = _build_header(canonical, current) if has_context else None
        return CortexOUT.work(
            f"identity.switch dry_run from={from_agent} to={canonical}",
            agent_id=canonical,
            from_agent=from_agent,
            header=header,
            contract=contract,
            contract_source=contract_source,
            available_identities=available,
            context_updated=False,
            dry_run=True,
        )

    # Step 3 — handoff record + PULSE audit (composed, not copied).
    handoff_out = handoff(
        target_agent=canonical,
        content=(
            f'target_agent:{canonical},summary:"{summary or f"identity switch from {from_agent}"}",'
            f'blps:"{blps}",tasks:"{tasks}"'
        ),
        dry_run=False,
        path=str(start),
        ctx=ctx,
    )
    if handoff_out.profile == OUT_ERROR:
        return handoff_out

    # Step 4 — update active context (same store/format as context.set).
    context_updated = False
    if has_context:
        try:
            ws_root = find_workspace_root(start=start)
            assert ws_root is not None  # context_get already resolved it
            blp = current.get("blp", "")
            blp_part = f' blp="{_escape_ses_value(blp)}"' if blp else ""
            entry = (
                f'CTX:{canonical} project="{_escape_ses_value(current.get("project", ""))}"'
                f' scope="{_escape_ses_value(current.get("scope", ""))}"{blp_part}'
                f' agent="{_escape_ses_value(canonical)}"'
                f' project_root="{_escape_ses_value(current.get("project_root", ""))}"'
            )
            (ws_root / CONTEXT_CORTEX).write_text(
                f"$0\n\n$1: CURRENT\n{entry}\n", encoding="utf-8"
            )
            context_updated = True
        except OSError as exc:
            # Handoff already persisted — report partial state honestly.
            return CortexOUT.error(
                f"handoff registered but context update failed: {exc}",
                code="CONTEXT_WRITE_ERROR",
                agent_id=canonical,
                from_agent=from_agent,
                handoff_done=True,
            )

    header = _build_header(canonical, current) if has_context else None

    # PULSE: switch-specific audit event (handoff already logged its own).
    try:
        pulse_root = find_project_root(start=start)
        if pulse_root is not None:
            event_id = next_pulse_event_id(pulse_root)
            append_pulse_to_brain(
                pulse_root,
                event_id=event_id,
                task_id="-",
                kind="identity_switch",
                agent=from_agent,
                payload=(
                    f"[identity.switch] from={from_agent} to={canonical} "
                    f"context_updated={context_updated}"
                ),
            )
    except Exception:  # noqa: BLE001
        pass

    return CortexOUT.work(
        f"identity.switch ok from={from_agent} to={canonical}"
        + (f' header="{header}"' if header else ""),
        agent_id=canonical,
        from_agent=from_agent,
        header=header,
        contract=contract,
        contract_source=contract_source,
        available_identities=available,
        handoff_path=handoff_out.fields.get("handoff_path", ""),
        context_updated=context_updated,
        dry_run=False,
    )


def _build_header(agent: str, current: dict[str, str]) -> str:
    """Build the HCORTEX header preserving project/scope/BLP."""
    header = (
        f"⬡ {agent}"
        f" | {current.get('project', '?')}"
        f" | {current.get('scope', '?')}"
    )
    if current.get("blp"):
        header += f" | {current['blp']}"
    return header
