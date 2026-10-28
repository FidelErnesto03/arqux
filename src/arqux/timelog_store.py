"""Canonical timelog persistence for a session (CYCLE-14 / BLP-002).

One self-contained CORTEX file per project/session::

    <project>/.arqux/timelog/SESXXX_yyyymmdd_hhmiss.cortex

The name comes from the *real* session id and its *original* UTC start, both of
which BLP-001 fixed at opening. Nothing here renames the file on resume.

Properties this module guarantees:

* **Exclusion.** The read-modify-write cycle is fenced by a reentrant file lock.
  The brain/SES lock is always taken first, so capture, correction, debugging
  and projection share one order and cannot deadlock.
* **Optimistic revision.** Writers pass the revision they based their edit on; a
  mismatch is a conflict and nothing is written.
* **Idempotent operations.** Repeating the same ``operation_ref`` replays the
  same block instead of adding another, and never silently changes its marks.
* **No hidden copies.** Replacement is a rename of a technical ``.cortex``
  temporary; no ``.bak``/``.bak.1`` is produced for this capability, and the
  temporary is reconciled or removed after an interruption.
* **Honest uncertainty.** A failed write keeps the last valid document and the
  caller learns whether the outcome is known, uncertain or rejected. A work
  action is never replayed because its annotation failed.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from .concurrency import reentrant_file_lock
from .session_identity import brain_lock, brain_path, timelog_name

TIMLOG_DIR = "timelog"
CANONICAL_RE = re.compile(r"^SES\d+_\d{8}_\d{6}\.cortex$")
TEMP_SUFFIX = ".tmp.cortex"
VERSION = "1"

IDENTITY_SIGIL = "TLG"
ACTIVITY_SIGIL = "ACT"
RECEIPT_SIGIL = "RCV"
PROJECTION_SIGIL = "PRJ"

SECTION_GLOSSARY = "$0"
SECTION_IDENTITY = "$1"
SECTION_ACTIVITIES = "$2"
SECTION_RECEIPTS = "$3"
SECTION_PROJECTIONS = "$4"

_GLOSSARY = (
    # $0 must be a real section header, not just a comment: the CODEC-CORTEX
    # parser rejects a file whose first section is not $0
    # (E002_GLOSSARY_NOT_FIRST). The glossary text lives in the comments below it.
    "$0\n"
    "\n"
    "# -- $0: TIMLOG LOCAL GLOSSARY --\n"
    "# Sigil | Name     | Type  | Risk | Cognitive Layer | Description\n"
    "# TLG   | timelog  | attrs | B    | Episodic        | Timelog identity and metadata\n"
    "# ACT   | activity | attrs | B    | Episodic        | One activity interval\n"
    "# RCV   | receipt  | attrs | B    | Episodic        | External projection receipt\n"
    "# PRJ   | projection | attrs | B  | Episodic        | Per-provider projection mark\n"
)


class TimelogError(Exception):
    """A rejected timelog operation with an actionable code."""

    def __init__(self, message: str, *, code: str = "TIMELOG_ERROR") -> None:
        super().__init__(message)
        self.code = code


class RevisionConflict(TimelogError):
    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            f"revision conflict: expected {expected}, file holds {actual}",
            code="TIMELOG_REVISION_CONFLICT",
        )


class MembershipError(TimelogError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="TIMELOG_MEMBERSHIP_ERROR")


class UnknownOperation(TimelogError):
    def __init__(self, operation_ref: str) -> None:
        super().__init__(f"operation {operation_ref!r} is not recorded in this timelog",
                         code="TIMELOG_OPERATION_NOT_FOUND")


def timelog_dir(project_root: Path | str) -> Path:
    """Directory holding the canonical timelogs of a project."""
    return brain_path(project_root).parent / TIMLOG_DIR


def canonical_name(session_id: str, opened_at: str) -> str:
    return timelog_name(session_id, opened_at)


def is_canonical(name: str) -> bool:
    """True only for the canonical pattern; technical temporaries never match."""
    return bool(CANONICAL_RE.match(name or ""))


def canonical_path(project_root: Path | str, session_id: str, opened_at: str) -> Path:
    return timelog_dir(project_root) / canonical_name(session_id, opened_at)


def list_timelogs(project_root: Path | str) -> list[str]:
    """Canonical timelog file names of the project, oldest first."""
    directory = timelog_dir(project_root)
    if not directory.exists():
        return []
    return sorted(n for n in os.listdir(directory) if is_canonical(n))


def lock_path(project_root: Path | str, name: str) -> Path:
    return timelog_dir(project_root) / f"{name}.lock"


def _clean_text(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ").strip()


def _field(attrs: str, key: str) -> str:
    """Read ``key:"value"`` (CORTEX) or ``key="value"`` from an attrs body."""
    m = re.search(rf'(?:^|[,{{\s]){re.escape(key)}[=:]"([^"]*)"', attrs)
    return m.group(1) if m else ""


def _serialize(document: dict[str, Any]) -> str:
    """Deterministic CODEC-CORTEX text: glossary, identity, blocks, receipts."""
    lines = [_GLOSSARY.rstrip("\n"), ""]
    lines.append(f"{SECTION_IDENTITY}: IDENTITY")
    lines.append(
        f'{IDENTITY_SIGIL}:identity{{project:"{_clean_text(document["project"])}",'
        f'ses:"{document["ses"]}",opened:"{document["opened"]}",'
        f'version:"{VERSION}",revision:"{document["revision"]}"}}\n'
    )
    lines.append("")
    lines.append(f"{SECTION_ACTIVITIES}: ACTIVITIES")
    for ref in sorted(document["blocks"]):
        block = document["blocks"][ref]
        end = block.get("end") or ""
        extra = ""
        if block.get("note"):
            extra += f',note:"{_clean_text(block["note"])}"'
        if block.get("auth"):
            extra += f',auth:"{_clean_text(block["auth"])}"'
        block_revision = block.get("revision") or document["revision"]
        lines.append(
            f'{ACTIVITY_SIGIL}:{_entry_name(ref)}'
            f'{{start:"{block["start"]}",end:"{end}",state:"{block.get("state", "open")}"'
            f'{extra},revision:"{block_revision}"}}\n'
        )
    lines.append("")
    lines.append(f"{SECTION_RECEIPTS}: RECEIPTS")
    for key in sorted(document["receipts"]):
        receipt = document["receipts"][key]
        lines.append(
            f'{RECEIPT_SIGIL}:{_entry_name(key)}'
            f'{{operation:"{_clean_text(receipt.get("operation", ""))}",'
            f'status:"{receipt.get("status", "pending")}",'
            f'destination:"{_clean_text(receipt.get("destination", ""))}",'
            f'state:"{receipt.get("state", "unknown")}",'
            f'remote:"{_clean_text(receipt.get("remote", ""))}",'
            f'revision:"{document["revision"]}"}}\n'
        )
    lines.append("")
    lines.append(f"{SECTION_PROJECTIONS}: PROJECTIONS")
    for key in sorted(document.get("projections", {})):
        mark = document["projections"][key]
        lines.append(
            f'{PROJECTION_SIGIL}:{_entry_name(key)}'
            f'{{operation:"{_clean_text(mark.get("operation", ""))}",'
            f'status:"{mark.get("status", "pending")}",'
            f'destination:"{_clean_text(mark.get("destination", ""))}",'
            f'state:"{mark.get("state", "unknown")}",'
            f'remote:"{_clean_text(mark.get("remote", ""))}",'
            f'blocks:"{_clean_text(mark.get("blocks", ""))}",'
            f'start:"{mark.get("start", "")}",'
            f'end:"{mark.get("end", "")}",'
            f'minutes:"{mark.get("minutes", "")}",'
            f'agent:"{_clean_text(mark.get("agent", ""))}",'
            f'projected_at:"{mark.get("projected_at", "")}",'
            f'revision:"{document["revision"]}"}}\n'
        )
    return "\n".join(lines) + "\n"


def _entry_name(ref: str) -> str:
    """Filesystem- and selector-safe entry name.

    Hyphens are replaced too: CORTEX uses ``-`` as its selector separator, so a
    name carrying one would not round-trip through ``$section/SIGIL:name``.
    """
    return re.sub(r"[^A-Za-z0-9._]", "_", str(ref)).strip("._") or "op"


def _parse(text: str) -> dict[str, Any]:
    """Parse the canonical document back into its model."""
    document = {
        "project": "",
        "ses": "",
        "opened": "",
        "revision": "0",
        "blocks": {},
        "receipts": {},
        "projections": {},
    }
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(f"{IDENTITY_SIGIL}:"):
            attrs = line[line.index("{") + 1: line.rindex("}")]
            document["project"] = _field(attrs, "project")
            document["ses"] = _field(attrs, "ses")
            document["opened"] = _field(attrs, "opened")
            document["revision"] = _field(attrs, "revision") or "0"
        elif line.startswith(f"{ACTIVITY_SIGIL}:"):
            name = line[len(ACTIVITY_SIGIL) + 1: line.index("{")]
            attrs = line[line.index("{") + 1: line.rindex("}")]
            document["blocks"][name] = {
                "start": _field(attrs, "start"),
                "end": _field(attrs, "end"),
                "state": _field(attrs, "state") or "open",
                "note": _field(attrs, "note"),
                "auth": _field(attrs, "auth"),
                "revision": _field(attrs, "revision"),
            }
        elif line.startswith(f"{RECEIPT_SIGIL}:"):
            name = line[len(RECEIPT_SIGIL) + 1: line.index("{")]
            attrs = line[line.index("{") + 1: line.rindex("}")]
            document["receipts"][name] = {
                "operation": _field(attrs, "operation"),
                "status": _field(attrs, "status") or "pending",
                "destination": _field(attrs, "destination"),
                "state": _field(attrs, "state") or "unknown",
                "remote": _field(attrs, "remote"),
            }
        elif line.startswith(f"{PROJECTION_SIGIL}:"):
            name = line[len(PROJECTION_SIGIL) + 1: line.index("{")]
            attrs = line[line.index("{") + 1: line.rindex("}")]
            document["projections"][name] = {
                "operation": _field(attrs, "operation"),
                "status": _field(attrs, "status") or "pending",
                "destination": _field(attrs, "destination"),
                "state": _field(attrs, "state") or "unknown",
                "remote": _field(attrs, "remote"),
                "blocks": _field(attrs, "blocks"),
                "start": _field(attrs, "start"),
                "end": _field(attrs, "end"),
                "minutes": _field(attrs, "minutes"),
                "agent": _field(attrs, "agent"),
                "projected_at": _field(attrs, "projected_at"),
            }
    return document


def _check_membership(document: dict[str, Any], session_id: str) -> None:
    ses = document.get("ses") or ""
    if ses and ses != session_id:
        raise MembershipError(
            f"timelog belongs to {ses}, not to the requested {session_id}"
        )


def _write(path: Path, text: str, *, keep_backup: bool = False) -> None:
    """Replace *path* with *text* through a technical ``.cortex`` temporary.

    No durable ``.bak``/``.bak.1`` is produced for this capability (AC-06).
    """
    temporary = path.with_name(f".{path.name}{TEMP_SUFFIX}")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _resolve(project_root: Path | str, session_id: str, opened_at: str | None) -> Path:
    """The canonical path for a session, searching when the start is unknown."""
    if opened_at:
        return canonical_path(project_root, session_id, opened_at)
    for name in list_timelogs(project_root):
        if name.startswith(f"{session_id}_"):
            return timelog_dir(project_root) / name
    return canonical_path(project_root, session_id, opened_at or "")


def ensure_timelog(
    project_root: Path | str,
    session: dict[str, Any],
    *,
    operation_ref: str = "session.open",
) -> dict[str, Any]:
    """Create the canonical file for *session* if it is missing. Idempotent.

    Opening spans two files (brain SES + timelog), so it is explicitly *not*
    atomic: identity is persisted first, then the file is created by a
    deterministic path, then the link is confirmed. A retry inspects the phases
    and completes the same session instead of starting a second one.
    """
    session_id = session["session_id"]
    opened_at = session.get("date", "")
    name = canonical_name(session_id, opened_at)
    path = timelog_dir(project_root) / name

    if str(session.get("suppressed", "")).lower() in ("true", "1", "yes"):
        # An authorized purge wins: resume/retry/projection must not recreate a
        # deleted timelog. A future record needs an explicit decision.
        return {"state": "suppressed", "path": str(path), "timelog": name}

    with reentrant_file_lock(lock_path(project_root, name)):
        if path.exists():
            return {"state": "exists", "path": str(path), "timelog": name}
        directory = timelog_dir(project_root)
        directory.mkdir(parents=True, exist_ok=True)
        document = {
            "project": session.get("project", ""),
            "ses": session_id,
            "opened": opened_at,
            "revision": "1",
            "blocks": {},
            "receipts": {},
            "projections": {},
        }
        try:
            _write(path, _serialize(document))
        except OSError as exc:
            # Uncertainty is reported, never converted into a new session.
            return {"state": "uncertain", "path": str(path), "timelog": name,
                    "error": str(exc)}
        return {"state": "created", "path": str(path), "timelog": name}


def load(
    project_root: Path | str,
    session_id: str,
    *,
    opened_at: str | None = None,
    path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Read one timelog. Read-only: never writes and never creates."""
    target = Path(path) if path else _resolve(project_root, session_id, opened_at)
    if path is not None and not is_canonical(target.name):
        # An explicit path that is not a canonical timelog is a membership
        # violation, not "no such file": silently returning None would let a
        # caller read an arbitrary .cortex and believe it was a session.
        raise MembershipError(f"{target.name} is not a canonical timelog path")
    if not target.exists() or not is_canonical(target.name):
        return None
    document = _parse(target.read_text(encoding="utf-8"))
    if document.get("ses") and document["ses"] != session_id:
        raise MembershipError(
            f"timelog {target.name} belongs to {document['ses']}, not to {session_id}"
        )
    return document


