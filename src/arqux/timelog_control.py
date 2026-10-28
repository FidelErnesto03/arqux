"""Query, correction and purge of timelogs (CYCLE-14 / BLP-004).

This is the user's side of the timelog: read it as pure data, correct it with
an explicit revision, and delete what the user orders deleted.

Guarantees:

* **Query is read-only.** It computes durations and totals from the file and
  never writes. A multi-session view keeps provenance and creates no joint file.
* **Durations are reproducible.** ``end - start`` in UTC for closed intervals.
  Open, invalid (end before start), timezone-less and unparseable data are
  *flagged*, never corrected or filled in. No rounding, no minimums.
* **Totals are a union, not a blind sum.** Overlapping intervals are merged and
  parent/child hierarchy is respected, so an interval is never counted twice.
* **Correction is explicit and authorized.** It writes a revision with a reason
  and the user's instruction reference, and marks previously projected receipts
  stale — it never edits what was already sent.
* **Purge is exact and authorized.** Archive, summarize or delete an exact
  selection; a minimal tombstone keeps integrity without the deleted content,
  and nothing recreates it afterwards.
"""

from __future__ import annotations

import calendar
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from . import timelog_store
from .session_identity import brain_lock, brain_path, get_session

_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:?\d{2})?$")


def _parse_epoch(ts: str) -> tuple[int | None, bool]:
    """Return (epoch|None, has_explicit_timezone)."""
    if not ts:
        return None, False
    m = _TS_RE.match(ts.strip())
    if not m:
        return None, False
    year, month, day, hour, minute, second, zone = m.groups()
    try:
        epoch = calendar.timegm((int(year), int(month), int(day),
                                 int(hour), int(minute), int(second), 0, 0, 0))
    except (ValueError, OverflowError):
        return None, False
    if zone in (None, ""):
        return epoch, False
    if zone == "Z":
        return epoch, True
    sign = 1 if zone[0] == "+" else -1
    digits = zone[1:].replace(":", "")
    offset = sign * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return epoch - offset, True


def _now_epoch() -> int:
    return int(time.time())


