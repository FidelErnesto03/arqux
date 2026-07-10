"""State persistence and discovery helpers.

The framework persists state via CODEC-CORTEX (`.cortex` + `.md`).
This module provides:
    - Workspace/project root discovery.
    - A thin abstraction over CODEC-CORTEX for read/write/verify.
    - Project brain operations: the single shared mind of a project.
    - Handoff and pulse operations: stored INSIDE the brain, not in separate files.

CODEC-CORTEX is a REQUIRED dependency. If not installed, the framework will
not start. The old YAML-frontmatter fallback is preserved for backward
compatibility with existing `.arqux/` files produced by v1.0.0, but all NEW
files are written in proper CODEC-CORTEX sigil format when available.
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
    META_BRAIN_CORTEX,
    PRODUCT_NAME,
    PRODUCT_NAME_UPPER,
    PROJECTS_CORTEX,
    TASKS_DIR,
    ARQUX_DIR,
)
from . import formats

#: Name of the session context file inside ``.arqux/``.
CONTEXT_CORTEX: str = "context.cortex"

# --- CODEC-CORTEX integration (REQUIRED) -----------------------------------

_HAS_CODEC_CORTEX: bool = False
_codec_cortex = None  # type: ignore[assignment]

try:
    import cortex.core.ast as _cc_ast
    import cortex.core.parser as _cc_parser
    import cortex.core.writer as _cc_writer
    import cortex.core.validator as _cc_validator
    import cortex.crud.mutations as _cc_mutations
    import cortex.crud.selectors as _cc_selectors
    import cortex.crud.transactions as _cc_transactions
    import cortex.hcortex.read_renderer as _cc_renderer
    import cortex.core.lexer as _cc_lexer

    _HAS_CODEC_CORTEX = True
    _codec_cortex = True  # sentinel
except ImportError:
    # Codec-cortex is a hard dependency, but we degrade gracefully for
    # environments where it hasn't been installed yet (e.g. fresh clone).
    _HAS_CODEC_CORTEX = False
    pass


def requires_codec_cortex() -> None:
    """Raise RuntimeError if CODEC-CORTEX is not available."""
    if not _HAS_CODEC_CORTEX:
        raise RuntimeError(
            "CODEC-CORTEX is required. Install with: pip install codec-cortex>=0.4.0"
        )


# --- Generic .cortex file operations -----------------------------------------

def cortex_read(path: str | Path) -> dict:
    """Parse a .cortex file into its AST representation.

    Returns a dict with:
        path: str
        sections: list of {id, title, entries, comments}
        glossary: {sigils, types, micro, contracts}
        content: str (raw text)

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    return {
        "path": str(path),
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "entries": [{"sigil": e.sigil, "name": e.name, "value": e.value} for e in s.entries],
                "comment_count": len(s.comments or []),
            }
            for s in doc.sections
        ],
        "glossary": {
            "sigil_count": len(doc.glossary.sigils) if doc.glossary else 0,
            "type_count": len(doc.glossary.types) if doc.glossary else 0,
        } if doc.glossary else {},
        "content": text,
        "size_bytes": len(text),
    }


def cortex_write(
    path: str | Path,
    content: str,
    *,
    force: bool = False,
) -> dict:
    """Parse *content* as CORTEX text and atomically write to *path*.

    Validates before writing. Returns the write result dict.

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = str(Path(path).resolve())
    doc = _cc_parser.parse_cortex(content, path=path)
    diags = _cc_validator.validate(doc)
    errors = [d for d in diags if d.get("severity") == "error"]
    if errors and not force:
        return {
            "path": path,
            "error": f"Validation failed ({len(errors)} errors). Use force=True to override.",
            "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')} (line {d.get('line','?')})" for d in errors],
        }

    result = _cc_transactions.atomic_write_cortex(doc, path, force=force)
    return {
        "path": path,
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "diagnostics": [str(d) for d in result.diagnostics] if result.diagnostics else [],
        "dry_run": result.dry_run,
    }


def cortex_verify(path: str | Path) -> dict:
    """Verify a .cortex file using CODEC-CORTEX validator.

    Returns a dict with path, valid (bool), diagnostics.

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    diags = _cc_validator.validate(doc)
    errors = [d for d in diags if d.get("severity") == "error"]
    return {
        "path": str(path),
        "valid": len(errors) == 0,
        "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')} (line {d.get('line','?')})" for d in diags],
        "sections": len(doc.sections),
        "entries": sum(len(s.entries) for s in doc.sections),
    }


