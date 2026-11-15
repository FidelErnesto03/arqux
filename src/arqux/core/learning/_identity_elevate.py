"""Brain LNG → identity contract elevation (behavioral learning line).

Architect rule (2026-11-15): lessons live ONLY in ``brain.cortex`` ``$8``
(LESSONS). From there a lesson may elevate to ``$11`` KNOWLEDGE (operational,
via ``cortex.learn.elevate``) or to an agent identity contract as ``AXM``/``LIM``
(behavioral, via this module). ``.lessons.cortex`` stores and identity
BEHAVIORAL-LESSONS sections are deprecated lesson containers.

The write into ``<agent>.cortex`` goes through
``IdentityManager.elevate_to_identity`` — the single sanctioned mutation path
for identity contracts (BLP-039 §16).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX
from ...identity import IdentityManager, IdentityNotFoundError, InvalidContractTypeError

_LESSONS_SECTION = "$8"

_CONTRACT_BY_TYPE = {"AXIOM": "AXM", "LIMIT": "LIM"}
_SIGIL_NAME_RE = r"[^\s{]+"


def _resolve_brain(project_root: Path | str) -> Path | None:
    """Return ``<project>/.arqux/brain.cortex`` or ``None``."""
    from ...state import find_project_root

    root = find_project_root(start=str(project_root))
    if root is not None:
        candidate = root / BRAIN_CORTEX
        if candidate.exists():
            return candidate
    direct = Path(project_root) / ARQUX_DIR / BRAIN_CORTEX
    if direct.exists():
        return direct
    return None


def _find_identities_dir(agent: str, start: Path) -> Path | None:
    """Walk up from *start* for ``.arqux/identities/<agent>.cortex``."""
    cursor = Path(start).resolve()
    while True:
        candidate = cursor / ARQUX_DIR / "identities" / f"{agent}.cortex"
        if candidate.exists():
            return candidate.parent
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


def _read_lesson(brain: Path, lesson_id: str) -> dict[str, Any] | None:
    from ...state import crud_read

    try:
        result = crud_read(brain, f"{_LESSONS_SECTION}/LNG:{lesson_id}")
    except Exception:  # noqa: BLE001
        return None
    entries = result.get("entries", [])
    if not entries:
        return None
    value = entries[0].get("value")
    return value if isinstance(value, dict) else {"lesson": str(value)}


def _lesson_body(value: dict[str, Any]) -> str:
    """Contract body text derived from the brain lesson fields."""
    parts = []
    lesson = str(value.get("lesson") or value.get("pattern") or "").strip()
    prevention = str(value.get("prevention") or "").strip()
    if lesson:
        parts.append(lesson)
    if prevention:
        parts.append(f"prevention: {prevention}")
    return " | ".join(parts) if parts else str(value.get("cause") or "")


def _identity_has_contract(identity_path: Path, sigil: str, name: str) -> bool:
    try:
        text = identity_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(rf"(?:^|\n){sigil}:{re.escape(name)}\{{", text))


def _preview_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def elevate_lesson_to_identity(
    project_root: Path | str,
    lesson_id: str,
    agent: str,
    contract_type: str,
    *,
    dry_run: bool = True,
    confirm_hash: str | None = None,
) -> dict[str, Any]:
    """Elevate a brain ``$8`` LNG lesson into an agent identity contract.

    ``contract_type`` is ``"AXIOM"`` (→ ``AXM``) or ``"LIMIT"`` (→ ``LIM``).
    ``dry_run=True`` (default) returns the proposal and ``preview_hash``
    without writing. Applying requires ``confirm_hash`` equal to the preview
    hash — the caller must have reviewed the exact proposal first.
    """
    contract_norm = str(contract_type or "").upper().strip()
    sigil = _CONTRACT_BY_TYPE.get(contract_norm)
    if sigil is None:
        return {
            "error": f"contract_type must be AXIOM or LIMIT; got {contract_type!r}",
            "code": "INVALID_CONTRACT_TYPE",
        }
    agent = (agent or "").strip().lower()
    if not agent:
        return {"error": "agent is required", "code": "INVALID_ARGS"}
    lesson_id = (lesson_id or "").strip()
    if not lesson_id:
        return {"error": "lesson_id is required", "code": "INVALID_ARGS"}

    brain = _resolve_brain(project_root)
    if brain is None:
        return {
            "error": "no project brain.cortex found — lessons live only in brain.cortex",
            "code": "NOT_FOUND",
        }

    value = _read_lesson(brain, lesson_id)
    if value is None:
        return {
            "error": f"LNG:{lesson_id} not found in brain $8",
            "code": "NOT_FOUND",
        }

    body = _lesson_body(value)
    if not body:
        return {
            "error": f"LNG:{lesson_id} has no lesson/pattern/prevention content to elevate",
            "code": "EMPTY_LESSON",
        }

    identities_dir = _find_identities_dir(agent, Path(project_root))
    if identities_dir is None:
        return {
            "error": f"no .arqux/identities/{agent}.cortex reachable from {project_root}",
            "code": "NOT_FOUND",
        }
    identity_path = identities_dir / f"{agent}.cortex"

    evidence_ref = f"brain:$8/LNG:{lesson_id}"
    proposal = {
        "agent": agent,
        "sigil": sigil,
        "name": lesson_id,
        "body": body,
        "status": "current",
        "source_lesson": lesson_id,
        "evidence_ref": evidence_ref,
    }
    canonical = "|".join(
        [agent, f"{sigil}:{lesson_id}", body, evidence_ref]
    )
    preview = _preview_hash(canonical)

    # confirm_hash is validated BEFORE the idempotent skip (ergonomics
    # issue): a wrong hash on an already-applied elevation must surface as
    # an error — reporting "skip" there would silently endorse an
    # unreviewed approval.
    if not dry_run and confirm_hash != preview:
        return {
            "error": (
                "preview approval required before applying elevation. "
                "Run dry-run, review the proposal, then pass confirm_hash."
            ),
            "preview_hash": preview,
            "proposal": proposal,
        }

    if _identity_has_contract(identity_path, sigil, lesson_id):
        return {
            "skip": True,
            "reason": f"{sigil}:{lesson_id} already present in {agent}.cortex",
            "agent": agent,
            "sigil": sigil,
            "lesson_id": lesson_id,
        }

    if dry_run:
        return {
            "mode": "dry_run",
            "proposal": proposal,
            "preview_hash": preview,
            "source": f"$8/LNG:{lesson_id}",
            "target": str(identity_path),
        }

    try:
        im = IdentityManager(identities_dir=identities_dir)
        result = im.elevate_to_identity(
            agent=agent,
            lesson_id=lesson_id,
            contract_type=contract_norm,
            pattern=body,
            evidence_ref=evidence_ref,
        )
    except (IdentityNotFoundError, InvalidContractTypeError) as exc:
        return {"error": str(exc), "code": "ELEVATE_ERROR"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"identity write failed: {exc}", "code": "ELEVATE_ERROR"}

    # silent_corruption guard: a handler must not report ok before the
    # artifact proves the write landed.
    if not _identity_has_contract(identity_path, sigil, lesson_id):
        return {
            "error": f"post-write verification failed: {sigil}:{lesson_id} absent from {identity_path}",
            "code": "VERIFY_FAILED",
        }

    try:
        from ...pulse import record_pulse

        record_pulse(
            Path(project_root),
            task_id=lesson_id,
            kind="lesson_elevate",
            agent=agent,
            payload=(
                f"identity.elevate ok agent={agent} {sigil}:{lesson_id} "
                f"from=$8/LNG:{lesson_id}"
            ),
        )
    except Exception:  # noqa: BLE001 - audit must not fail the elevation
        pass

    return {
        "mode": "applied",
        "proposal": proposal,
        "preview_hash": preview,
        "result": result,
        "verified": True,
    }


__all__ = ["elevate_lesson_to_identity"]
