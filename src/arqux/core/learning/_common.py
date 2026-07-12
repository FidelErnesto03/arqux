"""Shared helpers for the learning engine package."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX

logger = logging.getLogger(__name__)

_HAS_CLE: bool = False
try:
    from cortex.core.ast import CortexDocument, Entry
    from cortex.core.parser import parse_cortex
    from cortex.core.writer import write_cortex
    from cortex.learning.index import rebuild_index
    from cortex.learning.policy import parse_policy_document
    from cortex.learning.candidates import detect_candidates
    from cortex.learning.elevation import plan_patch, apply_patch, render_diff
    from cortex.learning.errors import LearningError

    _HAS_CLE = True
except ImportError:
    CortexDocument = None  # type: ignore
    Entry = None  # type: ignore
    parse_cortex = None  # type: ignore
    write_cortex = None  # type: ignore
    rebuild_index = None  # type: ignore
    parse_policy_document = None  # type: ignore
    detect_candidates = None  # type: ignore
    plan_patch = None  # type: ignore
    apply_patch = None  # type: ignore
    render_diff = None  # type: ignore
    LearningError = None  # type: ignore


POLICY_FILENAME = "learn-policies.cortex"


def _resolve_project_root(path: str | None) -> Path | None:
    """Find the project root (parent of .arqux/) from ``path`` or cwd."""
    from ...state import find_project_root
    result = find_project_root(start=path)
    if result is None:
        return None
    return result.parent


def _load_policies(project_root: Path) -> Any | None:
    """Load learn-policies.cortex from ``.arqux/``.

    Returns a ``LearningPolicySet`` or ``None`` (policy invalid). If the
    project-local policy is missing, fall back to the packaged default so
    migrated projects can still run cortex.learn before policy seeding.
    """
    if not _HAS_CLE:
        return None
    policy_path = _resolve_policy_path(project_root)
    if not policy_path.exists():
        return None
    from cortex.core.parser import parse_cortex
    doc = parse_cortex(policy_path.read_text(encoding="utf-8"))
    if not doc:
        return None
    return parse_policy_document(doc)


def _resolve_policy_path(project_root: Path) -> Path:
    """Return project policy path or packaged default fallback."""
    project_policy = project_root / ARQUX_DIR / POLICY_FILENAME
    if project_policy.exists():
        return project_policy
    return Path(__file__).resolve().parent.parent.parent / "templates" / POLICY_FILENAME


def _build_brain_doc(project_root: Path) -> CortexDocument | None:
    """Build a CortexDocument from the project's brain.cortex sections.

    Uses the existing ``formats._build_brain_doc()`` to convert sections
    dict → CortexDocument so the learning engine can process it.
    """
    from ...state import read_brain
    from ...formats import _build_brain_doc as _build_doc
    from cortex.core.ast import CortexDocument as CDoc

    fm, sections, _ = read_brain(project_root)
    doc = CDoc()
    _build_doc(doc, fm, sections)
    return doc


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
