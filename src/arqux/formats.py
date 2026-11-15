"""Bidirectional format conversion: Arqux internal data model ↔ CORTEX.

Maps Arqux governance state to/from proper CORTEX sigil format.
BLP-005: All .cortex output uses ArqUX's own string-based builders
(``_fmt_entry``, ``_serialise_attrs``) for canonical formatting —
single-line attrs, body preservation, valid $0 glossary.
No dependency on CODEC-CORTEX writer.

Design (sigil mapping, GRADIENT-12 brain canon):
  ArqUX metadata       → $1 IDENTITY ARQX:artifact{level, name, usage, kind,
                         version, last_writer, updated} for brains; the
                         out-of-band ``$19 ARQUX METADATA`` slot is still
                         emitted for non-brain artifacts (tasks, cycles,
                         manifest). Legacy $0.1 / $15 / $19 slots resolve
                         on read.
  KNOWLEDGE             → $3 KNW:<name>{...}
  RISKS                 → $4 RSK:<name>{...}
  FOCUS                 → $5 FCS:current{...}
  OBJECTIVES            → $6 OBJ:<name>{...}
  ACTIVE_CONTEXT        → $7 WRK:current{...} + HND:<target>{...}
  LESSONS               → $8 LNG:<name>{...}
  LOOPS                 → $9 LOOP:<name>{...}
  SESSIONS              → $10 SES:<agent>{...}
  (legacy HANDOFFS/PULSE/ISSUES sections resolve by title on read; AUD
  events now live in the session timelog ``$5 EVENTS``)

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
from typing import Any

from .constants import (
    W001_NO_METADATA,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactUsage,
    CortexLevel,
)

logger = logging.getLogger(__name__)


# === BLP-041: ARQX metadata sigil ==========================================
#
# Every .cortex file carries an ARQX:artifact entry declaring level (0-3),
# name, usage, and kind. Writers emit it in the canonical ``$19`` out-of-band
# slot (brain canon uses ``$15``, identity artifacts ``$1``); the legacy
# ``$0.1`` sub-section still resolves on read. The ARQX sigil is declared in
# the $0 glossary so the 1.0 parser recognises it as a valid attrs sigil.
#
# Example:
#
#     $0
#
#     # ARQX | artifact | attrs | B | Semantic | ArqUX artifact metadata
#     # IDN  | identity  | attrs | B | Semantic | Actor identity
#     ...
#
#     $19: ARQUX METADATA
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

#: Section header writers emit for ArqUX metadata.
#:
#: ``$19`` is the canonical out-of-band slot for non-brain artifacts (the
#: brain canon reserves ``$15``; identity artifacts embed metadata in ``$1``).
#: ``$0.1`` is the pre-1.0 BLP-041 location: a sub-section of the glossary,
#: chosen so the metadata entry was not part of ``$0`` itself (E033). CORTEX
#: 1.0 forbids that shape (G004 — the glossary may contain only
#: declarations), so it is accepted on read but never emitted on write.
#: See ``_read_arqux_from_ast`` and BLP-001 T-1.17.
_ARQUX_META_SECTION = "$19"
_ARQUX_META_TITLE = "ARQUX METADATA"
_ARQUX_META_SIGIL = "ARQX"
_ARQUX_META_ENTRY = "artifact"

#: Lookup priority for ``ARQX:artifact`` across sections.  ``$0.1`` is the
#: BLP-041 location (pre-1.0), ``$1`` the canonical identity slot, ``$15``
#: the brain-canon slot (cortex-brain-section-canon) and ``$19`` the slot
#: writers emit for non-brain artifacts.  Any other section is still
#: scanned last — metadata resolution is by sigil, never by position.
_ARQUX_META_PRIORITY = {"$0.1": 0, "$1": 1, "$15": 2, "$19": 3}


@dataclass
class CortexArtifact:
    """A parsed .cortex artifact with its metadata and raw payload.

    ``metadata`` is the validated ArtifactMetadata extracted from ARQX:artifact
    (or ArtifactMetadata.default(0) + W001 warning when missing).
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
    """Parse ``text`` and extract ARQX:artifact attrs.

    Resolution is sigil-driven: ``ARQX:artifact`` is accepted in any section,
    preferring canonical slots in ``_ARQUX_META_PRIORITY`` order
    (``$0.1`` legacy → ``$1`` identity → ``$15`` brain canon → ``$19`` writer
    slot). Position-fixed lookup was the silent-degradation trap of audit
    H-08: writers emit ``$15``/``$19``, so a ``$0.1``/``$1``-only reader
    degraded every governed artifact to NIVEL 0.

    Returning None degrades the artifact to NIVEL 0 (W001_NO_METADATA), so a
    silent miss here is a governance failure: BLP-001 T-1.17.

    BLP-005: parsing goes through the ArqUX-owned model
    (:func:`arqux.cortex.model.parse_native`), which binds codec 1.0.x when
    installed and the legacy 0.6.x shape otherwise — metadata resolution is
    governance semantics, never codec-dependent.
    """
    try:
        from .cortex.model import parse_native
        doc = parse_native(text)
        ordered = sorted(
            doc.sections,
            key=lambda sec: _ARQUX_META_PRIORITY.get(
                sec.id, len(_ARQUX_META_PRIORITY)),
        )
        for sec in ordered:
            for entry in sec.entries:
                if (
                    entry.sigil == _ARQUX_META_SIGIL
                    and entry.name == _ARQUX_META_ENTRY
                    and isinstance(entry.value, dict)
                ):
                    return entry.value
    except Exception:
        pass
    # Strict parse failed (e.g. pre-1.0 artifacts carrying ``$0.1``, which the
    # v1 grammar rejects as G004). Fall back to the lenient reader — a
    # malformed-but-metadata-bearing artifact must still resolve its level.
    try:
        from .cortex.reader import cortex_to_dict
        doc = cortex_to_dict(text)
        ordered = sorted(
            doc.get("sections", []),
            key=lambda sec: _ARQUX_META_PRIORITY.get(
                str(sec.get("id")), len(_ARQUX_META_PRIORITY)),
        )
        for sec in ordered:
            if not isinstance(sec, dict):
                continue
            for entry in sec.get("entries", []):
                if not isinstance(entry, dict):
                    continue
                value = entry.get("attrs") or entry.get("value")
                if (
                    entry.get("sigil") == _ARQUX_META_SIGIL
                    and entry.get("name") == _ARQUX_META_ENTRY
                    and isinstance(value, dict)
                ):
                    return value
    except Exception:
        return None
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
    1. Native parser → ARQX:artifact in any section (priority-ordered slots)
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
    """Render the canonical ``$19`` section with ``ARQX:artifact{...}``.

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
    """Return True if the text has ARQX:artifact (any slot, or legacy metadata)."""
    if _read_arqux_from_ast(text) is not None:
        return True
    return _LEGACY_METADATA_RE.search(text) is not None


def read_cortex_artifact(path: str | Path) -> CortexArtifact:
    """Read a .cortex file and return a CortexArtifact.

    Uses ``read_arqux_metadata()`` for metadata extraction (supports both
    ARQX:artifact in any canonical slot and legacy §0 METADATA block).

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
    {"sigil": "HND", "name": "handoff",      "type": "attrs",     "risk": "M", "layer": "Episodic",     "desc": "Pending handoff to another agent"},
    {"sigil": "DEC", "name": "decision",     "type": "attrs",     "risk": "M", "layer": "Episodic",     "desc": "Session decision record"},
    {"sigil": "LOOP","name": "loop",         "type": "attrs",     "risk": "B", "layer": "Working",      "desc": "Autonomous loop declaration"},
    {"sigil": "ISS", "name": "issue",        "type": "attrs",     "risk": "M", "layer": "Episodic",     "desc": "Tracked issue entry"},
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
# AXM   | axiom      | attrs      | H | Prefrontal     | Project behavioral axiom
# IDN   | identity   | attrs      | B | Semantic       | Actor identity
# FCS   | focus      | attrs      | H | Working        | Active attention anchor
# OBJ   | objective  | attrs      | H | Working        | Active goal with success criterion
# WRK   | work       | attrs      | B | Working        | Current execution state
# SES   | session    | attrs      | M | Episodic       | Compressed I/O/R episode
# HDL   | handler    | attrs-pos  | M | Semantic       | Handoff descriptor
# HND   | handoff    | attrs      | M | Episodic       | Pending handoff (state, not file)
# DEC   | decision   | attrs      | M | Episodic       | Session decision (lives in timelog)
# LOOP  | loop       | attrs      | B | Working        | Autonomous loop declaration
# ISS   | issue      | attrs      | M | Episodic       | Tracked issue entry
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

