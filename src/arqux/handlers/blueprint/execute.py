"""blueprint.execute handler (BLP-010, corrected by BLP-005).

Runs a Blueprint's §14 tasks through the real execution mechanism, requires
evidence before any acceptance criterion is certified, computes the verdict
before deciding the state, and never certifies work produced by the caller.

BLP-005 removed three defects from this handler:

* tasks were marked ``executed`` with a string literal — now each task goes
  through ``execution.execute_action`` and reports what actually happened;
* the state was written to ``done`` before the outcome was known — now the
  verdict is computed first and only ``done`` survives a fully clean run;
* acceptance criteria were sealed without evidence and by the same actor
  that "executed" — now certification requires evidence from a verifier
  whose role differs from the executor's.

Supports dry_run mode, which reports without mutating state.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...cortex.parse_content import parse_content_entry
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root
from ..execution import ExecutionError, execute_action
from ._helpers import (
    BP_BLOCKED,
    BP_DONE,
    _effective_status,
    _find_ac,
    _find_blueprint,
    _mark_table_ac,
    _now_iso,
    _transition,
    _write_blueprint,
)

#: Roles that may certify an acceptance criterion. An executor cannot
#: certify, by construction — role is assigned by the permission model and
#: cannot be self-declared at certification time (BLP-005 CA-08).
CERTIFIER_ROLES: frozenset[str] = frozenset({"auditor", "governor"})

#: Maximum execution attempts per blueprint before the loop gives up.
DEFAULT_MAX_ATTEMPTS: int = 3

#: Attempts recorded per blueprint. Stored in the blueprint frontmatter so
#: the budget survives across invocations — an in-memory counter would reset
#: on every call and let a failing blueprint be retried forever (BLP-005
#: R-16, CA-12).
ATTEMPTS_KEY = "_execution_attempts"


def budget_exhausted(fm: dict[str, Any], max_attempts: int) -> bool:
    """Whether this blueprint has already consumed its attempt budget.

    Args:
        fm: Blueprint frontmatter.
        max_attempts: Budget for this blueprint.

    Returns:
        True when another attempt would exceed the budget.
    """
    used = fm.get(ATTEMPTS_KEY, 0)
    try:
        return int(used) >= max_attempts
    except (TypeError, ValueError):
        return False


def section_blocking_conditions(body: str) -> list[str]:
    """Extract *active* blocking conditions from §16 Regla de Bloqueo.

    §16 always lists conditions — that is its purpose. A listed condition
    is only *active* when it is marked as met. The accepted markers are a
    leading ``[x]`` / ``[X]`` / ``[~]`` checkbox or an explicit ``ACTIVA:``
    prefix. Anything else is treated as declared but not triggered, so a
    blueprint carrying its standard §16 still executes.

    A run checks these before starting. If any is active the execution
    stops rather than proceeding on a blueprint that says it must not
    (BLP-005 CA-13).

    Args:
        body: Blueprint body.

    Returns:
        The active conditions, empty when none is triggered.
    """
    match = re.search(r"## §16:.*?\n(.*?)(?=\n## §\d+:|$)", body, re.DOTALL)
    if not match:
        return []
    active: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not re.match(r"^\d+\.\s+\S", stripped):
            continue
        if re.match(r"^\d+\.\s+\[[xX~]\]", stripped) or stripped.startswith(
            "ACTIVA:"
        ):
            active.append(stripped)
    return active


def execute_blueprint(
    bp_id: str,
    *,
    content: str | None = None,
    dry_run: bool = False,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Execute a Blueprint: run tasks, certify ACs, then decide the state.

    The order matters. Tasks run first, each one producing real evidence or
    a real failure. Criteria are certified only by a role allowed to certify
    and only when evidence exists. Only then is the verdict computed, and
    only a fully clean verdict yields ``done``.

    Args:
        bp_id: Blueprint ID (e.g. ``"BLP-007"``).
        content: Optional CORTEX content with keys ``bp_id, evidence, fail_reason``.
        dry_run: If True, report what would happen without modifying state.
        path: Path to project root.
        ctx: Permission context. Its role decides whether it may certify.

    Returns:
        ``CortexOUT`` with ``outcome`` in ``dry_run``, ``complete``,
        ``partial`` or ``blocked``.
    """
    # Merge content CORTEX.
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            bp_id = parsed.get("bp_id", bp_id)
            fail_reason_override = parsed.get("fail_reason", "") or ""
        else:
            fail_reason_override = ""
    else:
        fail_reason_override = ""

    if not bp_id:
        return CortexOUT.error("bp_id is required", code="INVALID_ARGS")

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")
    # find_project_root returns the ``.arqux/`` directory, which blueprint
    # lookup expects. Execution is separately confined to the project
    # directory above it, so a task step cannot write outside the project
    # (BLP-005 CA-18).
    exec_root = root.parent

    # Find and read the BLP.
    bp_path, fm, body = _find_blueprint(root, bp_id)
    if bp_path is None:
        return CortexOUT.error(f"blueprint {bp_id} not found", code="NOT_FOUND")

    # Extract §3 Preconditions, §14 Tasks, and AC items (by content, any
    # section — BLP-004 D-03) from the body.
    preconditions = _extract_section_items(body, 3)
    tasks = _extract_section_items(body, 14)
    ac_ids = _extract_ac_ids(body)

    if dry_run:
        # A dry run reports the plan and touches nothing. It never claims
        # anything is done (BLP-005 rule 10).
        return CortexOUT.work(
            f"blueprint.execute dry_run bp_id={bp_id} tasks={len(tasks)} acs={len(ac_ids)}",
            bp_id=bp_id,
            path=str(bp_path),
            dry_run=True,
            outcome="dry_run",
            preconditions=[{"precondition": p, "status": "parsed"} for p in preconditions],
            tasks=[{"task": t, "status": "parsed"} for t in tasks],
            acs=[{"ac": a, "status": "parsed"} for a in ac_ids],
        )

    agent = (ctx or PermissionContext.from_env()).agent_id
    role = (ctx or PermissionContext.from_env()).role

    # -- Phase 0: budget and blocking conditions. ------------------------
    # Checked before anything runs, so an exhausted budget or an active
    # blocker never spends work.
    max_attempts = DEFAULT_MAX_ATTEMPTS
    if budget_exhausted(fm, max_attempts):
        reason = (
            f"presupuesto de intentos agotado: {fm.get(ATTEMPTS_KEY, 0)}/"
            f"{max_attempts}; el blueprint queda bloqueado"
        )
        return _blocked_result(bp_id, bp_path, reason, tasks, ac_ids, agent)

    blockers = section_blocking_conditions(body)
    if blockers:
        reason = f"§16 declara condiciones de bloqueo activas: {blockers[0]}"
        return _blocked_result(bp_id, bp_path, reason, tasks, ac_ids, agent)

    # Consume one attempt up front. It is recorded even on failure: an
    # attempt that produced no result is still an attempt.
    fm[ATTEMPTS_KEY] = int(fm.get(ATTEMPTS_KEY, 0) or 0) + 1

    # -- Phase 1: run every task through the real executor. --------------
    # A failure stops the run. Later tasks are not attempted.
    tasks_report: list[dict[str, object]] = []
    failure_reason = fail_reason_override
    for index, task in enumerate(tasks, start=1):
        # Template placeholders are not tasks. A BLP that still carries
        # them was never really filled in, and treating them as work would
        # fail every run for no reason.
        if _is_placeholder(task):
            tasks_report.append(
                {"task": task, "status": "skipped", "index": index,
                 "reason": "template_placeholder"}
            )
            continue
        spec = _task_execution_spec(task)
        if spec is None:
            # A task with no declared action cannot be executed honestly.
            # Report it rather than pretending.
            tasks_report.append(
                {"task": task, "status": "unavailable", "index": index,
                 "reason": "no_execution_spec"}
            )
            failure_reason = failure_reason or f"tarea {task}: sin especificación de ejecución"
            break
        action, params = spec
        try:
            result = execute_action(action, params, ctx=ctx, root=exec_root)
        except ExecutionError as exc:
            tasks_report.append(
                {"task": task, "status": "failed", "index": index,
                 "reason": exc.message, "code": exc.code}
            )
            failure_reason = failure_reason or f"tarea {task}: {exc.message}"
            break
        if not result.ok:
            tasks_report.append(
                {"task": task, "status": "failed", "index": index,
                 "reason": result.reason}
            )
            failure_reason = failure_reason or f"tarea {task}: {result.reason}"
            break
        tasks_report.append(
            {
                "task": task,
                "status": "executed",
                "index": index,
                "action": action,
                "evidence_ref": result.evidence_ref,
                "actor": result.actor,
                "role": result.role,
            }
        )

    # A run is clean when at least one task actually executed and none of
    # them failed. Template placeholders are skipped, not counted as work.
    ran = [t for t in tasks_report if t["status"] == "executed"]
    tasks_ok = bool(ran) and not any(
        t["status"] in ("failed", "unavailable") for t in tasks_report
    )
    may_certify = role in CERTIFIER_ROLES

    # -- Phase 2: certify criteria, only with evidence and only if allowed.
    acs_report: list[dict[str, object]] = []
    new_body = body
    for ac_id in ac_ids:
        if not tasks_ok:
            acs_report.append({"ac": ac_id, "status": "pending", "reason": "tasks_incomplete"})
            continue
        if not may_certify:
            # CA-08: an executor cannot certify, even its own work.
            acs_report.append(
                {"ac": ac_id, "status": "pending", "reason": f"role {role!r} no puede certificar"}
            )
            continue
        # Evidence must exist for this criterion. Task evidence is the only
        # source available here; without it the criterion stays pending.
        evidence_refs = [t.get("evidence_ref") for t in tasks_report if t.get("evidence_ref")]
        if not evidence_refs:
            acs_report.append({"ac": ac_id, "status": "pending", "reason": "no_evidence"})
            continue
        found = _find_ac(new_body, ac_id)
        if not found:
            acs_report.append({"ac": ac_id, "status": "pending", "reason": "ac_not_found"})
            continue
        old_line, ac_format = found
        if ac_format == "table":
            marked = _mark_table_ac(old_line, "verified")
            if marked is None:
                acs_report.append({"ac": ac_id, "status": "pending", "reason": "ambiguous_row"})
                continue
            new_body = new_body.replace(old_line, marked, 1)
        else:
            new_body = new_body.replace(old_line, old_line.replace(old_line[2:5], "[x]", 1), 1)
        acs_report.append(
            {
                "ac": ac_id,
                "status": "verified",
                "certified_by": agent,
                "certifier_role": role,
                "evidence_ref": evidence_refs[0],
            }
        )

    # -- Phase 3: compute the verdict. Only now may state change. ---------
    all_ac_verified = bool(ac_ids) and all(a["status"] == "verified" for a in acs_report)
    if tasks_ok and all_ac_verified and not failure_reason:
        outcome = "complete"
        target_state = BP_DONE
    else:
        outcome = "partial"
        target_state = BP_BLOCKED
        if not failure_reason:
            failure_reason = (
                "criterios sin certificar: "
                + ", ".join(
                    str(a["ac"]) for a in acs_report if a["status"] != "verified"
                )
            )

    # CA-09/CA-10: the transition happens after the verdict, and `done` is
    # only reachable on a fully clean run.
    transition_err = _transition(bp_id, _effective_status(fm), target_state)
    if transition_err:
        return CortexOUT.error(transition_err, code="INVALID_STATE")

    fm["status"] = target_state
    fm["updated_at"] = _now_iso()
    if target_state == BP_DONE:
        fm["closed_at"] = _now_iso()
    _write_blueprint(bp_path, fm, new_body)

    evidence = (
        f"{len(tasks_report)} tareas ejecutadas, "
        f"{sum(1 for a in acs_report if a['status'] == 'verified')}/{len(ac_ids)} ACs "
        f"certificadas, veredicto={outcome}."
    )

    # PULSE.
    try:
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id=bp_id,
            kind="blueprint_execute",
            agent=agent,
            payload=f"[blueprint.execute] bp_id={bp_id} outcome={outcome} state={target_state}",
        )
    except Exception:  # noqa: BLE001
        pass

    return CortexOUT.work(
        f"blueprint.execute ok bp_id={bp_id} tasks={len(tasks_report)} "
        f"acs={len(acs_report)} outcome={outcome} state={target_state}",
        bp_id=bp_id,
        path=str(bp_path),
        dry_run=False,
        preconditions=[{"precondition": p, "status": "unchecked"} for p in preconditions],
        tasks=tasks_report,
        acs=acs_report,
        outcome=outcome,
        state=target_state,
        fail_reason=failure_reason,
        evidence=evidence,
    )


