"""`issue` module — governed lifecycle for the .arqux/issues/ registry (T-027).

Handlers:
    issue.create  — report a new issue (status: open); channels local|github|both
    issue.update  — triage / fix / verify an issue (status transitions, GH sync)
    issue.list    — list issues, optionally filtered by status/channel
    issue.read    — read one issue verbatim (local file or remote GH issue)

Channels (2026-11-18): ``local`` is the internal queue (``.arqux/issues/``);
``github`` files an issue on the repo (remote is authoritative, local keeps a
``gh-*`` mirror); ``both`` links a canonical local file to a remote issue.
The repo resolves via ``repo=`` > ``IDN:github_issues{repo:...}`` (brain) >
``gh repo view`` of the checkout. ``gh`` CLI must be authenticated.

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
import json as _json
import re
import shutil
import subprocess
from pathlib import Path

from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..pulse import read_pulse_from_brain, record_pulse
from ..state import find_write_project_root

VALID_SEVERITIES = ("low", "medium", "high", "blocking")
VALID_STATUSES = ("open", "triaged", "fixed", "verified", "wontfix", "duplicate")
VALID_CHANNELS = ("local", "github", "both")

# Statuses that close the GitHub issue (rest stay open remotely).
_GH_CLOSING_STATUSES = ("verified", "wontfix", "duplicate")

_HEADER_RE = re.compile(
    r"^# Severity:\s*(?P<severity>[\w-]+)\s*\|\s*Status:\s*(?P<status>[^|]+?)"
    r"(?:\s*\|\s*Handler:\s*(?P<handler>.*?))?"
    r"(?:\s*\|\s*Date:\s*(?P<date>\S+))?"
    # Optional channel tail: `| Channel: github | gh_repo:"o/n" | gh_number:"N"`.
    # Captured (not parsed) so legacy headers keep matching verbatim.
    r"(?P<extra>(?:\s*\|[^|]*)*)\s*$"
)


def _canonical_status(raw: str | None) -> str:
    """First token of the status field (legacy files annotate after it)."""
    return ((raw or "").split() or [""])[0].strip().lower()

_ISSUE_TEMPLATE = """\
# ISSUE: {title}
# Severity: {severity} | Status: open | Handler: {handler} | Date: {date}{channel_extra}

## PROBLEM
{body}

## CONTEXT
reported_by: {agent}
reported_at: {now}
{gh_context}
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


#: Longest header line accepted. The header is read by humans and by tools
#: (issue.list, a future board); a 3.000-character title is unusable.
TITLE_MAX = 120


