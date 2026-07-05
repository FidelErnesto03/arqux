"""
Bidirectional format conversion: Arqux internal data model ↔ CODEC-CORTEX.

This module maps Arqux's governance state (brain sections, tasks, manifests)
to/from proper CODEC-CORTEX sigil-based format with $0 glossary.

Design (sigil mapping):

  Arqux Section         → CODEC-CORTEX section + sigil
  ───────────────────────────────────────────────────
  Metadata (fm)         → $1  with IDN:governor{...}
  FOCUS                 → $2  with FCS:current{value:"..."}
  OBJECTIVES            → $3  with OBJ:<name>{goal:"...", status:"..."}
  SESSIONS              → $4  with SES:<agent>{agent:"...", role:"...", joined:"...", status:"..."}
  HANDOFFS              → $5  with HDL:<n>{from:"...", to:"...", task:"...", note:"...", ts:"..."}
  PULSE                 → $6  with AUD:<id>{event_id:"...", task:"...", kind:"...", agent:"...", payload:"..."}
  LESSONS               → $7  with LNG:<name>{context:"...", detail:"..."}
  ACTIVE_CONTEXT        → $8  with WRK:current{cycle:"...", task:"...", writer:"..."}
  RISKS                 → $9  with RSK:<name>{description:"...", mitigation:"...", severity:"..."}
  CONCURRENCY           → $10 with ERR:concurrency{version:"...", last_writer:"...", updated:"..."}

  Task frontmatter      → $1  with WRK:task{id,status,assignee,cycle,complexity,priority,created,updated}
  Task # OBJ            → $2  with OBJ:objective{text:"..."}
  Task # PRE            → $3  with CNST:pre<N>{text:"..."}
  Task # PROC           → $4  with STP:step<N>{action:"..."}
  Task # AC             → $5  with CLAIM:ac<N>{criterion:"..."}
  Task # BLK            → $6  with BLK:blocker{N}{condition:"...", action:"HALT_AND_REPORT"}
  Task # NOTE/EVIDENCE  → $7  with AUD:note{ts:"...", note:"..."} / AUD:evidence{evidence:"..."}

  Manifest metadata     → $1  with IDN:workspace{version,governor,created,status,product}
  Meta-brain            → $1  with KNW:meta{knowledge:[],lessons:[],workspace:"..."}
  Projects index        → $1  with DOM:project<N>{name:"...", path:"..."}
"""

from __future__ import annotations

import re
import time
from typing import Any


# --- Glossary template (injected into every Arqux-governed file) ------------

ARQUX_GLOSSARY = """# -- $0: ARQUX GOVERNANCE GLOSSARY --
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
# relación = canonical type
#
# Micro-glossary:
# cur=current pln=planned fut=future blk=blocked
# min=minimum rec=recovery wrk=work full=full
# ok=success fail=failure part=partial"""


# --- Serialise entry value to CORTEX attrs string ---------------------------

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
            # Escape quotes and backslashes
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{escaped}"')
        elif isinstance(v, (list, tuple)):
            # Store as JSON string
            import json
            escaped = json.dumps(v, ensure_ascii=False).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{escaped}"')
        else:
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{escaped}"')
    return ", ".join(parts)


def _parse_attrs(text: str) -> dict[str, Any]:
    """Parse attrs string back to dict: key:value, key2:\"string\""""
    result: dict[str, Any] = {}
    # Simple attrs parser
    i = 0
    while i < len(text):
        # Skip whitespace and comma
        while i < len(text) and (text[i] in ' ,'):
            i += 1
        if i >= len(text):
            break
        # Read key
        key_start = i
        while i < len(text) and text[i] not in ':., ' and text[i] != ',':
            i += 1
        key = text[key_start:i]
        if i >= len(text) or text[i] != ':':
            break
        i += 1  # skip ':'
        # Read value
        if i < len(text) and text[i] == '"':
            i += 1  # skip opening quote
            val_start = i
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            value = text[val_start:i]
            # Unescape
            value = value.replace('\\"', '"').replace('\\\\', '\\')
            i += 1  # skip closing quote
        else:
            val_start = i
            while i < len(text) and text[i] not in ', ':
                i += 1
            value = text[val_start:i].strip()
            # Try to parse bool/int/float
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
                    pass  # keep as string
        result[key] = value
    return result


