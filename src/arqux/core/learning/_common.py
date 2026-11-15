"""Shared helpers for the learning engine package.

Native implementation only (no external codec dependencies).
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR

logger = logging.getLogger(__name__)

POLICY_FILENAME = "learn-policies.cortex"



def _resolve_project_root(path: str | None) -> Path | None:
    """Find the project root (parent of .arqux/) from ``path`` or cwd."""
    from ...state import find_project_root
    result = find_project_root(start=path)
    if result is None:
        return None
    return result.parent


def _resolve_policy_path(project_root: Path) -> Path:
    """Return project policy path or packaged default fallback."""
    project_policy = project_root / ARQUX_DIR / POLICY_FILENAME
    if project_policy.exists():
        return project_policy
    return Path(__file__).resolve().parent.parent.parent / "templates" / POLICY_FILENAME


def _load_policies(project_root: Path) -> Any | None:
    """Load learn-policies.cortex from ``.arqux/``.

    Returns the parsed policy document, or ``None`` if the policy is missing
    or invalid. The caller is responsible for deciding what to do with
    ``None`` — it is NOT the same as an empty policy.
    """
    from ...cortex.reader import cortex_to_dict
    from .algorithms import parse_policy_document

    policy_path = _resolve_policy_path(project_root)
    if not policy_path.exists():
        return None
    try:
        doc = cortex_to_dict(policy_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - unreadable policy => None, not crash
        logger.warning("learn-policies: cannot parse %s", policy_path)
        return None
    return parse_policy_document(doc)


def learning_engine_available() -> tuple[bool, str | None]:
    """Report whether the native learning engine can operate.

    Returns ``(True, None)`` when the engine is wireable. ``(False, cause)``
    otherwise. The ``cause`` string is actionable — callers propagate it
    verbatim to the user instead of silently returning an empty list.
    """
    try:
        from .document import load_brain_document  # noqa: F401
        from .protocol import LearningDocument  # noqa: F401
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"import error: {exc}"


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _build_brain_doc(project_root: Path):
    """Build a native learning document from the brain.

    BLP-002: no longer returns a CortexDocument. Callers receive a
    ``NativeLearningDocument`` that satisfies ``LearningDocument``.
    """
    from .document import load_brain_document

    return load_brain_document(project_root)
