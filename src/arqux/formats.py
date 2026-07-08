"""Bidirectional format conversion: Arqux internal data model ↔ CODEC-CORTEX.

Maps Arqux governance state to/from proper CODEC-CORTEX sigil format.
All .cortex output passes through ``cortex.core.writer.write_cortex()`` for
canonical formatting — single-line attrs, body preservation, valid $0 glossary.

Design (sigil mapping):
  Metadata (fm)         → $1 IDN:governor{...}
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

import re
import time
from typing import Any

# --- Glossary definitions ---------------------------------------------------

_SIGIL_DEFS: list[dict[str, str]] = [
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
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except (ValueError, TypeError):
                    pass
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
    from cortex.core.ast import CortexDocument, Section, Entry, SigilDef

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
            entries.append(_entry(sid, sigil, "objective", {"text": content}))
        elif sigil == "STP":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    action = re.sub(r'^\d+\.\s*', '', line)
                    entries.append(_entry(sid, sigil, f"step{i+1}",
                                          {"action": action}))
        elif sigil == "CNST":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    entries.append(_entry(sid, sigil, f"pre{i+1}",
                                          {"text": line.lstrip("- ")}))
        elif sigil == "CLAIM":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    entries.append(_entry(sid, sigil, f"ac{i+1}",
                                          {"criterion": line.lstrip("- ")}))
        elif sigil == "BLK":
            for i, line in enumerate(content.splitlines()):
                line = line.strip()
                if line and line.startswith("-"):
                    entries.append(_entry(sid, sigil, f"b{i+1}", {
                        "condition": line.lstrip("- "),
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
                _entry(sid, "AUD", key.lower(), {"text": content}),
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


def brain_from_model(frontmatter: dict, sections: dict[str, str]) -> str:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
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
    lessons = brain.get("lessons", [])
    parts.append(_fmt_section(1, "META-BRAIN", [_fmt_entry("KNW", "meta", {
        "topic": "cross-project knowledge",
        "content": f"{len(lessons)} lessons, {len(brain.get('knowledge', []))} knowledge items",
        "status": "active",
    })]))
    return "\n".join(parts) + "\n"


def projects_to_cortex(projects: list[dict]) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
    entries = []
    for i, p in enumerate(projects):
        entries.append(_fmt_entry("DOM", f"p{i+1:03d}", {
            "name": p.get("name", "?"), "path": p.get("path", "?"),
        }))
    parts.append(_fmt_section(1, "PROJECTS", entries))
    return "\n".join(parts) + "\n"


def task_to_cortex(frontmatter: dict, body: str) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
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
            import json
            parts.append(_fmt_section(sec_num, key, [_fmt_entry("AUD", key.lower(), {"text": content})]))
            sec_num += 1
    return "\n".join(parts) + "\n"


def cycle_to_cortex(cycle: dict) -> str:
    parts = ["$0", "", _ARQUX_GLOSSARY_TEXT, ""]
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