def _truncate_title(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= TITLE_MAX else text[: TITLE_MAX - 1].rstrip() + "…"


def _split_title(desc: str, title: str | None) -> tuple[str, str]:
    """Return ``(title_for_the_header, full_body)``.

    ``desc`` keeps its line structure: the first line is the title when the
    caller does not pass one, and the whole text is the body. Collapsing desc
    into one line made it both the header and the body — a 3.000-character
    ``# ISSUE:`` line repeated under ``## PROBLEM`` (issue 2026-10-26).
    """
    body = (desc or "").strip()
    if title:
        return _truncate_title(title), body
    first = body.split("\n", 1)[0].strip()
    return _truncate_title(first or body), body


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
    return record_pulse(
        root, task_id=task_id, kind="issue",
        agent=agent, payload=payload,
    )


# --- GitHub channel (2026-11-18): remote issue sink for external reports ---


def _gh_available() -> tuple[bool, str]:
    """``gh`` CLI present and authenticated — else (False, reason)."""
    if shutil.which("gh") is None:
        return False, "gh CLI not installed"
    try:
        proc = subprocess.run(
            ["gh", "auth", "status", "-h", "github.com"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"gh auth check failed: {exc}"
    if proc.returncode != 0:
        return False, "gh not authenticated (run: gh auth login)"
    return True, ""


def _gh_repo(root: Path, override: str | None = None) -> tuple[str | None, str]:
    """Resolve the target GitHub repo as owner/name.

    Precedence: explicit *override* > ``IDN:github_issues{repo:...}`` entry in
    the project brain > ``gh repo view`` of the checkout containing *root*
    (its origin remote). Returns (repo, error_message).
    """
    if override and override.strip():
        return override.strip(), ""

    # Brain-declared repo: IDN:github_issues{repo:"owner/name"} in $1.
    try:
        from ..core.state._crud import crud_read

        brain = root / "brain.cortex"
        if brain.exists():
            ents = crud_read(str(brain), "IDN:github_issues").get("entries", [])
            for e in ents:
                val = e.get("value")
                if isinstance(val, dict) and val.get("repo"):
                    return str(val["repo"]).strip(), ""
    except Exception:
        pass

    # Fallback: the git remote of the project checkout itself.
    try:
        proc = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True, text=True, timeout=15, cwd=str(root.parent),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip(), ""
        err = (proc.stderr or proc.stdout).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        err = str(exc)
    return None, f"could not resolve GitHub repo (set repo= or IDN:github_issues in brain): {err}"


def _gh(args: list[str], *, timeout: int = 30) -> tuple[bool, str, str]:
    """Run a gh command. Returns (ok, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)
    return proc.returncode == 0, proc.stdout, proc.stderr


def _gh_create_issue(repo: str, title: str, body: str,
                     severity: str) -> dict[str, str]:
    """Create a GitHub issue; returns {url, number} or raises RuntimeError.

    Labels are best-effort: repos that lack ``severity:*``/``source:arqux``
    labels get the issue created without them (missing labels otherwise
    abort the whole create).
    """
    ok, reason = _gh_available()
    if not ok:
        raise RuntimeError(f"github channel unavailable: {reason}")
    body_with_origin = f"{body}\n\n---\n_reported via ArqUX issue.create (github channel)_"
    args = ["issue", "create", "-R", repo,
            "--title", _truncate_title(title),
            "--body", body_with_origin]
    gh_ok, out, err = _gh(
        args + ["--label", f"severity:{severity}", "--label", "source:arqux"],
    )
    if not gh_ok and "label" in (err or "").lower():
        # Retry without labels only when labels were the failure — a generic
        # retry could duplicate a remote issue that actually got created.
        gh_ok, out, err = _gh(args)
    if not gh_ok:
        raise RuntimeError(f"gh issue create failed: {err.strip() or out.strip()}")
    lines = out.strip().splitlines()
    if not lines:
        raise RuntimeError("gh issue create returned empty output")
    url = lines[-1].strip()
    number = url.rstrip("/").rsplit("/", 1)[-1] if "/issues/" in url else ""
    return {"url": url, "number": number}


def _gh_comment_and_transition(repo: str, number: str,
                               label: str, note: str,
                               *, close: bool = False,
                               close_reason: str = "completed") -> str:
    """Comment the transition + close when terminal. Returns action taken."""
    if not number:
        return "github mirror without issue number — skipped remote sync"
    actions = []
    comment = f"ArqUX issue lifecycle → **{label}**"
    if note:
        comment += f"\n\n{note}"
    ok, _out, err = _gh(["issue", "comment", number, "-R", repo, "--body", comment])
    if not ok:
        return f"github comment failed: {err.strip()}"
    actions.append("commented")
    if close:
        ok, _out, err = _gh(
            ["issue", "close", number, "-R", repo, "--reason", close_reason])
        actions.append("closed" if ok else f"close failed: {err.strip()}")
    return "+".join(actions)


# Canonical channel tail — matches ONLY the strict, end-of-header form
# `| Channel: <chan> | gh_repo:"o/n" | gh_number:"N"` (audit 2026-11-18 N1:
# a `handler`/`note` carrying `Channel:` mid-line must never parse as a
# channel — that would let a forged header drive gh issue close/comment
# against arbitrary issues).
_CHANNEL_TAIL_RE = re.compile(
    r'\|\s*Channel:\s*(\w+)\s*\|\s*gh_repo:"([^"]*)"\s*\|\s*gh_number:"([^"]*)"\s*$'
)


def _channel_tail(text: str) -> tuple[str, str, str, str]:
    """(tail_string, channel, gh_repo, gh_number) of the header line — strict
    end-of-header match only. Forged/malformed tails return local."""
    for line in text.splitlines():
        if line.startswith("# Severity:"):
            m = _CHANNEL_TAIL_RE.search(line)
            if m:
                return m.group(0), m.group(1), m.group(2), m.group(3)
            return "", "local", "", ""
    return "", "local", "", ""


def _read_channel(text: str) -> tuple[str, str, str]:
    """(channel, gh_repo, gh_number) parsed from the issue header line."""
    _tail, chan, repo, num = _channel_tail(text)
    return chan, repo, num


def _channel_matches(file_channel: str, wanted: str) -> bool:
    """Channel filter semantics for issue.list: ``local`` is exact, ``github``
    matches every GH-linked file (github + both), ``both`` is exact."""
    if wanted == "github":
        return file_channel in ("github", "both")
    return file_channel == wanted


def create_issue(
    severity: str,
    desc: str,
    *,
    title: str | None = None,
    handler: str = "",
    channel: str = "local",
    repo: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Report a new issue (status: open).

    Channels (2026-11-18):

    - ``local`` — internal registry only, ``<project>/.arqux/issues/``.
    - ``github`` — the remote GitHub issue is the artifact of record; a
      ``gh-<date>-<slug>.issue.md`` mirror is kept locally (channel github).
    - ``both`` — the local file stays canonical AND a linked GitHub issue is
      created (channel both). For reports that live in both queues.

    The target repo resolves: explicit *repo* (owner/name) >
    ``IDN:github_issues{repo:...}`` in the project brain > the checkout's
    ``gh repo view``. External-user reports land via ``github``/``both``;
    internal work keeps ``local``.
    """
    if severity not in VALID_SEVERITIES:
        return CortexOUT.error(
            f"invalid severity {severity!r}; must be one of {list(VALID_SEVERITIES)}",
            code="INVALID_ARGS",
        )
    if channel not in VALID_CHANNELS:
        return CortexOUT.error(
            f"invalid channel {channel!r}; must be one of {list(VALID_CHANNELS)}",
            code="INVALID_ARGS",
        )
    body = (desc or "").strip()
    if not body:
        return CortexOUT.error("desc is required", code="INVALID_ARGS")
    header_title, body = _split_title(body, title)
    # `|` stripped: a handler carrying `| Channel: ...` must never reach the
    # header line — channel forgery via handler (audit 2026-11-18 N1).
    handler = " ".join((handler or "").replace("|", " ").split())

    root = find_write_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    # --- GitHub side first: the remote id feeds the local header + PULSE ---
    gh_repo = ""
    gh_url = ""
    gh_number = ""
    if channel in ("github", "both"):
        gh_repo, repo_err = _gh_repo(root, repo)
        if gh_repo is None:
            return CortexOUT.error(repo_err, code="GITHUB_REPO_UNRESOLVED")
        try:
            gh = _gh_create_issue(gh_repo, header_title, body, severity)
        except RuntimeError as exc:
            return CortexOUT.error(str(exc), code="GITHUB_UNAVAILABLE")
        gh_url = gh["url"]
        gh_number = gh["number"]

    issues_dir = _issues_dir(root)
    issues_dir.mkdir(parents=True, exist_ok=True)

    agent = (ctx or PermissionContext.from_env()).agent_id
    today = _dt.date.today().isoformat()
    base = f"{today}-{_slugify(header_title)}"
    # Remote-first issues carry the gh- prefix so the local mirror reads
    # at a glance; `both` keeps the canonical name (local file leads).
    prefix = "gh-" if channel == "github" else ""
    filename = f"{prefix}{base}.issue.md"
    n = 2
    while (issues_dir / filename).exists():
        filename = f"{prefix}{base}-{n}.issue.md"
        n += 1

    issue_id = Path(filename).stem.removesuffix(".issue")
    channel_extra = ""
    if channel in ("github", "both"):
        # The tail declares the REAL channel so list(channel=both) works.
        channel_extra = (
            f' | Channel: {channel}'
            f' | gh_repo:"{gh_repo}" | gh_number:"{gh_number}"'
        )
    # T-027 (audit F-2): trace BEFORE the write so a failed write still
    # leaves a PULSE record of the attempted mutation.
    event_id = _pulse(
        root, issue_id,
        f"issue.create {filename} severity={severity} status=open"
        f" channel={channel}"
        + (f" gh={gh_repo}#{gh_number}" if gh_number else "")
        + f" by={agent}",
        agent,
    )

    gh_context = f"gh_url: {gh_url}\n" if gh_url else ""
    content = _ISSUE_TEMPLATE.format(
        title=header_title,
        body=body,
        severity=severity,
        handler=handler or agent,
        date=today,
        channel_extra=channel_extra,
        gh_context=gh_context,
        agent=agent,
        now=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    (issues_dir / filename).write_text(content, encoding="utf-8")

    fields = {
        "issue_id": issue_id,
        "file": str(issues_dir / filename),
        "severity": severity,
        "status": "open",
        "channel": channel,
        "event_id": event_id,
        "title": header_title,
    }
    if gh_url:
        fields["github_url"] = gh_url
        fields["github_number"] = gh_number
        fields["github_repo"] = gh_repo
    if title is None and len(" ".join(body.split())) > TITLE_MAX:
        # The caller handed a long paragraph and no title: the header carries a
        # truncated first line while the body keeps the whole text. Say so
        # instead of accepting the ambiguity silently.
        fields["warning"] = (
            f"desc exceeds {TITLE_MAX} chars and no title was given; the header "
            "shows the truncated first line — pass title= to control it"
        )
    return CortexOUT.work(f"issue.create ok id={issue_id}", **fields)


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

    root = find_write_project_root(start=path)
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
    # Preserve the channel tail (`| Channel: x | gh_repo:"…" | …`) — strict
    # end-of-header form only; a forged/malformed tail is dropped on rewrite
    # (sanitizes legacy forgeries instead of propagating them, audit N1).
    channel_tail, _ch, _gr, _gn = _channel_tail(text)

    new_header = (
        f"# Severity: {new_severity} | Status: {new_status}"
        f" | Handler: {new_handler} | Date: {new_date}"
        f"{channel_tail}"
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

    fields = {
        "issue_id": issue_id,
        "status": new_status,
        "previous_status": old_status,
        "severity": new_severity,
        "audit_ref": audit_ref or "",
        "event_id": event_id,
    }

    # GitHub channel (2026-11-18): the local file is authoritative — a remote
    # sync failure never vetoes the local transition. On a status change (or
    # a note) a comment is pushed; transitions into a closing status close
    # the remote issue (verified→completed, wontfix/duplicate→not planned).
    file_channel, gh_repo, gh_number = _read_channel(text)
    if file_channel in ("github", "both") and (
        new_status != old_status or clean_note
    ):
        closing = new_status != old_status and new_status in _GH_CLOSING_STATUSES
        sync = _gh_comment_and_transition(
            gh_repo, gh_number,
            new_status if new_status != old_status else "note",
            clean_note,
            close=closing,
            close_reason="completed" if new_status == "verified" else "not planned",
        )
        fields["channel"] = file_channel
        fields["github_sync"] = sync
        if "failed" in sync or "skipped" in sync:
            fields["warning"] = (
                f"local transition committed but github sync {sync} "
                "— remote issue left stale"
            )

    return CortexOUT.work(
        f"issue.update ok id={issue_id} status={old_status}->{new_status}",
        **fields,
    )


def list_issues(
    *,
    status: str | None = None,
    channel: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """List issues in <project>/.arqux/issues/, optionally by status/channel.

    ``channel=github`` matches every GH-linked file (github + both) — the
    external queue. ``local``/``both`` are exact matches.
    """
    if status is not None and status not in VALID_STATUSES:
        return CortexOUT.error(
            f"invalid status {status!r}; must be one of {list(VALID_STATUSES)}",
            code="INVALID_ARGS",
        )
    if channel is not None and channel not in VALID_CHANNELS:
        return CortexOUT.error(
            f"invalid channel {channel!r}; must be one of {list(VALID_CHANNELS)}",
            code="INVALID_ARGS",
        )
    root = find_write_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    issues_dir = _issues_dir(root)
    items: list[dict[str, str]] = []
    if issues_dir.exists():
        for candidate in sorted(issues_dir.glob("*.issue.md")):
            text = candidate.read_text(encoding="utf-8")
            header = _parse_header(text)
            if header is None:
                continue
            file_channel, gh_repo, gh_number = _read_channel(text)
            if channel is not None and not _channel_matches(file_channel, channel):
                continue
            canonical = _canonical_status(header["status"])
            if status is not None and canonical != status:
                continue
            item = {
                # Same id contract as issue.create (no `.issue` suffix).
                "id": candidate.stem.removesuffix(".issue"),
                "severity": header["severity"],
                "status": canonical,
                "handler": header.get("handler") or "",
                "date": header.get("date") or "",
                "channel": file_channel,
            }
            if gh_number:
                item["gh_repo"] = gh_repo
                item["gh_number"] = gh_number
                item["gh_url"] = f"https://github.com/{gh_repo}/issues/{gh_number}"
            items.append(item)

    return CortexOUT.work(
        f"issues={len(items)}"
        + (f" status={status}" if status else "")
        + (f" channel={channel}" if channel else ""),
        issues=items,
        total=len(items),
    )


def read_issue(
    issue_id: str,
    *,
    channel: str = "local",
    repo: str | None = None,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read one issue verbatim.

    ``channel=local`` (default) reads the file in ``.arqux/issues/`` by stem.
    ``channel=github`` reads the REMOTE GitHub issue: *issue_id* is then the
    GH number of a mirrored file (repo comes from the mirror header), or a
    bare ``gh-<n>``/``<n>`` reference resolved against ``repo=``/brain/checkout.
    """
    root = find_write_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    if channel == "github":
        number = ""
        gh_repo = ""
        text = ""
        issue_file = _find_issue_file(_issues_dir(root), issue_id)
        if issue_file is not None:
            # A local mirror carries the remote coordinates in its header.
            text = issue_file.read_text(encoding="utf-8")
            _ch, gh_repo, number = _read_channel(text)
        if not number:
            # Bare remote reference: "gh-42" or "42".
            m = re.fullmatch(r"(?:gh-)?(\d+)", issue_id.strip())
            if not m:
                return CortexOUT.error(
                    f"channel=github needs a gh number (issue_id={issue_id!r} "
                    "is not a mirrored file and not gh-<n>/<n>)",
                    code="INVALID_ARGS",
                )
            number = m.group(1)
        if not gh_repo:
            gh_repo, repo_err = _gh_repo(root, repo)
            if gh_repo is None:
                return CortexOUT.error(repo_err, code="GITHUB_REPO_UNRESOLVED")
        ok, out, err = _gh([
            "issue", "view", number, "-R", gh_repo,
            "--json", "number,title,state,labels,body,url,comments",
        ])
        if not ok:
            return CortexOUT.error(
                f"gh issue view failed: {err.strip() or out.strip()}",
                code="GITHUB_UNAVAILABLE",
            )
        try:
            remote = _json.loads(out)
        except _json.JSONDecodeError as exc:
            return CortexOUT.error(
                f"gh returned unparsable payload: {exc}", code="PARSE_ERROR",
            )
        return CortexOUT.work(
            f"issue=gh-{number} ({gh_repo})",
            issue_id=issue_id,
            channel="github",
            gh_repo=gh_repo,
            gh_number=number,
            github_url=remote.get("url", ""),
            state=remote.get("state", ""),
            title=remote.get("title", ""),
            labels=[l.get("name", "") for l in remote.get("labels", [])],
            body=remote.get("body", ""),
            comments=remote.get("comments", []),
            local_file=str(issue_file) if issue_file is not None else "",
        )

    if channel != "local":
        return CortexOUT.error(
            f"invalid channel {channel!r}; must be local or github",
            code="INVALID_ARGS",
        )

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
            "Report a new issue (status: open) with a PULSE event. "
            "channel=local (default) writes to <project>/.arqux/issues/ only; "
            "channel=github creates a GitHub issue + local gh- mirror; "
            "channel=both keeps the local file canonical and links a GH issue. "
            "Severity: low|medium|high|blocking. The header uses title when "
            "given, else the first line of desc, truncated to "
            f"{TITLE_MAX} chars; the full desc is the body under ## PROBLEM."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": list(VALID_SEVERITIES)},
                "desc": {"type": "string", "description": "Problem description (full body)."},
                "title": {"type": "string",
                          "description": (f"Short header line (max {TITLE_MAX} chars). "
                                          "Defaults to the first line of desc.")},
                "handler": {"type": "string", "description": "Who detected it (defaults to caller)."},
                "channel": {
                    "type": "string",
                    "enum": list(VALID_CHANNELS),
                    "default": "local",
                    "description": (
                        "local = .arqux/issues/ only; github = GitHub issue + local "
                        "gh- mirror; both = canonical local file + linked GH issue."
                    ),
                },
                "repo": {
                    "type": "string",
                    "description": (
                        "Target GitHub repo as owner/name for github/both. "
                        "Defaults: IDN:github_issues{repo:...} in brain, else the "
                        "checkout's gh repo view."
                    ),
                },
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
            "auditor's verdict — the validator profile is the auditor). "
            "GitHub-linked issues get a transition comment; verified/wontfix/"
            "duplicate also close the remote issue."
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
        "description": (
            "List issues in <project>/.arqux/issues/, filtered by status and/or "
            "channel (github matches all GH-linked files — the external queue)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": list(VALID_STATUSES)},
                "channel": {"type": "string", "enum": list(VALID_CHANNELS)},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
        },
    },
    {
        "name": "issue.read",
        "fn": read_issue,
        "description": (
            "Read one issue verbatim. channel=local (default) reads the file by "
            "stem; channel=github reads the remote GitHub issue (issue_id = the "
            "mirror stem or gh-<n>/<n>, repo from mirror/repo=/brain/checkout)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "string"},
                "channel": {"type": "string", "enum": ["local", "github"], "default": "local"},
                "repo": {"type": "string", "description": "owner/name override for channel=github."},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
            "required": ["issue_id"],
        },
    },
]
