"""BLP-046: migrate legacy ``tasks/*.cortex`` artifacts to CODEC-CORTEX v0.5.

Task artifacts written before v0.5 stored three critical sigils with a
different field spelling:

======================  ==========================================
legacy                   required by the v0.5 validator
======================  ==========================================
``WRK:task{id,status}``  + ``phase``, ``current``, ``blocked``, ``survive``
``OBJ:objective{text}``  ``goal``, ``success``, ``status``, ``survive``
``AUD:evidence{text}``  ``event``, ``evidence``, ``result``, ``date``
======================  ==========================================

Without this migration every task artifact in the workspace reports
E032_CRITICAL_SIGIL_INCOMPLETE even though its content is intact — the
fields simply live under different names.

The migration is deliberately lossless: nothing is deleted and no value is
invented. ``success`` is derived from the task's own acceptance criteria when
they exist; when they do not, it records that the criterion was absent rather
than fabricating one.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["migrate_legacy_task", "STRIP_FRONTMATTER"]

#: Statuses the v0.5 validator accepts on a critical sigil.
_VALID_STATUS = {
    "blocked",
    "current",
    "deprecated",
    "done",
    "experimental",
    "future",
    "planned",
    "specification",
}

#: Legacy task statuses that are not in :data:`_VALID_STATUS`.
_LEGACY_STATUS_MAP = {
    "draft": "planned",
    "in_progress": "current",
    "open": "current",
    "closed": "done",
    "complete": "done",
    "completed": "done",
    "cancelled": "deprecated",
    "wontfix": "deprecated",
}

#: Status -> WRK:phase.
_PHASE_MAP = {
    "done": "closed",
    "current": "active",
    "planned": "planning",
    "blocked": "blocked",
    "deprecated": "cancelled",
}

_FRONTMATTER_RE = re.compile(r"\A\s*---\s*\n.*?\n---\s*\n", re.DOTALL)


def STRIP_FRONTMATTER(text: str) -> str:  # noqa: N802 - handler-style name
    """Drop a leading YAML block if present.

    Two task artifacts (``CYCLE-12/tasks/T-028`` and ``T-031``) carry a YAML
    header that duplicates the CORTEX metadata and confuses the parser.
    """
    return _FRONTMATTER_RE.sub("", text, count=1)


def _map_status(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return "current"
    if value in _VALID_STATUS:
        return value
    return _LEGACY_STATUS_MAP.get(value, "current")


def _acceptance_criteria(sections: list[dict[str, Any]]) -> list[str]:
    """Collect CLAIM criteria from the whole document."""
    found: list[str] = []
    for section in sections:
        for entry in section.get("entries", []) or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("sigil")) != "CLAIM":
                continue
            attrs = entry.get("attrs") or {}
            criterion = attrs.get("criterion") or attrs.get("value")
            if criterion:
                found.append(str(criterion).strip())
    return found


def _migrate_wrk(attrs: dict[str, Any], objective: str) -> dict[str, Any]:
    status = _map_status(attrs.get("status"))
    attrs["status"] = status
    attrs.setdefault("phase", _PHASE_MAP.get(status, "active"))
    if not attrs.get("current"):
        attrs["current"] = objective or "tarea registrada en artefacto legacy"
    attrs.setdefault("blocked", "yes" if status == "blocked" else "no")
    attrs.setdefault("survive", "work")
    return attrs


def _migrate_obj(attrs: dict[str, Any], criteria: list[str], task_status: str) -> dict[str, Any]:
    goal = attrs.get("text") or attrs.get("goal") or ""
    attrs["goal"] = str(goal)
    attrs.pop("text", None)
    if not attrs.get("success"):
        if criteria:
            attrs["success"] = (
                "Criterios de aceptacion registrados: " + "; ".join(criteria)
            )
        else:
            attrs["success"] = (
                "Criterio de exito NO registrado en el artefacto legacy; "
                "revisar con el Arquitecto (migracion BLP-046)"
            )
    attrs.setdefault("status", "done" if task_status == "done" else "current")
    attrs.setdefault("survive", "work")
    return attrs


def _migrate_aud(attrs: dict[str, Any], task_id: str, fallback_date: str) -> dict[str, Any]:
    text = str(attrs.get("text") or attrs.get("evidence") or "")
    attrs["evidence"] = text
    attrs.pop("text", None)
    attrs.setdefault("event", f"legacy evidence record {task_id}")
    attrs.setdefault("result", text)
    attrs.setdefault("date", fallback_date or "2026-07-01T00:00:00Z")
    return attrs


def _walk_entries(sections: list[dict[str, Any]], fn) -> None:
    for section in sections:
        for entry in section.get("entries", []) or []:
            if isinstance(entry, dict):
                fn(entry)


def migrate_legacy_task(doc: dict[str, Any]) -> dict[str, Any]:
    """Return *doc* with legacy task sigils rewritten to the v0.5 shape.

    Operates on the ArqUX document model (as produced by ``cortex_to_dict``)
    and mutates a shallow copy, so the caller keeps ownership of the input.
    """
    sections = [dict(s) for s in doc.get("sections", []) if isinstance(s, dict)]
    criteria = _acceptance_criteria(sections)

    task_id = ""
    task_status = "current"
    fallback_date = ""
    objective = ""

    def scan(entry: dict[str, Any]) -> None:
        nonlocal task_id, task_status, fallback_date, objective
        sigil = str(entry.get("sigil"))
        attrs = entry.get("attrs")
        if not isinstance(attrs, dict):
            return
        if sigil == "WRK" and str(entry.get("name")) == "task":
            task_id = str(attrs.get("id", ""))
            task_status = _map_status(attrs.get("status"))
            fallback_date = str(attrs.get("updated") or attrs.get("created") or "")

    _walk_entries(sections, scan)

    def find_objective(entry: dict[str, Any]) -> None:
        nonlocal objective
        if str(entry.get("sigil")) == "OBJ":
            attrs = entry.get("attrs") or {}
            objective = str(attrs.get("text") or attrs.get("goal") or objective)

    _walk_entries(sections, find_objective)

    def rewrite(entry: dict[str, Any]) -> None:
        sigil = str(entry.get("sigil"))
        attrs = entry.get("attrs")
        if not isinstance(attrs, dict):
            return
        if sigil == "WRK" and str(entry.get("name")) == "task":
            entry["attrs"] = _migrate_wrk(attrs, objective)
        elif sigil == "OBJ":
            entry["attrs"] = _migrate_obj(attrs, criteria, task_status)
        elif sigil == "AUD" and str(entry.get("name")) in {"evidence", ""}:
            entry["attrs"] = _migrate_aud(attrs, task_id, fallback_date)

    for section in sections:
        section["entries"] = [
            e if not isinstance(e, dict) else dict(e)
            for e in (section.get("entries") or [])
        ]
    _walk_entries(sections, rewrite)

    new_doc = dict(doc)
    new_doc["sections"] = sections
    return new_doc
