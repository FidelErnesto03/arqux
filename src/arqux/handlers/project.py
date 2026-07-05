"""`project` module — project-level governance.

Handlers:
    project.init     — initialize .arqux/ in a project, register in workspace
    project.bind     — bind an agent identity to the current project (writes to brain SESSIONS)
    project.unbind   — release an agent binding (marks session as released in brain)
    project.status   — active project status (cycles, tasks, agents, brain version)
    project.lessons  — list lessons local to current project (from brain LESSONS section)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..constants import (
    BRAIN_CORTEX,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_SESSIONS,
    CYCLES_DIR,
    OUT_WORK,
    PROJECTS_CORTEX,
    ARQUX_DIR,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..state import (
    add_session_to_brain,
    find_project_root,
    find_workspace_root,
    read_brain,
    remove_session_from_brain,
    write_brain,
)


def init_project(
    name: str,
    path: str | None = None,
    seed: str | None = None,
    verbose: bool = False,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Initialize `.<product>/` in a project directory and register it in the workspace.

    One-step initialization:
    1. Creates .arqux/ skeleton (manifest, cycles dir)
    2. Registers project in workspace projects index
    3. If `seed` is provided, writes it directly as brain.cortex
       (pre-populated with FCS, OBJ, RSK, KNW, etc.)
    4. Detects pre-existing context and emits seed instructions if no seed given
    """
    target = Path(path or os.getcwd()).resolve()
    gov_dir = target / ARQUX_DIR
    gov_dir.mkdir(parents=True, exist_ok=True)
    (gov_dir / CYCLES_DIR).mkdir(exist_ok=True)

    # Register in workspace projects index.
    ws_root = find_workspace_root(start=target)
    if ws_root is not None:
        projects_path = ws_root / PROJECTS_CORTEX
        entry = f"- {name} at {target}\n"
        with projects_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    if seed:
        # One-step: seed content provided — write directly as brain.cortex.
        (gov_dir / BRAIN_CORTEX).write_text(seed, encoding="utf-8")
        return CortexOUT.work(
            f"project.init ok name={name} path={gov_dir} brain=seeded",
            project=name,
            path=str(gov_dir),
            registered_in_workspace=ws_root is not None,
            brain="seeded",
        )

    # No seed: create default brain skeleton and detect context.
    brain = {
        "level": 2,
        "project": name,
        "path": str(target),
        "brain_version": "0",
        "brain_last_writer": (ctx or PermissionContext.from_env()).agent_id,
        "brain_updated": _now_iso(),
    }
    write_brain(gov_dir, brain)

    # Detect pre-existing project context and build seed instructions.
    seed_notes = _detect_project_context(target)

    response = CortexOUT.work(
        f"project.init ok name={name} path={gov_dir}",
        project=name,
        path=str(gov_dir),
        registered_in_workspace=ws_root is not None,
    )

    if seed_notes:
        seed_block = "\n".join(seed_notes)
        response = CortexOUT(
            profile=response.profile,
            message=response.message + "\n" + seed_block,
            fields=response.fields,
        )

    return response


