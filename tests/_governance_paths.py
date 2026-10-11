"""Locate governance artifacts the way the platform actually stores them.

BLP-001, audit finding HD-SKIP. The workspace-dependent tests in
``test_cortex_conformance.py`` and ``test_cortex_migration.py`` were guarded
by

    _HAS_WORKSPACE_FILES = _BRAIN_CORTEX.exists() and _JARVIS_CORTEX.exists()

with the identity path hardcoded to ``<project>/.arqux/identities/``. ArqUX
stores identities at **workspace** level, not project level, so the guard
evaluated false and thirteen tests skipped with the declared reason
"workspace .cortex files not available in CI checkout" — a statement that
was simply untrue. Ten of those tests pass; three were failing for the same
wrong-path reason.

A skip whose reason is false is a gate that declares itself closed without
looking, which is exactly what rule R-09 forbids. This module resolves the
artifact where it genuinely lives instead.
"""

from __future__ import annotations

from pathlib import Path

ARQUX_ROOT = Path(__file__).resolve().parent.parent


def _workspace_root(start: Path) -> Path | None:
    """Walk up from *start* to the workspace root, the same rule ArqUX uses.

    Mirrors ``arqux.identity_resolver._find_workspace_root``: a ``.arqux``
    directory is never the workspace root, even when it holds an AGENTS.md.
    """
    if start.name == ".arqux":
        start = start.parent
    for parent in [start, *start.parents]:
        if parent.name == ".arqux":
            continue
        if (parent / "AGENTS.md").exists() or (parent / ".arqux" / "AGENTS.md").exists():
            return parent
    return None


def _candidates(parts: tuple[str, ...]) -> list[Path]:
    """Every plausible location for *parts*, nearest governance level first."""
    start = ARQUX_ROOT
    if start.name == ".arqux":
        start = start.parent
    levels = [p for p in [start, *start.parents] if p.name != ".arqux"]
    return [level.joinpath(".arqux", *parts) for level in levels]


def governance_artifact(*parts: str) -> Path:
    """Resolve a governance artifact by walking up the governance levels.

    Search order matches how the platform nests governance: a project owns
    its cycles, blueprints and brain, while identities are workspace-level
    and shared. Detection of "the workspace root" is deliberately *not*
    used — a project with its own ``AGENTS.md`` looks exactly like a
    workspace root, which is what made the original guard fail. Walking up
    and taking the first hit needs no such guess.

    When the artifact is found nowhere, the project-level path is returned
    so the caller can still ``.exists()`` it and report the gap honestly.

    Args:
        *parts: Path segments below the ``.arqux`` directory.

    Returns:
        The first existing candidate, or the project-level path.
    """
    candidates = _candidates(parts)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
