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
        Canonical event name, e.g. ``"blueprint.approve"``.
    focus:
        If provided, updates ``FCS:current`` in brain.cortex.
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
        from arqux.state import crud_update
    except ImportError:
        logger.warning("sync_brain: crud_update not available, skipping")
        return

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    current_text = f"{event}: {detail}" if detail else event

    try:
        crud_update(
            str(brain_path),
            "$8/WRK:current",
            set_={
                "phase": "current",
                "current": current_text,
                "blocked": "no",
                "updated": ts,
                "event": event,
            },
            force=True,
        )
    except Exception:
        logger.exception("sync_brain: failed to update WRK:current @ $8 (continuing)")

    if focus:
        try:
            crud_update(
                str(brain_path),
                "$2/FCS:current",
                set_={
                    "what": focus,
                    "priority": "medium",
                    "status": "current",
                    "updated": ts,
                    "event": event,
                },
                force=True,
            )
        except Exception:
            logger.exception("sync_brain: failed to update FCS:current @ $2 (continuing)")

    if metrics:
        _update_metrics(brain_path, metrics, ts)
        _sync_meta_brain(project_root, metrics, event, ts)


def _update_metrics(
    brain_path: Path,
    metrics: dict[str, Any],
    ts: str,
) -> None:
    """Merge *metrics* into the brain's PULSE section."""
    try:
        from arqux.state import crud_add
    except ImportError:
        return

    for key, value in metrics.items():
        try:
            knw_status = "done" if key == "tasks_done" else "current"
            crud_add(
                str(brain_path),
                section="$6",
                sigil="KNW",
                name=key,
                value={
                    "name": key,
                    "value": str(value),
                    "updated": ts,
                    "topic": "metrics",
                    "content": f"metric {key}={value}",
                    "status": knw_status,
                },
                create_section=False,
                force=True,
            )
        except Exception:
            logger.debug("sync_brain: failed to add metric %s=%s (continuing)", key, value)


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


def _sync_meta_brain(
    project_root: Path,
    metrics: dict[str, Any],
    event: str,
    ts: str,
) -> None:
    """Sync metrics to meta-brain DOM:arqux entry."""
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

        crud_update(
            str(meta_brain_path),
            "$2/DOM:arqux",
            set_=dom_updates,
            force=True,
        )
    except Exception:
        logger.exception("sync_brain: failed to sync meta-brain @ DOM:arqux (continuing)")


def reconcile_brain(project_root: Path) -> dict[str, Any]:
    """Reconcile brain.cortex persistent state with filesystem reality.

    Scans all cycles and blueprints, counts by status, and updates:
    - brain.cortex §3 (OBJ): goal with accurate counts
    - brain.cortex §10 (KNW): project_knowledge topic
    - brain.cortex §19 (ARQX metadata): version, last_sync
    - meta-brain.cortex $2/DOM:arqux: counts if meta-brain exists

    Returns dict with reconciliation report.
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result = {
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

        # 2. Reconstruct brain.cortex §3 (OBJ)
        try:
            from arqux.state import crud_update

            goal = (
                f"Mantener sincronia entre brain.cortex y estado real del proyecto. "
                f"{total_blps} BLPs gestionados en {len(open_cycles) + len(closed_cycles)} ciclos "
                f"({', '.join(sorted(open_cycles + closed_cycles))})."
            )

            crud_update(
                str(project_root / ".arqux" / "brain.cortex"),
                "$3/OBJ:_",
                set_={
                    "goal": goal,
                    "status": "current",
                    "success": "synced",
                    "survive": "work",
                    "updated": ts,
                    "event": "brain.reconcile",
                },
                force=True,
            )
            result["reconciled"] = True
        except Exception as e:
            result["errors"].append(f"Failed to update OBJ: {e}")

        # 3. Reconstruct meta-brain.cortex $2/DOM:arqux
        try:
            from arqux.state import crud_update, find_workspace_root

            ws_root = find_workspace_root(start=project_root.parent)
            if ws_root is not None:
                meta_brain = ws_root / "meta-brain.cortex"
                if meta_brain.exists():
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

                    crud_update(
                        str(meta_brain),
                        "$2/DOM:arqux",
                        set_=dom_updates,
                        force=True,
                    )
                    result["meta_synced"] = True
        except Exception as e:
            result["errors"].append(f"Failed to sync meta-brain: {e}")

    except Exception as e:
        result["errors"].append(f"Reconciliation failed: {e}")

    return result


def _fm_val(fm_text: str, key: str) -> str:
    """Extract a value from YAML frontmatter text by key."""
    m = re.search(rf'^{key}:\s*"([^"]*)"', fm_text, re.MULTILINE)
    return m.group(1) if m else ""


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
                title = _fm_val(fm_text, "title") or ""
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
                })
            except Exception:
                continue

    # 2. Scan tasks in this cycle
    tasks_dir = cdir / "tasks"
    task_counts: dict[str, int] = {}
    if tasks_dir.is_dir():
        for tfile in sorted(tasks_dir.glob("*.cortex")):
            try:
                from arqux.core.state._project import parse_cortex_file
                fm_t, _ = parse_cortex_file(tfile)
                status = fm_t.get("status", "")
                if status:
                    task_counts[status] = task_counts.get(status, 0) + 1
            except Exception:
                continue

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
        te = row["title"].replace("|", "\\|")
        table_rows.append(
            f"| {row['id']} | {te} | {row['status']} | {row['priority']} | {row['governor']} |"
        )
    section_6 = "\n".join(table_rows) if table_rows else (
        "| BLP ID | Título | Estado | Prioridad | Gobernador |\n"
        "|---|---|---|---|---|\n"
        "| _— | _Sin BLPs en este ciclo_ | _ | _ | _ |"
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

        # Replace §6 table: from header to next ## § or end
        manifest_text = re.sub(
            r"(## §6: Blueprints \(Índice\).*?\n)(?:.*?)(?=\n## §7:|\Z)",
            lambda m: m.group(1) + "\n" + section_6 + "\n",
            manifest_text,
            count=1,
            flags=re.DOTALL,
        )

        # Replace §7 section: from header to next ## § or end
        manifest_text = re.sub(
            r"(## §7: Estado y Métricas.*?\n)(?:.*?)(?=\n## §8:|\Z)",
            lambda m: m.group(1) + "\n" + section_7 + "\n",
            manifest_text,
            count=1,
            flags=re.DOTALL,
        )

        manifest_path.write_text(manifest_text, encoding="utf-8")
        result["reconciled"] = True
        result["updated_at"] = ts

    except Exception as e:
        result["errors"].append(f"Failed to write MANIFEST.md: {e}")

    return result
