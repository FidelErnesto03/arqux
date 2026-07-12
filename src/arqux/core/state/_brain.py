"""Project brain operations — the single shared mind of a project."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ...constants import (
    ARQUX_DIR,
    BRAIN_CORTEX,
    BRAIN_SECTION_ACTIVE_CONTEXT,
    BRAIN_SECTION_CONCURRENCY,
    BRAIN_SECTION_FOCUS,
    BRAIN_SECTION_HANDOFFS,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_OBJECTIVES,
    BRAIN_SECTION_PULSE,
    BRAIN_SECTION_RISKS,
    BRAIN_SECTION_SESSIONS,
    CYCLES_DIR,
    PRODUCT_NAME,
    TASKS_DIR,
)
from . import _HAS_CODEC_CORTEX, _cc_parser
from ._parse import parse_brain_sections
from ._project import parse_cortex_file
from ._render import (
    write_cortex_pair,
)

# --- Project brain (the single shared mind) --------------------------------
#
# The brain.cortex is the SHARED MENTAL STATE of a project. Every agent
# bound to the project reads and writes the same brain. This is how multiple
# agents working concurrently share a single project mind:
#
#   - The FOCUS section tells every agent what the project is currently about.
#   - The OBJECTIVES section lists stable project goals (not tasks).
#   - The SESSIONS section lists which agents are bound and their roles.
#   - The HANDOFFS section is a chronological log of work handed between agents.
#   - The PULSE section is the append-only event trace (was pulse.jsonl).
#   - The LESSONS section holds lessons learned local to this project.
#   - The ACTIVE_CONTEXT section names the currently active cycle/task.
#   - The RISKS section lists project-specific risks.
#   - The CONCURRENCY section holds optimistic-locking state (version + writer).


def _resolve_brain_path(project_root: Path) -> Path:
    """Resolve the canonical brain.cortex path.

    If ``project_root`` is the project root (has ``.arqux/`` subdirectory),
    returns ``project_root / ARQUX_DIR / BRAIN_CORTEX``.
    If ``project_root`` IS the ``.arqux/`` directory, returns
    ``project_root / BRAIN_CORTEX``.
    Falls back to ``project_root / BRAIN_CORTEX`` for backward compat.
    """
    if project_root.name == ARQUX_DIR:
        return project_root / BRAIN_CORTEX
    arqux_candidate = project_root / ARQUX_DIR / BRAIN_CORTEX
    if arqux_candidate.exists() or (project_root / ARQUX_DIR).is_dir():
        return arqux_candidate
    return project_root / BRAIN_CORTEX


def read_brain(project_root: Path) -> tuple[dict[str, Any], dict[str, str], str]:
    """Read the project brain.

    Supports both legacy YAML-frontmatter and canonical CODEC-CORTEX sigil
    formats. When a sigil-format brain is detected, extracts fields from
    the AST and normalizes them into the expected frontmatter + sections.

    Returns (frontmatter, sections, raw_body).
    `sections` is a dict mapping section name to raw text content.
    """
    brain_path = _resolve_brain_path(project_root)
    if not brain_path.exists():
        return {}, {}, ""

    text = brain_path.read_text(encoding="utf-8")

    # Try CODEC-CORTEX parser for sigil-format brains.
    if _HAS_CODEC_CORTEX and "$0" in text[:80]:
        try:
            doc = _cc_parser.parse_cortex(text, path=str(brain_path))
            fm: dict[str, Any] = {
                "brain_version": "0",
                "brain_last_writer": "",
                "brain_updated": "",
                "level": "2",
                "project": "",
                "path": "",
                "governor": "",
            }
            sections: dict[str, str] = {}

            # Map section titles to Arqux brain section names.
            # BLP-036: the canonical Level-3 brain has 13 sections ($0..$12).
            # We accept both the legacy 9-section form and the v3.0 13-section
            # form. Sections not in the legacy tuple are still extracted
            # (so future BLPs can read them) but are not required.
            sect_map = {
                # Legacy / canonical sections (mapped to handler keys).
                "IDENTITY": None,           # $1 — extracts metadata
                "FOCUS": "FOCUS",           # $3
                "OBJECTIVES": "OBJECTIVES", # $4
                "SESSIONS": "SESSIONS",     # $4 (legacy) — kept for back-compat
                "HANDOFFS": "HANDOFFS",     # $5 / $10 (canonical)
                "PULSE": "PULSE",           # $6 (legacy) / $5 STATE (canonical)
                "LESSONS": "LESSONS",       # $6 / $7 (legacy)
                "ACTIVE_CONTEXT": "ACTIVE_CONTEXT",  # $5 STATE (canonical)
                "RISKS": "RISKS",           # $9
                "KNOWLEDGE": "KNOWLEDGE",   # $2
                "CONCURRENCY": None,        # $11 — extracts metadata
                # New canonical sections (BLP-036) — preserved but not
                # yet exposed as legacy handler keys.
                "METADATA": None,
                "STATE": "ACTIVE_CONTEXT",
                "DECISIONS": "DECISIONS",
                "AXIOMS": "AXIOMS",
                "LIMITS": "LIMITS",
                "HANDOFF": "HANDOFFS",
                "ISSUES": "ISSUES",
            }

            for sec in doc.sections:
                sec_name = (sec.title or sec.id).upper()
                mapped = sect_map.get(sec_name)
                if mapped is None:
                    # Extract metadata from identity and concurrency sections.
                    for e in (sec.entries or []):
                        if sec_name == "IDENTITY" and e.sigil == "IDN":
                            fm["governor"] = e.value.get("governor", e.value.get("agent", ""))
                            fm["level"] = e.value.get("level", "2")
                            fm["project"] = e.value.get("project", "")
                            fm["path"] = e.value.get("path", "")
                        elif sec_name == "CONCURRENCY" and e.sigil == "ERR":
                            fm["brain_version"] = e.value.get("version", "0")
                            fm["brain_last_writer"] = e.value.get("last_writer", "")
                            fm["brain_updated"] = e.value.get("updated", "")
                    continue

                # Build section content from entries in handler-compatible format.
                lines: list[str] = []
                for e in (sec.entries or []):
                    if isinstance(e.value, dict):
                        # Format entries in handler-compatible format.
                        if mapped == "SESSIONS":
                            date = e.value.get("date", e.value.get("joined", ""))
                            ts = f"{date}T00:00:00Z"
                            agent = e.name.replace("_", "-") if e.name else e.value.get("agent", "")
                            role = e.value.get("role", "active")
                            status = "active" if "released" not in str(e.value) else "released"
                            lines.append(f"- [{ts}] agent={agent} role={role} status={status}")
                        elif mapped == "HANDOFFS":
                            from_ = e.value.get("from", "")
                            to_ = e.value.get("to", "")
                            task = e.value.get("task", "-")
                            note = e.value.get("note", "")
                            ts = e.value.get("ts", "")
                            lines.append(f"- [{ts}] {from_} -> {to_} task={task} :: {note}")
                        elif mapped == "PULSE":
                            event_id = e.value.get("event", e.name)
                            task = e.value.get("task", "-")
                            kind = e.value.get("kind", "note")
                            agent = e.value.get("agent", "")
                            payload = e.value.get("evidence", e.value.get("payload", ""))
                            ts = e.value.get("ts", e.value.get("date", ""))
                            lines.append(f"- [{ts}] id={event_id} task={task} kind={kind} agent={agent} :: {payload}")
                        elif mapped == "LESSONS":
                            detail = e.value.get("lesson", e.value.get("detail", ""))
                            lines.append(f"- {detail}")
                        elif mapped == "ACTIVE_CONTEXT":
                            current = e.value.get("cycle", e.value.get("current", ""))
                            lines.append(f"- cycle={current}")
                        elif mapped == "RISKS":
                            description = e.value.get("description", "")
                            lines.append(f"- {description}")
                        elif mapped == "KNOWLEDGE":
                            content = e.value.get("content", "")
                            if content:
                                lines.append(content)
                        elif mapped == "OBJECTIVES":
                            goal = e.value.get("goal", "")
                            lines.append(f"- {goal}")
                        elif mapped == "FOCUS":
                            what = e.value.get("what", e.value.get("value", ""))
                            if what:
                                lines.append(what)
                    elif e.value:
                        lines.append(str(e.value))
                sections[mapped] = "\n".join(lines)

            body_parts = [f"# {k}\n{v}" for k, v in sections.items()]
            return fm, sections, "\n".join(body_parts)

        except Exception:  # noqa: BLE001
            pass

    # Fallback to legacy YAML parser.
    fm, body = parse_cortex_file(brain_path)
    sections = parse_brain_sections(body)
    return fm, sections, body


def write_brain_sections(
    project_root: Path,
    frontmatter: dict[str, Any],
    sections: dict[str, str],
) -> tuple[Path, Path]:
    """Write the project brain from frontmatter + sections dict."""
    directory = _resolve_brain_path(project_root).parent
    return write_cortex_pair(directory, "brain", frontmatter, sections)


def ensure_brain_section(sections: dict[str, str], name: str) -> str:
    """Get a section's content, or empty string if absent."""
    return sections.get(name, "").strip()


