"""State persistence and discovery helpers.

The framework persists state via CODEC-CORTEX (`.cortex` + `.md`).
This module provides:
    - Workspace/project root discovery.
    - A thin abstraction over CODEC-CORTEX for read/write/verify.
    - Project brain operations: the single shared mind of a project.
    - Handoff and pulse operations: stored INSIDE the brain, not in separate files.

If `codec-cortex` is not installed, a minimal fallback writes plain CORTEX
files (frontmatter + body) so the framework is testable in isolation.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .constants import (
    BRAIN_CORTEX,
    BRAIN_HCORTEX,
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
    MANIFEST_CORTEX,
    MANIFEST_HCORTEX,
    META_BRAIN_CORTEX,
    META_BRAIN_HCORTEX,
    PRODUCT_NAME,
    PRODUCT_NAME_UPPER,
    PROJECTS_CORTEX,
    PROJECTS_HCORTEX,
    TASKS_DIR,
    ARQUX_DIR,
)


# --- CODEC-CORTEX integration ---------------------------------------------

try:
    import codec_cortex  # type: ignore[import-not-found]

    HAS_CODEC_CORTEX: bool = True
except ImportError:  # pragma: no cover - exercised in fallback tests
    codec_cortex = None  # type: ignore[assignment]
    HAS_CODEC_CORTEX = False


# --- CORTEX file rendering --------------------------------------------------

def write_cortex_pair(
    directory: Path,
    stem: str,
    frontmatter: dict[str, Any],
    body: str,
) -> tuple[Path, Path]:
    """Write a `.cortex` + `.md` pair.

    If CODEC-CORTEX is installed, the HCORTEX form is derived from the CORTEX
    form via the codec. Otherwise, a simple human-readable markdown is
    generated inline.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    cortex_path = directory / f"{stem}.cortex"
    hcortex_path = directory / f"{stem}.md"

    cortex_content = render_cortex(frontmatter, body)
    cortex_path.write_text(cortex_content, encoding="utf-8")

    if HAS_CODEC_CORTEX and hasattr(codec_cortex, "to_human"):
        try:
            hcortex_content = codec_cortex.to_human(cortex_content)
            hcortex_path.write_text(hcortex_content, encoding="utf-8")
            return cortex_path, hcortex_path
        except Exception:  # noqa: BLE001
            pass  # fall through to manual rendering

    hcortex_content = render_hcortex(frontmatter, body)
    hcortex_path.write_text(hcortex_content, encoding="utf-8")
    return cortex_path, hcortex_path


def render_cortex(frontmatter: dict[str, Any], body: str) -> str:
    """Render a CORTEX file: YAML frontmatter + body with # SECTION markers."""
    lines: list[str] = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_yaml_value(value)}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip())
    lines.append("")
    return "\n".join(lines)


def render_hcortex(frontmatter: dict[str, Any], body: str) -> str:
    """Render an HCORTEX file: human-readable markdown derived from CORTEX.

    HCORTEX is a form of writing markdown oriented to facilitate reading,
    understanding, and organization, minimizing token consumption. The
    transformation rules are defined in AGENTS.md §9 (HCORTEX format).
    """
    title = frontmatter.get("id") or frontmatter.get("name") or "Untitled"
    lines: list[str] = [f"# {title}", ""]
    if "name" in frontmatter and frontmatter["name"] != title:
        lines.append(f"**Name:** {frontmatter['name']}")
        lines.append("")

    lines.append("## Metadata")
    lines.append("")
    for key, value in frontmatter.items():
        if key in {"id", "name"}:
            continue
        lines.append(f"- **{key}:** {_yaml_value(value)}")
    lines.append("")
    lines.append("## Body")
    lines.append("")
    lines.append(body.rstrip())
    lines.append("")
    return "\n".join(lines)


def _yaml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return "[" + ", ".join(str(v) for v in value) + "]"
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


# --- CORTEX file parsing ----------------------------------------------------

_SECTION_RE = re.compile(r"^# ([A-Z][A-Z_]+)\s*$", re.MULTILINE)


def parse_cortex_file(path: Path) -> tuple[dict[str, Any], str]:
    """Parse a CORTEX file: YAML frontmatter + body.

    Returns (frontmatter_dict, body_text).
    """
    text = path.read_text(encoding="utf-8")
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


