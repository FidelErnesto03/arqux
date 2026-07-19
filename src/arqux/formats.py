"""Bidirectional format conversion: Arqux internal data model ↔ CODEC-CORTEX.

Maps Arqux governance state to/from proper CODEC-CORTEX sigil format.
All .cortex output passes through ``cortex.core.writer.write_cortex()`` for
canonical formatting — single-line attrs, body preservation, valid $0 glossary.

Design (sigil mapping):
  ArqUX metadata       → $0.1 ARQX:artifact{level, name, usage, kind}
  FOCUS                 → $2 FCS:current{...}
  OBJECTIVES            → $3 OBJ:<name>{...}
  SESSIONS              → $4 SES:<agent>{...}
  HANDOFFS              → $5 HDL:<n>{...}
  PULSE                 → $6 AUD:<id>{...}
  LESSONS               → $7 LNG:<name>{...}
  ACTIVE_CONTEXT        → $8 WRK:current{...}
  RISKS                 → $9 RSK:<name>{...}
  CONCURRENCY           → $10 ERR:concurrency{...}

  Task frontmatter      → $1 WRK:task{...}
  Task # OBJ            → $2 OBJ:objective{...}
  Task # PRE            → $3 CNST:pre<N>{...}
  Task # PROC           → $4 STP:step<N>{...}
  Task # AC             → $5 CLAIM:ac<N>{...}
  Task # BLK            → $6 BLK:blocker<N>{...}

  Manifest metadata     → $1 IDN:workspace{...}
  Meta-brain            → $1 KNW:meta{...}
  Projects index        → $1 DOM:p<N>{...}
"""
from __future__ import annotations

import contextlib
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cortex.core.ast import Entry

from .constants import (
    W001_NO_METADATA,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactUsage,
    CortexLevel,
)

logger = logging.getLogger(__name__)


# === BLP-041: ARQX metadata sigil in $0.1 ==================================
#
# Every .cortex file carries an ARQX:artifact entry in section $0.1 declaring
# level (0-3), name, usage, and kind. The ARQX sigil is declared in the $0
# pipe-table so CODEC-CORTEX recognises it as a valid attrs sigil.
#
# Example:
#
#     $0
#
#     # ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata
#     # IDN  | identity  | attrs | B | Semantic | Actor identity
#     ...
#
#     $0.1: ARQUX METADATA
#
#     ARQX:artifact{level:3, name:"brain", usage:"state", kind:"native"}
#
# When the entry is missing, read_arqux_metadata() returns ArtifactMetadata.default(0)
# and emits a W001_NO_METADATA warning — the framework degrades gracefully.
#
# Legacy §0 METADATA blocks (# §0 METADATA{...}) are still detected during
# migration via _LEGACY_METADATA_RE as a fallback.

#: Regex matching the legacy §0 METADATA comment block (pre-BLP-041).
_LEGACY_METADATA_RE = re.compile(
    r"#\s*§0\s*METADATA\s*\{(?P<body>[^}]*)\}",
    re.DOTALL,
)

#: Required fields in ARQX:artifact metadata.
_REQUIRED_METADATA_FIELDS: tuple[str, ...] = ("level", "name", "usage", "kind")

#: Section name for ArqUX metadata.
_ARQUX_META_SECTION = "$0.1"
_ARQUX_META_TITLE = "ARQUX METADATA"
_ARQUX_META_SIGIL = "ARQX"
_ARQUX_META_ENTRY = "artifact"


@dataclass
class CortexArtifact:
    """A parsed .cortex artifact with its metadata and raw payload.

    ``metadata`` is the validated ArtifactMetadata extracted from ARQX:artifact
    in ``$0.1`` (or ArtifactMetadata.default(0) + W001 warning when missing).
    ``payload`` is the raw file content as read from disk.
    ``filename`` is the file's stem (e.g. "brain" for "brain.cortex").
    ``path`` is the source path if loaded from disk, else None.
    """
    metadata: ArtifactMetadata
    payload: str
    filename: str = ""
    path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def level(self) -> CortexLevel:
        return self.metadata.level


# ---------------------------------------------------------------------------
# ARQX metadata reader (BLP-041): uses CODEC-CORTEX parser
# ---------------------------------------------------------------------------


def _read_arqux_from_ast(text: str) -> dict[str, Any] | None:
    """Parse ``text`` with CODEC-CORTEX and extract ARQX:artifact attrs.

    Returns the parsed attrs dict, or None if no ARQX:artifact entry found
    in ``$0.1`` (or if CODEC-CORTEX parser is unavailable).
    """
    try:
        from cortex.core.parser import parse_cortex
        doc = parse_cortex(text)
        for sec in doc.sections:
            if sec.id == _ARQUX_META_SECTION:
                for entry in sec.entries:
                    if entry.sigil == _ARQUX_META_SIGIL and entry.name == _ARQUX_META_ENTRY:
                        if isinstance(entry.value, dict):
                            return entry.value
                        return None
        return None
    except Exception:
        return None


def _read_legacy_metadata(text: str) -> dict[str, Any] | None:
    """Fallback: extract metadata from legacy ``# §0 METADATA{...}`` block."""
    match = _LEGACY_METADATA_RE.search(text)
    if not match:
        return None
    body = match.group("body")
    result: dict[str, Any] = {}
    raw_lines = body.split("\n")
    parts: list[str] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if not line:
            continue
        sub_parts = _split_respecting_quotes(line)
        parts.extend(sub_parts)
    for part in parts:
        part = part.strip().rstrip(",").strip()
        if not part:
            continue
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip().rstrip(",").strip()
        if not key:
            continue
        result[key] = _coerce_metadata_value(value)
    return result if result else None


