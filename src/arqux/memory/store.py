"""BLP-002: local derived store with safe degradation.

The store is a disposable projection of CORTEX. It is never the source of
truth: whenever the index is absent, corrupt, truncated, ambiguous, expired or
stale, the store discards it and rebuilds from the canonical CORTEX documents.
It never repairs the index by guessing, and never returns partial or
unverified data (CA-04, CA-05, CA-07, CA-08).

Standard library only (CA-06).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .models import MemoryRecord
from .rebuild import INDEX_VERSION, MemoryIndex, build_index, content_hash, sha256_text


class MemoryStore(Protocol):
    """Queryable view over projected memory records."""

    def query(self, **filters: Any) -> list[MemoryRecord]: ...

    def rebuild(self) -> MemoryIndex: ...


@dataclass(frozen=True)
class LoadResult:
    """Outcome of a load: the records plus how they were obtained."""

    records: tuple[MemoryRecord, ...]
    origin: str
    reason: str


class LocalStore:
    """A JSON-file derived index over canonical CORTEX sources."""

    def __init__(
        self,
        index_path: str | Path,
        source_paths: Iterable[str | Path],
        *,
        ttl_seconds: int = 3600,
    ) -> None:
        self.index_path = Path(index_path)
        self.source_paths = [Path(p) for p in source_paths]
        self.ttl_seconds = int(ttl_seconds)

    # -- derived index --------------------------------------------------
    def _read_index(self, now_epoch: float) -> tuple[MemoryIndex | None, str]:
        """Return the index, or ``None`` with a reason to rebuild.

        Every rejection path discards the whole index rather than trusting a
        subset — a partially readable index is not a verified one.
        """
        if not self.index_path.is_file():
            return None, "index absent"
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, "index corrupt"

        if not isinstance(data, dict) or data.get("version") != INDEX_VERSION:
            return None, "index version mismatch"

        expires = data.get("expires_at")
        try:
            if expires is not None and now_epoch > float(expires):
                return None, "index expired"
        except (TypeError, ValueError):
            return None, "index corrupt"

        raw_records = data.get("records")
        if not isinstance(raw_records, list):
            return None, "index ambiguous"
        try:
            records = tuple(MemoryRecord.from_dict(r) for r in raw_records)
        except (KeyError, TypeError, ValueError):
            return None, "index corrupt"

        if data.get("content_hash") != content_hash(records):
            return None, "index hash mismatch"

        if self._is_stale(data.get("sources")):
            return None, "index stale"

        return (
            MemoryIndex(
                records=records,
                content_hash=str(data.get("content_hash", "")),
                rebuilt_at=str(data.get("rebuilt_at", "")),
                sources=dict(data.get("sources") or {}),
            ),
            "index valid",
        )

    def _is_stale(self, stored_sources: Any) -> bool:
        """True when a canonical source no longer matches the recorded hash."""
        if not isinstance(stored_sources, dict):
            return True
        for source, digest in stored_sources.items():
            path = Path(source)
            try:
                current = sha256_text(path.read_text(encoding="utf-8")) if path.is_file() else None
            except OSError:
                current = None
            if current != digest:
                return True
        return False

    def load(self, *, now_epoch: float | None = None) -> LoadResult:
        moment = time.time() if now_epoch is None else float(now_epoch)
        index, reason = self._read_index(moment)
        if index is None:
            index = self.rebuild(now_epoch=moment)
            return LoadResult(records=index.records, origin="rebuild", reason=reason)
        return LoadResult(records=index.records, origin="index", reason=reason)

    def rebuild(self, *, now_epoch: float | None = None) -> MemoryIndex:
        moment = time.time() if now_epoch is None else float(now_epoch)
        index = build_index(self.source_paths)
        self._write_index(index, moment)
        return index

    def _write_index(self, index: MemoryIndex, now_epoch: float) -> None:
        payload = index.to_dict()
        payload["expires_at"] = float(now_epoch) + self.ttl_seconds
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.index_path.with_name(self.index_path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.index_path)

    # -- queries --------------------------------------------------------
    def query(
        self,
        *,
        kind: str | None = None,
        scope: str | None = None,
        status: str | None = None,
        prefix: str | None = None,
        now_epoch: float | None = None,
    ) -> list[MemoryRecord]:
        result = self.load(now_epoch=now_epoch)
        out: list[MemoryRecord] = []
        for record in result.records:
            if kind is not None and record.kind != kind:
                continue
            if scope is not None and record.scope != scope:
                continue
            if status is not None and record.status != status:
                continue
            if prefix is not None and not record.address.startswith(prefix):
                continue
            out.append(record)
        return out
