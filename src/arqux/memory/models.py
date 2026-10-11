"""BLP-002: Memory Core typed records.

A :class:`MemoryRecord` is a *projection* of an entry that lives in a
canonical CORTEX document. The record is never a source of truth: it always
carries the address of the entry it came from, so every read can be traced
back to the CORTEX file (CA-08).

Standard library only (BLP-002 CA-06).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

# Allowed sources (BLP-002 §3): sessions, lessons, knowledge and outcomes.
SIGIL_KINDS: dict[str, str] = {
    "SES": "session",
    "LNG": "lesson",
    "KNW": "knowledge",
    "AUD": "outcome",
}
VALID_KINDS = frozenset(SIGIL_KINDS.values())
VALID_SCOPES = frozenset({"session", "project", "workspace"})
VALID_STATUSES = frozenset({"active", "expired", "stale"})

_DEFAULT_CONFIDENCE = {"lesson": 0.9, "knowledge": 0.8, "outcome": 0.7, "session": 0.6}
_DEFAULT_SCOPE = {
    "session": "session",
    "lesson": "project",
    "knowledge": "project",
    "outcome": "project",
}
# §7.4 — no secrets or unnecessary payloads are stored.
_SECRET_MARKERS = ("token", "secret", "password", "passwd", "api_key", "apikey", "private")


@dataclass(frozen=True)
class Origin:
    """Where inside the canonical document the record came from."""

    source: str
    section: str
    sigil: str
    name: str

    @property
    def address(self) -> str:
        return f"{self.source}#{self.section}:{self.sigil}:{self.name}"


@dataclass(frozen=True)
class Provenance:
    """How the projection was produced; always points back to CORTEX."""

    derived_from: str
    source_sha256: str
    rebuilt_at: str


@dataclass(frozen=True)
class MemoryRecord:
    """A typed projection of one canonical CORTEX entry."""

    kind: str
    address: str
    origin: Origin
    provenance: Provenance
    confidence: float
    scope: str
    ttl: int | None
    created_at: str
    status: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f"invalid record kind: {self.kind!r}")
        if self.scope not in VALID_SCOPES:
            raise ValueError(f"invalid scope: {self.scope!r}")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {self.status!r}")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence!r}")
        if self.ttl is not None and int(self.ttl) < 0:
            raise ValueError(f"ttl must be >= 0: {self.ttl!r}")

    @property
    def created_epoch(self) -> float:
        """Epoch seconds of ``created_at``; 0.0 when unparseable (never guessed)."""
        if not self.created_at:
            return 0.0
        try:
            return datetime.fromisoformat(
                self.created_at.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            return 0.0

    def is_expired(self, now_epoch: float) -> bool:
        if self.ttl is None:
            return False
        base = self.created_epoch
        return base > 0.0 and now_epoch > base + int(self.ttl)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "address": self.address,
            "origin": asdict(self.origin),
            "provenance": asdict(self.provenance),
            "confidence": self.confidence,
            "scope": self.scope,
            "ttl": self.ttl,
            "created_at": self.created_at,
            "status": self.status,
            "payload": dict(self.payload),
        }

    def stable_dict(self) -> dict[str, Any]:
        """Deterministic view used for hashing — excludes volatile fields.

        ``rebuilt_at`` changes on every rebuild and must not enter the content
        hash, or CA-03 (identical successive rebuilds) could never hold.
        """
        data = self.to_dict()
        data["provenance"].pop("rebuilt_at", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecord:
        return cls(
            kind=str(data["kind"]),
            address=str(data["address"]),
            origin=Origin(**data["origin"]),
            provenance=Provenance(**data["provenance"]),
            confidence=float(data["confidence"]),
            scope=str(data["scope"]),
            ttl=data.get("ttl"),
            created_at=str(data.get("created_at") or ""),
            status=str(data["status"]),
            payload=dict(data.get("payload") or {}),
        )


def sanitize_payload(attrs: dict[str, Any]) -> dict[str, Any]:
    """Drop obvious secrets; keep the payload minimal (BLP-002 §7.4)."""
    clean: dict[str, Any] = {}
    for key, value in attrs.items():
        if any(marker in str(key).lower() for marker in _SECRET_MARKERS):
            continue
        clean[str(key)] = value
    return clean


def record_from_entry(
    entry: dict[str, Any],
    *,
    source: str,
    section: str,
    source_sha256: str,
    rebuilt_at: str,
) -> MemoryRecord | None:
    """Project one CORTEX entry into a :class:`MemoryRecord`.

    Returns ``None`` when the entry's sigil is not an allowed memory source,
    so the projection stays within the declared scope (BLP-002 §3).
    """
    kind = SIGIL_KINDS.get(str(entry.get("sigil", "")))
    if kind is None:
        return None
    attrs = entry.get("attrs")
    if not isinstance(attrs, dict):
        attrs = {"body": entry.get("body")}

    origin = Origin(
        source=source, section=section, sigil=str(entry.get("sigil", "")), name=str(entry.get("name", ""))
    )

    raw_conf = attrs.get("confidence")
    try:
        confidence = float(raw_conf) if raw_conf is not None else _DEFAULT_CONFIDENCE[kind]
    except (TypeError, ValueError):
        confidence = _DEFAULT_CONFIDENCE[kind]

    scope = str(attrs.get("scope") or _DEFAULT_SCOPE[kind])
    if scope not in VALID_SCOPES:
        scope = _DEFAULT_SCOPE[kind]

    raw_ttl = attrs.get("ttl")
    try:
        ttl = int(raw_ttl) if raw_ttl is not None else None
    except (TypeError, ValueError):
        ttl = None

    # ``created_at`` stays stable across rebuilds: from the source attrs, or
    # empty — never the volatile rebuild timestamp.
    created_at = str(attrs.get("date") or attrs.get("created_at") or "")

    return MemoryRecord(
        kind=kind,
        address=origin.address,
        origin=origin,
        provenance=Provenance(
            derived_from=origin.address, source_sha256=source_sha256, rebuilt_at=rebuilt_at
        ),
        confidence=confidence,
        scope=scope,
        ttl=ttl,
        created_at=created_at,
        status="active",
        payload=sanitize_payload(attrs),
    )