def _detect_project_context(project_root: Path) -> list[str]:
    """Scan project for pre-existing context and return seed instructions.

    Returns a list of CORTEX-formatted lines for the agent to follow.
    The agent (LLM) reads these and populates brain.cortex via cortex.write.
    """
    notes: list[str] = []
    has_context = False

    # 1. Check for NOMOS legacy brain (.cortex/brain.cortex).
    nomos_brain = project_root / ".cortex" / "brain.cortex"
    if nomos_brain.exists():
        has_context = True
        notes.append("STP:seed{")
        notes.append(f'  action:"study and migrate NOMOS brain at {nomos_brain}",')
        notes.append('  instructions:"Read .cortex/brain.cortex content. Extract FCS, OBJ, AXM,')
        notes.append('               RSK, KNW, LNG sections. Write them to .arqux/brain.cortex')
        notes.append('               via cortex.write(path=..., content=..., force=true).')
        notes.append('               Preserve all axioms, risks, objectives, and knowledge.')
        notes.append('               DO NOT edit .cortex/brain.cortex — leave NOMOS brain intact.',
        )
        notes.append("}")

    # 2. Check for documentation files.
    docs_found = []
    for doc_name in ("AGENTS.md", "README.md", "SKILL.md"):
        if (project_root / doc_name).exists():
            docs_found.append(doc_name)
    if docs_found:
        has_context = True
        doc_list = ", ".join(docs_found)
        notes.append("STP:read_docs{")
        notes.append(f'  files:"{doc_list}",')
        notes.append('  action:"read each file for project purpose, conventions, active goals",')
        notes.append('  instructions:"Extract FCS, OBJ, KNW, RSK. Write to .arqux/brain.cortex')
        notes.append('               via cortex.write after studying project docs."')
        notes.append("}")

    # 3. Detect tech stack.
    tech_files = []
    for fname in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "composer.json"):
        if (project_root / fname).exists():
            tech_files.append(fname)
    if tech_files:
        has_context = True
        tech_list = ", ".join(tech_files)
        notes.append("STP:scan_stack{")
        notes.append(f'  files:"{tech_list}",')
        notes.append(f'  action:"read manifest files for language, framework, dependencies",')
        notes.append(f'  purpose:"populate KNW section with tech stack and architectural patterns"')
        notes.append("}")

    if not has_context:
        notes.append("STP:seed_empty{")
        notes.append('  note:"No pre-existing project context detected.',)
        notes.append('        Brain.cortex remains as scaffold. Agent may study the project')
        notes.append('        manually and seed via cortex.write at any time.")')
        notes.append("}")

    notes.insert(0, "# -- BRAIN SEEDING INSTRUCTIONS (for the calling agent) --")
    notes.insert(0, "")
    return notes


def bind(
    agent_id: str,
    role: str,
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Bind an agent identity to the current project with a role.

    Writes a session entry to the brain's SESSIONS section. The brain is the
    shared project mind — every agent bound to the project reads the same
    SESSIONS section to know who else is active.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    add_session_to_brain(root, agent_id, role)

    return CortexOUT.work(
        f"project.bind ok agent={agent_id} role={role} (session recorded in brain)",
        agent_id=agent_id,
        role=role,
    )


def unbind(agent_id: str, path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """Release an agent binding from the current project.

    Marks the session as released in the brain's SESSIONS section. The entry
    is preserved for history; only the `status=active` flag changes.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    result = remove_session_from_brain(root, agent_id)
    if result == "not_found":
        return CortexOUT.work(
            f"project.unbind ok agent={agent_id} (no active session)",
            agent_id=agent_id,
        )

    return CortexOUT.work(
        f"project.unbind ok agent={agent_id} (session released in brain)",
        agent_id=agent_id,
    )


def status(path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """Active project status: cycles, tasks, agents, brain version.

    The brain version is the optimistic-lock counter — every mutation bumps
    it. Agents reading the brain should check the version before writing.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    cycles_dir = root / CYCLES_DIR
    cycles = sorted(p.name for p in cycles_dir.iterdir()) if cycles_dir.exists() else []

    fm, sections, _ = read_brain(root)
    sessions_raw = sections.get(BRAIN_SECTION_SESSIONS, "")
    active_agents = sum(1 for ln in sessions_raw.splitlines() if "status=active" in ln)
    brain_version = fm.get("brain_version", "0")

    return CortexOUT.profile(
        OUT_WORK,
        f"project={root.parent.name} cycles={len(cycles)} active_agents={active_agents} "
        f"brain_version={brain_version}",
        project=str(root.parent),
        cycles=len(cycles),
        active_agents=active_agents,
        brain_version=brain_version,
        shared_mind=str(root / BRAIN_CORTEX),
    )


def lessons(path: str | None = None, ctx: PermissionContext | None = None) -> CortexOUT:
    """List lessons local to the current project.

    Reads from the brain's LESSONS section. These are CONTEXTUAL lessons —
    they apply to this project only. Behavioral lessons (how a role should
    act regardless of project) live in the identity's `.cortex`, not here.
    """
    root = find_project_root(start=path)
    if root is None:
        return CortexOUT.error("no project initialized", code="NOT_FOUND")

    fm, sections, _ = read_brain(root)
    lessons_raw = sections.get(BRAIN_SECTION_LESSONS, "").strip()
    lesson_lines = [ln for ln in lessons_raw.splitlines() if ln.strip()]

    return CortexOUT.work(
        f"contextual_lessons={len(lesson_lines)} (behavioral lessons live in identity .cortex)",
        count=len(lesson_lines),
        kind="contextual",
        brain_path=str(root / BRAIN_CORTEX),
    )


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