def parse_brain_sections(body: str) -> dict[str, str]:
    """Split a brain body into its # SECTION → content mapping.

    The brain body is structured as:

        # FOCUS
        ...focus text...

        # OBJECTIVES
        - obj 1
        - obj 2

        # SESSIONS
        ...

    Returns a dict mapping each section name to its raw text content
    (lines, unstripped). Sections not present in the body are absent
    from the dict.
    """
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def rebuild_brain_body(sections: dict[str, str]) -> str:
    """Rebuild a brain body from its section mapping."""
    parts: list[str] = []
    for section_name in (
        BRAIN_SECTION_FOCUS,
        BRAIN_SECTION_OBJECTIVES,
        BRAIN_SECTION_SESSIONS,
        BRAIN_SECTION_HANDOFFS,
        BRAIN_SECTION_PULSE,
        BRAIN_SECTION_LESSONS,
        BRAIN_SECTION_ACTIVE_CONTEXT,
        BRAIN_SECTION_RISKS,
        BRAIN_SECTION_CONCURRENCY,
    ):
        if section_name in sections:
            parts.append(f"# {section_name}")
            parts.append("")
            parts.append(sections[section_name].strip())
            parts.append("")
    return "\n".join(parts).strip() + "\n"


# --- Discovery -------------------------------------------------------------

@dataclass
class WorkspaceRoot:
    path: Path
    manifest: dict[str, Any] = field(default_factory=dict)


def find_workspace_root(start: Path | str | None = None) -> Path | None:
    """Walk up from `start` (default: cwd) looking for `.<product>/manifest.cortex`."""
    cursor = Path(start or os.getcwd()).resolve()
    target_dir = ARQUX_DIR
    target_file = MANIFEST_CORTEX

    while True:
        candidate = cursor / target_dir / target_file
        if candidate.exists():
            return cursor / target_dir
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


def find_project_root(start: Path | str | None = None) -> Path | None:
    """Find a project-level `.<product>/` directory (must contain brain.cortex)."""
    cursor = Path(start or os.getcwd()).resolve()
    target_dir = ARQUX_DIR

    while True:
        candidate = cursor / target_dir / BRAIN_CORTEX
        if candidate.exists():
            return cursor / target_dir
        if cursor.parent == cursor:
            return None
        cursor = cursor.parent


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


def read_brain(project_root: Path) -> tuple[dict[str, Any], dict[str, str], str]:
    """Read the project brain.

    Returns (frontmatter, sections, raw_body).
    `sections` is a dict mapping section name → raw text content.
    """
    brain_path = project_root / BRAIN_CORTEX
    if not brain_path.exists():
        return {}, {}, ""
    fm, body = parse_cortex_file(brain_path)
    sections = parse_brain_sections(body)
    return fm, sections, body


def write_brain_sections(
    project_root: Path,
    frontmatter: dict[str, Any],
    sections: dict[str, str],
) -> tuple[Path, Path]:
    """Write the project brain from frontmatter + sections dict."""
    body = rebuild_brain_body(sections)
    return write_cortex_pair(project_root, "brain", frontmatter, body)


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


def append_handoff(
    project_root: Path,
    *,
    from_agent: str,
    to_agent: str,
    task_id: str | None,
    note: str,
) -> str:
    """Append a handoff entry to the brain's HANDOFFS section.

    Returns the rendered handoff line.
    """
    fm, sections, _ = read_brain(project_root)
    ts = _now_iso()
    line = f"- [{ts}] {from_agent} -> {to_agent} task={task_id or '-'} :: {note}"
    append_to_brain_section(sections, BRAIN_SECTION_HANDOFFS, line)
    # Bump concurrency version.
    _bump_concurrency(fm, from_agent)
    write_brain_sections(project_root, fm, sections)
    return line


def append_pulse_to_brain(
    project_root: Path,
    *,
    event_id: str,
    task_id: str | None,
    kind: str,
    agent: str,
    payload: str,
    cycle: str | None = None,
) -> str:
    """Append a pulse entry to the brain's PULSE section.

    Returns the rendered pulse line.
    """
    fm, sections, _ = read_brain(project_root)
    ts = _now_iso()
    cycle_part = f" cycle={cycle}" if cycle else ""
    line = (
        f"- [{ts}] id={event_id} task={task_id or '-'} kind={kind}{cycle_part} "
        f"agent={agent} :: {payload}"
    )
    append_to_brain_section(sections, BRAIN_SECTION_PULSE, line)
    _bump_concurrency(fm, agent)
    write_brain_sections(project_root, fm, sections)
    return line


