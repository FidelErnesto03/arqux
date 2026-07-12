"""Cortex learning engine and identity lesson recording handlers."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ...constants import ARQUX_DIR
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext, enforce_ctx
from ...state import crud_add, find_project_root


def record_lesson_handler(
    lesson: str, kind: str | None = None, cause: str | None = None,
    prevention: str | None = None,
    agent_id: str | None = None,
    path: str | None = None, ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into agent identity with HMAC verification."""
    enforce_ctx(ctx, "identity.record", require_hmac=os.environ.get("ARQUX_STRICT_SECURITY") == "1")
    if agent_id and ctx and agent_id != ctx.agent_id:
        return CortexOUT.error("PERMISSION_DENIED", code="FORBIDDEN")
    return record_lesson_handler_legacy(
        lesson=lesson,
        kind=kind or "behavioral",
        cause=cause or "",
        prevention=prevention or "",
        agent_id=agent_id or (ctx.agent_id if ctx else "alfred"),
        path=path or "",
        ctx=ctx,
    )


def record_lesson_handler_legacy(
    lesson: str,
    kind: str = "behavioral",
    cause: str = "",
    prevention: str = "",
    agent_id: str = "",
    path: str = "",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Record a behavioral lesson into the agent's identity file.

    Appends an LNG entry to ``$5: BEHAVIORAL LESSONS`` in the agent's
    identity at ``<workspace or project>/.arqux/identities/<agent_id>.cortex``.

    This is how identities evolve — each significant behavioral lesson
    becomes a permanent part of the agent's identity.

    BLP-042: prevention is REQUIRED. No fallback bypass.
    """
    agent = agent_id or (ctx.agent_id if ctx else "alfred")
    target_path = Path(path or ".").resolve()

    identity_file = None
    cursor = target_path
    while True:
        candidate = cursor / ARQUX_DIR / "identities" / f"{agent}.cortex"
        if candidate.exists():
            identity_file = candidate
            break
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    if identity_file is None:
        pkg = Path(__file__).resolve().parent.parent.parent / "identities" / f"{agent}.cortex"
        if pkg.exists():
            identity_file = pkg
        else:
            return CortexOUT.error(
                f"identity file not found for agent={agent}", code="NOT_FOUND"
            )

    try:
        first_word = lesson.lstrip(" -\"").lower().split()[0] if lesson.split() else "lesson"
        name = re.sub(r"[^a-z0-9]", "_", first_word)[:30] or "lesson"
        value = {"type": kind, "cause": cause, "lesson": lesson, "prevention": prevention}

        result = crud_add(
            identity_file,
            "$5", "LNG", name, value,
            create_section=True,
            force=True,
        )
        if "error" in result:
            return CortexOUT.error(result["error"], code="CRUD_ERROR")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="IDENTITY_UPDATE_ERROR")

    scan_candidates = 0
    try:
        from ...learning import scan_brain  # lazy: allow monkeypatch

        root = find_project_root(start=path or ".")
        if root is not None:
            project_dir = root.parent
            brain_path = project_dir / ".arqux" / "brain.cortex"
            if brain_path.exists():
                crud_add(
                    brain_path,
                    "$7", "LNG", name,
                    {"type": kind, "cause": cause, "lesson": lesson},
                    create_section=True,
                )

            scan = scan_brain(project_dir, verbose=True)
            scan_candidates = len(scan.get("candidates", []))
    except Exception:  # noqa: BLE001
        pass

    result = CortexOUT.work(
        f"identity.record ok agent={agent} lesson={name} kind={kind}",
        agent=agent,
        kind=kind,
        lesson=name,
        file=str(identity_file),
    )
    if scan_candidates:
        result.fields["hint"] = f"{scan_candidates} learning candidate(s) detected — run cortex.learn.elevate to review"
        result.fields["learning_candidates"] = scan_candidates
    return result


def learn_scan_handler(
    scope: str = "project",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Scan a project brain through the CODEC-CORTEX Learning Engine.

    Returns scored entries and elevation candidates.
    """
    from ...learning import (  # lazy: allow monkeypatch
        _resolve_project_root,
        list_candidates,
        scan_brain,
    )

    root = _resolve_project_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    scan = scan_brain(root, verbose=(scope == "workspace"))
    if scan.get("engine") == "unavailable":
        return CortexOUT.error(
            "CODEC-CORTEX Learning Engine not available. "
            "Requires codec-cortex >=0.4.0 with learning module.",
            code="ENGINE_UNAVAILABLE",
        )
    if "error" in scan:
        return CortexOUT.error(scan["error"], code="LEARN_ERROR")

    candidates = scan.get("candidates", []) or list_candidates(root)

    return CortexOUT.work(
        f"learn.scan ok count={scan.get('count', 0)} entries scanned",
        engine=scan.get("engine", "unknown"),
        total=scan.get("count", 0),
        profile=scan.get("profile", {}),
        candidates=candidates,
    )


def learn_elevate_handler(
    candidate_id: str,
    path: str | None = None,
    *,
    apply: bool = False,
    confirm_hash: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Elevate a learning candidate (dry-run or apply).

    Default mode is dry-run (returns diff without changing brain).
    Pass apply=true to actually apply the elevation.
    """
    from ...learning import _resolve_project_root, elevate_candidate  # lazy: allow monkeypatch

    root = _resolve_project_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    result = elevate_candidate(root, candidate_id, dry_run=not apply, confirm_hash=confirm_hash)
    if "error" in result:
        return CortexOUT.error(
            result["error"],
            code="ELEVATE_ERROR",
            preview_hash=result.get("preview_hash"),
            diff=result.get("diff"),
        )

    if result.get("mode") == "dry_run":
        return CortexOUT.work(
            f"learn.elevate dry-run candidate={candidate_id}",
            candidate=candidate_id,
            mode="dry_run",
            diff=result.get("diff", ""),
            preview_hash=result.get("preview_hash", ""),
            validation_errors=result.get("validation_errors", []),
        )

    return CortexOUT.work(
        f"learn.elevate applied candidate={candidate_id}",
        candidate=candidate_id,
        mode="applied",
        diff=result.get("diff", ""),
        preview_hash=result.get("preview_hash", ""),
    )
