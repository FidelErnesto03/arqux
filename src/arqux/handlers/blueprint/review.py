"""Blueprint review/completion handlers.

complete, approve, ac, re_delegate, block_for_architect, fail, cancel
"""

from __future__ import annotations

import re

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...sync import reconcile_cycle, sync_brain
from ._helpers import (
    BP_BLOCKED,
    BP_CANCELLED,
    BP_DONE,
    BP_DRAFT,
    BP_IN_PROGRESS,
    _find_blueprint,
    _now_iso,
    _record_bp_evidence,
    _record_to_brain,
    _resolve_root,
    _transition,
    _validate_execution_complete,
    _write_blueprint,
)

# ---------------------------------------------------------------------------
# blueprint.complete
# ---------------------------------------------------------------------------


def complete_blueprint(
    bp_id: str,
    evidence: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Declare execution complete. State → done (completado + aprobado implicitamente)."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_DONE)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    execution_errors = _validate_execution_complete(body, evidence)
    if execution_errors:
        return CortexOUT.error(
            "Cannot complete: Blueprint execution evidence is incomplete.",
            code="EXECUTION_INCOMPLETE",
            **execution_errors,
        )

    fm["status"] = BP_DONE
    fm["closed_at"] = _now_iso()
    fm["updated_at"] = _now_iso()
    fm["evidence"] = evidence or ""
    _write_blueprint(bp_path, fm, body)

    # Record completion in brain
    _record_to_brain(root, bp_id, "done", evidence or "")

    # Record evidence in brain PULSE
    _record_bp_evidence(root, bp_id, "blueprint.complete",
                        f"BLP {bp_id} completed — {evidence or 'execution done'}",
                        ctx=ctx)

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.complete",
        focus="Próximo BLP o cierre de ciclo",
        metrics={"blueprints_done": 1},
        detail=f"BLP {bp_id} completed and approved",
    )

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.complete ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_DONE,
        evidence=evidence or "",
        instruction="Blueprint completed and approved. Check if cycle can be closed.",
    )


# ---------------------------------------------------------------------------
# blueprint.fail
# ---------------------------------------------------------------------------


def fail_blueprint(
    bp_id: str,
    reason: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Blueprint hit an obstacle. State → blocked."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    fm["status"] = BP_BLOCKED
    fm["blocked_reason"] = reason
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.fail ok id={bp_id} reason={reason!r}",
        blueprint_id=bp_id,
        status=BP_BLOCKED,
        reason=reason,
        instruction="Governor evaluates: re-plan or cancel.",
    )


# ---------------------------------------------------------------------------
# blueprint.cancel
# ---------------------------------------------------------------------------


def cancel_blueprint(
    bp_id: str,
    reason: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Cancel a Blueprint. State → cancelled. Works from any non-terminal state."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")
    fm["status"] = BP_CANCELLED
    fm["cancelled_reason"] = reason or "cancelled"
    fm["closed_at"] = _now_iso()
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)
    _record_to_brain(root, bp_id, "cancelled", reason or "")

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.cancel",
        metrics={"blueprints_cancelled": 1},
        detail=f"{bp_id} cancelled: {reason or ''}",
    )

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.cancel ok id={bp_id}",
        blueprint_id=bp_id, status=BP_CANCELLED, reason=reason,
    )


# ---------------------------------------------------------------------------
# blueprint.re_delegate
# ---------------------------------------------------------------------------


def re_delegate_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Re-delegate after verification failure. Re-opens a done/blocked blueprint."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    valid_from = fm.get("status", BP_DRAFT)
    if valid_from not in (BP_DONE, BP_BLOCKED):
        return CortexOUT.error(
            f"Blueprint is {valid_from} — must be done or blocked to re-delegate",
            code="INVALID_STATE",
        )

    fm["status"] = BP_IN_PROGRESS
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.re_delegate ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_IN_PROGRESS,
        instruction="Executor retries. Re-open from done/blocked back to in_progress.",
    )


# ---------------------------------------------------------------------------
# blueprint.block_for_architect
# ---------------------------------------------------------------------------


def block_for_architect(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Mark Blueprint for Architect manual review (3rd fail)."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    fm["status"] = BP_BLOCKED
    fm["blocked_reason"] = "Architect manual review required"
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.block_for_architect ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_BLOCKED,
        instruction="Present to Architect: 'Blueprint failed verification 3 times. Your decision?'",
    )


# ---------------------------------------------------------------------------
# blueprint.ac
# ---------------------------------------------------------------------------


def ac_blueprint(
    bp_id: str,
    ac_id: str,
    status: str,
    evidence: str | None = None,
    reason: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Verify one AC in §12. Fail triggers auto re-delegate (max 3)."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") not in (BP_IN_PROGRESS,):
        return CortexOUT.error(
            f"blueprint is {fm.get('status')} — must be in_progress",
            code="INVALID_STATE",
        )

    if status not in ("verified", "failed"):
        return CortexOUT.error("status must be 'verified' or 'failed'", code="INVALID_ARGS")

    pattern = r"^(- \[[ ~x]\] \*\*" + re.escape(ac_id) + r":\*\* .+)$"
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        return CortexOUT.error(f"ac {ac_id} not found in §12", code="NOT_FOUND")

    old_line = match.group(1)
    ts = _now_iso()

    if status == "verified":
        new_line = old_line.replace(old_line[2:5], "[x]", 1)
        if evidence:
            new_line += f"\n  > [{ts}] Verified: {evidence}"
        body = body.replace(old_line, new_line, 1)
    else:
        new_line = old_line  # keep unchecked
        reason_text = reason or "AC verification failed"
        if evidence:
            new_line += f"\n  > [{ts}] FAIL: {reason_text} — {evidence}"
        else:
            new_line += f"\n  > [{ts}] FAIL: {reason_text}"
        body = body.replace(old_line, new_line, 1)

    fm["updated_at"] = ts
    _write_blueprint(bp_path, fm, body)

    # Record evidence in brain PULSE
    _record_bp_evidence(root, bp_id, "blueprint.ac",
                        f"AC {ac_id} {status}{' — ' + (evidence or reason or '') if status == 'failed' else ' — ' + (evidence or '')}",
                        ctx=ctx)

    fields = {
        "blueprint_id": bp_id,
        "ac_id": ac_id,
        "status": status,
    }
    if status == "failed":
        fields["instruction"] = "AC failed. Re-open via blueprint.re_delegate() if needed."
    return CortexOUT.work(
        f"blueprint.ac ok id={bp_id} ac={ac_id} status={status}",
        **fields,
    )
