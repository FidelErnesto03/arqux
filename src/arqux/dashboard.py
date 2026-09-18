"""arqux status --dashboard: visual workspace dashboard (BLP-010).

Supports two output formats:
- ``hcortex`` (default): clean markdown for MCP transport and agent consumption.
- ``rich``: ANSI-colored panels for direct CLI terminal usage.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .constants import ARQUX_DIR, META_BRAIN_CORTEX
from .cortex_out import CortexOUT
from .state import find_workspace_root

_HAS_CODEC_CORTEX = False
_cc_parser = None
try:
    import cortex.core.parser as _cc_parser
    _HAS_CODEC_CORTEX = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Data extraction helpers (shared by both renderers)
# ---------------------------------------------------------------------------


def _get_agents_from_meta(ws_root: Path) -> list[dict]:
    """Extract agent IDN entries from meta-brain.cortex."""
    meta_path = ws_root / META_BRAIN_CORTEX
    if not meta_path.exists():
        return []
    text = meta_path.read_text(encoding="utf-8")
    if not _HAS_CODEC_CORTEX or "$0" not in text[:80]:
        return []
    doc = _cc_parser.parse_cortex(text, path=str(meta_path))
    agents = []
    for sec in doc.sections:
        if sec.title and sec.title.upper() == "AGENTS":
            for entry in (sec.entries or []):
                if entry.sigil == "IDN" and hasattr(entry, "value") and isinstance(entry.value, dict):
                    agents.append({
                        "name": entry.name,
                        "role": entry.value.get("role", ""),
                        "status": entry.value.get("status", ""),
                    })
    return agents


def _get_projects_from_meta(ws_root: Path) -> list[dict]:
    """Extract project DOM entries from meta-brain.cortex."""
    meta_path = ws_root / META_BRAIN_CORTEX
    if not meta_path.exists():
        return []
    text = meta_path.read_text(encoding="utf-8")
    if not _HAS_CODEC_CORTEX or "$0" not in text[:80]:
        return []
    doc = _cc_parser.parse_cortex(text, path=str(meta_path))
    projects = []
    seen_names = set()
    for sec in doc.sections:
        for entry in (sec.entries or []):
            if entry.sigil == "DOM" and hasattr(entry, "value") and isinstance(entry.value, dict):
                val = entry.value
                name = val.get("name", entry.name)
                if name in seen_names:
                    continue
                seen_names.add(name)
                projects.append({
                    "name": name,
                    "path": val.get("path", ""),
                    "domain": val.get("domain", ""),
                    "status": val.get("status", ""),
                    "cycle": val.get("cycle", ""),
                    "blueprints_done": val.get("blueprints_done", "0"),
                })
    return projects


def _get_evidence_events(ws_root: Path) -> list[dict]:
    """Read recent evidence from the active project's brain PULSE."""
    project_arqux = ws_root.parent / "ARQUX" / ARQUX_DIR
    brain_path = project_arqux / "brain.cortex"
    if not brain_path.exists():
        return []
    text = brain_path.read_text(encoding="utf-8")
    if not _HAS_CODEC_CORTEX or "$0" not in text[:80]:
        return []
    doc = _cc_parser.parse_cortex(text, path=str(brain_path))
    events = []
    for sec in doc.sections:
        if sec.title and sec.title.upper() in ("PULSE", "STATE"):
            for entry in (sec.entries or []):
                if entry.sigil == "AUD" and hasattr(entry, "value") and isinstance(entry.value, dict):
                    events.append({
                        "id": entry.name,
                        "kind": entry.value.get("kind", ""),
                        "agent": entry.value.get("agent", ""),
                        "result": (entry.value.get("result", "") or entry.value.get("evidence", "") or "")[:80],
                    })
    return events[-5:]


def _color_for_status(status: str) -> str:
    return {"pass": "green", "fail": "red", "warn": "yellow", "ok": "green", "error": "red"}.get(status, "white")


