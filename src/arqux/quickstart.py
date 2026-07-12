"""arqux quickstart — interactive workspace onboarding (BLP-008)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .constants import ARQUX_DIR
from .cortex_out import CortexOUT
from .state import find_workspace_root


def _copy_agents_md(ws_root: Path) -> str:
    """Copy AGENTS.md from the package to the workspace root if not present."""
    dst = ws_root.parent / "AGENTS.md"
    if dst.exists():
        return "AGENTS.md already present in workspace"

    # Look for AGENTS.md in package
    src = Path(__file__).resolve().parent.parent.parent / "AGENTS.md"
    if not src.exists():
        src = Path(__file__).resolve().parent.parent / "AGENTS.md"
    if not src.exists():
        return "AGENTS.md not found in package — create manually"
    shutil.copy2(src, dst)
    return "AGENTS.md placed in workspace root"


def quickstart(path: str | None = None) -> CortexOUT:
    """Interactive workspace onboarding.

    Detects current state and guides the user through:
    1. Workspace initialization (if needed)
    2. AGENTS.md setup
    3. Identity configuration
    """
    target = Path(path or os.getcwd()).resolve()
    target / ARQUX_DIR
    ws_root = find_workspace_root(start=path)

    steps: list[str] = []
    already_governed = ws_root is not None

    if not already_governed:
        from .handlers.workspace import init_workspace

        init_workspace(path=str(target), verbose=False)
        steps.append(f"✅ Workspace initialized at {target}")
        ws_root = find_workspace_root(start=path)
    else:
        steps.append(f"✅ Workspace already governed at {ws_root.parent}")

    # Copy AGENTS.md
    agents_result = _copy_agents_md(ws_root)
    steps.append(f"✅ {agents_result}")

    # Suggest next steps
    steps.append("")
    steps.append("📋 Next steps:")
    steps.append("  1. Set your identity:     export ARQUX_AGENT_ID=<name>")
    steps.append("  2. Set your role:          export ARQUX_AGENT_ROLE=governor|executor|auditor")
    steps.append("  3. Register a project:     arqux call project.init path=<project-dir>")
    steps.append("  4. Create a cycle:         arqux call cycle.create name=CYCLE-01")

    return CortexOUT.full("\n".join(steps))