def _coerce_metadata_value(raw: str) -> Any:
    """Coerce a raw metadata value string into a Python value."""
    raw = raw.strip()
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    if raw.isdigit():
        return int(raw)
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    return raw


def _split_respecting_quotes(text: str) -> list[str]:
    """Split ``text`` on commas, respecting quoted substrings."""
    parts: list[str] = []
    buf: list[str] = []
    in_quote = False
    quote_ch = ""
    for ch in text:
        if not in_quote and ch in ('"', "'"):
            in_quote = True
            quote_ch = ch
            buf.append(ch)
        elif in_quote and ch == quote_ch:
            in_quote = False
            quote_ch = ""
            buf.append(ch)
        elif not in_quote and ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def read_arqux_metadata(text: str) -> ArtifactMetadata:
    """Extract ArtifactMetadata from CODEC-CORTEX text.

    Tries:
    1. CODEC-CORTEX parser → ARQX:artifact in $0.1 (BLP-041 format)
    2. Legacy regex → # §0 METADATA{...} (pre-BLP-041 format, for migration)

    Falls back to ``ArtifactMetadata.default(level=0)`` + W001 warning.
    """
    data = _read_arqux_from_ast(text)
    if data is None:
        data = _read_legacy_metadata(text)
    if data is None:
        logger.warning("%s: file lacks ARQX metadata — degrading to NIVEL 0", W001_NO_METADATA)
        return ArtifactMetadata.default(level=0)
    for field_name in _REQUIRED_METADATA_FIELDS:
        if field_name not in data:
            raise ValueError(f"ARQX metadata missing required field: {field_name!r}")
    level_raw = data["level"]
    level_int = int(level_raw) if isinstance(level_raw, str) else int(level_raw)
    if level_int not in {0, 1, 2, 3}:
        raise ValueError(f"Invalid level: {level_int}. Must be 0-3.")
    name = str(data["name"])
    if not name:
        raise ValueError("ARQX metadata field 'name' must be a non-empty string")
    return ArtifactMetadata(
        level=CortexLevel.from_int(level_int),
        name=name,
        usage=ArtifactUsage.from_str(str(data["usage"])),
        kind=ArtifactKind.from_str(str(data["kind"])),
        agent=data.get("agent"),
        source=data.get("source"),
        upstream_version=data.get("upstream_version"),
    )


def render_arqux_section(metadata: ArtifactMetadata) -> str:
    """Render ``$0.1`` section with ``ARQX:artifact{...}`` entry.

    Returns the section text including header and entry.
    """
    d = metadata.to_dict()
    parts_list: list[str] = []
    for key in ("level", "name", "usage", "kind"):
        val = d[key]
        if isinstance(val, str):
            parts_list.append(f'{key}:"{val}"')
        else:
            parts_list.append(f"{key}:{val}")
    for opt_key in ("agent", "source", "upstream_version"):
        val = d.get(opt_key)
        if val is not None:
            parts_list.append(f'{opt_key}:"{val}"')
    body = ", ".join(parts_list)
    entry = f"{_ARQUX_META_SIGIL}:{_ARQUX_META_ENTRY}{{{body}}}"
    header = f"{_ARQUX_META_SECTION}: {_ARQUX_META_TITLE}"
    return f"\n{header}\n\n{entry}\n"


def has_arqux_metadata(text: str) -> bool:
    """Return True if the text has ARQX:artifact in $0.1 (or legacy metadata)."""
    if _read_arqux_from_ast(text) is not None:
        return True
    return _LEGACY_METADATA_RE.search(text) is not None


def read_cortex_artifact(path: str | Path) -> CortexArtifact:
    """Read a .cortex file and return a CortexArtifact.

    Uses ``read_arqux_metadata()`` for metadata extraction (supports both
    BLP-041 ARQX:artifact in $0.1 and legacy §0 METADATA block).

    Returns:
    - ``metadata``: validated ArtifactMetadata (or default(0) + W001)
    - ``payload``: raw file content
    - ``filename``: file stem
    - ``path``: source Path
    - ``warnings``: warning codes (e.g. ``["W001_NO_METADATA"]``)
    """
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    if _read_arqux_from_ast(raw) is not None or _LEGACY_METADATA_RE.search(raw) is not None:
        metadata = read_arqux_metadata(raw)
        warnings = []
    else:
        warnings = [W001_NO_METADATA]
        metadata = ArtifactMetadata.default(level=0)
        logger.warning("%s: %s lacks ARQX metadata — degrading to NIVEL 0", W001_NO_METADATA, p)
    return CortexArtifact(
        metadata=metadata,
        payload=raw,
        filename=p.stem,
        path=p,
        warnings=warnings,
    )


# --- Glossary definitions ---------------------------------------------------

