"""REQ-11: ``arqux evidence export`` — signed evidence bundles.

Packs execution spans from ``.arqux/timelog/SES*.cortex`` — identity, skill,
files touched, timestamps, per-timelog SHA-256 — into a single
``bundle.cortex``. Chat transcripts, personal prompts and proprietary source
never leave the workspace: entries marked ``visibility:"private"`` are
excluded unless explicitly overridden.

Flag contract (spec §REQ-11):
- ``--allow-raw``      export private-marked entries verbatim (audit use)
- ``--redact-private`` strip private-marked entries, record the count
- neither + private present → export BLOCKED (explicit human decision required)
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .constants import ARQUX_DIR

_ENTRY_RX = re.compile(r"^([A-Z]{2,4}):(\w+)\{(.*)\}\s*$")
_PRIVATE_RX = re.compile(r'visibility:"private"')
_EVENT_SIGILS = ("AUD", "DEC", "ERR", "LOOP")

_BUNDLE_CONTRACTS = [
    'ARQX:arqx_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"ArqUX artifact metadata", open:true}',
    'EVD:evd_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Evidence bundle", open:true}',
    'SPN:spn_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Execution span", open:true}',
    'AUD:aud_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Audit event", open:true}',
    'DEC:dec_contract{type:"attrs", weight:"M", focus:"value", fields:"value:any?", desc:"Decision event", open:true}',
    'ERR:err_contract{type:"attrs", weight:"H", focus:"value", fields:"value:any?", desc:"Error event", open:true}',
    'LOOP:loop_contract{type:"attrs", weight:"B", focus:"value", fields:"value:any?", desc:"Loop event", open:true}',
]


def _session_spans(timelog: Path) -> list[str]:
    """SPN line(s) describing the session span inside a timelog."""
    digest = hashlib.sha256(timelog.read_bytes()).hexdigest()[:16]
    agent = opened = closed = ""
    for line in timelog.read_text(encoding="utf-8").splitlines():
        m = _ENTRY_RX.match(line.strip())
        if not m:
            continue
        sigil, _, attrs = m.groups()
        if sigil == "SES":
            agent = agent or (re.search(r'agent:"([^"]*)"', attrs) or [None, ""])[1]
        opened = opened or (re.search(r'(?:opened|ts|started):"([^"]*)"', attrs) or [None, ""])[1]
        closed = closed or (re.search(r'closed:"([^"]*)"', attrs) or [None, ""])[1]
    ses_id = timelog.stem.split("_", 1)[0]
    return [
        f'SPN:{ses_id.lower()}{{session:"{ses_id}", identity:"{agent}", '
        f'opened:"{opened}", closed:"{closed}", sha256:"{digest}", '
        f'source:"{timelog.name}"}}'
    ]


def _event_lines(timelog: Path) -> tuple[list[str], int]:
    """(exportable event lines, private count) for a timelog."""
    out: list[str] = []
    private = 0
    in_events = False
    for line in timelog.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("$"):
            in_events = stripped.upper().startswith("$5")
            continue
        if not in_events:
            continue
        m = _ENTRY_RX.match(stripped)
        if not m or m.group(1) not in _EVENT_SIGILS:
            continue
        if _PRIVATE_RX.search(stripped):
            private += 1
            continue
        out.append(stripped)
    return out, private


def export_bundle(
    project_root: Path,
    out_path: Path,
    *,
    allow_raw: bool = False,
    redact_private: bool = False,
) -> dict:
    """Build the evidence bundle; returns export stats or raises on block."""
    timelog_dir = Path(project_root) / ARQUX_DIR / "timelog"
    timelogs = sorted(timelog_dir.glob("SES*.cortex")) if timelog_dir.is_dir() else []

    # Scan first: private markings anywhere in the timelogs gate the export.
    private_total = sum(
        1
        for tl in timelogs
        for line in tl.read_text(encoding="utf-8").splitlines()
        if _PRIVATE_RX.search(line)
    )
    if private_total and not (allow_raw or redact_private):
        raise PermissionError(
            f"{private_total} private-marked field(s) found — export blocked. "
            "Pass --redact-private to strip them or --allow-raw to include."
        )

    spans: list[str] = []
    events: list[str] = []
    redacted = 0
    for tl in timelogs:
        spans.extend(_session_spans(tl))
        if allow_raw:
            in_events = False
            for line in tl.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("$"):
                    in_events = stripped.upper().startswith("$5")
                    continue
                if in_events and _ENTRY_RX.match(stripped):
                    events.append(stripped)
        else:
            ev, priv = _event_lines(tl)
            events.extend(ev)
            redacted += priv

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    project = Path(project_root).name
    lines = [
        "$0",
        "",
        "$0:format{cortex:1.0, encoding:UTF-8}",
        "",
        *_BUNDLE_CONTRACTS,
        "",
        "$19: ARQUX METADATA",
        f'ARQX:artifact{{level:0, name:"evidence-{now}", usage:"export", kind:"bundle"}}',
        "",
        "$1: EVIDENCE",
        f'EVD:bundle{{generated:"{now}", project:"{project}", '
        f'spans:{len(spans)}, events:{len(events)}, '
        f'redacted:{redacted}, raw:{str(allow_raw).lower()}}}',
        "",
        "$2: SPANS",
        *spans,
        "",
        "$3: EVENTS",
        *events,
        "",
    ]
    out_path = Path(out_path)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "path": str(out_path),
        "spans": len(spans),
        "events": len(events),
        "redacted": redacted,
        "raw": allow_raw,
    }


__all__ = ["export_bundle"]
