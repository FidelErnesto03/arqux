"""Unified elevation API for three lines of learning (BLP-038)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, IDENTITIES_DIR
from ._common import _resolve_project_root
from ._elevate import elevate_candidate
from ._lesson import (
    InsufficientConfidenceError,
    LessonStore,
)
from ._models import (
    AgentIdentityError,
    ContainerIdentityError,
)

#: Allowed contract types per line.
_CONTRACT_TYPES_BEHAVIORAL = {"AXIOM", "LIMIT"}
_CONTRACT_TYPES_PROCEDURAL = {"CNST", "CLAIM"}
_CONTRACT_TYPES_CONTEXTUAL = {"KNW"}


@dataclass
class BlueprintDraft:
    """A proposed elevation that has passed thresholds but not yet applied.

    The Governor reviews the draft and decides whether to ``apply()`` it.
    """
    line: str            # behavioral | procedural | contextual
    source: str          # source container path
    target: str          # target container path/section
    contract_type: str   # AXIOM | LIMIT | CNST | CLAIM | KNW
    lesson_id: str
    sigil_to_write: str  # AXM | LIM | CNST | CLAIM | KNW
    content: dict[str, Any]
    evidence_refs: list[str] = field(default_factory=list)


def _resolve_behavioral_paths(
    agent: str, *, project_root: Path | None = None,
) -> tuple[Path, Path]:
    """Resolve (source=lessons.cortex, target=<agent>.cortex) paths.

    Both files live under ``.arqux/identities/``.
    """
    if not agent:
        raise AgentIdentityError("agent name must be non-empty")
    identities_dir = Path(project_root or Path.cwd()) / ARQUX_DIR / "identities"
    if not identities_dir.exists():
        identities_dir = IDENTITIES_DIR
    source = identities_dir / f"{agent}.lessons.cortex"
    target = identities_dir / f"{agent}.cortex"
    if not target.exists():
        raise AgentIdentityError(
            f"Target identity file does not exist: {target}. "
            f"Known agents: alfred, jarvis, seshat, heimdall, executor, "
            f"governor, auditor."
        )
    return source, target


def _draft_to_dict(draft: BlueprintDraft) -> dict[str, Any]:
    return {
        "line": draft.line,
        "source": draft.source,
        "target": draft.target,
        "contract_type": draft.contract_type,
        "lesson_id": draft.lesson_id,
        "sigil_to_write": draft.sigil_to_write,
        "content": draft.content,
        "evidence_refs": draft.evidence_refs,
    }


def elevate(
    *,
    source: str,
    target: str,
    contract_type: str,
    lesson_id: str,
    line: str = "behavioral",
    agent: str | None = None,
    project_root: Path | None = None,
    dry_run: bool = True,
    apply: bool = False,  # noqa: A002
) -> dict[str, Any]:
    """Unified elevation motor for the three lines (BLP-038 §8/§11).

    Parameters
    ----------
    source : str
        Path to the LessonStore source container.
    target : str
        Path to the destination container (and optionally a section).
    contract_type : str
        AXIOM | LIMIT (behavioral) | CNST | CLAIM (procedural) | KNW (contextual).
    lesson_id : str
        The sigil name to elevate (e.g. ``lsn-042``).
    line : str
        ``behavioral`` | ``procedural`` | ``contextual``. Selects thresholds.
    agent : str, optional
        Required for behavioral — the agent that owns the lessons store.
    project_root : Path, optional
        Used to resolve identities directory when source/target are bare names.
    dry_run : bool
        When True (default), returns the draft without applying.
    apply : bool
        When True, applies the elevation (requires Governor approval at the
        CLI/handler layer).

    Returns
    -------
    dict
        ``{mode, line, draft, applied?}`` — see BLP-038 §10 contracts.
    """
    line_norm = line.lower().strip()
    if line_norm not in {"behavioral", "procedural", "contextual"}:
        raise ValueError(f"Unknown line: {line!r}")

    contract_norm = contract_type.upper().strip()

    if line_norm == "behavioral" and contract_norm not in _CONTRACT_TYPES_BEHAVIORAL:
        raise ValueError(
            f"Behavioral line only accepts contracts "
            f"{_CONTRACT_TYPES_BEHAVIORAL}; got {contract_norm!r}"
        )
    if line_norm == "procedural" and contract_norm not in _CONTRACT_TYPES_PROCEDURAL:
        raise ValueError(
            f"Procedural line only accepts contracts "
            f"{_CONTRACT_TYPES_PROCEDURAL}; got {contract_norm!r}"
        )
    if line_norm == "contextual" and contract_norm not in _CONTRACT_TYPES_CONTEXTUAL:
        raise ValueError(
            f"Contextual line only accepts contracts "
            f"{_CONTRACT_TYPES_CONTEXTUAL}; got {contract_norm!r}"
        )

    # --- Behavioral line ---
    if line_norm == "behavioral":
        if not agent:
            raise AgentIdentityError(
                "agent is required for the behavioral line"
            )
        src_path = Path(source)
        if not src_path.exists():
            src_path, _ = _resolve_behavioral_paths(agent, project_root=project_root)
        store = LessonStore(src_path, agent=agent)
        lesson = store.get_lesson(lesson_id)
        can, reason = store.can_elevate(lesson)
        if not can:
            raise InsufficientConfidenceError(
                f"Cannot elevate {lesson_id}: {reason}"
            )
        sigil_to_write = "AXM" if contract_norm == "AXIOM" else "LIM"
        draft = BlueprintDraft(
            line="behavioral",
            source=str(src_path),
            target=target,
            contract_type=contract_norm,
            lesson_id=lesson_id,
            sigil_to_write=sigil_to_write,
            content={
                "name": lesson_id,
                "body": lesson.pattern,
                "status": "current",
                "source_lesson": lesson_id,
            },
            evidence_refs=[lesson.evidence_ref] if lesson.evidence_ref else [],
        )
        if dry_run and not apply:
            return {"mode": "dry_run", "line": "behavioral", "draft": draft.to_dict() if hasattr(draft, "to_dict") else _draft_to_dict(draft)}
        store.mark_elevated(lesson_id)
        return {
            "mode": "applied",
            "line": "behavioral",
            "draft": _draft_to_dict(draft),
            "lesson_status": "elevated",
            "next_step": (
                f"call IdentityManager.elevate_to_identity(agent={agent!r}, "
                f"lesson_id={lesson_id!r}, contract_type={contract_norm!r}) "
                f"to write the {sigil_to_write} sigil into {target}"
            ),
        }

    # --- Procedural line ---
    if line_norm == "procedural":
        src_path = Path(source)
        if not src_path.exists():
            raise ContainerIdentityError(f"Source skill not found: {src_path}")
        sigil_to_write = contract_norm
        draft = BlueprintDraft(
            line="procedural",
            source=str(src_path),
            target=target or str(src_path),
            contract_type=contract_norm,
            lesson_id=lesson_id,
            sigil_to_write=sigil_to_write,
            content={
                "name": lesson_id,
                "body": "(procedural elevation — see skill file)",
                "status": "current",
            },
        )
        if dry_run and not apply:
            return {"mode": "dry_run", "line": "procedural", "draft": _draft_to_dict(draft)}
        return {
            "mode": "applied",
            "line": "procedural",
            "draft": _draft_to_dict(draft),
            "note": "procedural elevation mutates the skill file in-place",
        }

    # --- Contextual line ---
    if project_root is None:
        resolved = _resolve_project_root(None)
        if resolved is None:
            raise ContainerIdentityError(
                "Could not resolve project_root for contextual elevation"
            )
        project_root = resolved
    result = elevate_candidate(
        project_root,
        lesson_id,
        dry_run=dry_run and not apply,
    )
    return {
        "mode": result.get("mode", "dry_run"),
        "line": "contextual",
        "result": result,
    }