def _count_blueprints(project_path: Path) -> dict[str, int]:
    """Count blueprints by status from a project's cycles directory."""
    arqux_dir = project_path / ARQUX_DIR
    cycles_dir = arqux_dir / "cycles"
    counts: dict[str, int] = {"done": 0, "ready": 0, "in_progress": 0, "draft": 0, "blocked": 0}
    if not cycles_dir.exists():
        return counts
    for cycle_dir in cycles_dir.iterdir():
        blps_dir = cycle_dir / "blueprints"
        if not blps_dir.exists():
            continue
        for blp_file in blps_dir.glob("BLP-*.md"):
            try:
                text = blp_file.read_text(encoding="utf-8")
                status = _extract_frontmatter_status(text)
                if status in counts:
                    counts[status] += 1
                else:
                    counts["draft"] += 1
            except Exception:
                counts["draft"] += 1
    return counts


def _extract_frontmatter_status(text: str) -> str:
    """Extract status from YAML frontmatter."""
    m = re.search(r'^status:\s*["\']?(\w+)["\']?\s*$', text, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r'"status":\s*"(\w+)"', text[:200])
    if m:
        return m.group(1)
    return "draft"


# ---------------------------------------------------------------------------
# Health check parsing (shared)
# ---------------------------------------------------------------------------


def _parse_health_checks(detail: str) -> list[tuple[str, str, str]]:
    """Parse doctor detail lines into (name, status, message) tuples.

    Status is derived from the emoji marker (primary) or text keywords (fallback).
    """
    checks: list[tuple[str, str, str]] = []
    for line in detail.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\s*\[([^\]]+)\]\s+(.+?):\s+(.+)$', line)
        if not m:
            continue
        marker, name, msg = m.group(1), m.group(2), m.group(3)
        if "✅" in marker:
            st = "PASS"
        elif "❌" in marker:
            st = "FAIL"
        elif "⚠" in marker:
            st = "WARN"
        elif "ok" in msg.lower() or "pass" in msg.lower() or "correct" in msg.lower():
            st = "PASS"
        elif "fail" in msg.lower() or "not found" in msg.lower() or "missing" in msg.lower():
            st = "FAIL"
        else:
            st = "WARN"
        checks.append((name, st, msg))
    return checks


# ---------------------------------------------------------------------------
# HCORTEX renderer (markdown — default for MCP)
# ---------------------------------------------------------------------------


def _hcortex_workspace(ws_root: Path, meta_ok: bool) -> str:
    lines = [
        "## Workspace",
        "",
        f"- **Root:** `{ws_root.parent}`",
        f"- **Meta-brain:** {'OK' if meta_ok else 'MISSING'}",
        "- **Governed by:** Arqux",
        "",
    ]
    return "\n".join(lines)


def _hcortex_projects(projects: list[dict]) -> str:
    if not projects:
        return "## Projects\n\n_No projects found_\n"
    lines = ["## Projects", ""]
    lines.append("| Project | Domain | Status | Cycle |")
    lines.append("|---|---|---|---|")
    for p in projects:
        lines.append(f"| {p['name']} | {p.get('domain', '')} | {p.get('status', '')} | {p.get('cycle', '')} |")
    lines.append("")
    return "\n".join(lines)


def _hcortex_agents(agents: list[dict]) -> str:
    if not agents:
        return ""
    lines = ["## Agents", ""]
    lines.append("| Agent | Role | Status |")
    lines.append("|---|---|---|")
    for a in agents:
        lines.append(f"| {a['name']} | {a['role']} | {a['status']} |")
    lines.append("")
    return "\n".join(lines)


def _hcortex_blueprints(projects: list[dict], roots_parent: Path) -> str:
    if not projects:
        return ""
    lines = ["## Blueprints by Status", ""]
    lines.append("| Project | Done | Ready | In Prog. | Draft | Total |")
    lines.append("|---|---|---|---|---|---|")
    for p in projects:
        proj_path = roots_parent / p["name"]
        counts = _count_blueprints(proj_path)
        total = sum(counts.values())
        lines.append(
            f"| {p['name']} | {counts['done']} | {counts['ready']} | "
            f"{counts['in_progress']} | {counts['draft']} | {total} |"
        )
    lines.append("")
    return "\n".join(lines)