def append_to_brain_section(
    sections: dict[str, str],
    name: str,
    line: str,
) -> None:
    """Append a single line to a brain section (mutates `sections` in place)."""
    current = sections.get(name, "").strip()
    if current:
        sections[name] = current + "\n" + line
    else:
        sections[name] = line


# --- Handoff and pulse (inside the brain) ----------------------------------
#
# Handoffs and pulses are NO LONGER separate files. They are appended to the
# HANDOFFS and PULSE sections of the project brain. This keeps the project
# mind in one place and makes concurrent agent coordination explicit.


def _bump_concurrency(frontmatter: dict[str, Any], writer: str) -> None:
    """Bump the brain version counter and record the writer."""
    try:
        current = int(frontmatter.get("brain_version", "0"))
    except (TypeError, ValueError):
        current = 0
    frontmatter["brain_version"] = str(current + 1)
    frontmatter["brain_last_writer"] = writer
    frontmatter["brain_updated"] = _now_iso()


def brain_version(project_root: Path) -> int:
    """Read the current brain version (for optimistic-lock checks)."""
    fm, _, _ = read_brain(project_root)
    try:
        return int(fm.get("brain_version", "0"))
    except (TypeError, ValueError):
        return 0


# --- Manifest / brain helpers ---------------------------------------------


