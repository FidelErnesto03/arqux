"""cortex.migrate handler (BLP-010).

Reads a source .cortex file, applies a transform function by name
("reseccionar", "resigilar"), and writes the target .cortex file.

Uses temp file + rename for atomicity. Supports dry_run mode.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from ...cortex.parse_content import parse_content_entry
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root

VALID_TRANSFORMS = ("reseccionar", "resigilar")


def migrate_handler(
    source_path: str,
    target_path: str,
    transform: str,
    *,
    content: str | None = None,
    dry_run: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Migrate a .cortex file by applying a named transform.

    Args:
        source_path: Path to the source .cortex file.
        target_path: Path to the target .cortex file (will be created/overwritten).
        transform: Transform name. One of: ``"reseccionar"``,
            ``"resigilar"``.
        content: Optional CORTEX content with keys:
            ``source_path, target_path, transform``.
        dry_run: If True, report what would happen without writing.
        ctx: Permission context.

    Transforms:

    - ``reseccionar`` — re-numbers sections sequentially ($1, $2, $3, ...)
      preserving their content.
    - ``resigilar`` — uppercases all sigil IDs (e.g. ``fcs:`` → ``FCS:``)
      and ensures they match the canonical form.
    """
    # Merge content CORTEX.
    if content:
        parsed = parse_content_entry(content)
        if parsed:
            source_path = parsed.get("source_path", source_path)
            target_path = parsed.get("target_path", target_path)
            transform = parsed.get("transform", transform)

    if transform not in VALID_TRANSFORMS:
        return CortexOUT.error(
            f"invalid transform={transform!r} (must be one of {VALID_TRANSFORMS})",
            code="INVALID_ARGS",
        )

    src = Path(source_path)
    if not src.exists():
        return CortexOUT.error(f"source file not found: {source_path}", code="NOT_FOUND")

    try:
        source_text = src.read_text(encoding="utf-8")
    except OSError as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    # Apply transform.
    try:
        if transform == "reseccionar":
            migrated_text = _reseccionar(source_text)
        else:  # resigilar
            migrated_text = _resigilar(source_text)
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="TRANSFORM_ERROR")

    if dry_run:
        return CortexOUT.work(
            f"cortex.migrate dry_run source={source_path} target={target_path} "
            f"transform={transform} bytes={len(migrated_text)}",
            source_path=source_path,
            target_path=target_path,
            transform=transform,
            dry_run=True,
            bytes_out=len(migrated_text),
        )

    # Atomic write.
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target.stem}_",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(migrated_text)
        os.replace(tmp_path, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    _record_pulse(source_path, ctx, transform=transform, target=target_path)

    return CortexOUT.work(
        f"cortex.migrate ok source={source_path} target={target_path} "
        f"transform={transform} bytes={len(migrated_text)}",
        source_path=source_path,
        target_path=target_path,
        transform=transform,
        bytes_out=len(migrated_text),
    )


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


def _reseccionar(text: str) -> str:
    """Re-number sections sequentially ($1, $2, $3, ...).

    Preserves the section title and content. Only the section ID is
    renumbered.
    """
    import re

    # Find all section headers: $N or $N.M at the start of a line,
    # followed by optional ": TITLE".
    section_pattern = re.compile(r"^\$(\d+(?:\.\d+)?)(:\s*.*)?$", re.MULTILINE)
    matches = list(section_pattern.finditer(text))

    if not matches:
        return text

    # Build the new text by replacing each section ID with a sequential one.
    out = []
    last_end = 0
    counter = 0
    for m in matches:
        # Skip $0 (glossary) and $0.1 (metadata) — they stay as-is.
        if m.group(1).startswith("0"):
            out.append(text[last_end : m.end()])
            last_end = m.end()
            continue
        counter += 1
        out.append(text[last_end : m.start()])
        new_id = f"${counter}"
        title = m.group(2) or ""
        out.append(f"{new_id}{title}")
        last_end = m.end()
    out.append(text[last_end:])
    return "".join(out)


def _resigilar(text: str) -> str:
    """Uppercase all sigil IDs and ensure canonical form.

    ``fcs:primary{...}`` → ``FCS:primary{...}``
    ``lng:lesson_001{...}`` → ``LNG:lesson_001{...}``
    """
    import re

    # Match sigil entries at the start of a line: SIGIL:name{...}
    # where SIGIL is lowercase or mixed-case.
    pattern = re.compile(
        r"^([a-z][a-z0-9_]{1,9}):([A-Za-z0-9_\-.]+)(\{)",
        re.MULTILINE,
    )

    def _upper(match: re.Match) -> str:
        sigil = match.group(1).upper()
        name = match.group(2)
        brace = match.group(3)
        return f"{sigil}:{name}{brace}"

    return pattern.sub(_upper, text)


def _record_pulse(
    source_path: str | None,
    ctx: PermissionContext | None,
    *,
    transform: str,
    target: str,
) -> None:
    """Append a PULSE event for the migrate call (best-effort)."""
    try:
        root = find_project_root(start=source_path)
        if root is None:
            return
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id="-",
            kind="handler_call",
            agent=agent,
            payload=f"[cortex.migrate] transform={transform} target={target}",
        )
    except Exception:  # noqa: BLE001
        pass
