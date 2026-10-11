"""BLP-002 CA-01: every record declares its mandatory fields.

The memory core projects CORTEX entries into typed records. CA-01 requires
each record to declare origin, provenance, confidence, scope, TTL and status.
"""

from __future__ import annotations

import pytest

from arqux.memory import (
    SIGIL_KINDS,
    MemoryRecord,
    Origin,
    Provenance,
    record_from_entry,
    sanitize_payload,
)

ENTRY = {
    "sigil": "LNG",
    "name": "l1",
    "attrs": {"type": "process", "cause": "c", "lesson": "l", "prevention": "p"},
}


def _record(**overrides) -> MemoryRecord:
    kwargs = {
        "kind": "lesson",
        "address": "a#b:LNG:l1",
        "origin": Origin(source="a", section="b", sigil="LNG", name="l1"),
        "provenance": Provenance(derived_from="a#b:LNG:l1", source_sha256="x", rebuilt_at="z"),
        "confidence": 0.9,
        "scope": "project",
        "ttl": None,
        "created_at": "",
        "status": "active",
        "payload": {},
    }
    kwargs.update(overrides)
    return MemoryRecord(**kwargs)


def test_record_from_entry_declares_all_mandatory_fields() -> None:
    record = record_from_entry(
        ENTRY, source="brain.cortex", section="$2", source_sha256="abc", rebuilt_at="now"
    )
    assert record is not None
    assert record.kind == "lesson"
    assert record.origin.source == "brain.cortex"
    assert record.origin.section == "$2"
    assert record.provenance.derived_from == record.address
    assert record.provenance.source_sha256 == "abc"
    assert 0.0 <= record.confidence <= 1.0
    assert record.scope in {"session", "project", "workspace"}
    assert record.ttl is None or record.ttl >= 0
    assert record.status in {"active", "expired", "stale"}


def test_sigil_mapping_covers_the_allowed_sources() -> None:
    assert SIGIL_KINDS == {
        "SES": "session",
        "LNG": "lesson",
        "KNW": "knowledge",
        "AUD": "outcome",
    }


def test_entry_outside_allowed_sources_is_not_projected() -> None:
    entry = {"sigil": "RSK", "name": "r", "attrs": {"risk": "x"}}
    assert record_from_entry(
        entry, source="s", section="$1", source_sha256="h", rebuilt_at="t"
    ) is None


def test_secrets_are_not_stored() -> None:
    payload = sanitize_payload({"topic": "t", "api_key": "SECRET", "auth_token": "x", "password": "p"})
    assert payload == {"topic": "t"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "bogus"},
        {"scope": "galaxy"},
        {"status": "half"},
        {"confidence": 1.5},
        {"ttl": -1},
    ],
)
def test_invalid_records_are_rejected(overrides) -> None:
    with pytest.raises(ValueError):
        _record(**overrides)


def test_ttl_expiry_uses_created_at() -> None:
    record = _record(created_at="2026-10-01T00:00:00Z", ttl=60)
    base = record.created_epoch
    assert not record.is_expired(base + 30)
    assert record.is_expired(base + 120)


def test_record_round_trips_through_dict() -> None:
    record = record_from_entry(
        ENTRY, source="brain.cortex", section="$2", source_sha256="abc", rebuilt_at="now"
    )
    assert MemoryRecord.from_dict(record.to_dict()) == record
