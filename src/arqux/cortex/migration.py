"""Reversible migration of legacy ArqUX CORTEX files.

The migration keeps the semantic document model intact while rewriting the
glossary contract required by CODEC-CORTEX 1.0.0rc1. It is deliberately
transactional: dry-run first, atomic write second, external verification last.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .atomic import atomic_write_text
from .codec_compat import codec_info, verify_text
from .reader import cortex_to_dict
from .writer import write_cortex_from_json

_FORMAT_RE = re.compile(r"^\s*\$0:format\{[^}]*cortex:\s*['\"]?([^,}\s'\"]+)", re.MULTILINE)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inspect_file(path: str | Path) -> dict[str, Any]:
    """Build a migration plan without modifying *path*."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(str(source))
    text = source.read_text(encoding="utf-8")
    try:
        document = cortex_to_dict(text)
    except Exception as exc:  # noqa: BLE001
        return {
            "path": str(source),
            "source_sha256": _sha256(text),
            "target_sha256": None,
            "source_format": (_FORMAT_RE.search(text) or [None, "legacy"])[1],
            "target_format": "0.1",
            "changed": False,
            "bytes_before": len(text.encode("utf-8")),
            "bytes_after": None,
            "codec": {
                "package": codec_info().package,
                "version": codec_info().version,
                "parser": codec_info().parser,
                "target_valid": False,
                "error": f"ArqUX reader rejected source: {type(exc).__name__}: {exc}",
            },
            "status": "unparseable",
            "error": f"{type(exc).__name__}: {exc}",
        }
    migrated = write_cortex_from_json(document, strict=True)
    info = codec_info()
    external_valid = False
    external_error: str | None = None
    try:
        verify_text(migrated, path=str(source))
        external_valid = True
    except Exception as exc:  # noqa: BLE001
        external_error = f"{type(exc).__name__}: {exc}"
    return {
        "path": str(source),
        "source_sha256": _sha256(text),
        "target_sha256": _sha256(migrated),
        "source_format": (_FORMAT_RE.search(text) or [None, "legacy"])[1],
        "target_format": "0.1",
        "changed": migrated != text,
        "bytes_before": len(text.encode("utf-8")),
        "bytes_after": len(migrated.encode("utf-8")),
        "codec": {
            "package": info.package,
            "version": info.version,
            "parser": info.parser,
            "target_valid": external_valid,
            "error": external_error,
        },
        "content": migrated,
    }


def migrate_file(
    path: str | Path,
    *,
    dry_run: bool = True,
    keep_backup: bool = True,
) -> dict[str, Any]:
    """Migrate one file; default mode is safe dry-run."""
    plan = inspect_file(path)
    result = {key: value for key, value in plan.items() if key != "content"}
    result["dry_run"] = dry_run
    if plan.get("status") == "unparseable":
        return result
    if dry_run or not plan["changed"]:
        result["status"] = "preview" if dry_run else "unchanged"
        return result
    if not plan["codec"]["target_valid"]:
        raise RuntimeError(
            "Refusing migration: generated file did not verify with "
            f"CODEC-CORTEX ({plan['codec']['error']})"
        )

    write_result = atomic_write_text(
        plan["content"], str(path), keep_backup=keep_backup
    )
    try:
        verify_text(Path(path).read_text(encoding="utf-8"), path=str(path))
    except Exception:
        if write_result.backup:
            Path(path).write_bytes(Path(write_result.backup).read_bytes())
        raise
    result.update({
        "status": "migrated",
        "dry_run": False,
        "backup": write_result.backup,
        "bytes_written": write_result.bytes_written,
    })
    return result


def migrate_tree(
    root: str | Path,
    *,
    dry_run: bool = True,
    keep_backup: bool = True,
) -> list[dict[str, Any]]:
    """Preview or migrate every ``.cortex`` file below *root*."""
    base = Path(root)
    if not base.exists():
        raise FileNotFoundError(str(base))
    files = sorted(
        file for file in base.rglob("*.cortex")
        if not file.name.endswith(".cortex.bck") and ".venv" not in file.parts
    )
    return [migrate_file(file, dry_run=dry_run, keep_backup=keep_backup) for file in files]


__all__ = ["inspect_file", "migrate_file", "migrate_tree"]