_SIGIL_DEFS: list[dict[str, str]] = [
    {"sigil": "ARQX", "name": "artifact",    "type": "attrs",     "risk": "B", "layer": "Semantic",     "desc": "ArqUX artifact metadata"},
    {"sigil": "IDN", "name": "identity",     "type": "attrs",     "risk": "B", "layer": "Semantic",     "desc": "Actor identity"},
    {"sigil": "FCS", "name": "focus",        "type": "attrs",     "risk": "H", "layer": "Working",      "desc": "Active attention anchor"},
    {"sigil": "OBJ", "name": "objective",    "type": "attrs",     "risk": "H", "layer": "Working",      "desc": "Active goal with success criterion"},
    {"sigil": "WRK", "name": "work",         "type": "attrs",     "risk": "B", "layer": "Working",      "desc": "Current execution state"},
    {"sigil": "SES", "name": "session",      "type": "attrs",     "risk": "M", "layer": "Episodic",     "desc": "Compressed I/O/R episode"},
    {"sigil": "HDL", "name": "handler",      "type": "attrs-pos", "risk": "M", "layer": "Semantic",     "desc": "Handoff descriptor"},
    {"sigil": "AUD", "name": "audit",        "type": "attrs",     "risk": "M", "layer": "Prefrontal",   "desc": "Verification/audit record"},
    {"sigil": "LNG", "name": "lesson",       "type": "attrs",     "risk": "M", "layer": "Episodic",     "desc": "Learned lesson or pattern"},
    {"sigil": "STP", "name": "step",         "type": "attrs",     "risk": "M", "layer": "Working",      "desc": "Task procedure step"},
    {"sigil": "CNST","name": "constraint",   "type": "attrs",     "risk": "H", "layer": "Prefrontal",   "desc": "Hard constraint or precondition"},
    {"sigil": "CLAIM","name": "claim",       "type": "attrs",     "risk": "M", "layer": "Prefrontal",   "desc": "Acceptance criterion"},
    {"sigil": "BLK", "name": "blocker",      "type": "attrs",     "risk": "H", "layer": "Prefrontal",   "desc": "Blocking condition"},
    {"sigil": "RSK", "name": "risk",         "type": "attrs",     "risk": "M", "layer": "Prefrontal",   "desc": "Identified risk with mitigation"},
    {"sigil": "KNW", "name": "knowledge",    "type": "attrs",     "risk": "B", "layer": "Semantic",     "desc": "Stable or promoted knowledge"},
    {"sigil": "DOM", "name": "domain",       "type": "attrs",     "risk": "B", "layer": "Semantic",     "desc": "Project/scope descriptor"},
    {"sigil": "ERR", "name": "error",        "type": "attrs",     "risk": "M", "layer": "Prefrontal",   "desc": "Concurrency / state info"},
    {"sigil": "DESC","name": "description",  "type": "cuerpo",    "risk": "B", "layer": "Semantic",     "desc": "Structured textual description"},
]

_ARQUX_GLOSSARY_TEXT = """# -- $0: ARQUX GOVERNANCE GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# ARQX  | artifact  | attrs      | B | Semantic       | ArqUX artifact metadata
# IDN   | identity   | attrs      | B | Semantic       | Actor identity
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# OBJ   | objective  | attrs      | H | Working        | Active goal with success criterion
# WRK   | work       | attrs      | B | Working        | Current execution state
# SES   | session    | attrs      | M | Episodic       | Compressed I/O/R episode
# HDL   | handler    | attrs-pos  | M | Semantic       | Handoff descriptor
# AUD   | audit      | attrs      | M | Prefrontal     | Verification/audit record
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson or pattern
# STP   | step       | attrs      | M | Working        | Task procedure step
# CNST  | constraint | attrs      | H | Prefrontal     | Hard constraint or precondition
# CLAIM | claim      | attrs      | M | Prefrontal     | Acceptance criterion
# BLK   | blocker    | attrs      | H | Prefrontal     | Blocking condition
# RSK   | risk       | attrs      | M | Prefrontal     | Identified risk with mitigation
# KNW   | knowledge  | attrs      | B | Semantic       | Stable or promoted knowledge
# DOM   | domain     | attrs      | B | Semantic       | Project/scope descriptor
# ERR   | error      | attrs      | M | Prefrontal     | Concurrency / state info
# DESC  | description | cuerpo     | B | Semantic       | Structured textual description
#
# Types:
# bloque = canonical type
# attrs = canonical type
# attrs-pos = canonical type
# cuerpo = canonical type
# relacion = canonical type
#
# Micro-glossary:
# cur=current pln=planned fut=future blk=blocked
# min=minimum rec=recovery wrk=work full=full
# ok=success fail=failure part=partial"""


# --- Helpers -----------------------------------------------------------------

def _build_glossary() -> str:
    """Build $0 glossary section text (injected comment-style)."""
    return _ARQUX_GLOSSARY_TEXT


def _e(name: str, attrs: dict[str, Any]) -> str:
    """Build a single-line CORTEX attrs entry: SIGIL:name{key:val, ...}.

    This is a thin wrapper — the canonical formatter (write_cortex)
    would further normalize this, but for direct use in existing
    _render_governance_cortex in state.py we keep _fmt_entry as-is.
    """
    return _fmt_entry(name.split(":")[0] if ":" in name else name,
                      name.split(":")[1] if ":" in name else name,
                      attrs)


def _fmt_entry(sigil: str, name: str, attrs: dict[str, Any]) -> str:
    """Format a single CODEC-CORTEX entry (serialize attrs to string)."""
    a = _serialise_attrs(attrs)
    return f"{sigil}:{name}{{{a}}}"


def _fmt_section(num: int, title: str, entries: list[str]) -> str:
    """Format a section with entries."""
    lines = [f"\n${num}: {title}", ""]
    if not entries:
        entries = ["# (empty)"]
    for e in entries:
        lines.extend([e, ""])
    return "\n".join(lines)


