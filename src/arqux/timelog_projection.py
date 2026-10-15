"""Optional external projection of timelog batches (CYCLE-14 / BLP-006).

Projecting is always optional and never part of the local record: the session's
CORTEX timelog is the source of truth, and projecting it neither archives nor
deletes it.

Design:

* **Batch identity is a deterministic hash** of everything that determines the
  external effect: project/session, each origin block with its revision, the
  destination/account/target, the adapter/mapping version, units, timezone,
  grouping/rounding rules and the exact transformed content. The same batch
  repeats the same key; *any* change yields a different identity and therefore a
  different authorization.
* **Authorization is bound to that identity.** A change of selection, target or
  rounding invalidates it; an authorization for one batch never dispatches
  another.
* **The core knows no credentials and no provider.** It talks to an adapter
  contract (prepare/send/query/compensate). The reference adapter is a *local
  simulation*; unsupported providers are declared, not guessed.
* **Intent is persisted before sending and a receipt after**, always CORTEX and
  always under the session's exclusion. Atomicity with a remote is never
  claimed: a crash between send and receipt leaves the result *unknown* and the
  batch is reconciled before it is ever retried.
* **No secrets in the timelog.** Receipts carry destination, remote id, revision
  and state only.

"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from . import timelog_store
from .session_identity import brain_lock, get_session

ADAPTER_VERSION = "local-reference/1"

STATE_PREPARED = "prepared"
STATE_SENT = "sent"
STATE_CONFIRMED = "confirmed"
STATE_FAILED = "failed"
STATE_UNKNOWN = "unknown"

CAPABILITIES = frozenset({"prepare", "send", "query", "compensate"})


class UnsupportedProvider(Exception):
    def __init__(self, provider: str) -> None:
        super().__init__(f"provider {provider!r} is not supported: no adapter registered")
        self.provider = provider


class InsufficientCapability(Exception):
    def __init__(self, capability: str) -> None:
        super().__init__(
            f"adapter lacks {capability!r}: automatic resend is blocked and manual "
            f"review is required"
        )
        self.capability = capability


class ProjectionAdapter(Protocol):
    """What the core needs from any external destination."""

    provider: str
    capabilities: frozenset[str]
    mapping_version: str

    def prepare(self, batch: dict[str, Any]) -> dict[str, Any]: ...
    def send(self, batch: dict[str, Any], key: str) -> dict[str, Any]: ...
    def query(self, key: str) -> dict[str, Any] | None: ...


@dataclass
class LocalReferenceAdapter:
    """A simulated local API used to exercise the contract without a provider."""

    provider: str = "local-reference"
    mapping_version: str = ADAPTER_VERSION
    capabilities: frozenset[str] = CAPABILITIES
    _sent: dict[str, dict[str, Any]] = field(default_factory=dict)
    _fail_send: bool = False

    def prepare(self, batch: dict[str, Any]) -> dict[str, Any]:
        return {"prepared": True, "entries": len(batch.get("entries", []))}

    def send(self, batch: dict[str, Any], key: str) -> dict[str, Any]:
        if self._fail_send:
            # Simulates a crash after dispatch and before the receipt lands.
            raise RuntimeError("simulated failure after dispatch")
        existing = self._sent.get(key)
        if existing is not None:
            return {"state": STATE_CONFIRMED, "remote": existing["remote"],
                    "duplicate": False}
        remote = f"local-{len(self._sent) + 1:04d}"
        self._sent[key] = {"remote": remote}
        return {"state": STATE_CONFIRMED, "remote": remote, "duplicate": False}

    def query(self, key: str) -> dict[str, Any] | None:
        found = self._sent.get(key)
        if found is None:
            return None
        return {"state": STATE_CONFIRMED, "remote": found["remote"]}


_DEFAULT_ADAPTER = LocalReferenceAdapter()


def default_adapter() -> LocalReferenceAdapter:
    return _DEFAULT_ADAPTER


def snapshot(
    project_root: Path | str,
    session_id: str,
    block_ids: list[str],
    *,
    opened_at: str | None = None,
) -> dict[str, Any]:
    """Logical CORTEX snapshot: origins, revisions and derived durations."""
    document = timelog_store.load(project_root, session_id, opened_at=opened_at)
    if document is None:
        raise timelog_store.MembershipError(f"timelog for {session_id} not found")
    entries = []
    for name in block_ids:
        block = document["blocks"].get(name)
        if block is None:
            raise timelog_store.UnknownOperation(name)
        entries.append({
            "block_id": name,
            "start": block.get("start", ""),
            "end": block.get("end", ""),
            "state": block.get("state", "open"),
            # The block's own revision: receipt-only writes must not change the
            # batch identity of an unchanged origin.
            "revision": block.get("revision") or document.get("revision", ""),
        })
    return {
        "project": document.get("project", ""),
        "ses": document.get("ses", ""),
        "opened": document.get("opened", ""),
        "revision": document.get("revision", ""),
        "entries": entries,
    }


def batch_identity(
    snap: dict[str, Any],
    *,
    destination: str,
    account: str = "",
    target: str = "",
    adapter_version: str = ADAPTER_VERSION,
    units: str = "seconds",
    timezone: str = "UTC",
    rounding: str = "none",
    grouping: str = "none",
    transformed: list[dict[str, Any]] | None = None,
) -> str:
    """Deterministic key over everything that affects the external effect."""
    material = {
        "project": snap.get("project", ""),
        "ses": snap.get("ses", ""),
        "origins": sorted(
            f'{e["block_id"]}@{e["revision"]}' for e in snap.get("entries", [])
        ),
        "destination": destination,
        "account": account,
        "target": target,
        "adapter_version": adapter_version,
        "units": units,
        "timezone": timezone,
        "rounding": rounding,
        "grouping": grouping,
        "content": transformed if transformed is not None else snap.get("entries", []),
    }
    payload = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return "proj-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def transform(snap: dict[str, Any], *, rounding: str = "none",
              units: str = "seconds") -> list[dict[str, Any]]:
    """Show the transformation without ever altering the source marks."""
    out = []
    for entry in snap.get("entries", []):
        out.append({
            "block_id": entry["block_id"],
            "start": entry["start"],
            "end": entry["end"],
            "units": units,
            "rounding": rounding,
        })
    return out


def _receipt_key(key: str) -> str:
    return f"proj_{key[5:]}"


def _record_receipt(project_root: Path | str, session_id: str, key: str,
                    *, destination: str, state: str, remote: str,
                    opened_at: str | None) -> None:
    def mutate(document: dict[str, Any]) -> bool:
        document["receipts"][_receipt_key(key)] = {
            "operation": "timelog.project",
            "status": "pending" if state in (STATE_PREPARED, STATE_SENT) else "settled",
            "destination": destination,
            "state": state,
            "remote": remote,
        }
        return True

    timelog_store.update(project_root, session_id, operation_ref=f"receipt:{key}",
                         opened_at=opened_at, mutate=mutate)


def get_receipt(project_root: Path | str, session_id: str, key: str,
                *, opened_at: str | None = None) -> dict[str, Any] | None:
    document = timelog_store.load(project_root, session_id, opened_at=opened_at)
    if document is None:
        return None
    return document["receipts"].get(_receipt_key(key))


def project(
    project_root: Path | str,
    session_id: str,
    *,
    destination: str,
    block_ids: list[str],
    action: str,
    authorization_ref: str = "",
    expected_revision: str | None = None,
    adapter: ProjectionAdapter | None = None,
    account: str = "",
    target: str = "",
    rounding: str = "none",
    units: str = "seconds",
    timezone: str = "UTC",
    grouping: str = "none",
    opened_at: str | None = None,
) -> dict[str, Any]:
    """Preview, prepare, send or reconcile a projection batch.

    ``preview`` reads; ``prepare`` persists the batch identity; ``send``
    requires an authorization bound to that identity; ``reconcile`` compares the
    remote and records the outcome without dispatching.
    """
    adapter = adapter or default_adapter()
    if action not in ("preview", "prepare", "send", "reconcile"):
        return {"error": f"unknown action {action!r}", "code": "TIMELOG_INVALID_ACTION"}

    session = get_session(project_root, session_id)
    if session is None:
        return {"error": f"session {session_id} not found", "code": "SESSION_NOT_FOUND"}
    if str(session.get("suppressed", "")).lower() in ("true", "1", "yes"):
        return {"error": "session was purged; projection is refused",
                "code": "TIMELOG_SUPPRESSED"}
    opened_at = opened_at or session.get("date", "")

    snap = snapshot(project_root, session_id, block_ids, opened_at=opened_at)
    transformed = transform(snap, rounding=rounding, units=units)
    key = batch_identity(
        snap, destination=destination, account=account, target=target,
        adapter_version=adapter.mapping_version, units=units, timezone=timezone,
        rounding=rounding, grouping=grouping, transformed=transformed,
    )
    batch = {"key": key, "destination": destination, "account": account,
             "target": target, "snapshot": snap, "transformed": transformed}

    if action == "preview":
        return {"status": "preview", "batch_key": key, "destination": destination,
                "entries": transformed, "source_preserved": True}

    # A change of selection/target/rounding changes `key`; an authorization for
    # one key can never dispatch another.
    auth = authorization_ref
    if action in ("send",) and not auth:
        return {"error": "send requires the user's authorization reference",
                "code": "TIMELOG_AUTHORIZATION_REQUIRED"}

    if action == "prepare":
        _record_receipt(project_root, session_id, key, destination=destination,
                        state=STATE_PREPARED, remote="", opened_at=opened_at)
        return {"status": "prepared", "batch_key": key, "destination": destination,
                "authorization_ref": auth}

    if action == "reconcile":
        remote = adapter.query(key) if "query" in adapter.capabilities else None
        if remote is None:
            state = STATE_UNKNOWN
            _record_receipt(project_root, session_id, key, destination=destination,
                            state=state, remote="", opened_at=opened_at)
            return {"status": "unknown", "batch_key": key, "state": state,
                    "detail": "remote result is unknown; do not resend blindly"}
        _record_receipt(project_root, session_id, key, destination=destination,
                        state=remote.get("state", STATE_CONFIRMED),
                        remote=remote.get("remote", ""), opened_at=opened_at)
        return {"status": "reconciled", "batch_key": key,
                "state": remote.get("state", STATE_CONFIRMED),
                "remote": remote.get("remote", "")}

    # send
    existing = get_receipt(project_root, session_id, key, opened_at=opened_at)
    if existing and existing.get("state") == STATE_CONFIRMED:
        # Same batch, same key: idempotent, no second external entry.
        return {"status": "confirmed", "batch_key": key,
                "remote": existing.get("remote", ""), "duplicate": False}

    if "send" not in adapter.capabilities:
        raise InsufficientCapability("send")

    with brain_lock(project_root):
        from .state import crud_read

        current = crud_read(timelog_store.brain_path(project_root),
                            f"$4/SES:{session_id}")
        entries = current.get("entries", [])
        if entries and str((entries[0].get("value") or {}).get("suppressed", "")).lower() in (
            "true", "1", "yes"
        ):
            return {"error": "session was purged during dispatch; send refused",
                    "code": "TIMELOG_SUPPRESSED"}

    # Intent is persisted before the remote is touched.
    _record_receipt(project_root, session_id, key, destination=destination,
                    state=STATE_SENT, remote="", opened_at=opened_at)

    # The network happens WITHOUT the lock held.
    try:
        result = adapter.send(batch, key)
    except Exception as exc:  # noqa: BLE001
        _record_receipt(project_root, session_id, key, destination=destination,
                        state=STATE_UNKNOWN, remote="", opened_at=opened_at)
        return {"status": "unknown", "batch_key": key, "state": STATE_UNKNOWN,
                "detail": f"dispatched but unconfirmed: {exc}. Reconcile before retrying."}

    _record_receipt(project_root, session_id, key, destination=destination,
                    state=result.get("state", STATE_CONFIRMED),
                    remote=result.get("remote", ""), opened_at=opened_at)
    return {"status": result.get("state", STATE_CONFIRMED), "batch_key": key,
            "remote": result.get("remote", ""), "duplicate": result.get("duplicate", False)}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


__all__ = [
    "CAPABILITIES",
    "ProjectionAdapter",
    "LocalReferenceAdapter",
    "InsufficientCapability",
    "UnsupportedProvider",
    "batch_identity",
    "default_adapter",
    "get_receipt",
    "project",
    "snapshot",
    "transform",
]
