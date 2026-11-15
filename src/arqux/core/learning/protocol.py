"""Document protocol for the native learning engine (BLP-002).

The learning engine used the codec's ``CortexDocument``/``Entry`` AST. Under
CORTEX 1.0 the codec may no longer carry ``learning`` at all (constitution,
Article III), so the engine now depends on a *protocol* it owns, not on an
externally provided dataclass.

Three members, read-only. That is the minimum the engine needs.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LearningEntry:
    """A single idea inside a learning-eligible section.

    Simpler than the codec's full AST: no positions, no glossary
    registration, just the four facts the engine reads.
    """

    sigil: str
    name: str
    value: dict[str, Any]
    section: str
    type: str  # "attrs" | "cuerpo" | "attrs-pos" | "bloque" | "relacion"


@runtime_checkable
class LearningDocument(Protocol):
    """Read-only view over a brain document.

    ``iter_entries`` yields ``(section_id, entry)`` pairs in document order.
    Callers that only need the entry can ignore the section id.
    """

    def iter_entries(self) -> Iterator[tuple[str, LearningEntry]]:
        ...

    def get_section(self, section_id: str) -> Any | None:
        """Return the raw section model, or ``None`` when absent."""
        ...


__all__ = ["LearningDocument", "LearningEntry"]
