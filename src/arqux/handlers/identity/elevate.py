"""identity.elevate — brain lesson → identity contract (behavioral line).

Elevates a ``$8`` LNG lesson from ``brain.cortex`` into an agent identity as
an ``AXM`` or ``LIM`` contract via ``IdentityManager.elevate_to_identity``.
Default mode is dry-run (returns the proposal + preview_hash); ``apply=true``
requires ``confirm_hash`` matching the reviewed proposal.
"""

from __future__ import annotations

from ...core.learning._identity_elevate import elevate_lesson_to_identity
from ...cortex_out import CortexOUT


def elevate(
    lesson_id: str,
    agent: str,
    contract_type: str,
    path: str | None = None,
    apply: bool = False,
    confirm_hash: str | None = None,
    ctx=None,
) -> CortexOUT:
    result = elevate_lesson_to_identity(
        path or ".",
        lesson_id,
        agent,
        contract_type,
        dry_run=not apply,
        confirm_hash=confirm_hash,
    )
    if "error" in result:
        return CortexOUT.error(
            result["error"],
            code=result.get("code", "ELEVATE_ERROR"),
            preview_hash=result.get("preview_hash"),
            proposal=result.get("proposal"),
        )
    if result.get("skip"):
        return CortexOUT.work(
            f"identity.elevate skip {result.get('sigil')}:{lesson_id} agent={agent}",
            **{k: v for k, v in result.items() if k != "skip"},
        )
    if result.get("mode") == "dry_run":
        return CortexOUT.work(
            f"identity.elevate dry-run {lesson_id} → {agent} ({result['proposal']['sigil']})",
            mode="dry_run",
            proposal=result.get("proposal"),
            preview_hash=result.get("preview_hash"),
            source=result.get("source"),
            target=result.get("target"),
        )
    return CortexOUT.work(
        f"identity.elevate applied {lesson_id} → {agent} verified=true",
        mode="applied",
        proposal=result.get("proposal"),
        preview_hash=result.get("preview_hash"),
        verified=result.get("verified"),
    )