def update(
    project_root: Path | str,
    session_id: str,
    *,
    operation_ref: str,
    expected_revision: str | None = None,
    mutate=None,
    opened_at: str | None = None,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Apply *mutate(document)* under exclusion, revision check and idempotency.

    Returns the resulting document. Repeating ``operation_ref`` with no
    mutation returns the recorded block unchanged — it never adds a second one.
    """
    target = Path(path) if path else _resolve(project_root, session_id, opened_at)
    if not is_canonical(target.name):
        raise MembershipError(f"{target.name} is not a canonical timelog path")
    if target.is_symlink() or target.resolve().parent != timelog_dir(project_root).resolve():
        raise MembershipError(f"{target.name} escapes the project timelog directory")

    name = target.name
    with reentrant_file_lock(lock_path(project_root, name)):
        if not target.exists():
            raise MembershipError(f"timelog {name} does not exist")
        text = target.read_text(encoding="utf-8")
        document = _parse(text)
        _check_membership(document, session_id)

        if expected_revision is not None and document["revision"] != expected_revision:
            raise RevisionConflict(expected_revision, document["revision"])

        applied = mutate(document) if mutate else False
        if not applied:
            # Idempotent replay: the operation is already represented.
            return {**document, "applied": False}

        document["revision"] = str(int(document["revision"] or "0") + 1)
        try:
            _write(target, _serialize(document))
        except OSError as exc:
            return {**document, "applied": False, "state": "uncertain",
                    "error": str(exc)}
        return {**document, "applied": True}


def open_block(
    project_root: Path | str,
    session_id: str,
    *,
    operation_ref: str,
    start: str | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    """Record the start of an activity. Repeating the operation is a no-op."""
    start = start or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def mutate(document: dict[str, Any]) -> bool:
        name = _entry_name(operation_ref)
        if name in document["blocks"]:
            return False
        document["blocks"][name] = {
            "start": start, "end": "", "state": "open",
            "revision": str(int(document["revision"] or "0") + 1),
        }
        return True

    return update(project_root, session_id, operation_ref=operation_ref,
                  expected_revision=expected_revision, mutate=mutate)


def close_block(
    project_root: Path | str,
    session_id: str,
    *,
    operation_ref: str,
    end: str | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    """Record the end of an activity. Unknown operations are rejected."""
    end = end or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    name = _entry_name(operation_ref)

    def mutate(document: dict[str, Any]) -> bool:
        if name not in document["blocks"]:
            raise UnknownOperation(operation_ref)
        block = document["blocks"][name]
        if block.get("end"):
            return False
        block["end"] = end
        block["state"] = "closed"
        block["revision"] = str(int(document["revision"] or "0") + 1)
        return True

    return update(project_root, session_id, operation_ref=operation_ref,
                  expected_revision=expected_revision, mutate=mutate)


def parse_document(text: str) -> dict[str, Any]:
    """Public wrapper: parse canonical timelog text into its model."""
    return _parse(text)


def serialize_document(document: dict[str, Any]) -> str:
    """Public wrapper: serialize a timelog model back to canonical text."""
    return _serialize(document)


def invalidate_pending(project_root: Path | str, session_id: str) -> dict[str, Any]:
    """Mark every open block as explicitly unterminated.

    Deleting a session must invalidate pending operations without recreating
    them, so an open interval can never be closed after its content is gone.
    """

    def mutate(document: dict[str, Any]) -> bool:
        changed = False
        for block in document["blocks"].values():
            if not block.get("end"):
                block["state"] = "unterminated"
                changed = True
        return changed

    return update(project_root, session_id, operation_ref="session.invalidate",
                  mutate=mutate)


__all__ = [
    "TimelogError",
    "RevisionConflict",
    "MembershipError",
    "UnknownOperation",
    "brain_lock",
    "canonical_name",
    "canonical_path",
    "close_block",
    "ensure_timelog",
    "invalidate_pending",
    "is_canonical",
    "list_timelogs",
    "load",
    "open_block",
    "parse_document",
    "serialize_document",
    "timelog_dir",
    "update",
]
