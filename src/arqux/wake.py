"""REQ-08: ``arqux wake --identity <role>`` — ultra-dense boot payload.

Single-shot cortex:1.0 output (<1500 tokens) carrying everything an LLM
agent needs to resume governed work without re-reading the tree:

- ``$1 WAKE``     — identity + project + cycle context
- ``$2 REGISTRY`` — meta-brain project registry (DOM entries, verbatim)
- ``$3 STATE``    — meta-brain WRK:current + project FCS/OBJ anchors
- ``$4 RULES``    — learn-policies rules with their enforce levels
- ``$5 TASK``     — the in-progress governed task, if any

Entries are copied verbatim from their source artifacts wherever possible:
valid syntax by construction and maximum information density.
"""
from __future__ import annotations

import re
from pathlib import Path

from .constants import ARQUX_DIR

_CONTRACTS = {
    "ARQX": 'ARQX:arqx_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"ArqUX artifact metadata", open:true}',
    "IDN": 'IDN:idn_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Identity", open:true}',
    "WRK": 'WRK:wrk_contract{type:"attrs", weight:"B", focus:"value", fields:"value:any?", desc:"Work state", open:true}',
    "DOM": 'DOM:dom_contract{type:"attrs", weight:"B", focus:"value", fields:"value:any?", desc:"Registry domain", open:true}',
    "RUL": 'RUL:rul_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Enforce rule", open:true}',
    "POL": 'POL:pol_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Policy rule", open:true}',
    "GTE": 'GTE:gel_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Mutation gate", open:true}',
    "TSK": 'TSK:tsk_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Task", open:true}',
    "FCS": 'FCS:fcs_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Focus", open:true}',
    "OBJ": 'OBJ:obj_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Objective", open:true}',
}

_ENTRY_RX = re.compile(r"^([A-Z]{2,4}):(\w+)\{.*\}\s*$")
_SECTION_RX = re.compile(r"^\$(\d+)\b")

# Attr keys kept verbatim in dense payloads — everything else is dropped.
_COMPACT_KEEP = {"name", "status", "cycle_status", "last_event", "updated",
                 "enforce", "on", "check", "action", "what", "current", "task",
                 "project", "cycle", "agent", "scope", "state", "pendiente",
                 "blocked", "obj", "task_id", "priority", "assignee",
                 "phase", "survive", "goal", "success"}


def _compact(line: str) -> str:
    """Project an entry onto _COMPACT_KEEP attrs (quote-aware attr split)."""
    m = re.match(r"^([A-Z]{2,4}):(\w+)\{(.*)\}\s*$", line.strip())
    if not m:
        return line
    sigil, name, body = m.groups()
    parts, buf, quoted = [], [], False
    for ch in body:
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    kept = [p.strip() for p in parts
            if p.strip().split(":", 1)[0].strip() in _COMPACT_KEEP]
    return f"{sigil}:{name}{{{', '.join(kept)}}}"


def available_identities(workspace_root: Path) -> list[str]:
    """Identity contract stems under ``<ws>/.arqux/identities/``."""
    ident_dir = Path(workspace_root) / ARQUX_DIR / "identities"
    if not ident_dir.is_dir():
        return []
    return sorted(p.stem for p in ident_dir.glob("*.cortex"))


def _entry_lines(path: Path, sigils: tuple[str, ...], limit: int) -> list[str]:
    """Verbatim entry lines for the given sigils outside ``$0``."""
    if not path.exists():
        return []
    out: list[str] = []
    in_glossary = False
    for line in path.read_text(encoding="utf-8").splitlines():
        sec = _SECTION_RX.match(line.strip())
        if sec:
            in_glossary = sec.group(1) == "0"
            continue
        if in_glossary:
            continue
        m = _ENTRY_RX.match(line.strip())
        if m and m.group(1) in sigils:
            out.append(_compact(line.strip()))
            if len(out) >= limit:
                break
    return out


def _current_cycle(project_root: Path) -> str:
    cycles_dir = Path(project_root) / ARQUX_DIR / "cycles"
    if not cycles_dir.is_dir():
        return "none"
    open_cycles = [
        d.name for d in sorted(cycles_dir.iterdir())
        if d.is_dir() and (d / "MANIFEST.md").exists()
        and 'status: "closed"' not in (d / "MANIFEST.md").read_text(encoding="utf-8", errors="ignore")
    ]
    return open_cycles[-1] if open_cycles else "none"


def _in_progress_task(project_root: Path, cycle_id: str) -> str | None:
    tasks_dir = Path(project_root) / ARQUX_DIR / "cycles" / cycle_id / "tasks"
    if not tasks_dir.is_dir():
        return None
    for f in sorted(tasks_dir.glob("*.cortex")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if _ENTRY_RX.match(line.strip()) and 'status:"in_progress"' in line:
                return _compact(line.strip())
    return None


def wake_payload(
    identity: str,
    workspace_root: Path,
    project_root: Path | None = None,
) -> str:
    """Render the dense wake document for *identity* (valid cortex:1.0)."""
    ws_arqux = Path(workspace_root) / ARQUX_DIR
    meta = ws_arqux / "meta-brain.cortex"

    project = project_root.name if project_root else "none"
    cycle = _current_cycle(project_root) if project_root else "none"

    dom = _entry_lines(meta, ("DOM",), limit=12)
    wrk = _entry_lines(meta, ("WRK",), limit=3)
    rules_src = (project_root / ARQUX_DIR / "learn-policies.cortex"
                 if project_root else None)
    rules = _entry_lines(rules_src, ("RUL", "GTE", "POL"), limit=10) if rules_src else []
    anchors = _entry_lines(
        project_root / ARQUX_DIR / "brain.cortex", ("FCS", "OBJ"), limit=2
    ) if project_root else []
    task = _in_progress_task(project_root, cycle) if project_root else None

    sigils = {"ARQX", "IDN", "WRK", "TSK"} | {l.split(":", 1)[0] for l in dom + rules + anchors}
    out = ["$0", "", "$0:format{cortex:1.0, encoding:UTF-8}", ""]
    out += [_CONTRACTS[s] for s in sorted(sigils) if s in _CONTRACTS]
    out += [
        "",
        "$19: ARQUX METADATA",
        f'ARQX:artifact{{level:0, name:"wake-{identity}", usage:"state", kind:"projection"}}',
    ]

    out += [
        "",
        "$1: WAKE",
        f'IDN:wake{{identity:"{identity}", kind:"generic", '
        f'workspace:"{workspace_root}", project:"{project}", cycle:"{cycle}"}}',
        "",
        "$2: REGISTRY",
        *dom,
        "",
        "$3: STATE",
        *wrk,
        *anchors,
        "",
        "$4: RULES",
        *rules,
        "",
        "$5: TASK",
        task or 'TSK:none{task_id:"none", note:"no in-progress task"}',
        "",
    ]
    return "\n".join(out)


__all__ = ["available_identities", "wake_payload"]
