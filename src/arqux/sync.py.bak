"""Brain sync — automatically update brain.cortex after handler mutations.

Every mutating handler (blueprint, task, cycle, skill, identity, project)
should call ``sync_brain()`` as its last line before returning success.
This keeps brain.cortex (WRK:current, FCS:current, metrics) always
reflecting the latest state — no more cognitive dissonance.

Since BLP-019, sync_brain also updates meta-brain.cortex (DOM:arqux)
when metrics are provided, keeping workspace-level knowledge in sync.

Usage::

    from arqux.sync import sync_brain

    sync_brain(
        project_root=root,
        event="blueprint.approve",
        focus="Próximo BLP o cierre de ciclo",
        metrics={"blueprints_done": 17},
    )
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
        Absolute path to the project root (where ``.arqux/`` lives).
    event:
        Canonical event name, e.g. ``"blueprint.approve"``.
    focus:
        If provided, updates ``FCS:current`` in brain.cortex.
        Only set this on *major* events (approve, create, cycle close).
    metrics:
        Optional dict of counters to merge into brain.cortex
        (e.g. ``{"blueprints_done": 17}``). When provided, also
        updates meta-brain.cortex DOM:arqux with the new counts.
    detail:
        Optional human-readable detail about the event.
    """
    if project_root is None:
        logger.warning("sync_brain: project_root is None, skipping")
        return

    brain_path = project_root / ".arqux" / "brain.cortex"
    if not brain_path.exists():
        logger.warning("sync_brain: brain.cortex not found at %s, skipping", brain_path)
        return

    # Use the CRUD layer from state.py for atomic writes.
    try:
        from arqux.state import crud_update
    except ImportError:
        logger.warning("sync_brain: crud_update not available, skipping")
        return

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    current_text = f"{event}: {detail}" if detail else event
    wrk_value = f"phase:active, current:{current_text}, blocked:no, updated:{ts}"

    try:
        # 1. Update WRK:current (ACTIVE_CONTEXT §8)
        crud_update(
            str(brain_path),
            "$8/WRK:current",
            set_={
                "phase": "active",
                "current": current_text,
                "blocked": "no",
                "updated": ts,
                "event": event,
            },
            force=True,
        )
    except Exception:
        logger.exception("sync_brain: failed to update WRK:current (continuing)")

    # 2. Update FCS:current if focus is provided (FOCUS §2)
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
            logger.exception("sync_brain: failed to update FCS:current (continuing)")

    # 3. Update metrics + meta-brain if provided
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
            crud_add(
                str(brain_path),
                section="$6",
                sigil="KNW",
                name=key,
                value={"value": str(value), "updated": ts},
                create_section=False,
                force=True,
            )
        except Exception:
            logger.debug("sync_brain: failed to add metric %s=%s (continuing)", key, value)


def _count_blueprints(root: Path) -> dict[str, int]:
    """Count blueprints by status from the filesystem.

    Scans all ``BLP-*.md`` files under ``cycles/``.
    Accepts either a project root (with ``.arqux/cycles/`` subdir)
    or the ``.arqux/`` directory directly (``cycles/`` subdir).
    """
    counts: dict[str, int] = {
        "done": 0, "draft": 0, "cancelled": 0,
        "review": 0, "in_progress": 0, "ready": 0,
        "blocked": 0,
    }

    # Try .arqux/cycles first (project root), then cycles/ (already in .arqux/)
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


def _sync_meta_brain(
    project_root: Path,
    metrics: dict[str, Any],
    event: str,
    ts: str,
) -> None:
    """Sync metrics to meta-brain DOM:arqux entry.

    Derives workspace root from project_root parent directory,
    updates DOM:arqux with handler count, test count, blueprint counts.
    """
    try:
        from arqux.state import find_workspace_root, crud_update

        ws_root = find_workspace_root(start=project_root)
        if ws_root is None:
            logger.debug("sync_brain: workspace root not found, skipping meta-brain sync")
            return

        meta_brain_path = ws_root / "meta-brain.cortex"
        if not meta_brain_path.exists():
            logger.debug("sync_brain: meta-brain.cortex not found at %s", meta_brain_path)
            return

        dom_updates: dict[str, Any] = {"updated": ts, "last_event": event}

        # Derive actual blueprint counts from the filesystem
        # (instead of relying on callers' hardcoded metric=1 values)
        try:
            bp_counts = _count_blueprints(project_root)
            dom_updates["blueprints_done"] = str(bp_counts.get("done", 0))
            dom_updates["blueprints_draft"] = str(bp_counts.get("draft", 0))
            dom_updates["blueprints_cancelled"] = str(bp_counts.get("cancelled", 0))
            dom_updates["blueprints_completed"] = str(bp_counts.get("review", 0))
        except Exception:
            logger.debug("sync_brain: failed to count blueprints, using metric values (continuing)")
            # Fallback: use caller-provided metric values
            for key in ("blueprints_done", "blueprints_draft",
                        "blueprints_cancelled", "blueprints_completed"):
                if key in metrics:
                    dom_updates[key] = str(metrics[key])

        # Non-blueprint metrics still come from callers (handlers, tests, etc.)
        for key, value in metrics.items():
            if key in ("handlers", "tests",
                       "tasks_done", "tasks_active", "cycles_closed"):
                dom_updates[key] = str(value)

        crud_update(
            str(meta_brain_path),
            "$2/DOM:arqux",
            set_=dom_updates,
            force=True,
        )
    except Exception:
        logger.exception("sync_brain: failed to sync meta-brain (continuing)")
