# SPDX-License-Identifier: MPL-2.0
"""ArqUX HCORTEX-READ renderer (BLP-005).

Native reimplementation of the codec-cortex READ renderer semantics over
:mod:`arqux.cortex.model`.  Produces the human-friendly Markdown view:
profile declaration first, P0→P5 ordering, per-entry rendering by shape,
explicit omission table.  ``roundtrip: false`` — this view is not
reversible by design.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .model import CortexDocument, Entry, Glossary

HCORTEX_READ_HEADER = "<!-- cortex-render: hcortex-read; roundtrip: false -->"

PLEVEL_ORDER = ["P0", "P1", "P2", "P3", "P4", "P5"]

SURVIVE_TO_PLEVEL = {
    "min": "P0",
    "recovery": "P1",
    "work": "P2",
    "full": "P5",
}

SIGIL_DEFAULT_PLEVEL = {
    "FCS": "P0", "OBJ": "P0", "STP": "P0", "CNST": "P0",
    "WRK": "P1", "AUD": "P1", "RSK": "P1", "NXT": "P1",
    "CLAIM": "P2", "LIM": "P2", "KNW": "P2", "LNG": "P2",
    "SES": "P3", "STAT": "P3", "REF": "P4", "DIAG": "P5",
    "TAG": "P5", "IDN": "P2", "DOM": "P2", "AXM": "P0", "!": "P0",
    "HDL": "P3", "PFL": "P2", "DEP": "P3", "DESC": "P4", "ERR": "P1",
}

SECTION_TITLES = {
    "$0": "Glossary (omitted)", "$1": "Identity", "$2": "Active Work",
    "$3": "Governance", "$4": "Rules", "$5": "Risks & Limits",
    "$6": "Diagrams", "$7": "Field Contracts", "$8": "Survival & Priorities",
    "$9": "Context Profiles", "$10": "Degradation Policy",
}

SIGIL_NAMES = {
    "IDN": "Identity", "DOM": "Domain", "AXM": "Axiom",
    "CNST": "Constraint", "FCS": "Focus", "OBJ": "Objective",
    "WRK": "Work State", "STP": "Next Step", "NXT": "Queued Action",
    "RSK": "Risk", "AUD": "Audit", "STAT": "Status", "REF": "Reference",
    "KNW": "Knowledge", "SES": "Session", "LNG": "Lesson",
    "DIAG": "Diagram", "CLAIM": "Claim", "LIM": "Limit",
    "HDL": "Handler", "TAG": "Tag", "PFL": "Pitfall", "DEP": "Dependency",
    "DESC": "Description", "ERR": "Error", "!": "Rule",
}

MODE_PROFILE_ALIAS = {"RECOVERY": "RECOVERY", "FULL": "FULL"}


@dataclass(frozen=True)
class Profile:
    name: str
    plevels: tuple[str, ...]
    token_budget: int | None = None

    def includes(self, plevel: str) -> bool:
        return plevel in self.plevels


PROFILES: dict[str, Profile] = {
    "MIN":      Profile("MIN",      ("P0",),              512),
    "RECOVERY": Profile("RECOVERY", ("P0", "P1"),        1024),
    "WORK":     Profile("WORK",     ("P0", "P1", "P2"),  3072),
    "FULL":     Profile("FULL",     tuple(PLEVEL_ORDER), None),
}
DEFAULT_PROFILE = "WORK"


def resolve_profile(name: str | None = None) -> Profile:
    if name is None:
        return PROFILES[DEFAULT_PROFILE]
    key = name.upper()
    if key not in PROFILES:
        raise ValueError(
            f"unknown HCORTEX profile {name!r}; "
            f"expected one of {sorted(PROFILES)}")
    return PROFILES[key]


def _escape_string(s: str) -> str:
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    return f'"{out}"'


def serialize_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _escape_string(value)
    if value is None:
        return '""'
    return _escape_string(json.dumps(value, ensure_ascii=False))


def classify_entry(entry: Entry) -> str:
    if isinstance(entry.value, dict):
        survive = entry.value.get("survive")
        if isinstance(survive, str) and survive in SURVIVE_TO_PLEVEL:
            return SURVIVE_TO_PLEVEL[survive]
        if entry.value.get("severity") == "blocking":
            return "P0"
    return SIGIL_DEFAULT_PLEVEL.get(entry.sigil, "P5")


def _plevel_rank(plevel: str) -> int:
    return PLEVEL_ORDER.index(plevel) if plevel in PLEVEL_ORDER else len(PLEVEL_ORDER)


@dataclass
class ProfileFilterResult:
    kept: list[tuple[str, Entry, str]]
    omitted: list[tuple[str, Entry, str, str]]


def filter_by_profile(doc: CortexDocument, profile: Profile) -> ProfileFilterResult:
    kept: list[tuple[str, Entry, str]] = []
    omitted: list[tuple[str, Entry, str, str]] = []
    for sec in doc.sections:
        if sec.id == "$0":
            continue
        for entry in sec.entries:
            plevel = classify_entry(entry)
            if profile.includes(plevel):
                kept.append((sec.id, entry, plevel))
            else:
                omitted.append((sec.id, entry, plevel,
                                f"excluded by profile {profile.name}"))
    kept.sort(key=lambda t: _plevel_rank(t[2]))
    return ProfileFilterResult(kept=kept, omitted=omitted)


def sort_by_plevel(entries: list[tuple[str, Entry, str]]
                   ) -> list[tuple[str, Entry, str]]:
    return sorted(entries, key=lambda t: _plevel_rank(t[2]))


def render_attrs_table(entry: Entry, with_source: bool = False) -> list[str]:
    if with_source:
        lines = ["| key | value | source |", "| --- | --- | --- |"]
    else:
        lines = ["| key | value |", "| --- | --- |"]
    rows = list(entry.value.items()) if isinstance(entry.value, dict) \
        else [("value", entry.value)]
    src = f"{entry.sigil}:{entry.name}"
    for k, v in rows:
        val = v.replace("|", "\\|") if isinstance(v, str) else serialize_value(v)
        lines.append(f"| {k} | {val} | `{src}` |" if with_source
                     else f"| {k} | {val} |")
    return lines


def render_cuerpo(entry: Entry) -> list[str]:
    text = str(entry.value or "").rstrip()
    return ["```text", text, "```"] if text else []


def render_bloque(entry: Entry) -> list[str]:
    text = str(entry.value or "").rstrip()
    lang = "puml" if ("@startuml" in text or "@enduml" in text) else "text"
    return [f"```{lang}", text, "```"]


def render_entry(entry: Entry, glossary: Glossary,
                 with_source: bool = False,
                 plevel: str | None = None) -> list[str]:
    out: list[str] = []
    sigil_name = SIGIL_NAMES.get(entry.sigil, entry.sigil)
    header = f"### {sigil_name}: {entry.name}"
    if plevel:
        header += f" <sub>[{plevel}]</sub>"
    elif with_source:
        header += f" <sub>[{entry.sigil}:{entry.name}]</sub>"
    out.append(header)
    out.append("")
    if entry.type in ("attrs", "attrs-pos"):
        out.extend(render_attrs_table(entry, with_source=with_source))
    elif entry.type == "cuerpo":
        if with_source:
            out.append(f"source: `{entry.sigil}:{entry.name}`")
            out.append("")
        out.extend(render_cuerpo(entry))
    elif entry.type == "bloque":
        if with_source:
            out.append(f"source: `{entry.sigil}:{entry.name}`")
            out.append("")
        out.extend(render_bloque(entry))
    elif entry.type == "relación":
        if with_source:
            out.append(f"source: `{entry.sigil}:{entry.name}`")
            out.append("")
        out.append(f"```\n{entry.value}\n```")
    else:
        out.append(str(entry.value))
    out.append("")
    return out


def _render_priority_layout(kept: list[tuple[str, Entry, str]],
                            doc: CortexDocument,
                            audit_mode: bool) -> list[str]:
    out: list[str] = []
    by_plevel: dict[str, list[tuple[str, Entry]]] = {}
    for sec_id, entry, plevel in kept:
        by_plevel.setdefault(plevel, []).append((sec_id, entry))
    for plevel in PLEVEL_ORDER:
        if plevel not in by_plevel:
            continue
        out.append(f"## Priority {plevel}")
        out.append("")
        for sec_id, entry in by_plevel[plevel]:
            out.append(f"<!-- section: {sec_id} · {entry.sigil}:{entry.name} · {plevel} -->")
            out.extend(render_entry(entry, doc.glossary,
                                    with_source=audit_mode, plevel=plevel))
    return out


def render_hcortex_read(
    doc: CortexDocument,
    with_source: bool = False,
    profile: str | None = None,
    mode: str = "READABLE",
    layout: str | None = None,
) -> str:
    """Render ``doc`` as HCORTEX-READ Markdown (codec-compatible)."""
    if mode in MODE_PROFILE_ALIAS:
        profile = profile or MODE_PROFILE_ALIAS[mode]
        if mode == "FULL":
            with_source = True

    prof = resolve_profile(profile)
    audit_mode = (mode.upper() == "AUDIT") or with_source
    audit_mode_str = "AUDIT" if audit_mode else mode.upper()

    if layout is None:
        layout = ("priority" if prof.name in ("MIN", "RECOVERY") or audit_mode
                  else "section")
    layout = layout.lower()

    result = filter_by_profile(doc, prof)
    kept = sort_by_plevel(result.kept)

    out: list[str] = []
    out.append(f"Perfil: CORTEX-{prof.name}")
    out.append(HCORTEX_READ_HEADER)
    out.append("")
    out.append("# HCORTEX-READ")
    out.append("")
    out.append(
        f"> Non-reversible human view. Profile: {prof.name} "
        f"(P-levels: {', '.join(prof.plevels)}). "
        f"Mode: {audit_mode_str}. Layout: {layout}.")
    out.append("")

    # Warn when $0 hides operational entries from this view.
    zero_ops = [
        f"{e.sigil}:{e.name}" for sec in doc.sections if sec.id == "$0"
        for e in sec.entries
        if e.sigil not in {"GSIG", "GTYP", "GMIC", "GCON"}
    ]
    if zero_ops:
        out.append("> ⚠ **WARNING**: $0 contains operational entries that are "
                   "hidden from this view:")
        for op in zero_ops[:10]:
            out.append(f"> - `{op}`")
        if len(zero_ops) > 10:
            out.append(f"> - ... and {len(zero_ops) - 10} more")
        out.append("> Run `cortex verify --strict` to fix "
                   "(E033_ZERO_SECTION_MEMORY_ENTRY).")
        out.append("")

    if layout == "priority":
        out.extend(_render_priority_layout(kept, doc, audit_mode))
    else:
        sections_kept: dict[str, list[tuple[Entry, str]]] = {}
        for sec_id, entry, plevel in kept:
            sections_kept.setdefault(sec_id, []).append((entry, plevel))
        for sec in doc.sections:
            if sec.id == "$0" or sec.id not in sections_kept:
                continue
            title = sec.title or SECTION_TITLES.get(sec.id, sec.id)
            out.append(f"## {sec.id} · {title}")
            out.append("")
            for entry, plevel in sections_kept[sec.id]:
                out.extend(render_entry(entry, doc.glossary,
                                        with_source=audit_mode,
                                        plevel=plevel))

    if result.omitted:
        out.append("## Omissions by profile")
        out.append("")
        out.append(
            f"The following entries were omitted by profile **{prof.name}** "
            f"(allowed P-levels: {', '.join(prof.plevels)}):")
        out.append("")
        out.append("| section | sigil | name | plevel | reason |")
        out.append("| --- | --- | --- | --- | --- |")
        for sec_id, entry, plevel, reason in result.omitted:
            out.append(f"| {sec_id} | {entry.sigil} | {entry.name} "
                       f"| {plevel} | {reason} |")
        out.append("")

    return "\n".join(out).rstrip() + "\n"
