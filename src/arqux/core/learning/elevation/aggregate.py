"""Aggregation of source entries into target-shaped values (data table)."""
from __future__ import annotations

from typing import Any

from ..protocol import LearningDocument

# Governance-owned defaults by destination sigil.
TARGET_FIELD_DEFAULTS: dict[str, dict[str, Any]] = {
    "LNG": {"type": "operational", "cause": "related_occurrences", "lesson": "elevated_lesson", "prevention": "consult_this_decision"},
    "KNW": {"topic": "elevated_knowledge", "content": "", "status": "active"},
    "SES": {"input": "", "output": "", "outcome": "elevated_outcome", "date": ""},
    "CNST": {"rule": "elevated_constraint", "severity": "blocking", "survive": "min"},
    "STP": {"action": "next_action", "reason": "elevated_from_recurrent_nxt", "owner": "agent", "status": "current", "survive": "min"},
}


def _sources(document: LearningDocument, source_entries: list[str]) -> list[Any]:
    wanted = set(source_entries)
    found = []
    for _section, e in document.iter_entries():
        if f"{e.sigil}:{e.name}" in wanted:
            found.append(e)
    return found


def aggregate_value(document: LearningDocument, source_entries: list[str], target: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    # Collect EVERY distinct signal per key — first-wins merging collapses a
    # cluster of real sessions into a single generic outcome ("active"),
    # which is what produced boilerplate lessons on elevation.
    collected: dict[str, list[str]] = {}
    for e in _sources(document, source_entries):
        value = e.value if isinstance(e.value, dict) else {}
        for key in ("topic", "outcome", "lesson", "risk", "statement", "content", "cause", "prevention", "rule", "action", "reason", "owner", "input", "output"):
            v = value.get(key)
            if isinstance(v, str) and v:
                if key not in merged:
                    merged[key] = v
                bucket = collected.setdefault(key, [])
                if v not in bucket:
                    bucket.append(v)
        if value.get("user_validated") is True or str(value.get("user_validated", "")).lower() == "true":
            merged["user_validated"] = True

    # A lesson elevated from a session cluster must say something real about
    # the cluster: distinct outcomes/inputs across sources, with the count —
    # never a single placeholder outcome.
    if target == "LNG" and source_entries:
        distinct = collected.get("outcome") or collected.get("output") or collected.get("input") or []
        if distinct:
            merged["lesson"] = f"Recurring pattern across {len(source_entries)} sessions: " + "; ".join(distinct[:5])
        merged["evidence_ref"] = ", ".join(source_entries[:10]) + ("..." if len(source_entries) > 10 else "")

    defaults = dict(TARGET_FIELD_DEFAULTS.get(target, {}))
    if target == "LNG":
        merged.setdefault("type", defaults["type"])
        merged.setdefault("cause", defaults["cause"])
        merged.setdefault("lesson", merged.get("outcome", merged.get("topic", defaults["lesson"])))
        merged.setdefault("prevention", defaults["prevention"])
    elif target == "KNW":
        merged.setdefault("topic", merged.get("topic", defaults["topic"]))
        merged.setdefault("content", merged.get("lesson", merged.get("outcome", defaults["content"])))
        merged.setdefault("status", defaults["status"])
    elif target == "SES":
        merged.setdefault("input", defaults["input"])
        merged.setdefault("output", defaults["output"])
        merged.setdefault("outcome", merged.get("outcome", defaults["outcome"]))
        merged.setdefault("date", defaults["date"])
    elif target == "CNST":
        merged.setdefault("rule", merged.get("risk", merged.get("statement", defaults["rule"])))
        merged.setdefault("severity", defaults["severity"])
        merged.setdefault("survive", defaults["survive"])
    elif target == "STP":
        merged.setdefault("action", defaults["action"])
        merged.setdefault("reason", defaults["reason"])
        merged.setdefault("owner", defaults["owner"])
        merged.setdefault("status", defaults["status"])
        merged.setdefault("survive", defaults["survive"])
    return merged


__all__ = ["TARGET_FIELD_DEFAULTS", "aggregate_value"]
