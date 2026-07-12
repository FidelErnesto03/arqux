"""Scanning and indexing logic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX
from ._common import (
    _HAS_CLE,
    _build_brain_doc,
    _hash_text,
    _load_policies,
    _resolve_policy_path,
    _resolve_project_root,
    detect_candidates,
    rebuild_index,
)


def scan_brain(
    project_root: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Scan the project brain through the learning engine.

    Returns a dict with:
        - entries: list of scored entries (id, sigil, hotness, promotion, risk, priority, action)
        - candidates: list of detected elevation candidates
        - count: total entries scanned
        - engine: available or unavailable
    """
    result: dict[str, Any] = {
        "engine": "unavailable",
        "count": 0,
        "entries": [],
        "candidates": [],
    }

    if not _HAS_CLE:
        return result
    result["engine"] = "available"

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return {**result, "error": "could_not_build_document"}

        policy_set = _load_policies(project_root)
        if not policy_set:
            return {**result, "error": "policies_not_found"}

        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(
            brain_doc,
            policy_set,
            brain_hash,
            policy_hash,
        )

        entries = []
        for eid, record in sorted(index.entries.items(), key=lambda x: x[1].read_priority):
            entries.append({
                "id": eid,
                "fingerprint": record.fingerprint,
                "hotness": record.hotness_score,
                "promotion": record.promotion_score,
                "risk": record.risk_weight,
                "priority": record.read_priority,
                "action": record.suggested_action,
                "signals": record.signals,
            })
        result["count"] = len(entries)
        result["entries"] = entries

        if verbose:
            candidates = detect_candidates(brain_doc, index, policy_set)
            result["candidates"] = [
                {
                    "id": c.candidate_id,
                    "source": c.source_entries,
                    "target": c.target,
                    "promotion_score": c.promotion_score,
                    "hotness_score": c.hotness_score,
                }
                for c in candidates
            ]

    except Exception as exc:
        return {**result, "error": str(exc)}

    return result


def list_candidates(
    project_root: Path,
) -> list[dict[str, Any]]:
    """List elevation candidates for the project."""
    if not _HAS_CLE:
        return []

    try:
        brain_doc = _build_brain_doc(project_root)
        if not brain_doc:
            return []

        policy_set = _load_policies(project_root)
        if not policy_set:
            return []

        brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        brain_hash = _hash_text(brain_path.read_text(encoding="utf-8"))
        policy_path = _resolve_policy_path(project_root)
        policy_hash = _hash_text(policy_path.read_text(encoding="utf-8"))

        index = rebuild_index(brain_doc, policy_set, brain_hash, policy_hash)
        candidates = detect_candidates(brain_doc, index, policy_set)

        return [
            {
                "id": c.candidate_id,
                "source": c.source_entries,
                "target": c.target,
                "promotion_score": c.promotion_score,
                "hotness_score": c.hotness_score,
            }
            for c in candidates
        ]
    except Exception:
        return []


def build_profile(
    project_root: Path,
) -> dict[str, Any]:
    """Produce a load priority profile (P0-P5) for the project brain."""
    scan = scan_brain(project_root)
    if "entries" not in scan:
        return {"error": "scan_failed", "engine": scan.get("engine", "unavailable")}

    profile: dict[str, int] = {}
    for entry in scan["entries"]:
        p = entry.get("priority", "P3")
        profile[p] = profile.get(p, 0) + 1

    return {
        "engine": scan.get("engine", "unavailable"),
        "total": scan.get("count", 0),
        "profile": dict(sorted(profile.items())),
    }
