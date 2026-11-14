"""A-01: post-write transaction guard for .cortex artifacts.

Every entry mutation is a read-modify-write of a governed file. The write is
only acceptable when the resulting document changes **exactly** the target
entry: any section outside the allowed set that differs is collateral damage.

The allowed set is resolved by the caller **before** the mutation with the
same selector semantics the mutator uses (explicit `$N/...` section, or the
sections `crud_read` matches for a legacy selector). Names are never used to
widen the set: an entry named identically in two sections must not authorise
writing to both (HD-01, audit 2026-11-13 — the previous name-based collection
masked collateral damage on the other same-named entry).

Root cause this guards (2026-11-13 kernel incident): the parser used to
classify any body containing a ``word: value`` fragment as attrs, so a prose
cuerpo was truncated on the next rewrite while the handler returned ``ok``.
The parser now classifies strictly; this guard is the second, independent
control.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from .reader import cortex_to_dict

__all__ = ["guard_write", "sections_changed"]


def _entries_by_section(doc: dict) -> dict[str, list]:
    return {
        str(section.get("id", "")): list(section.get("entries") or [])
        for section in doc.get("sections", [])
        if isinstance(section, dict)
    }


def sections_changed(before_text: str, after_text: str) -> list[str]:
    """Section ids whose entries differ between the two documents."""
    before = _entries_by_section(cortex_to_dict(before_text))
    after = _entries_by_section(cortex_to_dict(after_text))
    changed: list[str] = []
    for sid in sorted(set(before) | set(after)):
        if before.get(sid) != after.get(sid):
            changed.append(sid)
    return changed


def _atomic_restore(path: Path, text: str) -> bool:
    """Restore *text* atomically (temp file + rename). True on success."""
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".restore", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise
        return True
    except OSError:
        return False


def guard_write(
    path: str | Path,
    before_text: str,
    *,
    allowed_sections: Iterable[str],
) -> dict | None:
    """Verify a completed write touched only the allowed sections.

    *allowed_sections* must be resolved by the caller from the selector
    semantics BEFORE the mutation. Returns ``None`` when the write is clean;
    otherwise restores *before_text* atomically and returns an error dict
    describing the violation (callers surface it as ``VALIDATION``).
    """
    target = Path(path)
    try:
        after_text = target.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem drift
        return {"error": f"post-write read failed: {exc}"}

    allowed = {str(section) for section in allowed_sections}
    violated = [
        sid for sid in sections_changed(before_text, after_text)
        if sid not in allowed
    ]
    if not violated:
        return None

    rolled_back = _atomic_restore(target, before_text)

    return {
        "error": (
            f"write altered unrelated sections {violated} — "
            + ("rolled back" if rolled_back else "ROLLBACK FAILED")
        ),
        "sections": violated,
        "rolled_back": rolled_back,
    }
