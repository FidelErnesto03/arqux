"""Migrator for ARQX:artifact (BLP-041).

Injects a ``$19: ARQUX METADATA`` section with ``ARQX:artifact{...}`` entry
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
    render_arqux_section,
)

# ARQX pipe-table declaration line to inject if missing.
_ARQX_PIPE_LINE = "# ARQX   | artifact   | attrs      | B | Semantic       | ArqUX artifact metadata"
# Executable ARQX contract declaration (CORTEX 1.0 I001): the pipe-table
# row alone is documentation — the strict parser needs a real declaration.
_ARQX_DECL_LINE = (
    'ARQX:arqx_contract{type:"attrs", weight:"M", focus:"value", '
    'fields:"value:any?", desc:"ArqUX ARQX entry", open:true}'
)
#: An executable ARQX declaration already present in the text. Detection is
#: shape-based — a contract line always carries a ``type:`` field — not
#: name-based: the metadata *data* entry ``ARQX:artifact{level, name, usage,
#: kind}`` never carries one, while historical glossaries declared the
#: contract under both ``arqx_contract`` and the colliding ``artifact``
#: name (timelog_store). Matching only the name would either miss the
#: contract (I001 left unrepaired) or mint a second ARQX symbol
#: (G015_DUPLICATE_SYMBOL).
_ARQX_DECL_RE = re.compile(r"^ARQX:\w+\s*\{[^}\n]*\btype\s*:", re.MULTILINE)
#: ``$0`` section header (``$0`` or ``$0: TITLE``). Excludes ``$0.1``
#: sub-sections and the ``$0:format{...}`` dialect line.
_ARQX_SEC0_RE = re.compile(r"^\$0(?:\s*:\s*(?!format\s*\{)[^\n]*)?\s*$", re.MULTILINE)
#: ``$0:format{...}`` dialect declaration line.
_ARQX_FORMAT_RE = re.compile(r"^\$0:format\s*\{[^\n]*(?:\n|$)", re.MULTILINE)
#: A section titled ``IDENTITY`` at any numeric slot — GRADIENT-12 resolves
#: by title, so the metadata entry targets the section, not ``$1`` blindly.
_ARQX_IDENTITY_RE = re.compile(
    r"^\$\d+\s*:\s*IDENTITY\b[^\n]*(?:\n|$)", re.MULTILINE | re.IGNORECASE
)

logger = logging.getLogger(__name__)


def _inject_arqux_glossary_line(text: str) -> str:
    """Ensure the $0 glossary declares ARQX: pipe-table row + contract."""
    if not _ARQX_DECL_RE.search(text):
        # No executable declaration — inject one inside the glossary span.
        # When a ``$0:format`` line exists the contract goes right after it
        # (the dispatcher-facing order every other writer emits); otherwise
        # it follows the ``$0`` header directly.
        fmt_match = _ARQX_FORMAT_RE.search(text)
        sec0_match = fmt_match or _ARQX_SEC0_RE.search(text)
        if sec0_match:
            insert_at = sec0_match.end()
            text = text[:insert_at] + "\n" + _ARQX_DECL_LINE + "\n" + text[insert_at:]
        else:
            text = "$0\n\n" + _ARQX_DECL_LINE + "\n\n" + text
    if re.search(r"^#\s*ARQX\s+\|", text, re.MULTILINE):
        return text  # pipe-table row already present
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
    """Inject ARQX:artifact if absent.

    GRADIENT-12: when the artifact has an ``IDENTITY`` section (brains,
    meta-brains, agent identities), the entry goes inside it — ``$19`` is
    only the out-of-band fallback for artifacts without one (tasks,
    cycles, manifest).

    Returns True if migration was performed, False if the file already had
    ARQX metadata (no-op).
    """
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"Cannot migrate non-existent file: {p}")

    content = p.read_text(encoding="utf-8")

    # Already has ARQX:artifact (any slot) → ensure the glossary declares
    # ARQX (pipe-table row AND executable contract — a missing contract is
    # I001 under the 1.0 parser), then skip.
    if _read_arqux_from_ast(content) is not None:
        ensured = _inject_arqux_glossary_line(content)
        if ensured != content:
            p.write_text(ensured, encoding="utf-8")
            logger.info("migrate_file: %s — ensured ARQX glossary declaration", p)
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
    entry_line = section_text.strip().splitlines()[-1]

    # Strip legacy §0 METADATA if present
    stripped = _remove_legacy_metadata(content)

    # Ensure ARQX is declared in the $0 pipe-table glossary
    stripped = _inject_arqux_glossary_line(stripped)

    identity_match = _ARQX_IDENTITY_RE.search(stripped)
    if identity_match:
        # Canon slot: ARQX:artifact inside the IDENTITY section.
        insert_at = identity_match.end()
        new_content = (
            stripped[:insert_at] + "\n" + entry_line + "\n" + stripped[insert_at:]
        )
    else:
        # ``$19`` is an out-of-band slot: append it at the end of the
        # document for artifacts without an IDENTITY section.
        new_content = stripped.rstrip("\n") + "\n" + section_text

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