def _serialise_attrs(d: dict[str, Any]) -> str:
    """Serialise a dict to attrs form: key:value, key2:\"string\"."""
    parts = []
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, bool):
            parts.append(f"{k}:{'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}:{v}")
        elif isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{escaped}"')
        elif isinstance(v, (list, tuple)):
            import json
            escaped = json.dumps(v, ensure_ascii=False).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{escaped}"')
        else:
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{escaped}"')
    return ", ".join(parts)


def _parse_attrs(text: str) -> dict[str, Any]:
    """Parse attrs string back to dict: key:value, key2:\"string\"."""
    result: dict[str, Any] = {}
    i = 0
    while i < len(text):
        while i < len(text) and (text[i] in ' ,'):
            i += 1
        if i >= len(text):
            break
        key_start = i
        while i < len(text) and text[i] not in ':., ' and text[i] != ',':
            i += 1
        key = text[key_start:i]
        if i >= len(text) or text[i] != ':':
            break
        i += 1
        if i < len(text) and text[i] == '"':
            i += 1
            val_start = i
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            value = text[val_start:i]
            value = value.replace('\\"', '"').replace('\\\\', '\\')
            i += 1
        else:
            val_start = i
            while i < len(text) and text[i] not in ', ':
                i += 1
            value = text[val_start:i].strip()
            if value == 'true':
                value = True
            elif value == 'false':
                value = False
            else:
                with contextlib.suppress(ValueError, TypeError):
                    value = float(value) if '.' in value else int(value)
        result[key] = value
    return result


# --- Public conversion API ---------------------------------------------------


def render_governance_cortex(stem: str, frontmatter: dict, body: str | dict) -> str:
    """Render governance file as CORTEX text using the canonical writer.

    Uses ``write_cortex()`` via CortexDocument AST to produce canonical
    single-line attrs with valid $0 glossary.
    Falls back to string-based builders when unavailable.
    """
    try:
        from cortex.core.writer import write_cortex as _wc
        doc = _build_doc(stem, frontmatter, body)
        if doc is not None:
            result = _wc(doc)
            if result:
                return result
    except Exception:
        pass
    return _build_fallback(stem, frontmatter, body)


def _build_doc(stem: str, frontmatter: dict, body):
    """Build a CortexDocument from Arqux model data.

    Returns a document that, when passed to write_cortex(), produces
    canonical single-line attrs with valid $0 glossary.
    """
    from cortex.core.ast import CortexDocument, Section, SigilDef

    doc = CortexDocument()

    # $0 MUST be the first section — write_cortex requires it.
    sec0 = Section(id="$0", title="")
    doc.sections.append(sec0)

    # Populate glossary from Arqux sigil definitions.
    for sdef in _SIGIL_DEFS:
        doc.glossary.add_sigil(SigilDef(
            sigil=sdef["sigil"], name=sdef["name"], type=sdef["type"],
            risk=sdef["risk"], layer=sdef["layer"],
            description=sdef["desc"],
        ))

    # $0.1: ARQUX METADATA — inject ARQX:artifact from frontmatter
    level = frontmatter.get("level", 2)
    name = frontmatter.get("name", stem)
    usage = frontmatter.get("usage", "state")
    kind = frontmatter.get("kind", "native")
    _add_section(doc, "$19", "ARQUX METADATA", [
        _entry("$19", "ARQX", "artifact", {
            "level": level,
            "name": name,
            "usage": usage,
            "kind": kind,
        }),
    ])

    if stem == "brain":
        _build_brain_doc(doc, frontmatter, body)
    elif stem == "manifest":
        _build_manifest_doc(doc, frontmatter)
    elif stem == "meta-brain":
        _build_meta_brain_doc(doc, frontmatter)
    elif stem == "projects":
        _build_projects_doc(doc, frontmatter)
    elif stem.startswith("T-"):
        _build_task_doc(doc, frontmatter, body)
    elif stem == "cycle":
        _build_cycle_doc(doc, frontmatter)
    else:
        return None
    return doc


def _add_section(doc, sec_id: str, title: str, entries: list[Entry]):
    """Add a section to the document."""
    from cortex.core.ast import Section
    sec = Section(id=sec_id, title=title)
    if entries:
        sec.entries = entries
    doc.sections.append(sec)


def _entry(section_id: str, sigil: str, name: str,
           value: dict[str, Any] | str) -> Entry:
    """Create an Entry with proper section reference."""
    from cortex.core.ast import Entry
    if isinstance(value, str):
        # cuerpo type / body
        return Entry(section=section_id, sigil=sigil, name=name,
                     type="cuerpo", value=value)
    return Entry(section=section_id, sigil=sigil, name=name,
                 type="attrs", value=value)


# --- Builders per stem -------------------------------------------------------