#: Executable sigil declarations generated from ``_SIGIL_DEFS`` (CORTEX 1.0).
#: The strict parser rejects any ``SIGIL:name`` whose sigil is not declared
#: in ``$0`` (I001_UNDECLARED_SYMBOL), and requires the ``$0:format``
#: dialect line (G010_FORMAT_REQUIRED). Builders that emit fresh artifacts
#: must include both — the comment table alone is documentation, not grammar.
_ARQUX_FORMAT_DECL = "$0:format{cortex:1.0, encoding:UTF-8}"


def _sigil_declarations() -> str:
    """Render executable ``SIGIL:name{...}`` declarations for ``_SIGIL_DEFS``.

    Same shape as migrated artifacts carry (e.g. brain.cortex ``$0``):
    ``FCS:focus{type:"attrs", weight:"H", fields:"value:any?", ...}``.
    """
    lines: list[str] = []
    for sdef in _SIGIL_DEFS:
        decl = (
            f'{sdef["sigil"]}:{sdef["name"]}'
            f'{{type:"{sdef["type"]}", weight:"{sdef["risk"]}", '
            f'fields:"value:any?", focus:"value", desc:"{sdef["desc"]}", '
            f'open:true}}'
        )
        if sdef["type"] == "attrs-pos":
            # G022: attrs-pos declarations must carry the positional
            # contract, and focus must name a pos field (G025). HDL
            # entries are emitted as ``HDL:hNNN{from|to|task|desc|date}``.
            decl = decl[:-1] + ', pos:"from:text|to:text|task:text|desc:text|date:text"}'
            decl = decl.replace('focus:"value"', 'focus:"desc"')
        lines.append(decl)
    return "\n\n".join(lines)


