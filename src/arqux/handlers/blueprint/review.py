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
    BP_REVIEW,
    LEARNING_GATE,
    MAX_VERIFICATION_LOOPS,
    _find_blueprint,
    _has_learning_recorded,
    _learning_instruction,
    _now_iso,
    _read_quality_gates,
    _record_bp_evidence,
    _record_to_brain,
    _resolve_root,
    _transition,
    _validate_approval_ready,
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
    """Declare execution complete. State → review."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_REVIEW)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    execution_errors = _validate_execution_complete(body, evidence)
    if execution_errors:
        return CortexOUT.error(
            "Cannot complete: Blueprint execution evidence is incomplete.",
            code="EXECUTION_INCOMPLETE",
            **execution_errors,
        )

    fm["status"] = BP_REVIEW
    fm["updated_at"] = _now_iso()
    fm["evidence"] = evidence or ""
    _write_blueprint(bp_path, fm, body)

    # Record evidence in brain PULSE
    _record_bp_evidence(root, bp_id, "blueprint.complete",
                        f"BLP {bp_id} completed — {evidence or 'execution done'}",
                        ctx=ctx)

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.complete",
        focus="Verificar ACs y aprobar",
        metrics={"blueprints_completed": 1},
        detail=f"BLP {bp_id} completed",
    )

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.complete ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_REVIEW,
        instruction="Auditor: cross-verify results against design. Call blueprint.approve() or blueprint.re_delegate().",
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
        instruction="Governor evaluates: re-plan (blueprint.mature) or cancel.",
    )


# ---------------------------------------------------------------------------
# blueprint.approve
# ---------------------------------------------------------------------------


def approve_blueprint(
    bp_id: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Auditor approves Blueprint after cross-verification. State → done."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    err = _transition(bp_id, fm.get("status", BP_DRAFT), BP_DONE)
    if err:
        return CortexOUT.error(err, code="INVALID_STATE")

    approval_errors = _validate_approval_ready(root, bp_id, fm, body)
    if approval_errors:
        return CortexOUT.error(
            "Cannot approve: Blueprint review evidence is incomplete.",
            code="APPROVAL_INCOMPLETE",
            **approval_errors,
        )

    gates_status = _read_quality_gates(fm)
    if gates_status and not gates_status.get(LEARNING_GATE, True) and _has_learning_recorded(root, bp_id):
        gates_status[LEARNING_GATE] = True
    if gates_status and not gates_status.get(LEARNING_GATE, True):
        return CortexOUT.error(
            "Cannot approve: has_learning_recorded is false. Call identity.record() first.",
            code="LEARNING_NOT_RECORDED",
            failed_gates=[LEARNING_GATE],
            instruction=_learning_instruction(f"blueprint.approve({bp_id})"),
        )

    fm["status"] = BP_DONE
    fm["closed_at"] = _now_iso()
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    # Record completion in brain
    _record_to_brain(root, bp_id, "done", fm.get("evidence", ""))

    # Record evidence in brain PULSE
    _record_bp_evidence(root, bp_id, "blueprint.approve",
                        f"BLP {bp_id} approved and closed",
                        ctx=ctx)

    # Auto-sync brain context
    sync_brain(
        root,
        "blueprint.approve",
        focus="Próximo BLP o cierre de ciclo",
        metrics={"blueprints_done": 1},
        detail=f"BLP {bp_id} approved",
    )

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.approve ok id={bp_id}",
        blueprint_id=bp_id,
        status=BP_DONE,
        instruction=(
            _learning_instruction(f"blueprint.approve({bp_id})")
            + " Check if cycle can be closed."
        ),
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
    """Cancel a Blueprint. State → cancelled. Governor-only."""
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
    """Re-delegate after verification failure. Max 3 times."""
    root = _resolve_root(path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    if fm.get("status") != BP_REVIEW:
        return CortexOUT.error(f"Blueprint is {fm.get('status')} — must be in review to re-delegate", code="INVALID_STATE")

    raw_loop = fm.get("verification_loop", 0)
    loop_count = int(raw_loop) if isinstance(raw_loop, str) else raw_loop
    if loop_count >= MAX_VERIFICATION_LOOPS:
        return CortexOUT.error(
            f"max re-delegation loops ({MAX_VERIFICATION_LOOPS}) reached. Call blueprint.block_for_architect().",
            code="MAX_LOOPS",
        )

    loop_count += 1
    fm["status"] = BP_IN_PROGRESS
    fm["verification_loop"] = loop_count
    fm["updated_at"] = _now_iso()
    _write_blueprint(bp_path, fm, body)

    cycle_id = fm.get("cycle", "")
    if cycle_id:
        reconcile_cycle(root, cycle_id)

    return CortexOUT.work(
        f"blueprint.re_delegate ok id={bp_id} loop={loop_count}/{MAX_VERIFICATION_LOOPS}",
        blueprint_id=bp_id,
        verification_loop=loop_count,
        max_loops=MAX_VERIFICATION_LOOPS,
        instruction=f"Executor retries with deviation feedback. Loop {loop_count} of {MAX_VERIFICATION_LOOPS}.",
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
    fm["blocked_reason"] = f"Verification failed {MAX_VERIFICATION_LOOPS} times — Architect manual review required"
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

    if fm.get("status") not in (BP_IN_PROGRESS, BP_REVIEW):
        return CortexOUT.error(
            f"blueprint is {fm.get('status')} — must be in_progress or review",
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
    else:
        new_line = old_line  # keep unchecked
        raw_loop = fm.get("verification_loop", 0)
        current = int(raw_loop) if isinstance(raw_loop, str) else raw_loop
        reason_text = reason or "AC verification failed"
        if evidence:
            new_line += f"\n  > [{ts}] FAIL (attempt {current + 1}): {reason_text} — {evidence}"
        else:
            new_line += f"\n  > [{ts}] FAIL (attempt {current + 1}): {reason_text}"

    body = body.replace(old_line, new_line, 1)
    fm["updated_at"] = ts
    _write_blueprint(bp_path, fm, body)

    # Record evidence in brain PULSE
    _record_bp_evidence(root, bp_id, "blueprint.ac",
                        f"AC {ac_id} {status}{' — ' + (evidence or reason or '') if status == 'failed' else ' — ' + (evidence or '')}",
                        ctx=ctx)

    if status == "failed":
        raw_loop = fm.get("verification_loop", 0)
        current = int(raw_loop) if isinstance(raw_loop, str) else raw_loop
        next_attempt = current + 1
        # Auto re-delegate (max 3 attempts). 3rd fail → block_for_architect.
        if fm.get("status") == BP_REVIEW and next_attempt < MAX_VERIFICATION_LOOPS:
            result = re_delegate_blueprint(bp_id, path=path, ctx=ctx)
            result.fields["instruction"] = _learning_instruction(
                f"blueprint.ac({bp_id}, {ac_id}) failed verification"
            )
            return result
        elif fm.get("status") == BP_REVIEW:
            fm["verification_loop"] = next_attempt
            _write_blueprint(bp_path, fm, body)
            return CortexOUT.work(
                f"blueprint.ac ok id={bp_id} ac={ac_id} status=failed "
                f"attempt={next_attempt}/{MAX_VERIFICATION_LOOPS} — max loops reached",
                blueprint_id=bp_id,
                ac_id=ac_id,
                status="failed",
                verification_loop=next_attempt,
                max_loops=MAX_VERIFICATION_LOOPS,
                instruction=(
                    "Call blueprint.block_for_architect() for manual review. "
                    + _learning_instruction(f"blueprint.ac({bp_id}, {ac_id}) failed verification")
                ),
            )

    fields = {
        "blueprint_id": bp_id,
        "ac_id": ac_id,
        "status": status,
    }
    if status == "failed":
        fields["instruction"] = _learning_instruction(f"blueprint.ac({bp_id}, {ac_id}) failed verification")
    return CortexOUT.work(
        f"blueprint.ac ok id={bp_id} ac={ac_id} status={status}",
        **fields,
    )