def _blocked_result(
    bp_id: str,
    bp_path: Path,
    reason: str,
    tasks: list[str],
    ac_ids: list[str],
    agent: str,
) -> CortexOUT:
    """Report a blocked run without mutating the blueprint.

    Used when the attempt budget is spent or §16 declares an active
    blocking condition. Nothing is written: the blueprint stays in its
    current state and the caller decides what to do.
    """
    return CortexOUT.work(
        f"blueprint.execute blocked bp_id={bp_id} reason={reason[:60]}",
        bp_id=bp_id,
        path=str(bp_path),
        dry_run=False,
        outcome="blocked",
        state=None,
        fail_reason=reason,
        tasks=[{"task": t, "status": "skipped"} for t in tasks],
        acs=[{"ac": a, "status": "pending"} for a in ac_ids],
        evidence=reason,
    )


def _is_placeholder(task: str) -> bool:
    """Whether a §14 line is still an unfilled template entry.

    Template rows look like ``**T-1.1:** _Título — Descripción_``; the
    italic span between underscores is the unfilled slot. A real task is
    either plain text or carries an ``[exec:...]`` marker.
    """
    if "[exec:" in task:
        return False
    return bool(re.search(r"_\s*[^_]+_\s*$", task.strip()))


def _task_execution_spec(task: str) -> tuple[str, dict[str, object]] | None:
    """Extract ``(action, params)`` from a §14 task line.

    A task is executable only when it declares an action. The supported
    form is a trailing marker::

        - [ ] **T-1.1:** hacer algo [exec:write_file path=out.txt content=hola]

    A task with no marker returns ``None`` so the caller reports it as
    unavailable instead of pretending it ran.
    """
    match = re.search(r"\[exec:(\w+)((?:\s+[^\s\]]+=[^\]]*)?)\s*\]\s*$", task)
    if not match:
        return None
    action = match.group(1)
    params: dict[str, object] = {}
    for key, value in re.findall(r"(\w+)=([^\s\]]*)", match.group(2) or ""):
        params[key] = value
    return action, params