def _iso(epoch: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def describe_block(name: str, block: dict[str, Any]) -> dict[str, Any]:
    """Duration and integrity flags for one activity block.

    An open block has no duration yet, but it is not unknown either: the server
    stamps ``last_activity`` and computes the elapsed window with its own clock,
    declaring it as a window rather than productive time (issue 2026-10-26).
    """
    start, start_tz = _parse_epoch(block.get("start", ""))
    end_raw = block.get("end", "")
    state = block.get("state", "open")
    described: dict[str, Any] = {
        "block_id": name,
        "start": block.get("start", ""),
        "end": end_raw,
        "state": state,
        "flags": [],
    }
    if not start_tz:
        described["flags"].append("start_without_timezone")
    if not end_raw:
        described["flags"].append("open" if state != "unterminated" else "unterminated")
        described["duration_seconds"] = None
        described["last_activity"] = block.get("last_activity", "")
        if start is None:
            described["elapsed_seconds"] = None
            return described
        now = _now_epoch()
        described["elapsed_seconds"] = max(0, now - start)
        described["elapsed_is_window"] = True
        described["as_of"] = _iso(now)
        return described
    end, end_tz = _parse_epoch(end_raw)
    if not end_tz:
        described["flags"].append("end_without_timezone")
    if start is None or end is None:
        described["flags"].append("unparsable_timestamp")
        described["duration_seconds"] = None
        return described
    if end < start:
        described["flags"].append("end_before_start")
        described["duration_seconds"] = None
        return described
    described["duration_seconds"] = end - start
    return described


def union_seconds(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Union of closed, eligible intervals — overlaps counted once.

    Returns the total, the merged intervals and the overlap count so the report
    can explain the definition and preserve provenance (AC-03).
    """
    intervals: list[tuple[int, int]] = []
    open_elapsed: list[int] = []
    open_count = 0
    for block in blocks:
        if block.get("state") in ("archived", "suppressed"):
            continue
        described = describe_block(block.get("block_id", ""), block)
        if described.get("duration_seconds") is None:
            if not block.get("end"):
                open_count += 1
                elapsed = described.get("elapsed_seconds")
                if elapsed is not None:
                    open_elapsed.append(elapsed)
            continue
        start, _ = _parse_epoch(block.get("start", ""))
        end, _ = _parse_epoch(block.get("end", ""))
        intervals.append((start, end))
    intervals.sort()
    merged: list[list[int]] = []
    overlaps = 0
    for start, end in intervals:
        if merged and start < merged[-1][1]:
            overlaps += 1
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    total = sum(end - start for start, end in merged)
    return {
        # Zero and unknown are different answers. While a block is open the
        # total cannot be known, so it is null — never 0 (issue 2026-10-26).
        "total_seconds": None if open_count else total,
        "closed_seconds": total,
        "open_elapsed_seconds": sum(open_elapsed),
        "open_block_count": open_count,
        "as_of": _iso(_now_epoch()),
        "interval_count": len(intervals),
        "overlaps_merged": overlaps,
        "definition": "union of closed intervals; overlapping time counted once. "
                      "total_seconds is null while any block is open; "
                      "open_elapsed_seconds is a window, not productive time",
        "merged": [{"start_epoch": s, "end_epoch": e} for s, e in merged],
    }


def query(
    project_root: Path | str,
    session_id: str,
    *,
    view: str = "session",
    opened_at: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    """Read-only view of one session, or an explicit multi-session view."""
    if view == "multisession":
        sessions = timelog_store.list_timelogs(project_root)
        views = []
        for name in sessions:
            ses = name.split("_", 1)[0]
            document = timelog_store.load(project_root, ses, opened_at=None,
                                          path=timelog_store.timelog_dir(project_root) / name)
            if document is None:
                continue
            described = _describe_document(document, ses, view="session")
            described["file"] = name
            views.append(described)
        return {
            "view": "multisession",
            "provenance": "one entry per canonical file; no joint file is created",
            "sessions": views,
        }

    document = timelog_store.load(project_root, session_id, opened_at=opened_at)
    if document is None:
        return {"error": "timelog not found", "code": "TIMELOG_NOT_FOUND"}
    result = _describe_document(document, session_id, view="session")
    if limit is not None:
        result["blocks"] = result["blocks"][offset:offset + limit]
        result["offset"] = offset
        result["returned"] = len(result["blocks"])
    return result


def _projection_block_ids(raw: str) -> list[str]:
    """Block ids covered by a projection mark's ``block_id@revision`` list."""
    return [part.split("@", 1)[0] for part in (raw or "").split(",") if part]


def _describe_projections(marks: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the native projection registry: what was sent where, and as what."""
    projections = []
    for key in sorted(marks):
        mark = marks[key]
        projections.append({
            "key": key,
            "operation": mark.get("operation", ""),
            "status": mark.get("status", "pending"),
            "destination": mark.get("destination", ""),
            "state": mark.get("state", "unknown"),
            "remote": mark.get("remote", ""),
            "blocks": mark.get("blocks", ""),
            "block_ids": _projection_block_ids(mark.get("blocks", "")),
            "interval": {"start": mark.get("start", ""), "end": mark.get("end", ""),
                         "minutes": mark.get("minutes", "")},
            "agent": mark.get("agent", ""),
            "projected_at": mark.get("projected_at", ""),
        })
    return projections


def _describe_document(document: dict[str, Any], session_id: str, *, view: str) -> dict[str, Any]:
    projections = _describe_projections(document.get("projections", {}))
    by_block: dict[str, list[dict[str, Any]]] = {}
    for mark in projections:
        for block_id in mark["block_ids"]:
            by_block.setdefault(block_id, []).append({
                "destination": mark["destination"],
                "remote": mark["remote"],
                "state": mark["state"],
                "status": mark["status"],
            })
    blocks = [
        describe_block(name, {**block, "block_id": name})
        for name, block in sorted(document["blocks"].items())
    ]
    for block in blocks:
        block["projections"] = by_block.get(block["block_id"], [])
    return {
        "view": view,
        "session_ref": session_id,
        "project": document.get("project", ""),
        "opened_at": document.get("opened", ""),
        "revision": document.get("revision", ""),
        "blocks": blocks,
        "projections": projections,
        "total": union_seconds([
            {**block, "block_id": name} for name, block in document["blocks"].items()
        ]),
    }


def summary(
    project_root: Path | str,
    session_id: str,
    *,
    period: str = "day",
) -> dict[str, Any]:
    """Aggregate the record by day, session or project.

    ``day`` counts blocks that start on the current UTC day (a block that
    crosses midnight is counted on its start day); ``session`` is the current
    session; ``project`` is every canonical file. Totals follow the union rule
    and stay ``null`` while any block is open.
    """
    if period not in ("day", "session", "project"):
        return {"error": f"unknown period {period!r}", "code": "TIMELOG_INVALID_PERIOD"}

    today = _iso(_now_epoch())[:10]
    per_session: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    directory = timelog_store.timelog_dir(project_root)
    for name in timelog_store.list_timelogs(project_root):
        ses = name.split("_", 1)[0]
        if period == "session" and ses != session_id:
            continue
        document = timelog_store.load(project_root, ses, opened_at=None,
                                      path=directory / name)
        if document is None:
            continue
        blocks = [
            {**block, "block_id": key}
            for key, block in sorted(document["blocks"].items())
        ]
        if period == "day":
            blocks = [b for b in blocks if b.get("start", "")[:10] == today]
        if not blocks:
            continue
        per_session.append({
            "session_ref": ses,
            "file": name,
            "opened": document.get("opened", ""),
            "blocks": len(blocks),
            "total": union_seconds(blocks),
        })
        collected.extend(blocks)

    return {
        "period": period,
        "day": today if period == "day" else "",
        "as_of": _iso(_now_epoch()),
        "sessions": per_session,
        "total": union_seconds(collected),
        "definition": "per-session union of closed intervals, then union across sessions",
        "window_vs_productive": (
            "native blocks are work windows that include pauses between turns; "
            "they are not productive hours"
        ),
    }


def review(
    project_root: Path | str,
    session_id: str,
    *,
    block_id: str,
    changes: dict[str, Any],
    reason: str,
    authorization_ref: str,
    expected_revision: str | None = None,
    opened_at: str | None = None,
) -> dict[str, Any]:
    """Authorized correction: write a revision with reason, mark receipts stale."""
    if not reason or not authorization_ref:
        return {"error": "a correction needs a reason and the user's authorization reference",
                "code": "TIMELOG_AUTHORIZATION_REQUIRED"}

    def mutate(document: dict[str, Any]) -> bool:
        block = document["blocks"].get(block_id)
        if block is None:
            raise timelog_store.UnknownOperation(block_id)
        changed = False
        for key in ("start", "end", "state"):
            if key in changes and changes[key] != block.get(key):
                block[key] = changes[key]
                changed = True
        if not changed:
            return False
        block["note"] = reason
        block["auth"] = authorization_ref
        block["revision"] = str(int(document["revision"] or "0") + 1)
        # Previously projected receipts become stale; the remote copy is never
        # edited here.
        for receipt in document["receipts"].values():
            if receipt.get("status") == "pending":
                receipt["status"] = "stale"
        # The native projection marks that cover the corrected origin become
        # stale too: a changed block is no longer what was sent.
        for mark in document.get("projections", {}).values():
            if (mark.get("status") != "stale"
                    and block_id in _projection_block_ids(mark.get("blocks", ""))):
                mark["status"] = "stale"
        return True

    try:
        result = timelog_store.update(
            project_root, session_id, operation_ref=f"review:{block_id}",
            expected_revision=expected_revision, opened_at=opened_at, mutate=mutate,
        )
    except timelog_store.UnknownOperation:
        return {"error": f"block {block_id!r} is not recorded in this timelog",
                "code": "TIMELOG_BLOCK_NOT_FOUND"}
    if result.get("state") == "uncertain":
        return {"status": "pending", "code": "TIMELOG_WRITE_UNCERTAIN",
                "detail": result.get("error", "")}
    return {"status": "applied" if result.get("applied") else "noop",
            "session_ref": session_id, "revision": result.get("revision", ""),
            "block_id": block_id}


def purge(
    project_root: Path | str,
    session_id: str,
    *,
    selection: list[str],
    mode: str = "delete",
    preview: bool = True,
    authorization_ref: str,
    expected_revision: str | None = None,
    opened_at: str | None = None,
) -> dict[str, Any]:
    """Archive, summarize or delete an exact selection. Preview mutates nothing.

    Projection marks live in the same file as the blocks they cover, so they are
    never removed ahead of their origin: a partial delete leaves the remaining
    marks intact, and a full delete removes them only under the same
    authorization and tombstone that removes the blocks themselves.
    """
    if mode not in ("archive", "summarize", "delete"):
        return {"error": f"unknown purge mode {mode!r}", "code": "TIMELOG_INVALID_MODE"}
    if not authorization_ref:
        return {"error": "purge needs the user's authorization reference",
                "code": "TIMELOG_AUTHORIZATION_REQUIRED"}

    document = timelog_store.load(project_root, session_id, opened_at=opened_at)
    if document is None:
        return {"error": "timelog not found", "code": "TIMELOG_NOT_FOUND"}

    present = [name for name in selection if name in document["blocks"]]
    missing = [name for name in selection if name not in document["blocks"]]
    plan = {
        "mode": mode,
        "selection": present,
        "not_found": missing,
        "auxiliaries": [_auxiliary(session_id)] if mode == "delete" else [],
        "declared_limits": "Git history and unmanaged external copies are out of scope",
    }

    if preview:
        return {"status": "preview", **plan}

    def mutate(doc: dict[str, Any]) -> bool:
        if mode == "delete":
            for name in present:
                doc["blocks"].pop(name, None)
        elif mode == "archive":
            for name in present:
                doc["blocks"][name]["state"] = "archived"
        else:  # summarize
            for name in present:
                block = doc["blocks"][name]
                block["state"] = "suppressed"
                block["note"] = "summarized on user's order"
        return bool(present)

    result = timelog_store.update(
        project_root, session_id, operation_ref=f"purge:{mode}",
        expected_revision=expected_revision, opened_at=opened_at, mutate=mutate,
    )
    if result.get("state") == "uncertain":
        return {"status": "pending", "code": "TIMELOG_WRITE_UNCERTAIN", **plan}

    if mode == "delete" and not result.get("blocks"):
        _apply_tombstone(project_root, session_id, opened_at, authorization_ref)

    return {"status": "applied", "revision": result.get("revision", ""), **plan}


def _auxiliary(session_id: str) -> str:
    return f"{session_id} timelog (canonical file and its locks)"


def _apply_tombstone(project_root: Path | str, session_id: str,
                     opened_at: str | None, authorization_ref: str) -> None:
    """Remove the canonical file and leave a minimal, content-free tombstone.

    The brain keeps only integrity metadata; the deleted content is not stored
    anywhere. A deleted file is never recreated by resume, retry or a pending
    projection.
    """
    with brain_lock(project_root):
        path = timelog_store.canonical_path(project_root, session_id, opened_at or "")
        if not path.exists() and opened_at is None:
            for name in timelog_store.list_timelogs(project_root):
                if name.startswith(f"{session_id}_"):
                    path = timelog_store.timelog_dir(project_root) / name
                    break
        with suppress(OSError):
            path.unlink(missing_ok=True)
        from .state import crud_update

        crud_update(
            brain_path(project_root),
            f"$4/SES:{session_id}",
            set_={"suppressed": "true", "timelog": "", "summary": "",
                  "purged_ref": authorization_ref, "purged_at": _now()},
            force=True,
        )


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


__all__ = ["query", "review", "purge", "describe_block", "union_seconds", "get_session"]