def write_manifest(
    workspace_root: Path,
    manifest: dict[str, Any],
) -> tuple[Path, Path]:
    """Write the workspace manifest (manifest.cortex + manifest.md)."""
    body = f"# WORKSPACE\n\nWorkspace governed by {PRODUCT_NAME}.\n"
    return write_cortex_pair(workspace_root, "manifest", manifest, body)


def write_meta_brain(
    workspace_root: Path,
    brain: dict[str, Any],
) -> tuple[Path, Path]:
    """Write the workspace-level meta-brain."""
    body = "# META-BRAIN\n\nCross-project knowledge and lessons.\n"
    return write_cortex_pair(workspace_root, "meta-brain", brain, body)


def write_projects_index(
    workspace_root: Path,
    projects: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """Write the workspace-level projects index."""
    body = "# PROJECTS\n\n" + "\n".join(
        f"- {p.get('name', '?')} at {p.get('path', '?')}" for p in projects
    )
    fm = {"count": len(projects), "projects": [p.get("name") for p in projects]}
    return write_cortex_pair(workspace_root, "projects", fm, body)


def write_brain(
    project_root: Path,
    brain: dict[str, Any],
) -> tuple[Path, Path]:
    """Write the project-level brain (initial creation form).

    For updates, use `write_brain_sections` after reading with `read_brain`.
    """
    directory = _resolve_brain_path(project_root).parent
    body = _initial_brain_body()
    return write_cortex_pair(directory, "brain", brain, body)


def _initial_brain_body() -> str:
    """Render the initial body for a fresh brain (all sections present, empty)."""
    parts: list[str] = []
    for section, description in (
        (BRAIN_SECTION_FOCUS, "(one-sentence current focus of the project)"),
        (BRAIN_SECTION_OBJECTIVES, "(stable project-level goals, not tasks)"),
        (BRAIN_SECTION_SESSIONS, "(agents currently bound to this project)"),
        (BRAIN_SECTION_HANDOFFS, "(chronological log of work handed between agents)"),
        (BRAIN_SECTION_PULSE, "(append-only event trace — replaces pulse.jsonl)"),
        (BRAIN_SECTION_LESSONS, "(contextual lessons — apply to this project only)"),
        (BRAIN_SECTION_ACTIVE_CONTEXT, "(currently active cycle/task)"),
        (BRAIN_SECTION_RISKS, "(project-specific risks and mitigations)"),
        (BRAIN_SECTION_CONCURRENCY, "(optimistic-locking state — do not edit by hand)"),
    ):
        parts.append(f"# {section}")
        parts.append("")
        parts.append(description)
        parts.append("")
    return "\n".join(parts).strip() + "\n"


# --- Cycle / task file helpers ---------------------------------------------


def cycle_dir(project_root: Path, cycle_id: str) -> Path:
    """Return the path to a cycle's directory."""
    return project_root / CYCLES_DIR / cycle_id


def task_path(project_root: Path, cycle_id: str, task_id: str) -> Path:
    """Return the path to a task's CORTEX file."""
    return cycle_dir(project_root, cycle_id) / TASKS_DIR / f"{task_id}.cortex"


def next_task_id(project_root: Path, cycle_id: str) -> str:
    """Determine the next task ID (T-NNN) in a cycle."""
    tasks_dir = cycle_dir(project_root, cycle_id) / TASKS_DIR
    if not tasks_dir.exists():
        return "T-001"
    existing = sorted(p.stem.replace(".cortex", "") for p in tasks_dir.glob("T-*.cortex"))
    if not existing:
        return "T-001"
    last = existing[-1].removeprefix("T-")
    try:
        n = int(last)
    except ValueError:
        n = 0
    return f"T-{n + 1:03d}"


def next_cycle_id(project_root: Path) -> str:
    """Determine the next cycle ID (CYCLE-NN)."""
    cycles_base = project_root / CYCLES_DIR
    if not cycles_base.exists():
        return "CYCLE-01"
    existing = sorted(p.name for p in cycles_base.iterdir() if p.is_dir())
    if not existing:
        return "CYCLE-01"
    last = existing[-1].removeprefix("CYCLE-")
    try:
        n = int(last)
    except ValueError:
        n = 0
    return f"CYCLE-{n + 1:02d}"


# --- Session/binding helpers (sessions live in the brain) -------------------


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


