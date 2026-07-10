"""Migrator for ARQX:artifact in $0.1 (BLP-041).

Injects a ``$0.1: ARQUX METADATA`` section with ``ARQX:artifact{...}`` entry
into existing .cortex files. Replaces legacy ``# §0 METADATA{...}`` blocks.

The migrator is IDEMPOTENT: re-running on an already migrated file is a no-op.

Usage as a library::

    from arqux.migrator import migrate_file, migrate_identity_files

    migrate_file(Path(".arqux/brain.cortex"),
                 level=3, name="brain", usage="state", kind="native")

Usage from the CLI::

    arqux migrate --path .arqux/brain.cortex --level 3 \\
        --name brain --usage state --kind native
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .constants import ArtifactKind, ArtifactMetadata, ArtifactUsage, CortexLevel
from .formats import (
    _LEGACY_METADATA_RE,
    _read_arqux_from_ast,
    has_arqux_metadata,
    render_arqux_section,
)

# ARQX pipe-table declaration line to inject if missing.
_ARQX_PIPE_LINE = "# ARQX   | artifact   | attrs      | B | Semantic       | ArqUX artifact metadata"

logger = logging.getLogger(__name__)


def _inject_arqux_glossary_line(text: str) -> str:
    """Ensure ``# ARQX | artifact | ...`` is in the $0 pipe-table."""
    if re.search(r"^#\s*ARQX\s+\|", text, re.MULTILINE):
        return text  # already present
    # Find the first pipe-table line (after "# Sigil | Name | ...") and insert ARQX after it
    pipe_header_match = re.search(
        r"^#\s*Sigil\s+\|\s*Name.*$", text, re.MULTILINE
    )
    if pipe_header_match:
        line_end = text.index("\n", pipe_header_match.start())
        return (
            text[: line_end + 1]
            + _ARQX_PIPE_LINE + "\n"
            + text[line_end + 1 :]
        )
    # No pipe table — append after the $0 header line
    sec0_match = re.search(r"^\$0", text, re.MULTILINE)
    if sec0_match:
        line_end = text.index("\n", sec0_match.start())
        return (
            text[: line_end + 1]
            + "\n" + _ARQX_PIPE_LINE + "\n"
            + text[line_end + 1 :]
        )
    return text


def _remove_legacy_metadata(text: str) -> str:
    """Strip the first ``# §0 METADATA{...}`` block from ``text``."""
    return _LEGACY_METADATA_RE.sub("", text, count=1).lstrip("\n")


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
    """Inject ARQX:artifact in $0.1 if absent.

    Returns True if migration was performed, False if the file already had
    ARQX metadata (no-op).
    """
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"Cannot migrate non-existent file: {p}")

    content = p.read_text(encoding="utf-8")

    # Already has ARQX:artifact in $0.1 → ensure glossary too, then skip
    if _read_arqux_from_ast(content) is not None:
        # Check if ARQX is declared in glossary; inject if missing
        if not re.search(r"^#\s*ARQX\s+\|", content, re.MULTILINE):
            content = _inject_arqux_glossary_line(content)
            p.write_text(content, encoding="utf-8")
            logger.info("migrate_file: %s — injected ARQX glossary line", p)
            return True
        logger.info("migrate_file: %s already has ARQX:artifact — skip", p)
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
    section_text = render_arqux_section(metadata)

    # Strip legacy §0 METADATA if present
    stripped = _remove_legacy_metadata(content)

    # Ensure ARQX is declared in the $0 pipe-table glossary
    stripped = _inject_arqux_glossary_line(stripped)

    # Find insertion point: after $0 glossary, before $1 (or end)
    # Look for first section header after $0 (e.g. "$1", "$2", etc.)
    sec_match = re.search(r"^\$[1-9]", stripped, re.MULTILINE)
    if sec_match:
        # Insert before $1
        insert_pos = sec_match.start()
        new_content = stripped[:insert_pos] + section_text + stripped[insert_pos:]
    else:
        # No other sections → append
        new_content = stripped.rstrip("\n") + "\n" + section_text + "\n"

    p.write_text(new_content, encoding="utf-8")
    logger.info("migrate_file: injected ARQX:artifact into %s (level=%d, name=%s)", p, level, name)
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
    field is recorded in ARQX:artifact so the file self-identifies its owner.
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
