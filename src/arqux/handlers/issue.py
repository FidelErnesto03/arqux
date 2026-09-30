"""`issue` module — governed lifecycle for the .arqux/issues/ registry (T-027).

Handlers:
    issue.create  — report a new issue (status: open)
    issue.update  — triage / fix / verify an issue (status transitions)
    issue.list    — list issues, optionally filtered by status
    issue.read    — read one issue file verbatim

Separation of responsibilities (Architect directive 2026-09-30): the
validator profile is the AUDITOR (Heimdall). Executors and governors may
report, triage and mark fixed; the transition to ``verified`` requires the
auditor's endorsement via ``audit_ref`` (a PULSE event ID carrying the
auditor's verdict). The auditor role itself is read-only and never calls
these mutating handlers — the endorsement reference is how the auditor's
verdict enters the lifecycle without breaking that contract.

Issue files live in ``<project>/.arqux/issues/`` as
``<YYYY-MM-DD>-<slug>.issue.md`` with a machine-parsable header line::

    # Severity: <low|medium|high|blocking> | Status: <open|triaged|fixed|verified|wontfix|duplicate> | Handler: <who> | Date: <YYYY-MM-DD>

Legacy ``.cortex`` issue files (CORTEX IDN:issue format) remain manageable
through the generic ``cortex.*`` handlers; this module governs the .md
format documented by the arqux-issues skill.

Every mutation appends a PULSE event (kind=issue) for traceability.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..pulse import append_pulse_to_brain, next_pulse_event_id, read_pulse_from_brain
from ..state import find_project_root

VALID_SEVERITIES = ("low", "medium", "high", "blocking")
VALID_STATUSES = ("open", "triaged", "fixed", "verified", "wontfix", "duplicate")

_HEADER_RE = re.compile(
    r"^# Severity:\s*(?P<severity>[\w-]+)\s*\|\s*Status:\s*(?P<status>[^|]+?)"
    r"(?:\s*\|\s*Handler:\s*(?P<handler>.*?))?"
    r"(?:\s*\|\s*Date:\s*(?P<date>\S+))?\s*$"
)


def _canonical_status(raw: str | None) -> str:
    """First token of the status field (legacy files annotate after it)."""
    return ((raw or "").split() or [""])[0].strip().lower()

_ISSUE_TEMPLATE = """\
# ISSUE: {desc}
# Severity: {severity} | Status: open | Handler: {handler} | Date: {date}

## PROBLEM
{desc}

## CONTEXT
reported_by: {agent}
reported_at: {now}

