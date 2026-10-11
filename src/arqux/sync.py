"""sync_brain — update brain.cortex after handler mutations.

v0.4.3 (patched): cleaned up stale PATCH: docstring (P1-K).

This module is fail-silent: any error is logged and swallowed.
It never interrupts the calling handler.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def sync_brain(
    project_root: Path,
    event: str,
    *,
    focus: str | None = None,
    focus_create_only: bool = False,
    metrics: dict[str, Any] | None = None,
    detail: str = "",
) -> None:
    """Update brain.cortex after a successful handler mutation.

    This function is **fail-silent**: any error is logged and swallowed.
    It never interrupts the calling handler.

    Parameters
    ----------
    project_root:
        Path to project root. Can be either:
        - The actual project root (has ``.arqux/`` subdirectory)
        - The ``.arqux/`` directory itself (as returned by
          ``state.find_project_root()``)
        The function auto-detects which case it is.
    event:
        Canonical event name, e.g. `blueprint.complete`.
    focus:
        If provided, updates ``FCS:current`` in brain.cortex.
    focus_create_only:
        When True, an existing ``FCS:current`` keeps its ``what`` — only
        ``updated``/``event`` are refreshed. The generic *focus* text is
        written only when no FCS entry exists yet.
    metrics:
        Optional dict of counters to merge into brain.cortex.
    detail:
        Optional human-readable detail about the event.
    """
    if project_root is None:
        logger.warning("sync_brain: project_root is None, skipping")
        return

    try:
        from arqux.state import _resolve_brain_path
        brain_path = _resolve_brain_path(project_root)
    except ImportError:
        from arqux.constants import ARQUX_DIR, BRAIN_CORTEX
        if project_root.name == ARQUX_DIR:
            brain_path = project_root / BRAIN_CORTEX
        elif (project_root / ARQUX_DIR / BRAIN_CORTEX).exists():
            brain_path = project_root / ARQUX_DIR / BRAIN_CORTEX
        else:
            brain_path = project_root / BRAIN_CORTEX

    if not brain_path.exists():
        logger.debug(
            "sync_brain: brain.cortex not found at %s, skipping (this is normal for new workspaces)",
            brain_path,
        )
        return

    try:
        from arqux.cortex.atomic import atomic_write_json
        from arqux.cortex.crud import add_entry, select_entries, update_entry
        from arqux.cortex.reader import cortex_to_dict
    except ImportError:
        logger.warning("sync_brain: cortex components not available, skipping")
        return

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    current_text = f"{event}: {detail}" if detail else event

    try:
        doc = cortex_to_dict(brain_path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("sync_brain: failed to read brain (continuing)")
        return

    changed = False

    try:
        update_entry(
            doc,
            "$8/WRK:current",
            set_={
                "phase": "current",
                "current": current_text,
                "blocked": "no",
                "updated": ts,
                "event": event,
            },
        )
        changed = True
    except Exception:
        logger.exception("sync_brain: failed to update WRK:current @ $8 (continuing)")

    if focus:
        try:
            if select_entries(doc, "$2/FCS:current"):
                set_ = {"updated": ts, "event": event}
                if not focus_create_only:
                    set_.update({
                        "what": focus,
                        "priority": "medium",
                        "status": "current",
                    })
                update_entry(doc, "$2/FCS:current", set_=set_)
                changed = True
            elif focus_create_only:
                add_entry(
                    doc,
                    "$2",
                    "FCS",
                    "current",
                    {
                        "name": "current",
                        "what": focus,
                        "priority": "medium",
                        "status": "current",
                        "survive": "work",
                        "updated": ts,
                        "event": event,
                    },
                    create_section=True,
                )
                changed = True
            else:
                logger.debug("sync_brain: no FCS:current @ $2 to update (continuing)")
        except Exception:
            logger.exception("sync_brain: failed to update FCS:current @ $2 (continuing)")

    requested_metrics = dict(metrics or {})
    if metrics and _upsert_metrics(doc, metrics, ts):
        changed = True

    if changed:
        try:
            atomic_write_json(doc, str(brain_path))
        except Exception:
            logger.exception("sync_brain: failed to write brain (continuing)")

    if metrics:
        # The project brain receives filesystem-truth counters, while the
        # meta-brain event retains explicit counters supplied by the mutation.
        # This keeps sync.run observability intact without making a caller's
        # event appear to have been ignored.
        _sync_meta_brain(project_root, requested_metrics, event, ts)


def _upsert_metrics(doc: dict[str, Any], metrics: dict[str, Any], ts: str) -> bool:
    """Upsert KNW:<metric> entries in $6 by name (doc-level batch helper).

    Existing entries are updated in place (value/updated/content); new
    metrics are appended. Metrics are skipped when $6 is absent.
    """
    from arqux.cortex.crud import add_entry, select_entries, update_entry

    changed = False
    for key, value in metrics.items():
        knw_status = "done" if key == "tasks_done" else "current"
        attrs = {
            "name": key,
            "value": str(value),
            "updated": ts,
            "topic": "metrics",
            "content": f"metric {key}={value}",
            "status": knw_status,
        }
        try:
            if select_entries(doc, f"$6/KNW:{key}"):
                update_entry(doc, f"$6/KNW:{key}", set_=attrs)
            else:
                add_entry(doc, "$6", "KNW", key, attrs, create_section=False)
        except Exception:
            logger.debug("sync_brain: failed to upsert metric %s=%s (continuing)", key, value)
            continue
        changed = True
    return changed


def _count_blueprints(root: Path) -> dict[str, int]:
    """Count blueprints by status from the filesystem."""
    counts: dict[str, int] = {
        "done": 0, "draft": 0, "cancelled": 0,
        "review": 0, "in_progress": 0, "ready": 0,
        "blocked": 0,
    }

    cycles_dir = root / ".arqux" / "cycles"
    if not cycles_dir.is_dir():
        cycles_dir = root / "cycles"
    if not cycles_dir.is_dir():
        return counts

    for bp_file in sorted(cycles_dir.rglob("BLP-*.md")):
        try:
            text = bp_file.read_text(encoding="utf-8")
            m = re.search(r'^status:\s*"([^"]+)"', text, re.MULTILINE)
            if m and m.group(1) in counts:
                counts[m.group(1)] += 1
        except Exception:
            continue
    return counts


_TASK_STATUS_RE = re.compile(r'WRK:task\{[^}]*?status:"([^"]+)"')


def _read_task_status(tfile: Path) -> str:
    """Status from a task ``.cortex`` (CORTEX ``WRK:task{...status:\\"...\\"}``).

    ``parse_cortex_file`` expects YAML frontmatter, which task files do not
    carry, so it returns ``{}`` — hence the direct regex.
    """
    try:
        m = _TASK_STATUS_RE.search(tfile.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except Exception:
        return ""


def recompute_brain_metrics(project_root: Path) -> dict[str, int]:
    """True count metrics recomputed from the filesystem.

    Fixes the frozen-KNW defect: handlers used to pass fixed constants
    (``tasks_done=1``), so KNW metric entries could never express totals.
    Recomputing absolute counts here lets every ``sync_brain`` /
    ``reconcile_brain`` write correct, idempotent values.
    """
    root = (project_root.parent if project_root.name == ".arqux"
            else project_root)
    bp = _count_blueprints(root)

    closed = opened = 0
    cycles_dir = root / ".arqux" / "cycles"
    if cycles_dir.is_dir():
        for cdir in sorted(cycles_dir.iterdir()):
            if not cdir.is_dir():
                continue
            status = ""
            manifest = cdir / "MANIFEST.md"
            if manifest.exists():
                m = re.search(r'^status:\s*"([^"]+)"',
                              manifest.read_text(encoding="utf-8"),
                              re.MULTILINE)
                status = m.group(1) if m else ""
            if status == "closed":
                closed += 1
            else:
                opened += 1

    tasks_done = tasks_active = 0
    if cycles_dir.is_dir():
        for tfile in cycles_dir.rglob("tasks/*.cortex"):
            st = _read_task_status(tfile).strip()
            if st in ("done", "completed"):
                tasks_done += 1
            elif st in ("in_progress", "in-progress", "active"):
                tasks_active += 1

    return {
        "blueprints_done": bp.get("done", 0),
        "blueprints_draft": bp.get("draft", 0),
        "blueprints_cancelled": bp.get("cancelled", 0),
        "cycles_closed": closed,
        "cycles_open": opened,
        "tasks_done": tasks_done,
        "tasks_active": tasks_active,
    }


def _merge_real_metrics(project_root: Path,
                        metrics: dict[str, Any]) -> dict[str, Any]:
    """Override count-metric keys with filesystem-recomputed totals."""
    try:
        real = recompute_brain_metrics(project_root)
    except Exception:
        logger.debug("sync_brain: metric recompute failed (continuing)")
        return metrics
    return {**metrics, **real}


def _count_tests(root: Path) -> int:
    """Count test files (*.py) in the tests/ directory of the project."""
    project_root = root.parent if root.name == ".arqux" else root
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return 0
    try:
        return len(list(tests_dir.glob("*.py")))
    except Exception:
        return 0


def _normalize_dom_name(name: str) -> str:
    """Normalize a project display name into a CORTEX DOM entry name.

    Convention (workspace projects.cortex / meta-brain §2): lowercase,
    ``[^a-z0-9_]`` → ``_``.  ``ARQUX`` → ``arqux``, ``Banco Familiar`` →
    ``banco_familiar``.
    """
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower())


def _project_name(project_root: Path) -> str:
    """Resolve the DOM entry name for *project_root*.

    Prefers the brain's declared identity (``$1/IDN:project{name}``);
    falls back to the directory name (parent when *project_root* is the
    ``.arqux`` directory itself).
    """
    try:
        from arqux.state import crud_read

        if project_root.name == ".arqux":
            brain_path = project_root / "brain.cortex"
            fallback = project_root.parent.name
        else:
            brain_path = project_root / ".arqux" / "brain.cortex"
            fallback = project_root.name
        if brain_path.exists():
            read = crud_read(brain_path, "$1/IDN:project")
            for entry in read.get("entries", []):
                value = entry.get("value") or {}
                declared = value.get("name") or value.get("product")
                if declared:
                    return _normalize_dom_name(str(declared))
        return _normalize_dom_name(fallback)
    except Exception:
        fallback = project_root.parent.name if project_root.name == ".arqux" else project_root.name
        return _normalize_dom_name(fallback)


def _upsert_meta_dom(meta_brain_path: Path, dom_name: str, project_root: Path) -> None:
    """Ensure ``$2/DOM:<dom_name>`` exists in the meta-brain (create if absent)."""
    from arqux.state import crud_add, crud_read

    try:
        existing = crud_read(meta_brain_path, f"$2/DOM:{dom_name}")
    except Exception:
        existing = {"entries": []}
    if existing.get("entries"):
        return
    proj_dir = project_root.parent if project_root.name == ".arqux" else project_root
    crud_add(
        meta_brain_path, "$2", "DOM", dom_name,
        {"name": proj_dir.name, "path": str(proj_dir), "status": "current"},
        create_section=False,
        force=True,
    )


def _dom_identity(entry: dict[str, Any]) -> tuple[str, str]:
    """Return the stable identity used to merge duplicate DOM records."""
    attrs = entry.get("attrs") or {}
    display_name = str(attrs.get("name") or entry.get("name") or "")
    return ("name", _normalize_dom_name(display_name))


def _dom_score(entry: dict[str, Any], canonical_name: str) -> tuple[int, int, int, str]:
    """Prefer canonical names, populated paths, and the newest record."""
    attrs = entry.get("attrs") or {}
    entry_name = _normalize_dom_name(str(entry.get("name") or ""))
    exact_name = int(entry_name == canonical_name)
    has_path = int(bool(str(attrs.get("path") or "").strip()))
    completeness = sum(1 for value in attrs.values() if value not in (None, ""))
    updated = str(attrs.get("updated") or "")
    return (exact_name, has_path, completeness, updated)


def _dedupe_meta_dom(meta_brain_path: Path) -> dict[str, Any]:
    """Merge semantically duplicate ``DOM`` entries in a workspace brain.

    Older sync implementations avoided exact CORTEX key collisions by adding
    suffixes to entry names (for example ``manhattan_0001_0005``).  That made
    syntactically unique entries which still described the same project.  The
    repair groups records by their declared project name, retains the newest
    canonical entry, and fills missing non-conflicting attributes from the
    historical records.  It is idempotent and writes only when a merge is
    required.
    """
    result: dict[str, Any] = {
        "duplicate_groups": 0,
        "removed": 0,
        "canonical": [],
        "changed": False,
    }
    if not meta_brain_path.exists():
        return result

    try:
        from arqux.cortex.atomic import atomic_write_json
        from arqux.cortex.reader import cortex_to_dict

        doc = cortex_to_dict(meta_brain_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["error"] = repr(exc)
        return result

    for section in doc.get("sections", []):
        if not isinstance(section, dict) or section.get("id") != "$2":
            continue
        entries = section.get("entries", [])
        if not isinstance(entries, list):
            continue

        groups: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or entry.get("sigil") != "DOM":
                continue
            identity = _dom_identity(entry)
            if identity[1]:
                groups.setdefault(identity, []).append((index, entry))

        replacements: dict[int, dict[str, Any]] = {}
        removals: set[int] = set()
        for (_, canonical_name), members in groups.items():
            if len(members) < 2:
                continue
            result["duplicate_groups"] += 1
            ranked = sorted(
                members,
                key=lambda item: _dom_score(item[1], canonical_name),
                reverse=True,
            )
            keep_index, keep_entry = ranked[0]
            merged = dict(keep_entry)
            merged_attrs = dict(keep_entry.get("attrs") or {})
            # Older entries may carry domain/cycle/governor while the newer
            # metrics row carries the current counters.  Merge only missing
            # values so current metrics and timestamps remain authoritative.
            for _, candidate in ranked[1:]:
                for key, value in (candidate.get("attrs") or {}).items():
                    if key not in merged_attrs or merged_attrs[key] in (None, ""):
                        merged_attrs[key] = value
            merged["name"] = canonical_name
            merged["attrs"] = merged_attrs
            replacements[keep_index] = merged
            for index, _ in members:
                if index != keep_index:
                    removals.add(index)
            result["removed"] += len(members) - 1
            result["canonical"].append(canonical_name)

        if removals:
            rebuilt: list[dict[str, Any]] = []
            for index, entry in enumerate(entries):
                if index in removals:
                    continue
                rebuilt.append(replacements.get(index, entry))
            section["entries"] = rebuilt
            result["changed"] = True

    if result["changed"]:
        try:
            atomic_write_json(doc, str(meta_brain_path))
        except Exception as exc:
            result["error"] = repr(exc)
            result["changed"] = False
    return result


def _sync_meta_brain(
    project_root: Path,
    metrics: dict[str, Any],
    event: str,
    ts: str,
) -> None:
    """Sync metrics to the meta-brain ``DOM:<project>`` entry."""
    try:
        from arqux.state import crud_update, find_workspace_root

        search_start = project_root.parent if project_root.name == ".arqux" else project_root

        ws_root = find_workspace_root(start=search_start)
        if ws_root is None:
            logger.debug("sync_brain: workspace root not found, skipping meta-brain sync")
            return

        meta_brain_path = ws_root / "meta-brain.cortex"
        if not meta_brain_path.exists():
            logger.debug("sync_brain: meta-brain.cortex not found at %s", meta_brain_path)
            return

        dom_name = _project_name(project_root)

        _dedupe_meta_dom(meta_brain_path)

        dom_updates: dict[str, Any] = {"updated": ts, "last_event": event}

        try:
            bp_counts = _count_blueprints(project_root)
            dom_updates["blueprints_done"] = str(bp_counts.get("done", 0))
            dom_updates["blueprints_draft"] = str(bp_counts.get("draft", 0))
            dom_updates["blueprints_cancelled"] = str(bp_counts.get("cancelled", 0))
            dom_updates["blueprints_completed"] = str(bp_counts.get("review", 0))
        except Exception:
            logger.debug("sync_brain: failed to count blueprints, using metric values (continuing)")
            for key in ("blueprints_done", "blueprints_draft",
                        "blueprints_cancelled", "blueprints_completed"):
                if key in metrics:
                    dom_updates[key] = str(metrics[key])

        try:
            test_count = _count_tests(project_root)
            dom_updates["tests"] = str(test_count)
        except Exception:
            logger.debug("sync_brain: failed to count tests, using metric values (continuing)")

        for key, value in metrics.items():
            if key in ("handlers", "tasks_done", "tasks_active", "cycles_closed"):
                dom_updates[key] = str(value)

        try:
            _upsert_meta_dom(meta_brain_path, dom_name, project_root)
        except Exception:
            logger.debug("sync_brain: could not create DOM:%s (continuing)", dom_name)

        crud_update(
            str(meta_brain_path),
            f"$2/DOM:{dom_name}",
            set_=dom_updates,
            force=True,
        )
    except Exception:
        logger.exception("sync_brain: failed to sync meta-brain @ DOM:<project> (continuing)")


def reconcile_brain(project_root: Path) -> dict[str, Any]:
    """Reconcile brain.cortex persistent state with filesystem reality.

    Scans all cycles and blueprints, counts by status, and updates:
    - For project root: brain.cortex §3 (OBJ): an existing entry keeps its
      operator-authored goal/status/survive — only success/updated/event
      are refreshed; a generic goal is created only when no OBJ exists
    - For workspace root: meta-brain.cortex $3 (FCS): an existing
      FCS:current keeps its what/priority/status — only updated/event
      are refreshed; a generic FCS is created only when absent
    - For both: meta-brain.cortex $2/DOM:<project>: counts if meta-brain exists

    Returns dict with reconciliation report.
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result: dict[str, Any] = {
        "reconciled": False,
        "discrepancies": [],
        "metrics": {},
        "errors": [],
    }

    # 1. Scan filesystem
    try:
        bp_counts = _count_blueprints(project_root)
        test_count = _count_tests(project_root)

        total_blps = sum(bp_counts.values())
        open_cycles = []
        closed_cycles = []

        cycles_dir = project_root / ".arqux" / "cycles"
        if cycles_dir.is_dir():
            for cdir in sorted(cycles_dir.iterdir()):
                if cdir.is_dir():
                    manifest = cdir / "MANIFEST.md"
                    if manifest.exists():
                        text = manifest.read_text(encoding="utf-8")
                        m = re.search(r'^status:\s*"([^"]+)"', text, re.MULTILINE)
                        if m:
                            status = m.group(1)
                            if status == "closed":
                                closed_cycles.append(cdir.name)
                            else:
                                open_cycles.append(cdir.name)
                        else:
                            open_cycles.append(cdir.name)
                    else:
                        open_cycles.append(cdir.name)
                elif cdir.name != "MANIFEST.md":
                    open_cycles.append(cdir.name)

        result["metrics"] = {
            "total_blueprints": total_blps,
            "blueprints_by_status": bp_counts,
            "open_cycles": len(open_cycles),
            "closed_cycles": len(closed_cycles),
            "tests": test_count,
        }

        # 2. Determine context: workspace root vs project root
        from arqux.state import crud_add, crud_read, crud_update, find_workspace_root

        ws_root = find_workspace_root(start=project_root)
        if ws_root is None:
            result["errors"].append("workspace root not found")
            return result

        # workspace root is .arqux/ directory; project_root is its parent
        # When project_root == ws_root.parent, we're at workspace context
        is_workspace_root = (ws_root.parent == project_root)

        # 3. Update brain or meta-brain based on context
        if is_workspace_root:
            # Workspace context: refresh meta-brain $3 (FCS) timestamp.
            # focus_create_only semantics (T-010): an existing FCS:current
            # keeps its what/priority/status; the generic reconciliation
            # text is written only when no FCS entry exists.
            meta_brain = ws_root / "meta-brain.cortex"
            if meta_brain.exists():
                result["meta_deduplication"] = _dedupe_meta_dom(meta_brain)
                fcs_text = (
                    f"Reconciliacion completada. {total_blps} BLPs gestionados "
                    f"en {len(open_cycles) + len(closed_cycles)} ciclos "
                    f"({', '.join(sorted(open_cycles + closed_cycles))})."
                )
                existing_fcs = crud_read(str(meta_brain), "$3/FCS:current").get("entries", [])
                if existing_fcs:
                    crud_update(
                        str(meta_brain),
                        "$3/FCS:current",
                        set_={"updated": ts, "event": "brain.reconcile"},
                        force=True,
                    )
                else:
                    crud_add(
                        str(meta_brain),
                        "$3",
                        "FCS",
                        "current",
                        {
                            "name": "current",
                            "what": fcs_text,
                            "priority": "low",
                            "status": "current",
                            "survive": "work",
                            "updated": ts,
                            "event": "brain.reconcile",
                        },
                        create_section=True,
                        force=True,
                    )
                result["reconciled"] = True
        else:
            # Project context: refresh brain.cortex §3 (OBJ), preserving
            # the operator-authored goal.
            # Tolerant: resolves the first OBJ:* entry — a missing OBJ is
            # recorded in errors[] instead of aborting (BLP-008 / BUG-003).
            # create_only semantics (T-015): an existing OBJ keeps its
            # operator-authored goal — only success/updated/event are
            # refreshed. The generic goal is written only when no OBJ
            # entry exists.
            brain_path = project_root / ".arqux" / "brain.cortex"
            if brain_path.exists():
                goal = (
                    f"Mantener sincronia entre brain.cortex y estado real del proyecto. "
                    f"{total_blps} BLPs gestionados en {len(open_cycles) + len(closed_cycles)} ciclos "
                    f"({', '.join(sorted(open_cycles + closed_cycles))})."
                )

                try:
                    objs = crud_read(str(brain_path), "$3/OBJ:*").get("entries", [])
                except Exception:
                    objs = []
                if objs:
                    crud_update(
                        str(brain_path),
                        f"$3/OBJ:{objs[0].get('name')}",
                        set_={
                            "success": "synced",
                            "updated": ts,
                            "event": "brain.reconcile",
                        },
                        force=True,
                    )
                else:
                    result["errors"].append("brain has no OBJ entry in §3")
                    crud_add(
                        str(brain_path),
                        "$3",
                        "OBJ",
                        "sync",
                        {
                            "name": "sync",
                            "goal": goal,
                            "status": "current",
                            "success": "synced",
                            "survive": "work",
                            "updated": ts,
                            "event": "brain.reconcile",
                        },
                        create_section=True,
                        force=True,
                    )
                result["reconciled"] = True

                # Upsert real count metrics into $6/KNW (issue: KNW metrics
                # were frozen because reconcile never wrote them).
                try:
                    from arqux.cortex.atomic import atomic_write_json as _awj
                    from arqux.cortex.reader import cortex_to_dict as _c2d
                    _doc = _c2d(brain_path.read_text(encoding="utf-8"))
                    if _upsert_metrics(_doc,
                                       recompute_brain_metrics(project_root),
                                       ts):
                        _awj(_doc, str(brain_path))
                except Exception as _exc:
                    result["errors"].append(f"metrics upsert failed: {_exc!r}")

        # 4. Sync to meta-brain DOM:<project> (always)
        try:
            if ws_root is not None:
                meta_brain = ws_root / "meta-brain.cortex"
                if meta_brain.exists():
                    if "meta_deduplication" not in result:
                        result["meta_deduplication"] = _dedupe_meta_dom(meta_brain)
                    dom_updates = {
                        "updated": ts,
                        "last_event": "brain.reconcile",
                        "blueprints_done": str(bp_counts.get("done", 0)),
                        "blueprints_draft": str(bp_counts.get("draft", 0)),
                        "blueprints_cancelled": str(bp_counts.get("cancelled", 0)),
                        "blueprints_completed": str(bp_counts.get("review", 0)),
                        "tests": str(test_count),
                        "open_cycles": str(len(open_cycles)),
                        "closed_cycles": str(len(closed_cycles)),
                        "total_blueprints": str(total_blps),
                    }

                    if is_workspace_root:
                        dom_name = _meta_self_dom(meta_brain) or _project_name(project_root)
                    else:
                        dom_name = _project_name(project_root)
                    try:
                        _upsert_meta_dom(meta_brain, dom_name, project_root)
                    except Exception:
                        logger.debug("reconcile: could not create DOM:%s (continuing)", dom_name)

                    crud_update(
                        str(meta_brain),
                        f"$2/DOM:{dom_name}",
                        set_=dom_updates,
                        force=True,
                    )
                    result["meta_synced"] = True
        except Exception as e:
            result["errors"].append(f"Failed to sync meta-brain: {e}")

    except Exception as e:
        result["errors"].append(f"Reconciliation failed: {e}")

    return result


