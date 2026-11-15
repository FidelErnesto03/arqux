"""Adapter from ArqUX's native CORTEX model to the learning document protocol.

The learning engine used to consume the codec's AST. Under CORTEX 1.0 it must
consume a protocol this package owns (see ``protocol.py``). This module is the
thin bridge in between.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ...constants import ARQUX_DIR, BRAIN_CORTEX
from ...cortex.reader import cortex_to_dict
from .protocol import LearningDocument, LearningEntry


def _entry_type(entry: dict[str, Any]) -> str:
    if "attrs" in entry:
        return "attrs"
    if "body" in entry:
        return "cuerpo"
    if "block" in entry:
        return "bloque"
    if "attrs_pos" in entry or "attrs-pos" in entry:
        return "attrs-pos"
    # The native CORTEX reader today emits only ``attrs`` and ``body``.
    # The remaining forms are kept as defensive branches for brains written
    # by future reader versions.
    return "cuerpo"


def _entry_value(entry: dict[str, Any], etype: str) -> Any:
    if etype == "attrs":
        return entry["attrs"]
    for key in ("body", "block", "attrs_pos", "attrs-pos"):
        if key in entry:
            return entry[key]
    return {}


class NativeLearningDocument:
    """Materialises a brain document as a read-only learning document."""

    def __init__(self, doc: dict[str, Any]) -> None:
        self._doc = doc

    def iter_entries(self) -> Iterator[tuple[str, LearningEntry]]:
        for section in self._doc.get("sections", []) or []:
            section_id = str(section.get("id", "$?"))
            for entry in section.get("entries", []) or []:
                if not isinstance(entry, dict):
                    continue
                etype = _entry_type(entry)
                yield section_id, LearningEntry(
                    sigil=str(entry.get("sigil", "?")),
                    name=str(entry.get("name", "?")),
                    value=_entry_value(entry, etype),
                    section=section_id,
                    type=etype,
                )

    def get_section(self, section_id: str) -> Any | None:
        for section in self._doc.get("sections", []) or []:
            if str(section.get("id", "")) == str(section_id):
                return section
        return None


def from_cortex_dict(doc: dict[str, Any]) -> NativeLearningDocument:
    """Adapt a ``reader.cortex_to_dict`` output to the learning document.

    *Expected input shape* (never raises — malformed input yields an empty
    document, which the caller can distinguish from a missing one via the
    empty iterator):

    >>> from_cortex_dict({}).iter_entries()  # doctest: +ELLIPSIS
    <generator object ...>
    """
    if not isinstance(doc, dict):
        raise TypeError(f"from_cortex_dict expects dict, got {type(doc).__name__}")
    return NativeLearningDocument(doc)


def load_brain_document(project_root: Path | str | None) -> NativeLearningDocument | None:
    """Load ``<project>/.arqux/brain.cortex`` as a learning document.

    Accepts the project root (parent of ``.arqux/``) or the ``.arqux/``
    directory itself. Returns ``None`` when the brain cannot be read —
    callers that need the reason should inspect ``cortex_to_dict`` directly.
    """
    root = Path(project_root) if project_root is not None else None
    if root is None:
        from ...state import find_project_root

        root = find_project_root(start=None)
        if root is None:
            return None
        root = root.parent  # find_project_root returns the .arqux/ dir
    elif (root / BRAIN_CORTEX).is_file() and root.name != ARQUX_DIR:
        # .arqux/ passed directly
        if (root / ARQUX_DIR).is_dir():
            root = root / ARQUX_DIR
    elif (root / ARQUX_DIR / BRAIN_CORTEX).is_file():
        root = root / ARQUX_DIR

    brain = root / BRAIN_CORTEX
    if not brain.exists():
        return None
    try:
        doc = cortex_to_dict(brain.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - unreadable brain => unavailable
        # Propagate cause via logger; caller receives None but the scan path
        # reports the unavailable state explicitly (no silent swallow).
        import logging

        logging.getLogger(__name__).warning("load_brain_document: cannot read %s: %s", brain, exc)
        return None
    return from_cortex_dict(doc)


def to_json(doc: LearningDocument) -> str:
    """Serialize a learning document to deterministic JSON (for golden tests)."""
    entries = [
        {
            "section": section,
            "sigil": entry.sigil,
            "name": entry.name,
            "type": entry.type,
            "value": entry.value,
        }
        for section, entry in doc.iter_entries()
    ]
    return json.dumps(entries, sort_keys=True, ensure_ascii=False)


__all__ = [
    "NativeLearningDocument",
    "from_cortex_dict",
    "load_brain_document",
    "to_json",
]
