"""Codec-version migration orchestration (BLP-005).

Hybrid migration pipeline: doctor detects version drift deterministically,
an agent performs the semantic transform guided by a protocol skill, and
this module provides the deterministic guarantees — entry census before and
after, semantic diff, mandatory backup, and post-write verification.

The census is *semantic*: ``SIGIL:name`` keys with a hash of the canonical
payload. Format-level reshapes declared by the migration report are
legitimate; undeclared disappearance or mutation is corruption.

Usage as a library::

    from arqux.migrate import (
        IMPLEMENTED_CODEC_VERSION,
        census_file,
        declared_codec_version,
        diff_census,
        plan_migration,
        scan_codec_drift,
    )

    drift = scan_codec_drift(Path(".arqux"))
    plan = plan_migration(Path(".arqux/brain.cortex"))
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

#: Codec version ARQUX implements and targets (codec-cortex 1.0.x line).
#: Migration target is pinned here — never "whatever is installed".
IMPLEMENTED_CODEC_VERSION = "1.0"

#: ``$0:format{...cortex:"0.1"...}`` / ``cortex:1.0`` declaration line.
_FORMAT_DECL_RE = re.compile(
    r"^\$0:format\s*\{[^}\n]*?\bcortex\s*:\s*\"?([0-9]+(?:\.[0-9]+)?)\"?",
    re.MULTILINE,
)


@dataclass
class DriftReport:
    """A .cortex file whose declared codec version differs from implemented."""

    path: Path
    declared: str
    implemented: str = IMPLEMENTED_CODEC_VERSION

    @property
    def ok(self) -> bool:
        return self.declared == self.implemented


@dataclass
class CensusEntry:
    key: str  # "SIGIL:name"
    hash: str  # sha256 of canonical payload json


@dataclass
class CensusDiff:
    """Semantic diff between a before/after census."""

    missing: list[str] = field(default_factory=list)      # in before, absent after
    added: list[str] = field(default_factory=list)        # in after, absent before
    changed: list[str] = field(default_factory=list)      # same key, different hash
    preserved: int = 0

    @property
    def ok(self) -> bool:
        return not (self.missing or self.changed)


def declared_codec_version(text: str) -> str | None:
    """Return the codec version declared in ``$0:format``, or None."""
    m = _FORMAT_DECL_RE.search(text)
    return m.group(1) if m else None


def scan_codec_drift(arqux_dir: Path | str) -> list[DriftReport]:
    """Scan every ``*.cortex`` under ``arqux_dir`` for version drift.

    Only files with an explicit ``cortex:`` declaration are checked;
    undeclared files follow codec defaults and are not drifted here.
    """
    root = Path(arqux_dir)
    reports: list[DriftReport] = []
    for path in sorted(root.rglob("*.cortex")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        declared = declared_codec_version(text)
        if declared is not None and declared != IMPLEMENTED_CODEC_VERSION:
            reports.append(DriftReport(path=path, declared=declared))
    return reports


def _canonical_payload_hash(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def census_file(path: Path | str) -> dict[str, str]:
    """Entry census of a .cortex file via ``cortex parse`` (authoritative AST).

    Returns ``{"SIGIL:name": sha256(payload)}`` for every idea in every
    section. Raises ``RuntimeError`` when the file cannot be parsed — a file
    that does not parse cannot be migrated safely.
    """
    path = Path(path)
    proc = subprocess.run(
        ["cortex", "parse", "-"],
        input=path.read_text(encoding="utf-8"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cortex parse failed for {path}: {proc.stderr.strip()[:200]}")
    ast = json.loads(proc.stdout)
    census: dict[str, str] = {}
    for section in ast.get("sections", []):
        for idea in section.get("ideas", []):
            symbol = idea.get("symbol")
            name = idea.get("name")
            if not symbol or not name:
                continue
            census[f"{symbol}:{name}"] = _canonical_payload_hash(idea.get("payload"))
    return census


def diff_census(
    before: dict[str, str],
    after: dict[str, str],
    declared_transforms: set[str] | None = None,
) -> CensusDiff:
    """Compare two censuses.

    ``declared_transforms`` lists entry keys the migration report declares as
    legitimately renamed/removed — they are excluded from ``missing``/``changed``
    but still reported under ``added`` when they reappear. Content mutation of
    a preserved key is always ``changed`` (format reshapes that keep semantic
    fields should hash-equal; payload-hash equality is the strict contract —
    the migration report must declare keys whose payload legitimately changed).
    """
    declared = declared_transforms or set()
    diff = CensusDiff()
    for key, h in before.items():
        if key not in after:
            if key not in declared:
                diff.missing.append(key)
        elif after[key] != h and key not in declared:
            diff.changed.append(key)
        else:
            diff.preserved += 1
    diff.added = sorted(k for k in after if k not in before)
    diff.missing.sort()
    diff.changed.sort()
    return diff


def backup_file(path: Path | str) -> Path:
    """Mandatory pre-migration backup: ``<name>.pre-migration-<YYYYMMDD>``."""
    src = Path(path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    dst = src.with_name(f"{src.name}.pre-migration-{stamp}")
    n = 1
    while dst.exists():
        dst = src.with_name(f"{src.name}.pre-migration-{stamp}-{n}")
        n += 1
    shutil.copy2(src, dst)
    return dst


# ---------------------------------------------------------------------------
# Migration registry — ordered deterministic steps per (from, to) pair.
# The semantic transform is NOT a function here: it is executed by the agent
# under the cortex-migrate skill protocol. These steps are the deterministic
# envelope around it.
# ---------------------------------------------------------------------------

MIGRATIONS: dict[tuple[str, str], dict[str, object]] = {
    ("0.1", "1.0"): {
        "deterministic_steps": [
            "backup",
            "census_before",
            "agent_transform_per_skill",
            "bump_format_decl",
            "validate",
            "cortex_verify",
            "census_after",
            "diff_census",
        ],
        "skill": "cortex-migrate",
        "notes": "GRADIENT-12 playbook: sections $19→canonical slots, contract conformance, DEC→axioms review.",
    },
}


def plan_migration(path: Path | str) -> dict[str, object] | None:
    """Return the migration plan for a drifted file, or None if not drifted."""
    path = Path(path)
    declared = declared_codec_version(path.read_text(encoding="utf-8"))
    if declared is None or declared == IMPLEMENTED_CODEC_VERSION:
        return None
    plan = MIGRATIONS.get((declared, IMPLEMENTED_CODEC_VERSION))
    if plan is None:
        return {
            "path": str(path),
            "from": declared,
            "to": IMPLEMENTED_CODEC_VERSION,
            "error": "no migration path registered",
        }
    return {"path": str(path), "from": declared, "to": IMPLEMENTED_CODEC_VERSION, **plan}