def read_pulse_from_brain(
    project_root: Path,
    *,
    task_id: str | None = None,
    cycle: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Read pulse entries from the brain's PULSE section.

    Each entry is returned as a dict with parsed fields:
        {ts, id, task, kind, cycle, agent, payload}
    """
    _, sections, _ = read_brain(project_root)
    raw = sections.get(BRAIN_SECTION_PULSE, "")
    entries: list[dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        entry = _parse_pulse_line(line)
        if not entry:
            continue
        if task_id and entry.get("task") != task_id:
            continue
        if cycle and entry.get("cycle") != cycle:
            continue
        if since and entry.get("ts", "") < since:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries


def _parse_pulse_line(line: str) -> dict[str, str] | None:
    """Parse a single pulse line: '- [ts] id=... task=... kind=... ... :: payload'."""
    m = re.match(
        r"^- \[(?P<ts>[^\]]+)\] id=(?P<id>\S+) task=(?P<task>\S+) kind=(?P<kind>\S+)"
        r"(?: cycle=(?P<cycle>\S+))? agent=(?P<agent>\S+) :: (?P<payload>.*)$",
        line,
    )
    if not m:
        return None
    entry: dict[str, str] = {
        "ts": m.group("ts"),
        "id": m.group("id"),
        "task": m.group("task"),
        "kind": m.group("kind"),
        "agent": m.group("agent"),
        "payload": m.group("payload"),
    }
    if m.group("cycle"):
        entry["cycle"] = m.group("cycle")
    return entry


def read_handoffs(
    project_root: Path,
    *,
    agent: str | None = None,
    task_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Read handoff entries from the brain's HANDOFFS section."""
    _, sections, _ = read_brain(project_root)
    raw = sections.get(BRAIN_SECTION_HANDOFFS, "")
    entries: list[dict[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        m = re.match(
            r"^- \[(?P<ts>[^\]]+)\] (?P<from>\S+) -> (?P<to>\S+) task=(?P<task>\S+) :: (?P<note>.*)$",
            line,
        )
        if not m:
            continue
        entry = {
            "ts": m.group("ts"),
            "from": m.group("from"),
            "to": m.group("to"),
            "task": m.group("task"),
            "note": m.group("note"),
        }
        if agent and agent not in (entry["from"], entry["to"]):
            continue
        if task_id and entry["task"] != task_id:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries


# --- Concurrency: optimistic locking on the brain ---------------------------
#
# Multiple agents may read/write the brain concurrently. We use an optimistic
# lock: every mutation bumps a `brain_version` counter in the frontmatter and
# records the last writer. If a writer reads an old version and tries to
# write, the handler should re-read and retry. In this minimal implementation
# we just bump the version on every write — full retry logic is the handler's
# responsibility.


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


def next_pulse_event_id(project_root: Path) -> str:
    """Generate the next pulse event ID (E-NNNN) based on existing pulse entries."""
    entries = read_pulse_from_brain(project_root, limit=10_000)
    if not entries:
        return "E-0001"
    # Find the max numeric suffix.
    max_n = 0
    for e in entries:
        try:
            n = int(e.get("id", "E-0000").removeprefix("E-"))
            max_n = max(max_n, n)
        except ValueError:
            continue
    return f"E-{max_n + 1:04d}"


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
    body = _initial_brain_body()
    return write_cortex_pair(project_root, "brain", brain, body)


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

def add_session_to_brain(
    project_root: Path,
    agent_id: str,
    role: str,
) -> str:
    """Add a session entry to the brain's SESSIONS section."""
    fm, sections, _ = read_brain(project_root)
    ts = _now_iso()
    line = f"- [{ts}] agent={agent_id} role={role} status=active"
    append_to_brain_section(sections, BRAIN_SECTION_SESSIONS, line)
    _bump_concurrency(fm, agent_id)
    write_brain_sections(project_root, fm, sections)
    return line


def remove_session_from_brain(
    project_root: Path,
    agent_id: str,
) -> str:
    """Remove a session entry from the brain's SESSIONS section."""
    fm, sections, _ = read_brain(project_root)
    sessions = sections.get(BRAIN_SECTION_SESSIONS, "")
    kept: list[str] = []
    removed = False
    for line in sessions.splitlines():
        if f"agent={agent_id}" in line and "status=active" in line:
            # Mark as released instead of deleting — preserves history.
            ts = _now_iso()
            kept.append(line.replace("status=active", f"status=released ts={ts}"))
            removed = True
        else:
            kept.append(line)
    sections[BRAIN_SECTION_SESSIONS] = "\n".join(kept).strip()
    _bump_concurrency(fm, agent_id)
    write_brain_sections(project_root, fm, sections)
    return "removed" if removed else "not_found"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
