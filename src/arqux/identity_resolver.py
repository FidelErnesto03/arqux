"""Identity resolution service for ArqUX.

Resolves runtime agent IDs (e.g. "hermes") to canonical ArqUX identity
names (e.g. "Alfred") by reading ``.arqux/identities/<agent_id>.cortex``
files.

BLP-007: Created as a centralized identity resolver so that session,
blueprint, and permission handlers all use the same resolution logic.
"""

from __future__ import annotations

from pathlib import Path


def resolve_agent_identity(
    agent_id: str,
    project_root: Path | None = None,
) -> str:
    """Resolve a runtime *agent_id* to its canonical ArqUX identity name.

    Looks for ``.arqux/identities/<agent_id>.cortex`` and reads the
    ``IDN:name`` entry. If the file doesn't exist or can't be parsed,
    returns *agent_id* unchanged as a safe fallback.

    Args:
        agent_id: The runtime agent identifier (e.g. ``"hermes"``).
        project_root: Optional project root for resolving the identities
            directory. If omitted, only the workspace-level identities
            are checked (``~/.arqux/identities/``).

    Returns:
        The resolved identity name (e.g. ``"alfred"``), or *agent_id*
        unchanged if resolution fails.
    """
    if not agent_id:
        return agent_id

    candidates: list[Path] = []

    # 1. Project-level identities
    if project_root is not None:
        proj_id = project_root / ".arqux" / "identities" / f"{agent_id}.cortex"
        candidates.append(proj_id)

    # 2. Workspace-level identities (walk up from project_root)
    if project_root is not None:
        ws = _find_workspace_root(project_root)
        if ws is not None:
            ws_id = ws / ".arqux" / "identities" / f"{agent_id}.cortex"
            if ws_id != candidates[0]:  # avoid duplicate
                candidates.append(ws_id)

    # 3. Home-level identities (~/.arqux/identities/)
    home_id = Path.home() / ".arqux" / "identities" / f"{agent_id}.cortex"
    candidates.append(home_id)

    for path in candidates:
        try:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            name = _extract_idn_name(text)
            if name:
                return name
        except (OSError, UnicodeDecodeError):
            continue

    # Fallback: scan all identity files in the project/workspace
    # (catches cases where runtime agent_id differs from identity filename)
    for src_dir in [p.parent for p in candidates if p.parent.exists()]:
        try:
            for f in sorted(src_dir.glob("*.cortex")):
                text = f.read_text(encoding="utf-8")
                name = _extract_idn_name(text)
                if name:
                    return name
        except (OSError, UnicodeDecodeError):
            continue

    return agent_id


def _find_workspace_root(start: Path) -> Path | None:
    """Walk up from *start* to find the workspace root (has AGENTS.md)."""
    for parent in [start] + list(start.parents):
        if (parent / "AGENTS.md").exists():
            return parent
        if (parent / ".arqux" / "AGENTS.md").exists():
            return parent
    return None


def _extract_idn_name(cortex_text: str) -> str | None:
    """Extract the ``IDN:name`` value from a CORTEX identity file.

    Looks for lines of the form::

        IDN:<name>{name:"<value>", ...}

    or::

        IDN:<name>{name:<value>, ...}

    Returns the first ``name`` field found, or ``None``.
    """
    import re

    # Pattern: IDN:anything{name:"value", ...} or IDN:anything{name:value, ...}
    m = re.search(r'IDN:\w+\{[^}]*?name[=:]\s*"([^"]+)"', cortex_text)
    if m:
        return m.group(1)

    # Fallback: unquoted name value
    m = re.search(r'IDN:\w+\{[^}]*?name[=:]\s*([^,}\s]+)', cortex_text)
    if m:
        return m.group(1)

    return None
