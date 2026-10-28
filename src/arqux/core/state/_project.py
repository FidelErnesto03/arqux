"""Project-level discovery and context helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX, META_BRAIN_CORTEX

# BLP-fix (T-005/G-9): _HAS_CODEC_CORTEX / _cc_* are defined in
# core.state.__init__ (as None when CODEC-CORTEX is absent), so a
# top-level 'from . import' is safe and no longer circular.
from . import _HAS_CODEC_CORTEX, _cc_parser

#: Name of the session context file inside ``.arqux/``.
CONTEXT_CORTEX: str = "context.cortex"
#: Per-execution context pointers (``.arqux/contexts/<exec>.cortex``).
CONTEXTS_DIR: str = "contexts"


# --- CORTEX file parsing (legacy fallback) -----------------------------------

_SECTION_RE = re.compile(r"^# ([A-Z][A-Z_]+)\s*$", re.MULTILINE)


def parse_cortex_file(path: Path) -> tuple[dict[str, Any], str]:
    """Parse a CORTEX file: YAML frontmatter + body.

    Returns (frontmatter_dict, body_text).

    If CODEC-CORTEX is available and the file is in canonical format,
    the parsing delegates to the full parser.
    """
    text = path.read_text(encoding="utf-8")

    # Try CODEC-CORTEX parser first for canonical .cortex files.
    if _HAS_CODEC_CORTEX and text.startswith("$") and "$0" in text[:40]:
        try:
            doc = _cc_parser.parse_cortex(text, path=str(path))
            fm: dict[str, Any] = {"document": path.stem, "sections": len(doc.sections)}
            # Extract task metadata if this is a task file (has WRK:task entry).
            task_fm: dict[str, Any] = {}
            for sec in doc.sections:
                for e in (sec.entries or []):
                    if e.sigil == "WRK" and e.name == "task":
                        task_fm = {
                            "id": e.value.get("id", path.stem),
                            "status": e.value.get("status", ""),
                            "governor": e.value.get("governor", ""),
                            "assignee": e.value.get("assignee", ""),
                            "priority": e.value.get("priority", "medium"),
                            "complexity": e.value.get("complexity", "standard"),
                            "cycle": e.value.get("cycle", ""),
                            "created": e.value.get("created", ""),
                            "updated": e.value.get("updated", ""),
                        }
                        if task_fm.get("id"):
                            fm.update(task_fm)
                            break
                if task_fm.get("id"):
                    break
            # Fallback: try to extract id from filename
            if not fm.get("id"):
                fm["id"] = path.stem
            # Serialize sections back to a markdown-like body with # SECTION headers
            # that parse_brain_sections can read.
            sigil_section_map = {
                "IDENTITY": None, "FOCUS": "FOCUS", "OBJECTIVES": "OBJECTIVES",
                "SESSIONS": "SESSIONS", "HANDOFFS": "HANDOFFS", "PULSE": "PULSE",
                "LESSONS": "LESSONS", "ACTIVE_CONTEXT": "ACTIVE_CONTEXT",
                "RISKS": "RISKS", "KNOWLEDGE": "KNOWLEDGE",
                "CONCURRENCY": "CONCURRENCY",
                "TASK": None, "WORKSPACE": None,
                "META-BRAIN": None, "PROJECTS": None, "CYCLE": None,
                "PRECONDITIONS": "PRE", "PROCEDURE": "PROC",
                "ACCEPTANCE": "AC", "BLOCKERS": "BLK",
                "OBJECTIVE": "OBJ", "NOTE": None, "EVIDENCE": None,
            }
            body_parts = []
            for sec in doc.sections:
                sec_title = (sec.title or sec.id).upper()
                target = sigil_section_map.get(sec_title, sec_title)
                if target is None:
                    continue
                body_parts.append(f"# {target}")
                body_parts.append("")
                for entry in sec.entries:
                    val = entry.value
                    if isinstance(val, dict):
                        parts = []
                        for k, v in val.items():
                            parts.append(f"{k}={v}")
                        body_parts.append("- " + ", ".join(parts))
                    elif val:
                        body_parts.append(str(val))
                body_parts.append("")
            return fm, "\n".join(body_parts)
        except Exception:  # noqa: BLE001
            pass

    # Legacy YAML frontmatter parser.
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text = parts[1].strip()
    body = parts[2].strip()
    fm: dict[str, Any] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        fm[key.strip()] = value
    return fm, body


# --- Discovery -------------------------------------------------------------


@dataclass
class WorkspaceRoot:
    path: Path
    manifest: dict[str, Any] = field(default_factory=dict)


def find_workspace_root(start: Path | str | None = None) -> Path | None:
    """Walk up from `start` (default: cwd) looking for `.<product>/meta-brain.cortex`."""
    cursor = Path(start or os.getcwd()).resolve()
    target_dir = ARQUX_DIR
    target_file = META_BRAIN_CORTEX

    while True:
        candidate = cursor / target_dir / target_file
        if candidate.exists():
            return cursor / target_dir
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


def find_project_root(start: Path | str | None = None) -> Path | None:
    """Find a project-level `.<product>/` directory (must contain brain.cortex).

    First walks up from *start* (default: cwd). If that fails and *start* is None,
    falls back to resolving the project from the workspace context file
    (``.arqux/context.cortex``), which is written by ``session.context.set``.
    """
    cursor = Path(start or os.getcwd()).resolve()
    target_dir = ARQUX_DIR

    # BC-6 fix: if start path itself ends with /.arqux, we are already inside
    # the .arqux/ directory — return it directly (no double nesting).
    if cursor.name == target_dir and (cursor / BRAIN_CORTEX).exists():
        return cursor

    while True:
        candidate = cursor / target_dir / BRAIN_CORTEX
        if candidate.exists():
            return cursor / target_dir
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    # Fallback: try to resolve from workspace context.cortex
    if start is not None:
        return None

    ws_root = find_workspace_root()
    if ws_root is None:
        return None

    # The per-execution pointer wins over the global one. ``context.cortex`` is
    # a single slot that any execution can overwrite: another client setting a
    # different project made a checkpoint land in the wrong brain
    # (2026-10-28, ARQUX -> Manhattan).
    for ctx_path in _context_candidates(ws_root):
        if not ctx_path.exists():
            continue
        raw = ctx_path.read_text(encoding="utf-8")
        m = re.search(r'project_root[=:]"([^"]*)"', raw)
        if not m:
            continue
        candidate = Path(m.group(1))
        if candidate.exists() and (candidate / ARQUX_DIR / BRAIN_CORTEX).exists():
            return candidate / ARQUX_DIR
    return None


def _context_candidates(ws_root: Path) -> list[Path]:
    """This execution's pointer first, the shared slot last."""
    candidates: list[Path] = []
    try:
        import hashlib

        from ...execution import authoritative_execution_key

        execution = authoritative_execution_key()
    except Exception:  # noqa: BLE001
        execution = None
    if execution:
        readable = re.sub(r"[^A-Za-z0-9._-]", "_", execution).strip("._")[:64] or "exec"
        digest = hashlib.sha256(execution.encode("utf-8")).hexdigest()[:12]
        candidates.append(ws_root / CONTEXTS_DIR / f"{readable}-{digest}.cortex")
    candidates.append(ws_root / CONTEXT_CORTEX)
    return candidates