def _meta_self_dom(meta_brain: Path) -> str | None:
    """Return the name of the workspace's self-DOM entry (``path:"."`` or
    ``domain:"workspace"``) in the meta-brain, or None if absent."""
    try:
        from arqux.state import crud_read

        doms = crud_read(meta_brain, "$2/DOM:*").get("entries", [])
        for entry in doms:
            value = entry.get("value") or {}
            if value.get("path") == "." or value.get("domain") == "workspace":
                return entry.get("name")
    except Exception:
        pass
    return None


def _fm_val(fm_text: str, key: str) -> str:
    """Extract a frontmatter scalar by key (quote-tolerant — BLP-003 F-5)."""
    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", fm_text, re.MULTILINE)
    if not m:
        return ""
    val = m.group(1).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1]
    return val


def _body_title(body: str | None) -> str:
    """Extract a Blueprint title from the body (BLP:TITLE marker or heading).

    Mirrors ``blueprint._read._body_title`` (kept local to avoid a circular
    import between ``sync`` and the blueprint package — BLP-003 F-2).
    """
    text = body or ""
    marker = re.search(
        r"<!--\s*BLP:TITLE\s*-->(.*?)<!--\s*/BLP:TITLE\s*-->",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if marker:
        for line in marker.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^#?\s*BLP-\d+:\s*(.*)$", line)
            if m and m.group(1).strip():
                return m.group(1).strip()
            return line.lstrip("#").strip()
    heading = re.search(r"^#\s+BLP-\d+:\s*(.+?)\s*$", text, re.MULTILINE)
    if heading and heading.group(1).strip():
        return heading.group(1).strip()
    return ""


# Cycle MANIFEST quality-gate keys (mirror CYCLE_MANIFEST_TEMPLATE.md).
MANIFEST_GATE_KEYS = [
    "has_clear_purpose",
    "has_explicit_scope",
    "has_measurable_objectives",
    "has_operational_guidelines",
    "has_control_points",
    "aligns_with_project",
]


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split a markdown file into (frontmatter_text, body) (BLP-003)."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parts[1].strip("\n"), parts[2]


def _set_fm_scalar(fm_text: str, key: str, value: str) -> str:
    """Set/replace a scalar frontmatter field as a quoted value (BLP-003)."""
    pattern = rf"(?m)^{re.escape(key)}:\s*.*$"
    repl = f'{key}: "{value}"'
    if re.search(pattern, fm_text):
        # lambda replacement keeps backslashes in *value* literal (H-F8).
        return re.sub(pattern, lambda _m: repl, fm_text, count=1)
    return fm_text.rstrip("\n") + f"\n{repl}\n"


def _read_gate_table(text: str, keys: list[str]) -> dict[str, bool]:
    """Read boolean quality gates from a markdown table by key (BLP-003)."""
    gates: dict[str, bool] = {}
    for key in keys:
        m = re.search(rf"\|\s*{re.escape(key)}\s*\|\s*([^|]*)\|", text or "")
        gates[key] = bool(m and "\u2705" in m.group(1))
    return gates


def _write_gate_block(
    fm_text: str, gates: dict[str, bool], key: str = "quality_gates@"
) -> str:
    """Replace/insert the ``quality_gates@`` block, cleaning legacy forms.

    Handles both the canonical multi-line block (``key: { ... }``) and the
    legacy flattened form written by older writers (``key: "{"`` followed by
    orphan ``has_*: "false,"`` lines), without leaving duplicate keys (BLP-003).
    """
    gate_names = set(gates)
    new_block = [f"{key}: {{"]
    for gate_key, gate_val in gates.items():
        new_block.append(f"  {gate_key}: {'true' if gate_val else 'false'},")
    new_block.append("}")

    lines = fm_text.split("\n")
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.strip().startswith(f"{key}:"):
            opens_block = line.rstrip().endswith("{")
            i += 1
            # Consume only the declared block: indented lines + closing brace
            # when it opens a block, or orphan flat gate lines in the legacy
            # (quoted `"{"`) form. Never eat unrelated indented keys (F-3).
            while i < len(lines):
                stripped = lines[i].strip()
                if not stripped:
                    if opens_block:
                        i += 1
                        continue
                    break
                head = stripped.split(":", 1)[0].strip() if ":" in stripped else ""
                if opens_block:
                    if stripped == "}" or lines[i][:1] in (" ", "\t"):
                        i += 1
                        if stripped == "}":
                            break
                        continue
                    break
                if head in gate_names:
                    i += 1
                    continue
                if stripped == "}":
                    i += 1
                    break
                break
            out.extend(new_block)
            replaced = True
            continue
        out.append(line)
        i += 1

    if not replaced:
        out.extend(new_block)
    return "\n".join(out)


def _resolve_governor(project_root: Path) -> str:
    """Resolve the project governor from brain.cortex ``$1/IDN`` (best-effort)."""
    try:
        from arqux.state import crud_read

        brain_path = project_root / ".arqux" / "brain.cortex"
        if brain_path.exists():
            read = crud_read(brain_path, "$1/IDN:governor")
            for entry in read.get("entries", []):
                gov = (entry.get("value") or {}).get("governor")
                if gov:
                    return str(gov)
    except Exception:
        pass
    return ""


def _read_blp_objective(text: str) -> str:
    """Extract the cycle objective a blueprint declares, if any.

    BLP-005 CA-19, hardened after Heimdall V-6. Only a *declaration*
    counts: the ``objetivo``/``objective`` frontmatter key, or an explicit
    ``*Objetivo:*`` line in the body. Free prose is never scanned.

    The previous version searched the whole document for ``CYC-OBJ-N``,
    so a blueprint stating "this does NOT address CYC-OBJ-7" was recorded
    as serving CYC-OBJ-7. An index that guesses is worse than one that
    admits ignorance, because the guess looks exactly like a truth.
    """
    fm_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        raw = _fm_val(fm_match.group(1), "objetivo") or _fm_val(
            fm_match.group(1), "objective"
        )
        if raw:
            return raw.strip()
    declared = re.search(
        r"^\s*\*\s*Objetivo\s*:\s*\*?\s*(CYC-OBJ-\d+)", text, re.MULTILINE | re.IGNORECASE
    )
    return declared.group(1) if declared else ""


_OPERATOR_BLOCK_RE = re.compile(
    r"<!--\s*OPERATOR\s*-->.*?<!--\s*/OPERATOR\s*-->", re.DOTALL
)


def _cell(value: str) -> str:
    """Make a value safe to interpolate into a derived manifest table.

    BLP-005 V-8 (Heimdall R-3, CRITICO). A blueprint title carrying
    ``<!-- OPERATOR --> ... <!-- /OPERATOR -->`` was written into the §6
    index verbatim. Because the reconciler preserves the operator block,
    that injection became permanent and read as if the Architect had
    written it. Any content derived from a blueprint must therefore lose
    its ability to open a marker.

    Comment delimiters are removed rather than escaped: a governance table
    has no legitimate use for them, and leaving the text visible keeps the
    index honest about what it contains.

    Args:
        value: Raw cell text.

    Returns:
        The text with comment delimiters removed and pipes escaped.
    """
    text = re.sub(r"<!--.*?-->", " ", value, flags=re.DOTALL)
    text = re.sub(r"<!--|-->", "", text)
    text = text.replace("|", "\\|")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _operator_block(existing: str) -> str:
    """Return the operator's preserved block from a section being rebuilt.

    BLP-005 CA-19, hardened after Heimdall V-7. §6 and §7 are derived: the
    reconciler regenerates them wholesale, so anything an operator wrote
    between the markers used to vanish without warning. Rather than
    document the loss, the section now carries an explicit block that
    survives regeneration:

    ``<!-- OPERATOR --> ... <!-- /OPERATOR -->``

    The operator opts in by delimiting their note. Everything outside the
    pair stays derived, so the section cannot quietly accumulate state
    that the filesystem no longer reflects.

    A block sitting inside a table row is refused outright. That is where
    an injected one lands, and it is how Heimdall R-3 turned a blueprint
    title into permanent manifest content.
    """
    found = _OPERATOR_BLOCK_RE.search(existing)
    if not found:
        return ""
    line_start = existing.rfind("\n", 0, found.start()) + 1
    if existing[line_start:found.start()].lstrip().startswith("|"):
        return ""
    return "\n\n" + found.group(0)


def _replace_marked_section(text: str, number: int, body: str) -> str:
    """Replace the content of ``§N`` without destroying its markers.

    BLP-005 CA-19. Two cases:

    * **Marked section** — the manifest declares
      ``<!-- CYCLE:N --> ... <!-- /CYCLE:N -->``. Only the text between
      the pair is replaced; both markers survive, so the section stays
      parseable and the next reconcile can find it again.
    * **Unmarked section** — fall back to the header-to-next-header span,
      which is the pre-existing behaviour.

    Args:
        text: Manifest body.
        number: Section number.
        body: Replacement content.

    Returns:
        The text with the section body replaced.
    """
    marked = re.compile(
        rf"(<!--\s*CYCLE:{number}\s*-->)(.*?)(<!--\s*/CYCLE:{number}\s*-->)",
        re.DOTALL,
    )
    if marked.search(text):
        return marked.sub(
            lambda m: m.group(1)
            + "\n"
            + body
            + _operator_block(m.group(2))
            + "\n"
            + m.group(3),
            text,
            count=1,
        )

    plain = re.compile(
        rf"(## §{number}:[^\n]*\n)(?:.*?)(?=\n## §\d+:|\Z)",
        re.DOTALL,
    )
    return plain.sub(lambda m: m.group(1) + "\n" + body + "\n", text, count=1)


def reconcile_cycle(project_root: Path, cycle_id: str) -> dict[str, Any]:
    """Reconcile a single cycle's MANIFEST.md with filesystem reality.

    Scans BLPs and tasks in the cycle, updates §6 (BLP index table)
    and §7 (metrics counts) in the cycle's MANIFEST.md.

    This is the automatic reconciliation that runs after every mutation
    at task and blueprint level. Always keeps the cycle MANIFEST fresh.

    Returns dict with reconciliation report.
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result: dict[str, Any] = {
        "reconciled": False,
        "cycle_id": cycle_id,
        "metrics": {},
        "errors": [],
    }

    # Callers pass either the project root or the .arqux/ directory
    # (find_project_root returns .arqux/). Normalize to the project root
    # so the cycles lookup below is correct (BLP-003).
    project_root = project_root.parent if project_root.name == ".arqux" else project_root

    cycles_dir = project_root / ".arqux" / "cycles"
    cdir = cycles_dir / cycle_id
    if not cdir.is_dir():
        result["errors"].append(f"cycle directory not found: {cycle_id}")
        return result

    manifest_path = cdir / "MANIFEST.md"
    if not manifest_path.exists():
        result["errors"].append(f"MANIFEST.md not found for {cycle_id}")
        return result

    # 1. Scan BLPs in this cycle
    bp_dir = cdir / "blueprints"
    bp_counts: dict[str, int] = {}
    bp_rows: list[dict[str, str]] = []

    if bp_dir.is_dir():
        for bp_file in sorted(bp_dir.glob("BLP-*.md")):
            try:
                text = bp_file.read_text(encoding="utf-8")
                fm_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
                if not fm_match:
                    continue
                fm_text = fm_match.group(1)

                bp_id = _fm_val(fm_text, "blueprint_id") or bp_file.stem
                title = _fm_val(fm_text, "title") or _body_title(text)
                status = _fm_val(fm_text, "status") or "draft"
                priority = _fm_val(fm_text, "priority") or "medium"
                governor = _fm_val(fm_text, "governor") or ""

                bp_counts[status] = bp_counts.get(status, 0) + 1
                display_title = (title[:60] + "...") if len(title) > 60 else title

                bp_rows.append({
                    "id": bp_id,
                    "title": display_title,
                    "status": status,
                    "priority": priority,
                    "governor": governor,
                    # BLP-005 CA-19: read the declared cycle objective so the
                    # index can link each blueprint back to §3.
                    "objective": _read_blp_objective(text),
                })
            except Exception:
                continue

    # 2. Scan tasks in this cycle
    tasks_dir = cdir / "tasks"
    task_counts: dict[str, int] = {}
    if tasks_dir.is_dir():
        for tfile in sorted(tasks_dir.glob("*.cortex")):
            status = _read_task_status(tfile)
            if status:
                task_counts[status] = task_counts.get(status, 0) + 1

    total_blps = sum(bp_counts.values())
    total_tasks = sum(task_counts.values())

    result["metrics"] = {
        "total_blueprints": total_blps,
        "blueprints_by_status": bp_counts,
        "total_tasks": total_tasks,
        "tasks_by_status": task_counts,
    }

    # 3. Build §6 BLP table
    order = ["draft", "defined", "ready", "in_progress",
             "review", "done", "cancelled", "blocked"]

    table_rows = []
    for row in bp_rows:
        te = _cell(row["title"])
        table_rows.append(
            f"| {row['id']} | {te} | {_cell(row['status'])} | {_cell(row['priority'])} "
            f"| {_cell(row['objective']) or '—'} | {_cell(row['governor'])} |"
        )
    # BLP-005 CA-19: the index carries the Objetivo column so §6 links each
    # blueprint to the cycle objective it serves. Losing it disconnects the
    # index from §3 and breaks the loop's objective selector.
    table_header = (
        "| BLP ID | Título | Estado | Prioridad | Objetivo | Gobernador |\n"
        "|---|---|---|---|---|---|"
    )
    section_6 = (
        table_header + "\n" + "\n".join(table_rows)
        if table_rows
        else table_header + "\n| _— | _Sin BLPs en este ciclo_ | _ | _ | _ | _ |"
    )

    # 4. Build §7 metrics
    labels = {
        "draft": "Draft", "defined": "Definido", "ready": "Ready",
        "in_progress": "En Progreso", "review": "Review", "done": "Done",
        "cancelled": "Cancelado", "blocked": "Bloqueado",
    }
    parts = []
    for s in order:
        c = bp_counts.get(s, 0)
        parts.append(f"**{labels[s]}:** {c}")

    progress_pct = 0
    if total_blps > 0:
        done_or_blocked = bp_counts.get("done", 0) + bp_counts.get("cancelled", 0)
        progress_pct = round(done_or_blocked / total_blps * 100)

    section_7 = (
        f"**Total Blueprints:** {total_blps} | "
        + " | ".join(parts)
        + f"\n**Progreso:** {progress_pct}%"
    )
    if total_tasks > 0:
        t_labels = {
            "open": "Abiertas", "draft": "Borrador", "in_progress": "En Progreso",
            "done": "Completadas", "blocked": "Bloqueadas",
            "cancelled": "Canceladas", "review": "Review",
        }
        t_parts = []
        for s in ["open", "draft", "in_progress", "done", "blocked",
                   "cancelled", "review"]:
            c = task_counts.get(s, 0)
            t_parts.append(f"**{t_labels[s]}:** {c}")
        section_7 += f"\n**Total Tareas:** {total_tasks} | " + " | ".join(t_parts)

    # 5. Rewrite MANIFEST.md sections
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")

        # BLP-005 CA-19: replace only the content between the section's
        # markers. The previous regex spanned from the header to the next
        # ``## §N``, which swallowed the closing ``<!-- /CYCLE:N -->`` and
        # any prose the blueprint had placed in the section, leaving the
        # manifest structurally invalid after every reconcile.
        manifest_text = _replace_marked_section(manifest_text, 6, section_6)
        manifest_text = _replace_marked_section(manifest_text, 7, section_7)

        # BLP-003: synchronize the MANIFEST frontmatter with reality.
        fm_text, m_body = _split_frontmatter(manifest_text)
        if fm_text is not None:
            # Preserve terminal/operator states (closed, active).
            if _fm_val(fm_text, "status") not in ("closed", "active"):
                active = any(
                    bp_counts.get(s, 0)
                    for s in ("ready", "in_progress", "review", "done")
                )
                fm_text = _set_fm_scalar(
                    fm_text, "status", "active" if active else "draft"
                )
            governor = _fm_val(fm_text, "governor")
            if not governor or governor.lower() == "anonymous":
                governor = _resolve_governor(project_root)
            if governor:
                fm_text = _set_fm_scalar(fm_text, "governor", governor)
            if not _fm_val(fm_text, "project_ref"):
                fm_text = _set_fm_scalar(fm_text, "project_ref", project_root.name)
            fm_text = _set_fm_scalar(fm_text, "updated_at", ts)

            # Only touch quality_gates@ when §9 actually declares gate rows.
            m9 = re.search(r"## §9:.*?(?=\n## §10:|\Z)", m_body, re.DOTALL)
            m9_text = m9.group(0) if m9 else ""
            if any(
                re.search(rf"\|\s*{re.escape(k)}\s*\|", m9_text)
                for k in MANIFEST_GATE_KEYS
            ):
                fm_text = _write_gate_block(
                    fm_text, _read_gate_table(m9_text, MANIFEST_GATE_KEYS)
                )

            manifest_text = f"---\n{fm_text}\n---{m_body}"

        manifest_path.write_text(manifest_text, encoding="utf-8")
        result["reconciled"] = True
        result["updated_at"] = ts

    except Exception as e:
        result["errors"].append(f"Failed to write MANIFEST.md: {e}")

    return result