def cortex_render(path: str | Path) -> str:
    """Render a .cortex file to HCORTEX READ markdown.

    Returns the rendered markdown text.

    Raises RuntimeError if CODEC-CORTEX is not available.
    """
    requires_codec_cortex()
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    return _cc_renderer.render_hcortex_read(doc)


# --- _cortex_crud -- partial file mutation via CODEC-CORTEX CRUD -----------


def _parse_and_mutate(
    path: Path,
    mutate_fn,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Parse a .cortex file, apply *mutate_fn* on the AST, validate and write.

    *mutate_fn* receives the parsed ``CortexDocument`` and returns it (modified).
    """
    requires_codec_cortex()
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    doc = mutate_fn(doc)
    diags = _cc_validator.validate(doc)
    errors = [d for d in diags if d.get("severity") == "error"]
    if errors and not force:
        return {
            "error": f"Validation failed ({len(errors)} errors). Use force=True to override.",
            "diagnostics": [f"[{d.get('code','?')}] {d.get('message','')}" for d in errors],
        }
    if dry_run:
        return {"dry_run": True, "path": str(path), "diagnostics": diags}
    try:
        result = _cc_transactions.atomic_write_cortex(doc, str(path), force=force)
    except Exception as e:
        return {"error": f"Atomic write failed: {e}", "non_bypassable": True}
    return {
        "path": str(path),
        "bytes_written": result.bytes_written,
        "backup": result.backup,
        "diagnostics": [str(d) for d in result.diagnostics] if result.diagnostics else [],
    }


def crud_read(path: str | Path, selector: str) -> dict:
    """Read entries matching *selector* from a .cortex file.

    Returns a dict with ``entries`` (list of matched entries).
    """
    requires_codec_cortex()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))
    sel = _cc_selectors.parse_selector(selector)
    entries = _cc_selectors.select(doc, selector)
    return {
        "path": str(path),
        "selector": selector,
        "entries": [
            {"sigil": e.sigil, "name": e.name, "section": e.section, "value": e.value}
            for e in entries
        ],
    }


def crud_add(
    path: str | Path,
    section: str,
    sigil: str,
    name: str,
    value: str | dict,
    *,
    create_section: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Add an entry to a .cortex file.

    Returns the write result dict.
    """
    p = Path(path)

    def _add(doc):
        _cc_mutations.add_entry(
            doc, section, sigil, name, value,
            create_section=create_section,
        )
        return doc

    return _parse_and_mutate(p, _add, force=force, dry_run=dry_run)


def crud_update(
    path: str | Path,
    selector: str,
    *,
    set_: dict | None = None,
    replace_body: str | None = None,
    append: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Update an entry selected by *selector* in a .cortex file.

    For attrs entries use ``set_`` (dict of key/value pairs to merge).
    For cuerpo/bloque entries use ``replace_body``.
    """
    p = Path(path)

    def _update(doc):
        _cc_mutations.update_entry(
            doc, selector,
            set_=set_, replace_body=replace_body, append=append,
        )
        return doc

    return _parse_and_mutate(p, _update, force=force, dry_run=dry_run)


def crud_delete(
    path: str | Path,
    selector: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete an entry matching *selector* from a .cortex file."""
    p = Path(path)

    def _delete(doc):
        _cc_mutations.delete_entry(doc, selector, force=force)
        return doc

    return _parse_and_mutate(p, _delete, force=force, dry_run=dry_run)


def crud_move(
    path: str | Path,
    selector: str,
    to_section: str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Move an entry from its current section to *to_section*."""
    p = Path(path)

    def _move(doc):
        _cc_mutations.move_entry(doc, selector, to_section)
        return doc

    return _parse_and_mutate(p, _move, force=force, dry_run=dry_run)


def crud_list(
    path: str | Path,
    *,
    section: str | None = None,
    sigil: str | None = None,
) -> dict:
    """List entries in a .cortex file, optionally filtered by section or sigil."""
    requires_codec_cortex()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    doc = _cc_parser.parse_cortex(text, path=str(path))

    sel_parts = []
    if section:
        sel_parts.append(section)
    s = "/".join(sel_parts)
    sep = "/" if s else ""
    if sigil:
        s += f"{sep}{sigil}:*"
    else:
        s += f"{sep}*"
    entries = _cc_selectors.select(doc, s)

    return {
        "path": str(path),
        "entries": [
            {"sigil": e.sigil, "name": e.name, "section": e.section, "value": e.value}
            for e in entries
        ],
    }

def write_cortex_pair(
    directory: Path,
    stem: str,
    frontmatter: dict[str, Any],
    body: str,
) -> tuple[Path, Path]:
    """Write a `.cortex` file.

    Governance files (brain, manifest, meta-brain, projects, cycle, T-NNN)
    are written in canonical CODEC-CORTEX sigil format when the library is
    available. Other files use the legacy YAML frontmatter format.

    HCORTEX .md twins are NOT automatically generated. Request them on demand
    via `cortex.render` MCP handler when the Architect needs human review.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    cortex_path = directory / f"{stem}.cortex"

    # Determine format based on stem.
    if _HAS_CODEC_CORTEX and stem in ("brain", "manifest", "meta-brain", "projects", "cycle"):
        cortex_content = _render_governance_cortex(stem, frontmatter, body)
    elif _HAS_CODEC_CORTEX and stem.startswith("T-"):  # Task files
        cortex_content = formats.task_to_cortex(frontmatter, body)
    else:
        cortex_content = _render_cortex(frontmatter, body)

    cortex_path.write_text(cortex_content, encoding="utf-8")
    return cortex_path, cortex_path  # Backward compat: returns (cortex, cortex)


def _render_governance_cortex(
    stem: str,
    frontmatter: dict[str, Any],
    body: str | dict,
) -> str:
    """Render a governance file in canonical CODEC-CORTEX format.

    Delegates to ``formats.render_governance_cortex()`` which uses
    CODEC-CORTEX's ``write_cortex()`` when available, falling back to
    the string-based builders otherwise.
    """
    return formats.render_governance_cortex(stem, frontmatter, body)


def _write_md_twin(
    cortex_path: Path,
    hcortex_path: Path,
    frontmatter: dict[str, Any],
    body: str,
) -> bool:
    """Write the .md twin. Returns True if CODEC-CORTEX was used."""
    if _HAS_CODEC_CORTEX:
        # Try to parse as proper CORTEX and render.
        try:
            text = cortex_path.read_text(encoding="utf-8")
            doc = _cc_parser.parse_cortex(text, path=str(cortex_path))
            md_content = _cc_renderer.render_hcortex_read(doc)
            hcortex_path.write_text(md_content, encoding="utf-8")
            return True
        except Exception:  # noqa: BLE001
            # Fall through to manual rendering if parse fails (e.g. YAML format).
            pass

    hcortex_content = _render_hcortex(frontmatter, body)
    hcortex_path.write_text(hcortex_content, encoding="utf-8")
    return False


def _render_cortex(frontmatter: dict[str, Any], body: str) -> str:
    """Render a CORTEX file: YAML frontmatter + body with # SECTION markers."""
    lines: list[str] = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_yaml_value(value)}")
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip())
    lines.append("")
    return "\n".join(lines)


def _render_hcortex(frontmatter: dict[str, Any], body: str) -> str:
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
                fm_key = f"sec_{target}"
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

    ctx_path = ws_root / CONTEXT_CORTEX
    if not ctx_path.exists():
        return None

    import re
    raw = ctx_path.read_text(encoding="utf-8")
    m = re.search(r'project_root="([^"]*)"', raw)
    if not m:
        return None

    fallback_root = Path(m.group(1))
    fallback_arqux = fallback_root / ARQUX_DIR / BRAIN_CORTEX
    if fallback_root.exists() and fallback_arqux.exists():
        return fallback_root / ARQUX_DIR
    return None


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
    `sections` is a dict mapping section name → raw text content.
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
            sect_map = {
                "IDENTITY": None,
                "FOCUS": "FOCUS",
                "OBJECTIVES": "OBJECTIVES",
                "SESSIONS": "SESSIONS",
                "HANDOFFS": "HANDOFFS",
                "PULSE": "PULSE",
                "LESSONS": "LESSONS",
                "ACTIVE_CONTEXT": "ACTIVE_CONTEXT",
                "RISKS": "RISKS",
                "KNOWLEDGE": "KNOWLEDGE",
                "CONCURRENCY": None,
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
