"""`workspace` module — workspace-level governance.

Handlers:
    workspace.init     — initialize .arqux/ at workspace root
    workspace.status   — workspace status (OUT-MIN by default)
    workspace.lessons  — lessons elevated to the meta-brain
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..constants import (
    CYCLE_OPEN,
    MANIFEST_CORTEX,
    META_BRAIN_CORTEX,
    OUT_AUDIT,
    OUT_MIN,
    OUT_WORK,
    PRODUCT_NAME,
    PROJECTS_CORTEX,
    ROLE_GOVERNOR,
    ARQUX_DIR,
    ARQUX_VERSION,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext, promote_first_governor
from ..state import (
    find_workspace_root,
    write_manifest,
    write_meta_brain,
    write_projects_index,
)


def init_workspace(
    path: str | None = None,
    verbose: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Initialize a workspace root.

    Creates `.<product>/` at the given path (default: cwd) with:
        - manifest.cortex / manifest.md
        - meta-brain.cortex / meta-brain.md
        - projects.cortex / projects.md

    The first agent to call this on a fresh workspace is implicitly promoted
    to governor (bootstrap case).
    """
    target = Path(path or os.getcwd()).resolve()
    gov_dir = target / ARQUX_DIR
    gov_dir.mkdir(parents=True, exist_ok=True)
    (gov_dir / "packages").mkdir(exist_ok=True)

    # Bootstrap: first caller becomes governor.
    if ctx is None:
        ctx = PermissionContext.from_env()
    if ctx.role != ROLE_GOVERNOR:
        ctx = promote_first_governor(ctx.agent_id)

    manifest = {
        "version": ARQUX_VERSION,
        "product": PRODUCT_NAME,
        "governor": ctx.agent_id,
        "created": _now_iso(),
        "status": "active",
    }
    write_manifest(gov_dir, manifest)

    meta_brain = {
        "level": 1,
        "workspace": target.name,
        "lessons": [],
        "knowledge": [],
    }
    write_meta_brain(gov_dir, meta_brain)

    write_projects_index(gov_dir, [])

    # Copy identity templates to .arqux/identities/ for behavioral evolution.
    identities_src = Path(__file__).resolve().parent.parent / "identities"
    if identities_src.is_dir():
        identities_dst = gov_dir / "identities"
        identities_dst.mkdir(exist_ok=True)
        for src in identities_src.glob("*.cortex"):
            dst = identities_dst / src.name
            if not dst.exists():
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Copy learn-policies.cortex template to .arqux/.
    policy_tmpl = Path(__file__).resolve().parent.parent / "templates" / "learn-policies.cortex"
    if policy_tmpl.exists():
        policy_dst = gov_dir / "learn-policies.cortex"
        if not policy_dst.exists():
            policy_dst.write_text(policy_tmpl.read_text(encoding="utf-8"), encoding="utf-8")

    # Create skill management directories.
    (gov_dir / "skills" / "originals").mkdir(parents=True, exist_ok=True)
    (gov_dir / "skills" / "adaptations").mkdir(parents=True, exist_ok=True)
    skills_src = Path(__file__).resolve().parent.parent / "skills"
    if skills_src.is_dir():
        skills_dst = gov_dir / "skills"
        skills_dst.mkdir(exist_ok=True)
        for src in skills_src.glob("*.skill.md"):
            dst = skills_dst / src.name
            if not dst.exists():
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    profile = OUT_AUDIT if verbose else OUT_MIN
    return CortexOUT.profile(
        profile,
        f"workspace.init ok path={gov_dir} governor={ctx.agent_id}",
        workspace=str(gov_dir),
        governor=ctx.agent_id,
    )


def status(verbose: bool = False, path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """Workspace status. Returns projects, cycles count, governor."""
    root = find_workspace_root(start=path)
    if root is None:
        return CortexOUT.error("workspace not initialized", code="NOT_FOUND")

    manifest_path = root / MANIFEST_CORTEX
    projects_path = root / PROJECTS_CORTEX
    meta_brain_path = root / META_BRAIN_CORTEX

    profile = OUT_AUDIT if verbose else OUT_MIN
    return CortexOUT.profile(
        profile,
        f"workspace={root.parent.name} manifest={manifest_path.exists()} "
        f"projects_index={projects_path.exists()} meta_brain={meta_brain_path.exists()}",
        workspace=str(root),
        manifest=manifest_path.exists(),
        projects_index=projects_path.exists(),
        meta_brain=meta_brain_path.exists(),
    )


def lessons(project: str | None = None, path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """List lessons elevated to the meta-brain."""
    root = find_workspace_root(start=path)
    if root is None:
        return CortexOUT.error("workspace not initialized", code="NOT_FOUND")

    meta_brain_path = root / META_BRAIN_CORTEX
    if not meta_brain_path.exists():
        return CortexOUT.work("no meta-brain yet", count=0)

    # In a real impl, this would parse the CORTEX file via codec-cortex.
    return CortexOUT.work(
        "meta-brain present",
        path=str(meta_brain_path),
        filter_project=project or "*",
    )


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