def _build_brain_doc(doc, frontmatter, sections_input):
    # Normalize input: accept either sections dict or body string.
    if isinstance(sections_input, str):
        from .state import parse_brain_sections
        sections_input = parse_brain_sections(sections_input) or {}
    sections = sections_input or {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # $1: IDENTITY
    _add_section(doc, "$1", "IDENTITY", [
        _entry("$1", "IDN", "governor", {
            "level": str(frontmatter.get("level", 2)),
            "project": frontmatter.get("project", "unknown"),
            "path": frontmatter.get("path", ""),
            "governor": frontmatter.get("governor",
                       frontmatter.get("brain_last_writer", "anonymous")),
            "created": frontmatter.get("brain_updated", now),
        }),
    ])

    # $2: FOCUS
    focus = (sections or {}).get("FOCUS", "").strip()
    focus_val = (focus if focus and focus != "(one-sentence current focus of the project)"
                 else "Project governance and development")
    _add_section(doc, "$2", "FOCUS", [
        _entry("$2", "FCS", "current", {
            "what": focus_val, "priority": "medium",
            "status": "current", "survive": "work",
        }),
    ])

    # $3: OBJECTIVES
    obj_entries = []
    for line in (sections or {}).get("OBJECTIVES", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_',
                          line.split(":")[0].split(" ")[0].lower())[:20] or "obj"
            obj_entries.append(
                _entry("$3", "OBJ", name, {
                    "goal": line, "status": "current",
                    "success": "", "survive": "work",
                }))
    _add_section(doc, "$3", "OBJECTIVES", obj_entries or [
        _entry("$3", "OBJ", "default", {
            "goal": "Default project objective",
            "status": "current", "success": "verified", "survive": "work",
        }),
    ])

    # $4: SESSIONS
    ses_entries = []
    for line in (sections or {}).get("SESSIONS", "").splitlines():
        m = re.match(r"^-\s*\[([^\]]+)\]\s*agent=(\S+)\s+role=(\S+)(.*)", line)
        if not m:
            continue
        date_val = m.group(1).split("T")[0] if "T" in m.group(1) else m.group(1)
        agent_name = m.group(2).replace("-", "_")
        ses_entries.append(
            _entry("$4", "SES", agent_name, {
                "input": f"session start for {m.group(2)}", "output": "",
                "role": m.group(3),
                "outcome": "active" if "released" not in line else "released",
                "date": date_val,
            }))
    _add_section(doc, "$4", "SESSIONS", ses_entries)

    # $5: HANDOFFS
    hdl_entries = []
    for i, line in enumerate((sections or {}).get("HANDOFFS", "").splitlines()):
        m = re.match(r"^-\s*\[([^\]]+)\]\s*(\S+)\s*->\s*(\S+)\s*task=(\S+)\s*::\s*(.*)", line)
        if m:
            hdl_entries.append(
                _entry("$5", "HDL", f"h{i+1:03d}", {
                    "from": m.group(2), "to": m.group(3),
                    "task": m.group(4), "note": m.group(5),
                    "ts": m.group(1),
                }))
    _add_section(doc, "$5", "HANDOFFS", hdl_entries)

    # $6: PULSE
    pulse_entries = []
    for line in (sections or {}).get("PULSE", "").splitlines():
        m = re.match(
            r"^-\s*\[([^\]]+)\]\s*id=(\S+)\s*task=(\S+)\s*kind=(\S+)"
            r"(?:\s*cycle=(\S+))?\s*agent=(\S+)\s*::\s*(.*)", line)
        if m:
            pulse_entries.append(
                _entry("$6", "AUD", m.group(2).replace("-", "_"), {
                    "event": m.group(2), "evidence": m.group(7),
                    "task": m.group(3), "kind": m.group(4),
                    "agent": m.group(6), "result": m.group(7),
                    "date": (m.group(1).split("T")[0]
                             if "T" in m.group(1) else m.group(1)),
                }))
    _add_section(doc, "$6", "PULSE", pulse_entries)

    # $7: LESSONS
    lng_entries = []
    for line in (sections or {}).get("LESSONS", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_',
                          line.split(":")[0].lower())[:20] or "lesson"
            lng_entries.append(
                _entry("$7", "LNG", name, {
                    "type": "contextual", "cause": "", "lesson": line,
                }))
    _add_section(doc, "$7", "LESSONS", lng_entries)

    # $8: ACTIVE_CONTEXT
    active = (sections or {}).get("ACTIVE_CONTEXT", "").strip()
    _add_section(doc, "$8", "ACTIVE_CONTEXT", [
        _entry("$8", "WRK", "current", {
            "phase": "active",
            "current": active if active and not active.startswith("(") else "Initial cycle",
            "blocked": "no", "survive": "work",
        }),
    ])

    # $9: RISKS
    rsk_entries = []
    for line in (sections or {}).get("RISKS", "").splitlines():
        if line.strip() and not line.strip().startswith("("):
            rsk_entries.append(
                _entry("$9", "RSK", "risk", {
                    "description": line.strip(),
                    "mitigation": "", "severity": "medium",
                }))
    _add_section(doc, "$9", "RISKS", rsk_entries)

    # $10: KNOWLEDGE
    knw_lines = (sections or {}).get("KNOWLEDGE", "").strip()
    knw_entries = []
    if knw_lines:
        knw_entries.append(
            _entry("$10", "KNW", "knowledge", {
                "topic": "project_knowledge",
                "content": knw_lines,
                "status": "active",
            }))
    _add_section(doc, "$10", "KNOWLEDGE", knw_entries)

    # $11: CONCURRENCY
    version = frontmatter.get("brain_version", "0")
    _add_section(doc, "$11", "CONCURRENCY", [
        _entry("$11", "ERR", "concurrency", {
            "version": str(version),
            "last_writer": frontmatter.get("brain_last_writer", ""),
            "updated": frontmatter.get("brain_updated", now),
        }),
    ])


def _build_manifest_doc(doc, manifest):
    _add_section(doc, "$1", "WORKSPACE", [
        _entry("$1", "IDN", "workspace", {
            "version": manifest.get("version", "1.0.0"),
            "product": manifest.get("product", "arqux"),
            "governor": manifest.get("governor", "anonymous"),
            "created": manifest.get("created", ""),
            "status": manifest.get("status", "active"),
        }),
    ])


def _build_meta_brain_doc(doc, brain):
    lessons = brain.get("lessons", [])
    _add_section(doc, "$1", "META-BRAIN", [
        _entry("$1", "KNW", "meta", {
            "topic": "cross-project knowledge",
            "content": (f"{len(lessons)} lessons, "
                        f"{len(brain.get('knowledge', []))} knowledge items"),
            "status": "active",
        }),
    ])


def _build_projects_doc(doc, projects):
    entries = []
    for i, p in enumerate(projects or []):
        entries.append(
            _entry("$1", "DOM", f"p{i+1:03d}", {
                "name": p.get("name", "?"), "path": p.get("path", "?"),
            }))
    _add_section(doc, "$1", "PROJECTS", entries)


def _strip_attr_prefix(value: str, key: str) -> str:
    """Strip a repeated serialized-attr prefix from a value.

    BLP-fix (T-006/G-12): when a CORTEX artifact is re-read and
    re-written, a value that already carries its own serialized
    ``key=`` prefix (e.g. ``"text=Corregir"``) would be wrapped again
    as ``{"text": "text=Corregir"}`` and rendered as
    ``text:"text=Corregir"`` — duplicating the prefix on every
    round-trip. Strip any leading ``key=`` (repeatedly) so re-writes
    stay idempotent.
    """
    if not isinstance(value, str) or not value:
        return value
    # Remove any leading run of "<key>=" and/or bullet markers "- " / "* "
    # (they may be interleaved, e.g. "text=- text=- text=...") so that
    # re-writing an already-normalized value stays idempotent.
    import re
    pattern = re.compile(rf"^(?:{re.escape(key)}=|[*-]\s*)+")
    prev = None
    while prev != value:
        prev = value
        value = pattern.sub("", value)
    return value


def _build_task_doc(doc, fm, body):
    _add_section(doc, "$1", "TASK", [
        _entry("$1", "WRK", "task", {
            "id": fm.get("id", ""), "status": fm.get("status", "draft"),
            "governor": fm.get("governor", ""),
            "assignee": fm.get("assignee", ""),
            "priority": fm.get("priority", "medium"),
            "complexity": fm.get("complexity", "standard"),
            "cycle": fm.get("cycle", ""),
            "created": fm.get("created", ""),
            "updated": fm.get("updated", ""),
        }),
    ])

    sections = _parse_task_body(body)
    sec_num = 2
    sec_map = {
        "OBJ": ("OBJECTIVE", "OBJ"),
        "PRE": ("PRECONDITIONS", "CNST"),
        "PROC": ("PROCEDURE", "STP"),
        "AC": ("ACCEPTANCE", "CLAIM"),
        "BLK": ("BLOCKERS", "BLK"),
    }

    for key, (title, sigil) in sec_map.items():
        content = sections.get(key, "")
        if not content:
            continue
        entries = []
        sid = f"${sec_num}"
        if sigil == "OBJ":
            # OBJ may be a single paragraph or a bulleted list; normalize
            # by stripping bullets and repeated 'text=' prefixes per line.
            obj_lines = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                obj_lines.append(_strip_attr_prefix(line.lstrip("-* "), "text"))
            obj_text = " ".join(obj_lines)
            entries.append(_entry(sid, sigil, "objective", {"text": obj_text}))
        elif sigil == "STP":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    action = re.sub(r'^\d+\.\s*', '', line)
                    action = _strip_attr_prefix(action, "action")
                    entries.append(_entry(sid, sigil, f"step{i+1}",
                                          {"action": action}))
        elif sigil == "CNST":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    val = line.lstrip("- ")
                    val = _strip_attr_prefix(val, "text")
                    entries.append(_entry(sid, sigil, f"pre{i+1}",
                                          {"text": val}))
        elif sigil == "CLAIM":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    val = line.lstrip("- ")
                    val = _strip_attr_prefix(val, "criterion")
                    entries.append(_entry(sid, sigil, f"ac{i+1}",
                                          {"criterion": val}))
        elif sigil == "BLK":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    cond = _strip_attr_prefix(line.lstrip("- "), "condition")
                    entries.append(_entry(sid, sigil, f"b{i+1}", {
                        "condition": cond,
                        "action": "HALT_AND_REPORT",
                    }))
        if entries:
            _add_section(doc, sid, title, entries)
            sec_num += 1

    for key in ("NOTE", "EVIDENCE"):
        content = sections.get(key, "")
        if content:
            sid = f"${sec_num}"
            _add_section(doc, sid, key, [
                _entry(sid, "AUD", key.lower(),
                       {"text": _strip_attr_prefix(content, "text")}),
            ])
            sec_num += 1


def _build_cycle_doc(doc, cycle):
    _add_section(doc, "$1", "CYCLE", [
        _entry("$1", "WRK", "cycle", {
            "id": cycle.get("id", ""), "name": cycle.get("name", "?"),
            "status": cycle.get("status", "open"),
            "created": cycle.get("created", ""),
            "description": cycle.get("description", ""),
        }),
    ])


def _build_fallback(stem: str, frontmatter: dict, body: str) -> str:
    """Fallback string-based builder when write_cortex is unavailable."""
    if stem == "brain":
        return brain_from_model(frontmatter, (body if isinstance(body, dict) else {}))
    if stem == "manifest":
        return manifest_to_cortex(frontmatter)
    if stem == "meta-brain":
        return meta_brain_to_cortex(frontmatter)
    if stem == "projects":
        return projects_to_cortex(frontmatter if isinstance(frontmatter, list) else [])
    if stem.startswith("T-"):
        return task_to_cortex(frontmatter, body if isinstance(body, str) else "")
    if stem == "cycle":
        return cycle_to_cortex(frontmatter)
    return _render_cortex(frontmatter, body if isinstance(body, str) else "")


# --- Legacy string-based builders (fallback) ---------------------------------


def _add_arqux_meta_section(parts: list[str], frontmatter: dict, default_name: str = "artifact") -> None:
    """Append ``$0.1: ARQUX METADATA`` + ``ARQX:artifact{...}`` to parts list.

    Reads level/name/usage/kind from frontmatter, falls back to defaults.
    """
    level = frontmatter.get("level", 2)
    name = frontmatter.get("name", default_name)
    usage = frontmatter.get("usage", "state")
    kind = frontmatter.get("kind", "native")
    vals: list[str] = []
    vals.append(f'level:{level}')
    vals.append(f'name:"{name}"')
    vals.append(f'usage:"{usage}"')
    vals.append(f'kind:"{kind}"')
    parts.append("")
    parts.append("$19: ARQUX METADATA")
    parts.append("")
    parts.append(f"ARQX:artifact{{{', '.join(vals)}}}")
    parts.append("")


def brain_from_model(frontmatter: dict, sections: dict[str, str]) -> str:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    _add_arqux_meta_section(parts, frontmatter, "brain")
    id_attrs = {
        "level": str(frontmatter.get("level", 2)),
        "project": frontmatter.get("project", "unknown"),
        "path": frontmatter.get("path", ""),
        "governor": frontmatter.get("governor", frontmatter.get("brain_last_writer", "anonymous")),
        "created": frontmatter.get("brain_updated", now),
    }
    parts.append(_fmt_section(1, "IDENTITY", [_fmt_entry("IDN", "governor", id_attrs)]))
    focus = sections.get("FOCUS", "").strip()
    focus_val = focus if focus and focus != "(one-sentence current focus of the project)" else ""
    parts.append(_fmt_section(2, "FOCUS", [_fmt_entry("FCS", "current", {"what": focus_val, "priority": "medium", "status": "current", "survive": "min"})]))
    obj_lines = []
    for line in sections.get("OBJECTIVES", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_', line.split(":")[0].split(" ")[0].lower())[:20] or "obj"
            obj_lines.append(_fmt_entry("OBJ", name, {"goal": line, "status": "current", "success": "", "survive": "work"}))
    parts.append(_fmt_section(3, "OBJECTIVES", obj_lines))
    ses_lines = []
    for line in sections.get("SESSIONS", "").splitlines():
        m = re.match(r"^-\s*\[([^\]]+)\]\s*agent=(\S+)\s+role=(\S+)(.*)", line)
        if not m:
            continue
        date_val = m.group(1).split("T")[0] if "T" in m.group(1) else m.group(1)
        agent_name = m.group(2).replace("-", "_")
        ses_lines.append(_fmt_entry("SES", agent_name, {
            "input": f"session start for {m.group(2)}", "output": "",
            "role": m.group(3),
            "outcome": "active" if "released" not in line else "released",
            "date": date_val,
        }))
    parts.append(_fmt_section(4, "SESSIONS", ses_lines))
    hdl_lines = []
    for i, line in enumerate(sections.get("HANDOFFS", "").splitlines()):
        m = re.match(r"^-\s*\[([^\]]+)\]\s*(\S+)\s*->\s*(\S+)\s*task=(\S+)\s*::\s*(.*)", line)
        if m:
            parts_val = [m.group(2), m.group(3), m.group(4), m.group(5), m.group(1)]
            hdl_lines.append(f"HDL:h{i+1:03d}{{{' | '.join(parts_val)}}}")
    parts.append(_fmt_section(5, "HANDOFFS", hdl_lines))
    pulse_lines = []
    for line in sections.get("PULSE", "").splitlines():
        m = re.match(r"^-\s*\[([^\]]+)\]\s*id=(\S+)\s*task=(\S+)\s*kind=(\S+)(?:\s*cycle=(\S+))?\s*agent=(\S+)\s*::\s*(.*)", line)
        if m:
            pulse_lines.append(_fmt_entry("AUD", m.group(2).replace("-", "_"), {
                "event": m.group(2), "evidence": m.group(7), "task": m.group(3),
                "kind": m.group(4), "agent": m.group(6), "result": m.group(7),
                "date": m.group(1).split("T")[0] if "T" in m.group(1) else m.group(1),
            }))
    parts.append(_fmt_section(6, "PULSE", pulse_lines))
    lng_lines = []
    for line in sections.get("LESSONS", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_', line.split(":")[0].lower())[:20] or "lesson"
            lng_lines.append(_fmt_entry("LNG", name, {"type": "contextual", "cause": "", "lesson": line}))
    parts.append(_fmt_section(7, "LESSONS", lng_lines))
    active = sections.get("ACTIVE_CONTEXT", "").strip()
    parts.append(_fmt_section(8, "ACTIVE_CONTEXT", [
        _fmt_entry("WRK", "current", {"phase": "active", "current": active if active and not active.startswith("(") else "", "blocked": "no", "survive": "work"})
    ]))
    rsk_lines = []
    for line in sections.get("RISKS", "").splitlines():
        if line.strip() and not line.strip().startswith("("):
            rsk_lines.append(_fmt_entry("RSK", "risk", {"description": line.strip(), "mitigation": "", "severity": "medium"}))
    parts.append(_fmt_section(9, "RISKS", rsk_lines))
    version = frontmatter.get("brain_version", "0")
    parts.append(_fmt_section(10, "CONCURRENCY", [
        _fmt_entry("ERR", "concurrency", {"version": str(version), "last_writer": frontmatter.get("brain_last_writer", ""), "updated": frontmatter.get("brain_updated", now)})
    ]))
    return "\n".join(parts) + "\n"


def manifest_to_cortex(manifest: dict) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    _add_arqux_meta_section(parts, manifest, "manifest")
    parts.append(_fmt_section(1, "WORKSPACE", [_fmt_entry("IDN", "workspace", {
        "version": manifest.get("version", "1.0.0"),
        "product": manifest.get("product", "arqux"),
        "governor": manifest.get("governor", "anonymous"),
        "created": manifest.get("created", ""),
        "status": manifest.get("status", "active"),
    })]))
    return "\n".join(parts) + "\n"


def meta_brain_to_cortex(brain: dict) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    _add_arqux_meta_section(parts, brain, "meta-brain")
    lessons = brain.get("lessons", [])
    parts.append(_fmt_section(1, "META-BRAIN", [_fmt_entry("KNW", "meta", {
        "topic": "cross-project knowledge",
        "content": f"{len(lessons)} lessons, {len(brain.get('knowledge', []))} knowledge items",
        "status": "active",
    })]))
    return "\n".join(parts) + "\n"


def projects_to_cortex(projects: list[dict]) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    _add_arqux_meta_section(parts, {"name": "projects", "usage": "state", "kind": "native", "level": 2}, "projects")
    entries = []
    for i, p in enumerate(projects):
        entries.append(_fmt_entry("DOM", f"p{i+1:03d}", {
            "name": p.get("name", "?"), "path": p.get("path", "?"),
        }))
    parts.append(_fmt_section(1, "PROJECTS", entries))
    return "\n".join(parts) + "\n"


def task_to_cortex(frontmatter: dict, body: str) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    _add_arqux_meta_section(parts, frontmatter, frontmatter.get("id", "task"))
    parts.append(_fmt_section(1, "TASK", [_fmt_entry("WRK", "task", {
        "id": frontmatter.get("id", ""), "status": frontmatter.get("status", "draft"),
        "governor": frontmatter.get("governor", ""), "assignee": frontmatter.get("assignee", ""),
        "priority": frontmatter.get("priority", "medium"), "complexity": frontmatter.get("complexity", "standard"),
        "cycle": frontmatter.get("cycle", ""), "created": frontmatter.get("created", ""),
        "updated": frontmatter.get("updated", ""),
    })]))
    sections = _parse_task_body(body)
    sec_num = 2
    sec_map = {
        "OBJ": ("OBJECTIVE", "OBJ"), "PRE": ("PRECONDITIONS", "CNST"),
        "PROC": ("PROCEDURE", "STP"), "AC": ("ACCEPTANCE", "CLAIM"),
        "BLK": ("BLOCKERS", "BLK"),
    }
    for key, (title, sigil) in sec_map.items():
        content = sections.get(key, "")
        if not content:
            continue
        entry_lines = []
        if sigil == "OBJ":
            entry_lines.append(_fmt_entry(sigil, "objective", {"text": content}))
        elif sigil == "STP":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    action = re.sub(r'^\d+\.\s*', '', line)
                    entry_lines.append(_fmt_entry(sigil, f"step{i+1}", {"action": action}))
        elif sigil == "CNST":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    entry_lines.append(_fmt_entry(sigil, f"pre{i+1}", {"text": line.lstrip("- ")}))
        elif sigil == "CLAIM":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    entry_lines.append(_fmt_entry(sigil, f"ac{i+1}", {"criterion": line.lstrip("- ")}))
        elif sigil == "BLK":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    entry_lines.append(_fmt_entry(sigil, f"b{i+1}", {"condition": line.lstrip("- "), "action": "HALT_AND_REPORT"}))
        if entry_lines:
            parts.append(_fmt_section(sec_num, title, entry_lines))
            sec_num += 1
    for key in ("NOTE", "EVIDENCE"):
        content = sections.get(key, "")
        if content:
            parts.append(_fmt_section(sec_num, key, [_fmt_entry("AUD", key.lower(), {"text": content})]))
            sec_num += 1
    return "\n".join(parts) + "\n"


def cycle_to_cortex(cycle: dict) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    _add_arqux_meta_section(parts, cycle, cycle.get("id", "cycle"))
    parts.append(_fmt_section(1, "CYCLE", [_fmt_entry("WRK", "cycle", {
        "id": cycle.get("id", ""), "name": cycle.get("name", "?"),
        "status": cycle.get("status", "open"), "created": cycle.get("created", ""),
        "description": cycle.get("description", ""),
    })]))
    return "\n".join(parts) + "\n"


def _parse_task_body(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^#\s*(\w+)", line)
        if m:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1)
            current_lines = []
        elif current_key:
            current_lines.append(line)
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def _render_cortex(frontmatter: dict, body: str) -> str:
    """Render legacy YAML-frontmatter format."""
    parts = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (list, tuple)):
            import json
            parts.append(f"{k}: {json.dumps(v)}")
        else:
            parts.append(f"{k}: {v}")
    parts.append("---")
    if body:
        parts.append("")
        parts.append(body)
    return "\n".join(parts) + "\n"
