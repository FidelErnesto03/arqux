"""Sigil definitions for CORTEX artifacts.

This module provides a local cache of sigil definitions used by the
``cortex.ref`` and ``cortex.format`` handlers (BLP-003).

Sigils are short uppercase tokens (3-5 chars) used as entry-type
identifiers in ``.cortex`` files. Each sigil has a canonical name, type,
risk level, cognitive layer, and a human-readable description.

The cache is populated from the standard ARQUX sigils declared in the
identity files and templates shipped with the package. Runtime sigils
discovered from the CODEC-CORTEX library are merged on top.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Sigil cache
# ---------------------------------------------------------------------------
#
# Each entry maps SIGIL_ID -> {name, type, risk, layer, description, fields?}
# Risk levels: B (bajo/low), M (medio/medium), H (alto/high)
# Cognitive layers: Semantic, Prefrontal, Working, Episodic

SIGIL_CACHE: dict[str, dict[str, Any]] = {
    # --- Metadata / artifact sigils ---
    "ARQX": {
        "name": "artifact",
        "type": "attrs",
        "risk": "B",
        "layer": "Semantic",
        "description": "ArqUX artifact metadata (level, name, usage, kind)",
    },
    # --- Identity sigils (Level 1) ---
    "IDN": {
        "name": "identity",
        "type": "attrs",
        "risk": "B",
        "layer": "Semantic",
        "description": "Agent identity descriptor",
    },
    "AXM": {
        "name": "axiom",
        "type": "attrs",
        "risk": "H",
        "layer": "Prefrontal",
        "description": "Non-negotiable principles (body field holds the axiom text)",
        "fields": "name,body,status",
    },
    "LIM": {
        "name": "limit",
        "type": "attrs",
        "risk": "M",
        "layer": "Prefrontal",
        "description": "Hard limits and boundaries",
        "fields": "name,limit,scope,severity,status",
    },
    "DESC": {
        "name": "description",
        "type": "attrs",
        "risk": "B",
        "layer": "Semantic",
        "description": "Agent description and style",
        "fields": "name,body,status",
    },
    "DOM": {
        "name": "domain",
        "type": "attrs",
        "risk": "B",
        "layer": "Semantic",
        "description": "Workspace domain metadata",
    },
    # --- Brain live-state sigils (Level 3) ---
    "FCS": {
        "name": "focus",
        "type": "attrs",
        "risk": "H",
        "layer": "Working",
        "description": "Active attention anchor — what the project is focused on now",
    },
    "OBJ": {
        "name": "objective",
        "type": "attrs",
        "risk": "H",
        "layer": "Working",
        "description": "Active goal — stable project-level objective",
    },
    "WRK": {
        "name": "work",
        "type": "attrs",
        "risk": "M",
        "layer": "Working",
        "description": "Work-in-progress entry — task or activity being executed",
    },
    "LNG": {
        "name": "lesson",
        "type": "attrs",
        "risk": "M",
        "layer": "Episodic",
        "description": "Learned lesson — behavioral or process",
    },
    "KNW": {
        "name": "knowledge",
        "type": "attrs",
        "risk": "B",
        "layer": "Semantic",
        "description": "Workspace-level knowledge entry",
        "fields": "name,topic,content,status",
    },
    "RSK": {
        "name": "risk",
        "type": "attrs",
        "risk": "M",
        "layer": "Prefrontal",
        "description": "Risk entry — description, impact, mitigation",
    },
    "NXT": {
        "name": "next",
        "type": "attrs",
        "risk": "L",
        "layer": "Working",
        "description": "Next action to take",
    },
    "SES": {
        "name": "session",
        "type": "attrs",
        "risk": "L",
        "layer": "Episodic",
        "description": "Session record — agent session context",
    },
    "HOF": {
        "name": "handoff",
        "type": "attrs",
        "risk": "L",
        "layer": "Episodic",
        "description": "Handoff between agents",
    },
    "AUD": {
        "name": "audit",
        "type": "attrs",
        "risk": "M",
        "layer": "Episodic",
        "description": "Audit event — append-only PULSE entry",
    },
    "ERR": {
        "name": "error",
        "type": "attrs",
        "risk": "H",
        "layer": "Prefrontal",
        "description": "Concurrency / error state entry",
    },
    "CLAIM": {
        "name": "claim",
        "type": "attrs",
        "risk": "H",
        "layer": "Working",
        "description": "Agent claim over a task or resource",
    },
    # --- Skill sigils (Level 2) ---
    "GTE": {
        "name": "gate",
        "type": "attrs",
        "risk": "H",
        "layer": "Prefrontal",
        "description": "Mutation gate — quality gate that must be passed",
    },
    "POL": {
        "name": "policy",
        "type": "attrs",
        "risk": "M",
        "layer": "Working",
        "description": "Learning policy",
    },
    "PRT": {
        "name": "protected",
        "type": "attrs",
        "risk": "H",
        "layer": "Prefrontal",
        "description": "Protected targets — sigils requiring explicit confirmation",
    },
    "THR": {
        "name": "threshold",
        "type": "attrs",
        "risk": "M",
        "layer": "Working",
        "description": "Learning thresholds",
    },
    # --- Glossary declaration sigil ---
    "GSIG": {
        "name": "glossary_sigil",
        "type": "attrs",
        "risk": "B",
        "layer": "Semantic",
        "description": "Canonical sigil declaration (codec-cortex 0.5.0+)",
    },
    # --- ADA (skill adaptation) ---
    "ADA": {
        "name": "adaptation",
        "type": "attrs",
        "risk": "M",
        "layer": "Episodic",
        "description": "Skill adaptation entry — deviation from canon",
    },
}


def get_sigil(sigil_id: str) -> dict[str, Any] | None:
    """Return the sigil definition or ``None`` if not found.

    Sigil IDs are matched case-insensitively but stored uppercase.
    """
    if not sigil_id:
        return None
    key = sigil_id.strip().upper()
    return SIGIL_CACHE.get(key)


def list_sigils() -> list[str]:
    """Return a sorted list of all known sigil IDs."""
    return sorted(SIGIL_CACHE.keys())


def register_sigil(sigil_id: str, definition: dict[str, Any]) -> None:
    """Register or update a sigil definition at runtime.

    This is intended for tests and for merging sigils discovered from
    CODEC-CORTEX at import time. Existing definitions are overwritten.
    """
    if not sigil_id:
        return
    key = sigil_id.strip().upper()
    SIGIL_CACHE[key] = dict(definition)


# Try to merge sigils from the CODEC-CORTEX library if available.
try:  # pragma: no cover — depends on optional dependency layout
    from cortex.core.glossary import SIGIL_REGISTRY as _cc_sigils  # type: ignore

    for _sid, _sdef in getattr(_cc_sigils, "items", lambda: [])():
        if isinstance(_sdef, dict):
            register_sigil(_sid, _sdef)
except Exception:  # noqa: BLE001 — codec-cortex layout varies across versions
    pass
