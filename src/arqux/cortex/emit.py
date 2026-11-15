"""Public ideatic emit helper (BLP-006 / gap 2.12/U4)."""
from __future__ import annotations

from .writer import write_cortex_from_json


def emit_ideatic(document: dict, *, strict: bool = True) -> str:
    """Emit ideatic/CORTEX text from a document model.

    Thin public helper over the native writer for tooling/tests that need a
    stable emission entrypoint.
    """
    return write_cortex_from_json(document, strict=strict)


__all__ = ["emit_ideatic"]