def _hcortex_events(events: list[dict]) -> str:
    if not events:
        return "## Recent Events\n\n_No recent events_\n"
    lines = ["## Recent Events", ""]
    lines.append("| ID | Kind | Agent | Detail |")
    lines.append("|---|---|---|---|")
    for ev in reversed(events[-5:]):
        detail = ev["result"][:60].replace("|", "\\|")
        lines.append(f"| {ev['id']} | {ev['kind']} | {ev['agent']} | {detail} |")
    lines.append("")
    return "\n".join(lines)


def _hcortex_health(health: object) -> str:
    passed = health.fields.get("passed", 0)
    failed = health.fields.get("failed", 0)
    warned = health.fields.get("warned", 0)
    detail = health.fields.get("detail", "")
    checks = _parse_health_checks(detail)
    lines = ["## Health", ""]
    if checks:
        lines.append("| Check | Result |")
        lines.append("|---|---|")
        for name, st, _msg in checks:
            lines.append(f"| {name} | {st} |")
        lines.append(f"| **Summary** | {passed} pass, {failed} fail, {warned} warn |")
    else:
        lines.append(f"_{passed} pass, {failed} fail, {warned} warn_")
    lines.append("")
    return "\n".join(lines)


def _build_hcortex(path: str | None = None) -> CortexOUT:
    """Build a HCORTEX (markdown) dashboard of the workspace."""
    ws_root = find_workspace_root(start=path)
    if ws_root is None:
        return CortexOUT.error("workspace not found", code="NOT_FOUND")

    meta_ok = (ws_root / META_BRAIN_CORTEX).exists()
    projects = _get_projects_from_meta(ws_root)
    agents = _get_agents_from_meta(ws_root)
    events = _get_evidence_events(ws_root)
    roots_parent = ws_root.parent

    sections: list[str] = []
    sections.append(_hcortex_workspace(ws_root, meta_ok))
    sections.append(_hcortex_projects(projects))
    agents_md = _hcortex_agents(agents)
    if agents_md:
        sections.append(agents_md)
    bp_md = _hcortex_blueprints(projects, roots_parent)
    if bp_md:
        sections.append(bp_md)
    sections.append(_hcortex_events(events))

    # Health
    try:
        from .doctor import run_all as doctor_run
        health = doctor_run(path=path)
        sections.append(_hcortex_health(health))
    except Exception as exc:
        sections.append(f"## Health\n\n_Unavailable: {exc}_\n")

    full_output = "\n".join(sections)
    return CortexOUT.full(full_output)


# ---------------------------------------------------------------------------
# Rich renderer (ANSI — for CLI terminal)
# ---------------------------------------------------------------------------


