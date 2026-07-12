"""Cortex read/write/verify/render handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import cortex_read, cortex_write, cortex_verify, cortex_render


# ---------------------------------------------------------------------------
# SectionCounter — in-memory sequential counter per (file, section)
# ---------------------------------------------------------------------------

_section_counter: dict[str, int] = {}

def _next_number(path: str, section: str) -> str:
    """Increment and return the next zero-padded 4-digit suffix for *section* in *path*."""
    key = f"{path}:::{section}"
    _section_counter[key] = _section_counter.get(key, 0) + 1
    return f"_{_section_counter[key]:04d}"


def read_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read and parse a .cortex file using CODEC-CORTEX.

    Returns sections, glossary, and raw content.
    """
    try:
        result = cortex_read(Path(path))
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    return CortexOUT.work(
        f"cortex.read ok path={path} sections={result['sections']}",
        path=str(result["path"]),
        sections=result["sections"],
        glossary=result["glossary"],
        size_bytes=result["size_bytes"],
    )


def write_handler(
    path: str,
    content: str,
    force: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Write (atomically) a .cortex file from CORTEX source text.

    Validates before writing. Pass force=True to skip validation errors.
    """
    try:
        result = cortex_write(Path(path), content, force=force)
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="WRITE_ERROR")

    if "error" in result:
        return CortexOUT.error(result["error"], code="VALIDATION_FAILED")

    return CortexOUT.work(
        f"cortex.write ok path={path} bytes={result['bytes_written']}",
        path=path,
        bytes_written=result["bytes_written"],
        backup=result.get("backup"),
        diagnostics=result.get("diagnostics", []),
    )


def verify_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Verify a .cortex file's structure using CODEC-CORTEX.

    Returns valid (bool), diagnostics, sections count, entries count.
    """
    try:
        result = cortex_verify(Path(path))
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="VERIFY_ERROR")

    profile = "OK" if result["valid"] else "ERROR"
    return CortexOUT.profile(
        profile,
        f"cortex.verify path={path} valid={result['valid']} "
        f"sections={result['sections']} entries={result['entries']}",
        path=path,
        valid=result["valid"],
        sections=result["sections"],
        entries=result["entries"],
        diagnostics=result.get("diagnostics", []),
    )


def render_handler(
    path: str,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Render a .cortex file to HCORTEX READ markdown."""
    try:
        md = cortex_render(Path(path))
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError as exc:
        return CortexOUT.error(f"CODEC-CORTEX not available: {exc}", code="MISSING_DEPENDENCY")
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="RENDER_ERROR")

    return CortexOUT.work(
        f"cortex.render ok path={path} rendered={len(md)} chars",
        path=path,
        format="hcortex-read",
        content=md,
    )