def _build_glossary() -> str:
    """Build the full ``$0`` body: format decl + comments + declarations.

    BLP-005: under the CORTEX 1.0 grammar a ``$0`` carrying only the comment
    table produces artifacts the strict parser cannot read back — every
    sigil used must be declared (I001) and the dialect line must be present
    (G010). Fresh governance files now satisfy both requirements.
    """
    return (
        _ARQUX_FORMAT_DECL
        + "\n\n"
        + _ARQUX_GLOSSARY_TEXT
        + "\n\n"
        + _sigil_declarations()
    )


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


def _legacy_entry_name(line: str, fallback: str, seen: dict[str, int]) -> str:
    """Derive a stable, non-empty entry name from a legacy free-text line.

    Returns ``""`` when the line carries no content. A bare bullet used to
    become the name ``_`` and an empty entry (issue 2026-10-26, BLP-024);
    repeated lines used to collide under the same name, so the caller passes
    the same ``seen`` dict to disambiguate them.
    """
    content = line.strip().lstrip("-*").strip()
    if not content:
        return ""
    name = re.sub(r"[^a-z0-9]+", "_", content.split(":")[0].lower()).strip("_")[:20]
    name = name or fallback
    count = seen.get(name, 0) + 1
    seen[name] = count
    return name if count == 1 else f"{name}_{count}"


