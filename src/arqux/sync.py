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
        from arqux.state import find_workspace_root, crud_update

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