def _fmt_entry(sigil: str, name: str, attrs: dict[str, Any]) -> str:
    """Format a single CODEC-CORTEX entry."""
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


# --- Manifest conversion ----------------------------------------------------

def brain_from_model(frontmatter: dict, sections: dict[str, str]) -> str:
    """Convert Arqux brain model (frontmatter + sections dict) to CORTEX text."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    parts = ["$0", "", ARQUX_GLOSSARY, ""]

    # $1: Identity / metadata
    id_attrs = {
        "level": str(frontmatter.get("level", 2)),
        "project": frontmatter.get("project", "unknown"),
        "path": frontmatter.get("path", ""),
        "governor": frontmatter.get("governor", frontmatter.get("brain_last_writer", "anonymous")),
        "created": frontmatter.get("brain_updated", now),
    }
    parts.append(_fmt_section(1, "IDENTITY", [_fmt_entry("IDN", "governor", id_attrs)]))

    # $2: FOCUS
    focus = sections.get("FOCUS", "").strip()
    focus_val = focus if focus and focus != "(one-sentence current focus of the project)" else ""
    parts.append(_fmt_section(2, "FOCUS", [_fmt_entry("FCS", "current", {"what": focus_val, "priority": "medium", "status": "current", "survive": "min"})]))

    # $3: OBJECTIVES
    obj_lines = []
    for line in sections.get("OBJECTIVES", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_', line.split(":")[0].split(" ")[0].lower())[:20] or "obj"
            obj_lines.append(_fmt_entry("OBJ", name, {"goal": line, "status": "current", "success": "", "survive": "work"}))
    parts.append(_fmt_section(3, "OBJECTIVES", obj_lines))

    # $4: SESSIONS
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

    # $5: HANDOFFS
    hdl_lines = []
    for i, line in enumerate(sections.get("HANDOFFS", "").splitlines()):
        m = re.match(r"^-\s*\[([^\]]+)\]\s*(\S+)\s*->\s*(\S+)\s*task=(\S+)\s*::\s*(.*)", line)
        if m:
            parts_val = [m.group(2), m.group(3), m.group(4), m.group(5), m.group(1)]
            hdl_lines.append(f"HDL:h{i+1:03d}{{{' | '.join(parts_val)}}}")
    parts.append(_fmt_section(5, "HANDOFFS", hdl_lines))

    # $6: PULSE
    pulse_lines = []
    for line in sections.get("PULSE", "").splitlines():
        m = re.match(
            r"^-\s*\[([^\]]+)\]\s*id=(\S+)\s*task=(\S+)\s*kind=(\S+)"
            r"(?:\s*cycle=(\S+))?\s*agent=(\S+)\s*::\s*(.*)",
            line,
        )
        if m:
            pulse_lines.append(_fmt_entry("AUD", m.group(2).replace("-", "_"), {
                "event": m.group(2), "evidence": m.group(7), "task": m.group(3),
                "kind": m.group(4), "agent": m.group(6), "result": m.group(7),
                "date": m.group(1).split("T")[0] if "T" in m.group(1) else m.group(1),
            }))
    parts.append(_fmt_section(6, "PULSE", pulse_lines))

    # $7: LESSONS
    lng_lines = []
    for line in sections.get("LESSONS", "").splitlines():
        line = line.strip()
        if line and not line.startswith("(") and not line.startswith("#"):
            name = re.sub(r'[^a-z0-9]', '_', line.split(":")[0].lower())[:20] or "lesson"
            lng_lines.append(_fmt_entry("LNG", name, {"type": "contextual", "cause": "", "lesson": line}))
    parts.append(_fmt_section(7, "LESSONS", lng_lines))

    # $8: ACTIVE_CONTEXT
    active = sections.get("ACTIVE_CONTEXT", "").strip()
    parts.append(_fmt_section(8, "ACTIVE_CONTEXT", [
        _fmt_entry("WRK", "current", {
            "phase": "active",
            "current": active if active and not active.startswith("(") else "",
            "blocked": "no",
            "survive": "work",
        })
    ]))

    # $9: RISKS
    rsk_lines = []
    for line in sections.get("RISKS", "").splitlines():
        if line.strip() and not line.strip().startswith("("):
            rsk_lines.append(_fmt_entry("RSK", "risk", {"description": line.strip(), "mitigation": "", "severity": "medium"}))
    parts.append(_fmt_section(9, "RISKS", rsk_lines))

    # $10: CONCURRENCY
    version = frontmatter.get("brain_version", "0")
    parts.append(_fmt_section(10, "CONCURRENCY", [
        _fmt_entry("ERR", "concurrency", {
            "version": str(version),
            "last_writer": frontmatter.get("brain_last_writer", ""),
            "updated": frontmatter.get("brain_updated", now),
        })
    ]))

    return "\n".join(parts) + "\n"


def manifest_to_cortex(manifest: dict[str, Any]) -> str:
    """Convert manifest dict to CORTEX text."""
    parts = ["$0", "", ARQUX_GLOSSARY, ""]
    parts.append(_fmt_section(1, "WORKSPACE", [
        _fmt_entry("IDN", "workspace", {
            "version": manifest.get("version", "1.0.0"),
            "product": manifest.get("product", "arqux"),
            "governor": manifest.get("governor", "anonymous"),
            "created": manifest.get("created", ""),
            "status": manifest.get("status", "active"),
        })
    ]))
    return "\n".join(parts) + "\n"


def meta_brain_to_cortex(brain: dict[str, Any]) -> str:
    """Convert meta-brain dict to CORTEX text."""
    parts = ["$0", "", ARQUX_GLOSSARY, ""]
    lessons_list = brain.get("lessons", [])
    parts.append(_fmt_section(1, "META-BRAIN", [
        _fmt_entry("KNW", "meta", {
            "topic": "cross-project knowledge",
            "content": f"{len(lessons_list)} lessons, {len(brain.get('knowledge', []))} knowledge items",
            "status": "active",
        })
    ]))
    return "\n".join(parts) + "\n"


def projects_to_cortex(projects: list[dict[str, Any]]) -> str:
    """Convert projects list to CORTEX text."""
    parts = ["$0", "", ARQUX_GLOSSARY, ""]
    entries = []
    for i, p in enumerate(projects):
        entries.append(_fmt_entry("DOM", f"p{i+1:03d}", {
            "name": p.get("name", "?"),
            "path": p.get("path", "?"),
        }))
    parts.append(_fmt_section(1, "PROJECTS", entries))
    return "\n".join(parts) + "\n"


def task_to_cortex(frontmatter: dict[str, Any], body: str) -> str:
    """Convert task frontmatter + body to CORTEX text."""
    parts = ["$0", "", ARQUX_GLOSSARY, ""]

    # $1: Task identity
    parts.append(_fmt_section(1, "TASK", [
        _fmt_entry("WRK", "task", {
            "id": frontmatter.get("id", ""),
            "status": frontmatter.get("status", "draft"),
            "governor": frontmatter.get("governor", ""),
            "assignee": frontmatter.get("assignee", ""),
            "priority": frontmatter.get("priority", "medium"),
            "complexity": frontmatter.get("complexity", "standard"),
            "cycle": frontmatter.get("cycle", ""),
            "created": frontmatter.get("created", ""),
            "updated": frontmatter.get("updated", ""),
        })
    ]))

    # Parse body sections
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

    # $N sections for notes/evidence
    for key in ("NOTE", "EVIDENCE"):
        content = sections.get(key, "")
        if content:
            import json
            parts.append(_fmt_section(sec_num, key, [
                _fmt_entry("AUD", key.lower(), {"text": content})
            ]))
            sec_num += 1

    return "\n".join(parts) + "\n"


def cycle_to_cortex(cycle: dict[str, Any]) -> str:
    """Convert cycle dict to CORTEX text."""
    parts = ["$0", "", ARQUX_GLOSSARY, ""]
    parts.append(_fmt_section(1, "CYCLE", [
        _fmt_entry("WRK", "cycle", {
            "id": cycle.get("id", ""),
            "name": cycle.get("name", "?"),
            "status": cycle.get("status", "open"),
            "created": cycle.get("created", ""),
            "description": cycle.get("description", ""),
        })
    ]))
    return "\n".join(parts) + "\n"


def _parse_task_body(body: str) -> dict[str, str]:
    """Parse task body sections like # OBJ, # PRE, # PROC, # AC, # BLK."""
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
