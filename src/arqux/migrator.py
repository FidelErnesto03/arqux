"""Migrator for §0 METADATA (BLP-035).

Injects a ``# §0 METADATA{...}`` prelude into existing .cortex files that
pre-date BLP-035. The migrator is IDEMPOTENT: re-running it on an already
migrated file is a no-op (the file is left untouched).

Migration contract (BLP-035 §7 Rule 2 — Immutability):
    The §0 METADATA block, once written, cannot be modified except by an
    official migration. This module ONLY adds the block when absent; it
    never edits or removes an existing block.

Usage as a library::

    from arqux.migrator import migrate_file, migrate_identity_files

    migrate_file(Path(".arqux/brain.cortex"),
                 level=3, name="brain", usage="state", kind="native")

Usage from the CLI::

    arqux migrate --path .arqux/brain.cortex --level 3 \
        --name brain --usage state --kind native
"""
from __future__ import annotations

import logging
from pathlib import Path

from .constants import ArtifactKind, ArtifactMetadata, ArtifactUsage, CortexLevel
from .formats import _METADATA_RE, render_metadata_block

logger = logging.getLogger(__name__)


def has_metadata_block(raw_content: str) -> bool:
    """Return True if ``raw_content`` already contains a §0 METADATA prelude."""
    return _METADATA_RE.search(raw_content) is not None


def migrate_file(
    filepath: Path | str,
    level: int,
    name: str,
    usage: str,
    kind: str,
    *,
    agent: str | None = None,
    source: str | None = None,
    upstream_version: str | None = None,
) -> bool:
    """Inject §0 METADATA at the top of ``filepath`` if absent.

    Returns True if migration was performed, False if the file already had
    a §0 METADATA block (no-op).

    The file is left byte-identical below the inserted block — only the
    prelude is added. This preserves round-tripping with CODEC-CORTEX.
    """
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"Cannot migrate non-existent file: {p}")

    content = p.read_text(encoding="utf-8")
    if has_metadata_block(content):
        logger.info("migrate_file: %s already has §0 METADATA — skip", p)
        return False

    metadata = ArtifactMetadata(
        level=CortexLevel.from_int(level),
        name=name,
        usage=ArtifactUsage.from_str(usage),
        kind=ArtifactKind.from_str(kind),
        agent=agent,
        source=source,
        upstream_version=upstream_version,
    )
    block = render_metadata_block(metadata)
    new_content = block + "\n\n" + content
    p.write_text(new_content, encoding="utf-8")
    logger.info("migrate_file: injected §0 METADATA into %s (level=%d, name=%s)", p, level, name)
    return True


def migrate_identity_files(identities_dir: Path | str) -> dict[str, bool]:
    """Migrate all agent identity files in ``identities_dir`` to NIVEL 1.

    Each ``<agent>.cortex`` file gets ``level: 1, usage: "identity",
    kind: "native"``. The agent name is derived from the file stem.

    Returns a mapping {agent_name: migrated?}.
    """
    d = Path(identities_dir)
    if not d.is_dir():
        raise NotADirectoryError(f"Identities directory not found: {d}")

    results: dict[str, bool] = {}
    for cortex_file in sorted(d.glob("*.cortex")):
        agent = cortex_file.stem
        results[agent] = migrate_file(
            cortex_file,
            level=1,
            name=agent,
            usage="identity",
            kind="native",
            agent=agent,
        )
    return results


def migrate_brain_file(brain_path: Path | str) -> bool:
    """Migrate a project ``brain.cortex`` to NIVEL 3 (BRAIN)."""
    return migrate_file(
        brain_path,
        level=3,
        name="brain",
        usage="state",
        kind="native",
    )


def migrate_meta_brain_file(meta_brain_path: Path | str) -> bool:
    """Migrate the workspace ``meta-brain.cortex`` to NIVEL 3 (BRAIN)."""
    return migrate_file(
        meta_brain_path,
        level=3,
        name="meta-brain",
        usage="state",
        kind="native",
    )


def migrate_lessons_file(
    lessons_path: Path | str,
    agent: str,
) -> bool:
    """Migrate an agent's ``<agent>.lessons.cortex`` to NIVEL 0 (PACKAGE).

    Used by BLP-038 when creating behavioral lesson stores. The ``agent``
    field is recorded in §0 METADATA so the file self-identifies its owner.
    """
    return migrate_file(
        lessons_path,
        level=0,
        name=f"{agent}-lessons",
        usage="lesson",
        kind="native",
        agent=agent,
    )


def migrate_skill_file(
    skill_path: Path | str,
    name: str,
    kind: str,
    *,
    source: str | None = None,
    upstream_version: str | None = None,
) -> bool:
    """Migrate a ``.skill.md`` file to NIVEL 2 (SKILL) (BLP-040).

    The ``kind`` field MUST be one of ``native``, ``inherited``, ``adapted``.
    For ``inherited`` skills, ``source`` and ``upstream_version`` are required
    by BLP-040 Rule 4.
    """
    if kind == "inherited" and (not source or not upstream_version):
        raise ValueError(
            "inherited skills require both 'source' and 'upstream_version' "
            "(BLP-040 Rule 4 — Atribución Obligatoria)"
        )
    return migrate_file(
        skill_path,
        level=2,
        name=name,
        usage="skill",
        kind=kind,
        source=source,
        upstream_version=upstream_version,
    )