def render_governance_cortex(stem: str, frontmatter: dict, body: str | dict) -> str:
    """Render governance file as CORTEX text.

    BLP-005: Uses ArqUX's own string-based builders as the primary path.
    The ``_build_fallback`` function calls ``brain_from_model``,
    ``manifest_to_cortex``, etc. which use ``_fmt_entry`` and
    ``_serialise_attrs`` — ArqUX's own serialization primitives.

    No dependency on CODEC-CORTEX writer.
    """
    return _build_fallback(stem, frontmatter, body)


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
    """Append ``$19: ARQUX METADATA`` + ``ARQX:artifact{...}`` to parts list.

    Reads level/name/usage/kind from frontmatter, falls back to defaults.
    ``$19`` is the far-from-zero operational slot (section ordering
    principle); the metadata reader resolves ARQX by sigil regardless.
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
    """Build a brain.cortex in GRADIENT-12 layout from the legacy model.

    Canonical order ($0..$10): IDENTITY carries ``ARQX:artifact`` with the
    concurrency fields (version/last_writer/updated) folded in — no
    ``$15 ARQUX_METADATA`` and no ``$12 CONCURRENCY``. Sections that exist
    only in the legacy model (HANDOFFS, PULSE, ISSUES) are appended after
    ``$10`` under their own titles when they carry content, so a legacy
    import loses nothing and title-based readers still resolve them.
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    parts = ["$0", "", _build_glossary(), ""]
    id_attrs = {
        "level": str(frontmatter.get("level", 2)),
        "project": frontmatter.get("project", "unknown"),
        "path": frontmatter.get("path", ""),
        "governor": frontmatter.get("governor", frontmatter.get("brain_last_writer", "anonymous")),
        "created": frontmatter.get("brain_updated", now),
    }
    version = frontmatter.get("brain_version", "0")
    meta_vals = [
        f"level:{frontmatter.get('level', 2)}",
        f'name:"{frontmatter.get("name", "brain")}"',
        f'usage:"{frontmatter.get("usage", "state")}"',
        f'kind:"{frontmatter.get("kind", "native")}"',
        f'version:"{version}"',
        f'last_writer:"{frontmatter.get("brain_last_writer", "")}"',
        f'updated:"{frontmatter.get("brain_updated", now)}"',
    ]
    parts.append(_fmt_section(1, "IDENTITY", [
        f"ARQX:artifact{{{', '.join(meta_vals)}}}",
        _fmt_entry("IDN", "governor", id_attrs),
    ]))
    # $2: AXIOMS — project behavioral axioms (canon
    # docs/reference/cortex-brain-section-canon.md).
    axm_lines = []
    seen_axioms: dict[str, int] = {}
    for line in sections.get("AXIOMS", "").splitlines():
        line = line.strip()
        if not line or line.startswith("(") or line.startswith("#"):
            continue
        name = _legacy_entry_name(line, "axiom", seen_axioms)
        if not name:
            continue
        axm_lines.append(_fmt_entry("AXM", name, {
            "rule": line, "severity": "blocking", "survive": "min",
        }))
    parts.append(_fmt_section(2, "AXIOMS", axm_lines))
    # $3: KNOWLEDGE
    knw_lines_str = sections.get("KNOWLEDGE", "").strip()
    knw_entries = []
    if knw_lines_str:
        knw_entries.append(_fmt_entry("KNW", "knowledge", {"topic": "project_knowledge", "content": knw_lines_str, "status": "active"}))
    parts.append(_fmt_section(3, "KNOWLEDGE", knw_entries))
    # $4: RISKS
    rsk_lines = []
    seen_risks: dict[str, int] = {}
    for line in sections.get("RISKS", "").splitlines():
        if not line.strip() or line.strip().startswith("("):
            continue
        name = _legacy_entry_name(line, "risk", seen_risks)
        if not name:
            continue
        rsk_lines.append(_fmt_entry("RSK", name, {"description": line.strip(), "mitigation": "", "severity": "medium"}))
    parts.append(_fmt_section(4, "RISKS", rsk_lines))
    # $5: FOCUS
    focus = sections.get("FOCUS", "").strip()
    focus_val = focus if focus and focus != "(one-sentence current focus of the project)" else ""
    parts.append(_fmt_section(5, "FOCUS", [_fmt_entry("FCS", "current", {"what": focus_val, "priority": "medium", "status": "current", "survive": "min"})]))
    # $6: OBJECTIVES
    obj_lines = []
    for line in sections.get("OBJECTIVES", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_', line.split(":")[0].split(" ")[0].lower())[:20] or "obj"
            obj_lines.append(_fmt_entry("OBJ", name, {"goal": line, "status": "current", "success": "", "survive": "work"}))
    parts.append(_fmt_section(6, "OBJECTIVES", obj_lines))
    # $7: ACTIVE_CONTEXT — WRK:current plus HND handoffs (canon destination).
    active = sections.get("ACTIVE_CONTEXT", "").strip()
    ctx_entries = [
        _fmt_entry("WRK", "current", {"phase": "active", "current": active if active and not active.startswith("(") else "", "blocked": "no", "survive": "work"})
    ]
    for line in sections.get("HANDOFFS", "").splitlines():
        m = re.match(r"^-\s*\[([^\]]+)\]\s*(\S+)\s*->\s*(\S+)\s*task=(\S+)\s*::\s*(.*)", line)
        if m:
            ctx_entries.append(_fmt_entry("HND", m.group(3), {
                "from": m.group(2), "to": m.group(3), "task": m.group(4),
                "note": m.group(5), "ts": m.group(1),
            }))
    parts.append(_fmt_section(7, "ACTIVE_CONTEXT", ctx_entries))
    # $8: LESSONS
    lng_lines = []
    seen_lessons: dict[str, int] = {}
    for line in sections.get("LESSONS", "").splitlines():
        line = line.strip()
        if not line or line.startswith("(") or line.startswith("#"):
            continue
        name = _legacy_entry_name(line, "lesson", seen_lessons)
        if not name:
            continue
        lng_lines.append(_fmt_entry("LNG", name, {"type": "contextual", "cause": "", "lesson": line}))
    parts.append(_fmt_section(8, "LESSONS", lng_lines))
    # $9: LOOPS
    parts.append(_fmt_section(9, "LOOPS", []))
    # $10: SESSIONS
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
    parts.append(_fmt_section(10, "SESSIONS", ses_lines))
    # Legacy-only sections survive as titled appendixes when they carry
    # content — title-based readers resolve them regardless of position.
    pulse_lines = []
    for line in sections.get("PULSE", "").splitlines():
        m = re.match(r"^-\s*\[([^\]]+)\]\s*id=(\S+)\s*task=(\S+)\s*kind=(\S+)(?:\s*cycle=(\S+))?\s*agent=(\S+)\s*::\s*(.*)", line)
        if m:
            pulse_lines.append(_fmt_entry("AUD", m.group(2).replace("-", "_"), {
                "event": m.group(2), "evidence": m.group(7), "task": m.group(3),
                "kind": m.group(4), "agent": m.group(6), "result": m.group(7),
                "date": m.group(1).split("T")[0] if "T" in m.group(1) else m.group(1),
            }))
    if pulse_lines:
        parts.append(_fmt_section(11, "PULSE", pulse_lines))
    issues = sections.get("ISSUES", "").strip()
    if issues and not issues.startswith("("):
        parts.append(_fmt_section(12, "ISSUES", [
            _fmt_entry("ISS", f"i{i+1}", {"description": ln.strip()})
            for i, ln in enumerate(issues.splitlines()) if ln.strip()
        ]))
    return "\n".join(parts) + "\n"


def manifest_to_cortex(manifest: dict) -> str:
    parts = ["$0", "", _build_glossary(), ""]
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
    parts = ["$0", "", _build_glossary(), ""]
    _add_arqux_meta_section(parts, brain, "meta-brain")
    lessons = brain.get("lessons", [])
    parts.append(_fmt_section(1, "META-BRAIN", [_fmt_entry("KNW", "meta", {
        "topic": "cross-project knowledge",
        "content": f"{len(lessons)} lessons, {len(brain.get('knowledge', []))} knowledge items",
        "status": "active",
    })]))
    return "\n".join(parts) + "\n"


def projects_to_cortex(projects: list[dict]) -> str:
    parts = ["$0", "", _build_glossary(), ""]
    _add_arqux_meta_section(parts, {"name": "projects", "usage": "state", "kind": "native", "level": 2}, "projects")
    entries = []
    for i, p in enumerate(projects):
        entries.append(_fmt_entry("DOM", f"p{i+1:03d}", {
            "name": p.get("name", "?"), "path": p.get("path", "?"),
        }))
    parts.append(_fmt_section(1, "PROJECTS", entries))
    return "\n".join(parts) + "\n"


def task_to_cortex(frontmatter: dict, body: str) -> str:
    parts = ["$0", "", _build_glossary(), ""]
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
            # OBJ may be a single paragraph or a bulleted list; normalize
            # by stripping bullets and repeated 'text=' prefixes per line.
            obj_lines = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                obj_lines.append(_strip_attr_prefix(line.lstrip("-* "), "text"))
            obj_text = " ".join(obj_lines)
            entry_lines.append(_fmt_entry(sigil, "objective", {"text": obj_text}))
        elif sigil == "STP":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    action = re.sub(r'^\d+\.\s*', '', line)
                    action = _strip_attr_prefix(action, "action")
                    entry_lines.append(_fmt_entry(sigil, f"step{i+1}", {"action": action}))
        elif sigil == "CNST":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    val = line.lstrip("- ")
                    val = _strip_attr_prefix(val, "text")
                    entry_lines.append(_fmt_entry(sigil, f"pre{i+1}", {"text": val}))
        elif sigil == "CLAIM":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    val = line.lstrip("- ")
                    val = _strip_attr_prefix(val, "criterion")
                    entry_lines.append(_fmt_entry(sigil, f"ac{i+1}", {"criterion": val}))
        elif sigil == "BLK":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    cond = _strip_attr_prefix(line.lstrip("- "), "condition")
                    entry_lines.append(_fmt_entry(sigil, f"b{i+1}", {"condition": cond, "action": "HALT_AND_REPORT"}))
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
    parts = ["$0", "", _build_glossary(), ""]
    _add_arqux_meta_section(parts, cycle, cycle.get("id", "cycle"))
    parts.append(_fmt_section(1, "CYCLE", [_fmt_entry("WRK", "cycle", {
        "id": cycle.get("id", ""), "name": cycle.get("name", "?"),
        "status": cycle.get("status", "open"), "created": cycle.get("created", ""),
        "description": cycle.get("description", ""),
    })]))
    return "\n".join(parts) + "\n"


def _cortex_entries(content: str, sigil: str) -> list[dict]:
    """Extract ``SIGIL:name{...}`` entries (parsed attrs) from a body slice."""
    out: list[dict] = []
    for m in re.finditer(rf"\b{re.escape(sigil)}:\w+\{{([^}}]*)\}}", content):
        try:
            out.append(_parse_attrs(m.group(1)))
        except Exception:  # noqa: BLE001
            continue
    return out


def _normalize_section_content(key: str, content: str) -> str:
    """Normalize a task section body to markdown lines the builders accept.

    Handles both markdown bodies (``- value``) and already-serialized CORTEX
    entries (``OBJ:objective{text:"..."}``) so that re-writing a CORTEX task
    heals it instead of dropping the entries (BUG-006 round-trip).
    """
    spec = {"OBJ": ("OBJ", "text"),
            "PRE": ("CNST", "text"),
            "PROC": ("STP", "action"),
            "AC": ("CLAIM", "criterion"),
            "BLK": ("BLK", "condition")}
    if key not in spec:
        return content
    sigil, attr = spec[key]
    vals = [
        _strip_attr_prefix(str(a.get(attr, "")), attr)
        for a in _cortex_entries(content, sigil)
    ]
    vals = [v for v in vals if v]
    if not vals:
        return content
    if key == "OBJ":
        return " ".join(vals)
    if key == "PROC":
        return "\n".join(f"{i + 1}. {v}" for i, v in enumerate(vals))
    return "\n".join(f"- {v}" for v in vals)


def _parse_task_body(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    title_map = {
        "OBJECTIVE": "OBJ", "PRECONDITIONS": "PRE", "PROCEDURE": "PROC",
        "ACCEPTANCE": "AC", "BLOCKERS": "BLK",
        "NOTE": "NOTE", "EVIDENCE": "EVIDENCE",
    }
    current_key: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        if current_key and current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

    for line in body.splitlines():
        md = re.match(r"^#\s*(\w+)", line)
        cx = re.match(r"^\$\d+:\s*([A-Za-z ]+?)\s*$", line)
        if md:
            _flush()
            current_key = md.group(1).upper()
            current_lines = []
        elif cx:
            _flush()
            current_key = title_map.get(cx.group(1).strip().upper())
            current_lines = []
        elif current_key:
            current_lines.append(line)
    _flush()

    for key in list(sections):
        sections[key] = _normalize_section_content(key, sections[key])
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
