"""BLP-002: deterministic rebuild of the derived memory index from CORTEX.

The rebuild reads only canonical CORTEX documents through ArqUX's own parser
(:func:`arqux.cortex.reader.cortex_to_dict`) and produces a *deterministic*
record set: two runs over the same inputs yield the same content hash
(CA-03), and deleting the index and rebuilding yields an equivalent set
(CA-02).

The index is a projection, never a source of truth. Standard library only
(CA-06).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..cortex.reader import cortex_to_dict
from .models import MemoryRecord, record_from_entry

INDEX_VERSION = 1


@dataclass(frozen=True)
class MemoryIndex:
    """A projected record set plus its drift-proof identity."""

    records: tuple[MemoryRecord, ...]
    content_hash: str
    rebuilt_at: str
    sources: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "version": INDEX_VERSION,
            "rebuilt_at": self.rebuilt_at,
            "content_hash": self.content_hash,
            "sources": dict(self.sources),
            "records": [record.to_dict() for record in self.records],
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(records: Iterable[MemoryRecord]) -> str:
    """Stable hash of the record set, excluding volatile fields.

    ``rebuilt_at`` is stripped by :meth:`MemoryRecord.stable_dict`, so two
    rebuilds of unchanged sources hash identically (CA-03).
    """
    canonical = [record.stable_dict() for record in sorted(records, key=lambda r: r.address)]
    blob = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(blob)


def build_index(
    source_paths: Iterable[str | Path], *, rebuilt_at: str | None = None
) -> MemoryIndex:
    """Project every allowed entry of every readable source into an index."""
    moment = rebuilt_at or _utc_now()
    records: list[MemoryRecord] = []
    sources: dict[str, str] = {}

    for raw in source_paths:
        path = Path(raw)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        digest = sha256_text(text)
        sources[str(path)] = digest
        document = cortex_to_dict(text)
        for section in document.get("sections", []):
            section_id = str(section.get("id", ""))
            if section_id == "$0":
                continue
            for entry in section.get("entries", []):
                record = record_from_entry(
                    entry,
                    source=str(path),
                    section=section_id,
                    source_sha256=digest,
                    rebuilt_at=moment,
                )
                if record is not None:
                    records.append(record)

    records.sort(key=lambda r: (r.address, r.kind))
    return MemoryIndex(
        records=tuple(records),
        content_hash=content_hash(records),
        rebuilt_at=moment,
        sources=sources,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