def _build_rich(path: str | None = None) -> CortexOUT:
    """Build a Rich (ANSI-colored) dashboard of the workspace."""
    ws_root = find_workspace_root(start=path)
    if ws_root is None:
        return CortexOUT.error("workspace not found", code="NOT_FOUND")

    console = Console(width=120, force_terminal=True)
    out_lines: list[str] = []

    # --- Section 1: Workspace info ---
    meta_ok = (ws_root / META_BRAIN_CORTEX).exists()
    info_table = Table(show_header=False, box=None)
    info_table.add_column("Key", style="cyan")
    info_table.add_column("Value")
    info_table.add_row("Workspace Root", str(ws_root.parent))
    info_table.add_row("Meta-brain", "OK" if meta_ok else "MISSING")
    info_table.add_row("Governed by", "Arqux")
    with console.capture() as capture:
        console.print(Panel(info_table, title="[bold]Workspace[/]", border_style="cyan"))
    out_lines.append(capture.get())

    # --- Section 2: Projects ---
    projects = _get_projects_from_meta(ws_root)
    if projects:
        proj_table = Table(box=None)
        proj_table.add_column("Project", style="cyan")
        proj_table.add_column("Domain")
        proj_table.add_column("Status")
        proj_table.add_column("Cycle")
        for p in projects:
            sc = _color_for_status(p.get("status", ""))
            proj_table.add_row(p["name"], p.get("domain", ""), f"[{sc}]{p.get('status', '')}[/]", p.get("cycle", ""))
        with console.capture() as capture:
            console.print(Panel(proj_table, title="[bold]Projects[/]", border_style="green"))
        out_lines.append(capture.get())
    else:
        with console.capture() as capture:
            console.print(Panel("[yellow]No projects found[/]", title="[bold]Projects[/]", border_style="green"))
        out_lines.append(capture.get())

    # --- Section 3: Agents ---
    agents = _get_agents_from_meta(ws_root)
    if agents:
        ag_table = Table(box=None)
        ag_table.add_column("Agent", style="cyan")
        ag_table.add_column("Role")
        ag_table.add_column("Status")
        for a in agents:
            sc = _color_for_status(a.get("status", ""))
            ag_table.add_row(a["name"], a["role"], f"[{sc}]{a['status']}[/]")
        with console.capture() as capture:
            console.print(Panel(ag_table, title="[bold]Agents[/]", border_style="green"))
        out_lines.append(capture.get())

    # --- Section 4: Blueprints by status ---
    roots_parent = ws_root.parent
    bp_table = Table(box=None)
    bp_table.add_column("Project", style="cyan")
    bp_table.add_column("Done", justify="right")
    bp_table.add_column("Ready", justify="right")
    bp_table.add_column("In Prog.", justify="right")
    bp_table.add_column("Draft", justify="right")
    bp_table.add_column("Total", justify="right")
    for p in projects:
        proj_path = roots_parent / p["name"]
        counts = _count_blueprints(proj_path)
        total = sum(counts.values())
        bp_table.add_row(
            p["name"],
            f"[green]{counts['done']}[/]",
            f"[blue]{counts['ready']}[/]",
            f"[yellow]{counts['in_progress']}[/]",
            str(counts['draft']),
            str(total),
        )
    with console.capture() as capture:
        console.print(Panel(bp_table, title="[bold]Blueprints by Status[/]", border_style="blue"))
    out_lines.append(capture.get())

    # --- Section 5: Recent events ---
    events = _get_evidence_events(ws_root)
    if events:
        ev_table = Table(box=None)
        ev_table.add_column("ID", style="cyan")
        ev_table.add_column("Kind")
        ev_table.add_column("Agent")
        ev_table.add_column("Detail")
        for ev in reversed(events[-5:]):
            ev_table.add_row(ev["id"], ev["kind"], ev["agent"], ev["result"][:60])
        with console.capture() as capture:
            console.print(Panel(ev_table, title="[bold]Recent Events[/]", border_style="magenta"))
        out_lines.append(capture.get())
    else:
        with console.capture() as capture:
            console.print(Panel("[yellow]No recent events[/]", title="[bold]Recent Events[/]", border_style="magenta"))
        out_lines.append(capture.get())

    # --- Section 6: Health ---
    try:
        from .doctor import run_all as doctor_run
        health = doctor_run(path=path)
        passed = health.fields.get("passed", 0)
        failed = health.fields.get("failed", 0)
        warned = health.fields.get("warned", 0)
        h_table = Table(box=None)
        h_table.add_column("Check", style="cyan")
        h_table.add_column("Result")
        detail = health.fields.get("detail", "")
        checks = _parse_health_checks(detail)
        for name, st, _msg in checks:
            color = {"PASS": "green", "FAIL": "red", "WARN": "yellow"}.get(st, "white")
            h_table.add_row(name, f"[{color}]{st}[/]")
        h_table.add_row("Summary", f"{passed} pass, {failed} fail, {warned} warn")
        with console.capture() as capture:
            console.print(Panel(h_table, title="[bold]Health[/]", border_style="yellow"))
        out_lines.append(capture.get())
    except Exception as exc:
        with console.capture() as capture:
            console.print(Panel(f"[yellow]Unavailable: {exc}[/]", title="[bold]Health[/]", border_style="yellow"))
        out_lines.append(capture.get())

    full_output = "\n".join(out_lines)
    return CortexOUT.full(full_output)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dashboard(path: str | None = None, fmt: str = "hcortex") -> CortexOUT:
    """Build a dashboard of the workspace.

    Args:
        path: Starting path for workspace root discovery.
        fmt: Output format — ``"hcortex"`` (markdown, default) or ``"rich"`` (ANSI).
    """
    if fmt == "rich":
        return _build_rich(path=path)
    return _build_hcortex(path=path)
