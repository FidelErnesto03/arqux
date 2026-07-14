"""Cortex read/write/verify/render handlers."""

from __future__ import annotations

from pathlib import Path

from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...state import cortex_read, cortex_render, cortex_verify, cortex_write
from ...sync import sync_brain

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
    *,
    mode: str = "cortex",
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Read and parse a .cortex file using CODEC-CORTEX.

    Two modes are supported (BLP-004):

    - ``mode="cortex"`` (default, canal I): returns the raw CORTEX
      entries as a dict — ``{sections: [...], glossary: {...}, raw: str,
      size_bytes: int}``. This is the canonical form for handler-to-handler
      communication.
    - ``mode="hcortex"`` (canal E): renders the file as human-readable
      HCORTEX markdown. This is the previous behaviour of
      ``cortex.render`` and is intended for display to the Architect.

    Args:
        path: Path to the ``.cortex`` file.
        mode: Output mode — ``"cortex"`` (default) or ``"hcortex"``.
        ctx: Permission context.
    """
    if mode not in ("cortex", "hcortex"):
        return CortexOUT.error(
            f"invalid mode={mode!r} (must be 'cortex' or 'hcortex')",
            code="INVALID_ARGS",
        )

    # Read raw text first — we need it for both modes.
    src_path = Path(path)
    if not src_path.exists():
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    try:
        raw_text = src_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CortexOUT.error(str(exc), code="READ_ERROR")

    if mode == "hcortex":
        # Render as HCORTEX markdown using cortex.render logic.
        try:
            md = cortex_render(src_path)
        except FileNotFoundError:
            return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
        except RuntimeError as exc:
            return CortexOUT.error(
                f"CODEC-CORTEX not available: {exc}",
                code="MISSING_DEPENDENCY",
            )
        except Exception as exc:  # noqa: BLE001
            return CortexOUT.error(str(exc), code="RENDER_ERROR")

        return CortexOUT.work(
            f"cortex.read ok path={path} mode=hcortex bytes={len(md)}",
            path=path,
            mode="hcortex",
            format="hcortex-read",
            content=md,
            size_bytes=len(md),
        )

    # mode == "cortex" — return raw CORTEX entries as a dict.
    try:
        result = cortex_read(src_path)
    except FileNotFoundError:
        return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
    except RuntimeError:
        # CODEC-CORTEX unavailable — fall back to raw text so the handler
        # is still useful in degraded environments.
        return CortexOUT.work(
            f"cortex.read ok path={path} mode=cortex (raw fallback) "
            f"bytes={len(raw_text)}",
            path=path,
            mode="cortex",
            format="cortex-raw",
            raw=raw_text,
            sections=[],
            glossary={},
            size_bytes=len(raw_text),
            degraded=True,
        )
    except Exception as exc:  # noqa: BLE001
        return CortexOUT.error(str(exc), code="PARSE_ERROR")

    return CortexOUT.work(
        f"cortex.read ok path={path} mode=cortex sections={result['sections']}",
        path=str(result["path"]),
        mode="cortex",
        format="cortex",
        sections=result["sections"],
        glossary=result["glossary"],
        raw=raw_text,
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

    # Post-write hook: auto-sync to meta-brain when writing a project brain.cortex
    _auto_sync_brain(path)

    return CortexOUT.work(
        f"cortex.write ok path={path} bytes={result['bytes_written']}",
        path=path,
        bytes_written=result["bytes_written"],
        backup=result.get("backup"),
        diagnostics=result.get("diagnostics", []),
    )


def _auto_sync_brain(path: str) -> None:
    """If *path* is a project-level brain.cortex, sync to meta-brain."""
    p = Path(path).resolve()
    if p.name != "brain.cortex":
        return
    parent = p.parent
    if parent.name == ".arqux":
        project_root = parent.parent
    elif (parent / ".arqux" / "brain.cortex").exists():
        project_root = parent
    else:
        return
    try:
        sync_brain(project_root, "cortex.write", focus="brain.cortex auto-sync")
    except Exception:
        pass


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