## LESSON
cause:      pending triage
fix:        pending triage
prevention: pending triage
"""


def _issues_dir(root: Path) -> Path:
    return root / "issues"


def _slugify(desc: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", desc.lower()).strip("-")
    return slug[:48] or "issue"


def _parse_header(text: str) -> dict[str, str] | None:
    """Parse the machine header line of an issue file (None if absent)."""
    for line in text.splitlines():
        if line.startswith("# Severity:"):
            m = _HEADER_RE.match(line)
            if m:
                return m.groupdict()
    return None


def _find_issue_file(issues_dir: Path, issue_id: str) -> Path | None:
    """Locate an issue file by its stem (with or without the .issue suffix)."""
    for pattern in ("*.issue.md", "*.md", "*.cortex"):
        for candidate in sorted(issues_dir.glob(pattern)):
            if candidate.stem == issue_id or candidate.stem.removesuffix(".issue") == issue_id:
                return candidate
    return None


def _pulse(root: Path, task_id: str, payload: str, agent: str) -> str:
    event_id = next_pulse_event_id(root)
    append_pulse_to_brain(
        root, event_id=event_id, task_id=task_id, kind="issue",
        agent=agent, payload=payload,
    )
    return event_id


def create_issue(
    severity: str,
    desc: str,
    *,
    handler: str = "",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Report a new issue (status: open) in <project>/.arqux/issues/."""
    if severity not in VALID_SEVERITIES:
        return CortexOUT.error(
            f"invalid severity {severity!r}; must be one of {list(VALID_SEVERITIES)}",
            code="INVALID_ARGS",
        )
    desc = " ".join((desc or "").split())
    if not desc:
        return CortexOUT.error("desc is required", code="INVALID_ARGS")
    handler = " ".join((handler or "").split())

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    issues_dir = _issues_dir(root)
    issues_dir.mkdir(parents=True, exist_ok=True)

    agent = (ctx or PermissionContext.from_env()).agent_id
    today = _dt.date.today().isoformat()
    base = f"{today}-{_slugify(desc)}"
    filename = f"{base}.issue.md"
    n = 2
    while (issues_dir / filename).exists():
        filename = f"{base}-{n}.issue.md"
        n += 1

    issue_id = base if n == 2 else f"{base}-{n - 1}"
    # T-027 (audit F-2): trace BEFORE the write so a failed write still
    # leaves a PULSE record of the attempted mutation.
    event_id = _pulse(
        root, issue_id,
        f"issue.create {filename} severity={severity} status=open by={agent}",
        agent,
    )

    content = _ISSUE_TEMPLATE.format(
        desc=desc,
        severity=severity,
        handler=handler or agent,
        date=today,
        agent=agent,
        now=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    (issues_dir / filename).write_text(content, encoding="utf-8")

    return CortexOUT.work(
        f"issue.create ok id={issue_id}",
        issue_id=issue_id,
        file=str(issues_dir / filename),
        severity=severity,
        status="open",
        event_id=event_id,
    )


def update_issue(
    issue_id: str,
    *,
    status: str | None = None,
    severity: str | None = None,
    note: str | None = None,
    audit_ref: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Update an issue's status/severity with a PULSE-traced transition.

    Separation of responsibilities: ``status=verified`` requires
    ``audit_ref`` — the PULSE event ID of the auditor's (Heimdall's)
    verdict. Without it the transition is rejected.
    """
    if status is not None and status not in VALID_STATUSES:
        return CortexOUT.error(
            f"invalid status {status!r}; must be one of {list(VALID_STATUSES)}",
            code="INVALID_ARGS",
        )
    if severity is not None and severity not in VALID_SEVERITIES:
        return CortexOUT.error(
            f"invalid severity {severity!r}; must be one of {list(VALID_SEVERITIES)}",
            code="INVALID_ARGS",
        )
    if status == "verified" and not (audit_ref or "").strip():
        return CortexOUT.error(
            "status=verified requires auditor endorsement: pass "
            "audit_ref=<PULSE event id of the auditor's verdict> "
            "(the validator profile is the auditor)",
            code="AUDIT_REF_REQUIRED",
        )
    if status is None and severity is None and not (note or "").strip():
        return CortexOUT.error(
            "nothing to update: pass status, severity or note",
            code="INVALID_ARGS",
        )

    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # T-027 (audit F-1): the endorsement must resolve to a real PULSE
    # event — attestational strings are not enough to certify verified.
    if status == "verified":
        ref = (audit_ref or "").strip()
        pulse_ids = {
            e.get("id") for e in read_pulse_from_brain(root, limit=10_000)
        }
        if ref not in pulse_ids:
            return CortexOUT.error(
                f"audit_ref {ref!r} does not resolve to a PULSE event in this "
                "project — the auditor's verdict must exist before verified",
                code="AUDIT_REF_INVALID",
            )

    issues_dir = _issues_dir(root)
    issue_file = _find_issue_file(issues_dir, issue_id)
    if issue_file is None:
        return CortexOUT.error(f"issue {issue_id} not found", code="NOT_FOUND")

    text = issue_file.read_text(encoding="utf-8")
    header = _parse_header(text)
    if header is None:
        return CortexOUT.error(
            f"issue {issue_id} has no parsable header line", code="INVALID_FORMAT"
        )

    old_status = _canonical_status(header["status"])
    new_severity = severity or header["severity"]
    new_status = status or old_status
    new_handler = header.get("handler") or ""
    new_date = header.get("date") or _dt.date.today().isoformat()

    new_header = (
        f"# Severity: {new_severity} | Status: {new_status}"
        f" | Handler: {new_handler} | Date: {new_date}"
    )
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# Severity:"):
            lines[i] = new_header
            break
    text = "\n".join(lines) + "\n"

    clean_note = ""
    if (note or "").strip():
        # T-027 (audit F-3): neutralize header-forgery lines in the note.
        clean_note = re.sub(r"(?m)^(#\s*Severity:)", r"> \1", note.strip())
        text += f"\n## UPDATE {_dt.date.today().isoformat()}\n\n{clean_note}\n"

    agent = (ctx or PermissionContext.from_env()).agent_id
    payload = (
        f"issue.update {issue_file.name} status={old_status}->{new_status}"
        + (f" audit_ref={audit_ref}" if audit_ref else "")
        + (f" note={clean_note[:80]}" if clean_note else "")
    )
    # T-027 (audit F-2): trace BEFORE the write.
    event_id = _pulse(root, issue_id, payload, agent)

    issue_file.write_text(text, encoding="utf-8")

    return CortexOUT.work(
        f"issue.update ok id={issue_id} status={old_status}->{new_status}",
        issue_id=issue_id,
        status=new_status,
        previous_status=old_status,
        severity=new_severity,
        audit_ref=audit_ref or "",
        event_id=event_id,
    )


def list_issues(
    *,
    status: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List issues in <project>/.arqux/issues/, optionally by status."""
    if status is not None and status not in VALID_STATUSES:
        return CortexOUT.error(
            f"invalid status {status!r}; must be one of {list(VALID_STATUSES)}",
            code="INVALID_ARGS",
        )
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    issues_dir = _issues_dir(root)
    items: list[dict[str, str]] = []
    if issues_dir.exists():
        for candidate in sorted(issues_dir.glob("*.issue.md")):
            header = _parse_header(candidate.read_text(encoding="utf-8"))
            if header is None:
                continue
            canonical = _canonical_status(header["status"])
            if status is not None and canonical != status:
                continue
            items.append({
                "id": candidate.stem,
                "severity": header["severity"],
                "status": canonical,
                "handler": header.get("handler") or "",
                "date": header.get("date") or "",
            })

    return CortexOUT.work(
        f"issues={len(items)}" + (f" status={status}" if status else ""),
        issues=items,
        total=len(items),
    )


def read_issue(
    issue_id: str,
    *,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read one issue file verbatim."""
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    issue_file = _find_issue_file(_issues_dir(root), issue_id)
    if issue_file is None:
        return CortexOUT.error(f"issue {issue_id} not found", code="NOT_FOUND")

    return CortexOUT.work(
        f"issue={issue_id}",
        issue_id=issue_id,
        file=str(issue_file),
        content=issue_file.read_text(encoding="utf-8"),
    )


handler_schemas = [
    {
        "name": "issue.create",
        "fn": create_issue,
        "description": (
            "Report a new issue (status: open) in <project>/.arqux/issues/ "
            "with a PULSE event. Severity: low|medium|high|blocking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": list(VALID_SEVERITIES)},
                "desc": {"type": "string", "description": "Problem description."},
                "handler": {"type": "string", "description": "Who detected it (defaults to caller)."},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
            "required": ["severity", "desc"],
        },
    },
    {
        "name": "issue.update",
        "fn": update_issue,
        "description": (
            "Update an issue's status/severity with a PULSE-traced transition. "
            "status=verified REQUIRES audit_ref (the PULSE event id of the "
            "auditor's verdict — the validator profile is the auditor)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string"},
                "status": {"type": "string", "enum": list(VALID_STATUSES)},
                "severity": {"type": "string", "enum": list(VALID_SEVERITIES)},
                "note": {"type": "string"},
                "audit_ref": {
                    "type": "string",
                    "description": "PULSE event id of the auditor's verdict (required for verified).",
                },
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
            "required": ["issue_id"],
        },
    },
    {
        "name": "issue.list",
        "fn": list_issues,
        "description": "List issues in <project>/.arqux/issues/, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": list(VALID_STATUSES)},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
        },
    },
    {
        "name": "issue.read",
        "fn": read_issue,
        "description": "Read one issue file verbatim by id (file stem).",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string"},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
            "required": ["issue_id"],
        },
    },
]