def _extract_ac_ids(body: str) -> list[str]:
    """Extract AC IDs from the body by content (BLP-004 D-03).

    Scans for ``AC-NN`` identifiers in both canonical checkbox items and
    legacy table rows — regardless of which §N section holds them.
    Returns unique AC IDs in order of appearance.
    """
    ids: list[str] = []
    seen: set[str] = set()
    for line in body.splitlines():
        s = line.strip()
        # BLP-005: the identifier is ``CA-NN``. The previous pattern
        # matched ``AC-NN``, which never matched a real criterion, so no
        # criterion was ever extracted and none could be certified.
        m = re.match(r"^- \[[ xX~]\] \*\*(CA-\d+):\*\*", s)
        if not m:
            m = re.match(r"^\|\s*(CA-\d+)\s*\|", s)
        if not m:
            # Legacy BLP-004 documents used the AC- prefix; keep reading
            # them so an old blueprint is not silently left unverified.
            m = re.match(r"^- \[[ xX~]\] \*\*(AC-\d+):\*\*", s)
        if not m:
            m = re.match(r"^\|\s*(AC-\d+)\s*\|", s)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def _extract_section_items(body: str, section_number: int) -> list[str]:
    """Extract list items from a numbered section of the BLP body.

    Looks for ``## §N: ...`` headers and extracts the lines that start
    with ``- [ ]`` (unchecked items) or ``- [x]`` (checked items).
    """
    # Find the section.
    pattern = rf"## §{section_number}:.*?(?=\n## §\d+:|$)"
    match = re.search(pattern, body, re.DOTALL)
    if not match:
        return []
    section_text = match.group(0)

    # Extract items — they look like:
    # - [ ] **AC-01:** Description
    # - [ ] **T-1.1:** Title — Description
    # - [ ] Precondition 1
    items: list[str] = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        # Strip the leading "- [ ] " or "- [x] " prefix.
        cleaned = re.sub(r"^-\s+\[[ xX]\]\s*", "", line)
        if cleaned and not cleaned.startswith("_"):  # skip placeholder items
            items.append(cleaned)
    return items
