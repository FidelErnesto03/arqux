"""Scanning and indexing logic — native implementation (BLP-003).

The API is kept compatible with what ``_scan.py`` exposed before:
``scan_brain`` / ``list_candidates`` / ``build_profile``. The internal
calls go to the native ``algorithms`` package, not to ``cortex.*``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR  # noqa: F401  (kept for API compatibility)
from ._common import (
    _build_brain_doc,
    _load_policies,
    learning_engine_available,
)
from .algorithms import (
    detect_candidates,
    rebuild_index,
)
from .protocol import LearningEntry

logger = logging.getLogger(__name__)


def _compute_priority(entry: LearningEntry) -> str:
    """Map an entry to a load priority (P0-P5).

    Deterministic rule: P0 = active decisions (FCS/OBJ with ``status=current``).
    P1 = current state (WRK). P2 = recent lessons (LNG). P3 = everything else.
    """
    if entry.sigil in {"FCS", "OBJ"} and str((entry.value or {}).get("status", "")).lower() == "current":
        return "P0"
    if entry.sigil == "WRK":
        return "P1"
    if entry.sigil == "LNG":
        return "P2"
    if entry.sigil == "KNW":
        return "P3"
    return "P4"


def scan_brain(
    project_root: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Scan the project brain through the learning engine.

    Parameters
    ----------
    project_root : Path
        Path to the project (must contain .arqux/).
    verbose : bool
        Include candidates in the output.

    Returns
    -------
    dict
        ``engine``: "available" or "unavailable" (when unavailable, ``error``
        is populated with the cause).
        ``count``: entries processed.
        ``entries``: list of {id, sigil, fingerprint, priority}.
        ``candidates``: populated only when ``verbose=True``.
    """
    ok, cause = learning_engine_available()
    if not ok:
        return {
            "engine": "unavailable",
            "cause": cause or "unknown",
            "count": 0,
            "entries": [],
            "candidates": [],
        }

    result: dict[str, Any] = {
        "engine": "available",
        "count": 0,
        "entries": [],
        "candidates": [],
    }

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {**result, "engine": "unavailable", "error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if policy_set is None:
            logger.info("scan_brain: no policy — running degraded (policy file missing or invalid)")

        index = rebuild_index(brain_doc)

        entries = []
        for eid, record in sorted(index.bins.items(), key=lambda kv: kv[0]):
            for e in record.entries:
                entries.append({
                    "id": f"{e.sigil}:{e.name}",
                    "sigil": e.sigil,
                    "name": e.name,
                    "fingerprint": eid,
                    "priority": _compute_priority(e),
                })

        result["count"] = len(entries)
        result["entries"] = entries

        if verbose:
            cands = detect_candidates(brain_doc)
            result["candidates"] = [
                c.to_dict() if hasattr(c, "to_dict") else {
                    "candidate_id": getattr(c, "candidate_id", ""),
                    "source_entries": getattr(c, "source_entries", []),
                    "target": getattr(c, "target", ""),
                    "promotion_score": getattr(c, "promotion_score", 0),
                    "hotness_score": getattr(c, "hotness_score", 0),
                    "risk_weight": getattr(c, "risk_weight", 0),
                    "read_priority": getattr(c, "read_priority", ""),
                    "suggested_action": getattr(c, "suggested_action", ""),
                }
                for c in cands
            ]

    except Exception as exc:  # noqa: BLE001
        logger.exception("scan_brain failed")
        result["engine"] = "unavailable"
        result["error"] = str(exc)

    return result


def list_candidates(
    project_root: Path,
) -> list[dict[str, Any]] | dict[str, Any]:
    """List elevation candidates for the project.

    Returns the candidate list, or a typed error dict
    ``{"error": ..., "engine": "unavailable", "cause": ...}`` when the engine
    cannot operate. Callers must branch on ``isinstance(result, dict)`` before
    iterating — the empty list alone is NOT a valid "engine unavailable"
    signal (BLP-002 AC-05: degradation must be explicit, never silent).
    """
    ok, cause = learning_engine_available()
    if not ok:
        return {"engine": "unavailable", "error": "learning engine unavailable", "cause": cause or "unknown"}

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {"engine": "unavailable", "error": "could_not_build_document", "cause": "brain unreadable"}
        cands = detect_candidates(brain_doc)
        return [
            c.to_dict() if hasattr(c, "to_dict") else {
                "candidate_id": getattr(c, "candidate_id", ""),
                "source_entries": getattr(c, "source_entries", []),
                "target": getattr(c, "target", ""),
                "promotion_score": getattr(c, "promotion_score", 0),
                "hotness_score": getattr(c, "hotness_score", 0),
                "risk_weight": getattr(c, "risk_weight", 0),
                "read_priority": getattr(c, "read_priority", ""),
                "suggested_action": getattr(c, "suggested_action", ""),
            }
            for c in cands
        ]
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_candidates failed")
        return {"engine": "unavailable", "error": str(exc), "cause": str(exc)}


def build_profile(
    project_root: Path,
) -> dict[str, Any]:
    """Produce a load priority profile (P0-P5) for the project brain."""
    scan = scan_brain(project_root, verbose=False)
    if scan.get("engine") == "unavailable":
        return {
            "engine": "unavailable",
            "error": scan.get("error", scan.get("cause", "unavailable")),
        }

    profile: dict[str, int] = {}
    for entry in scan["entries"]:
        p = entry.get("priority", "P4")
        profile[p] = profile.get(p, 0) + 1

    return {
        "engine": scan.get("engine"),
        "total": scan.get("count", 0),
        "profile": dict(sorted(profile.items())),
    }
