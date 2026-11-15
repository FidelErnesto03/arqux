"""In-memory index for the learning engine (BLP-003)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ..protocol import LearningDocument, LearningEntry

ENGINE_VERSION = "native-1"
SCHEMA_VERSION = "1"
ALGORITHM = "sha256-wordset-16"


@dataclass
class Bin:
    """A single bucket in the index."""

    key: str
    entries: list[LearningEntry] = field(default_factory=list)

    def add(self, entry: LearningEntry) -> None:
        self.entries.append(entry)


@dataclass
class LearnIndex:
    bins: dict[str, Bin] = field(default_factory=dict)
    engine_version: str = ENGINE_VERSION
    schema_version: str = SCHEMA_VERSION

    def add(self, key: str, entry: LearningEntry) -> None:
        self.bins.setdefault(key, Bin(key)).add(entry)

    def lookup(self, key: str) -> list[LearningEntry]:
        bin_ = self.bins.get(key)
        return bin_.entries if bin_ else []

    def keys(self):
        return self.bins.keys()

    def __len__(self) -> int:
        return len(self.bins)


def _words(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text.lower())
    return [t for t in tokens if t]


def _fingerprint(entry: LearningEntry) -> str:
    words = _words(entry.name + " " + entry.sigil + " " + str(entry.value))
    return hashlib.sha256(" ".join(sorted(words)).encode()).hexdigest()[:16]


def rebuild_index(document: LearningDocument) -> LearnIndex:
    idx = LearnIndex()
    for _section, entry in document.iter_entries():
        if entry.sigil in {"SES", "LNG", "KNW", "WRK", "OBJ", "FCS"}:
            idx.add(_fingerprint(entry), entry)
    return idx


def remove_from_index(index: LearnIndex, entry: LearningEntry) -> None:
    key = _fingerprint(entry)
    bin_ = index.bins.get(key)
    if bin_ is None:
        return
    bin_.entries = [e for e in bin_.entries if e.name != entry.name or e.sigil != entry.sigil]
    if not bin_.entries:
        del index.bins[key]


__all__ = ["ALGORITHM", "Bin", "ENGINE_VERSION", "LearnIndex", "SCHEMA_VERSION", "rebuild_index", "remove_from_index"]
