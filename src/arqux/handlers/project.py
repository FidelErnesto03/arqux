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

from ..constants import (
    ARQUX_DIR,
    BRAIN_CORTEX,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_SESSIONS,
    CYCLES_DIR,
    OUT_WORK,
    PROJECTS_CORTEX,
)
from ..cortex_out import CortexOUT
from ..permissions import PermissionContext
from ..sessions import add_session_to_brain, remove_session_from_brain
from ..state import (
    cortex_write,
    find_project_root,
    find_workspace_root,
    read_brain,
    write_brain,
)
from ..sync import sync_brain


def init_project(
    name: str,
    path: str | None = None,
    seed: str | None = None,
    verbose: bool = False,
    cycle: str | None = None,
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
    # Create .arqux/ skeleton.
    gov_dir.mkdir(parents=True, exist_ok=True)
    (gov_dir / CYCLES_DIR).mkdir(exist_ok=True)
    (gov_dir / "packages").mkdir(exist_ok=True)

    # Copy learn-policies.cortex template for learning engine.
    policy_tmpl = Path(__file__).resolve().parent.parent / "templates" / "learn-policies.cortex"
    if policy_tmpl.exists():
        dst = gov_dir / "learn-policies.cortex"
        if not dst.exists():
            dst.write_text(policy_tmpl.read_text(encoding="utf-8"), encoding="utf-8")

    # Register in workspace projects index.
    ws_root = find_workspace_root(start=target)
    if ws_root is not None:
        projects_path = ws_root / PROJECTS_CORTEX
        entry = f"- {name} at {target}\n"
        with projects_path.open("a", encoding="utf-8") as fh:
            fh.write(entry)

    if seed:
        # One-step: seed content provided — write directly as brain.cortex.
        result = cortex_write(gov_dir / BRAIN_CORTEX, seed)
        if "error" in result:
            raise RuntimeError(f"brain.cortex seed write rejected: {result['error']}")

        # Update meta-brain with cross-project knowledge.
        if ws_root is not None:
            _update_meta_brain(ws_root, name, str(target), seed)

        # P1-D: auto-create cycle if specified.
        if cycle:
            try:
                from .cycle import create_cycle
                create_cycle(name=cycle, path=str(target), ctx=ctx)
            except Exception:
                pass  # cycle creation is best-effort
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
    """Scan project for pre-existing context and return explicit seed instructions.

    Returns a list of CORTEX-formatted lines instructing the agent to study the
    project thoroughly and build a complete brain.cortex with ALL sections
    populated. The brain replaces the manifest, critical guidelines, lessons,
    and technical directives for the project.
    """
    notes: list[str] = []
    ctx_items: list[str] = []

    # 1. Detect NOMOS legacy brain.
    nomos_brain = project_root / ".cortex" / "brain.cortex"
    if nomos_brain.exists():
        ctx_items.append("  - Read .cortex/brain.cortex (NOMOS legacy) for axioms, risks, objectives")

    # 2. Detect documentation files.
    for doc_name in ("AGENTS.md", "README.md"):
        if (project_root / doc_name).exists():
            ctx_items.append(f"  - Read {doc_name} for project purpose, conventions, protocols")

    # 3. Detect tech stack.
    for fname in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "composer.json"):
        if (project_root / fname).exists():
            ctx_items.append(f"  - Read {fname} for language, framework, dependencies")

    # 4. Detect source structure.
    for src_dir in ("src", "lib", "app", "backend", "frontend"):
        if (project_root / src_dir).is_dir():
            ctx_items.append(f"  - Scan {src_dir}/ for architecture patterns, module structure")

    notes.append("")
    notes.append("# -- BRAIN SEEDING: BUILD COMPLETE PROJECT BRAIN --")
    notes.append("")
    notes.append("STP:build_brain{")
    notes.append('  step:"1 - STUDY the project thoroughly",')
    notes.append('  sources:')
    if ctx_items:
        notes.extend(ctx_items)
    else:
        notes.append('    "(no pre-existing context found — study project structure)"')
    notes.append("")
    notes.append('  step:"2 - BUILD brain.cortex content with ALL sections below",')
    notes.append('  format:"Canonical CODEC-CORTEX sigil with $0 glossary",')
    notes.append('  sections:')
    notes.append('    $1:  IDENTITY')
    notes.append('      IDN:project{name, product, version, purpose}')
    notes.append('      IDN:governor{level, project, path, governor}')
    notes.append('      DOM:scope{area, purpose}')
    notes.append('')
    notes.append('    $2:  FOCUS')
    notes.append('      FCS:current{what, priority, status}')
    notes.append('      One-sentence active focus for the project.')
    notes.append('')
    notes.append('    $3:  OBJECTIVES')
    notes.append('      OBJ:name{goal, status, success}')
    notes.append('      Active goals with measurable success criteria.')
    notes.append('')
    notes.append('    $4:  SESSIONS')
    notes.append('      SES:agent{input, output, role, outcome, date}')
    notes.append('      Initial session: the governor adopting the project.')
    notes.append('')
    notes.append('    $5:  HANDOFFS')
    notes.append('      HDL:handoff{from, to, task, note}')
    notes.append('      Optional — populate if handoff contracts exist.')
    notes.append('')
    notes.append('    $6:  PULSE')
    notes.append('      AUD:event{event, evidence, task, kind, agent, result}')
    notes.append('      Initial evidence: project initialization record.')
    notes.append('')
    notes.append('    $7:  LESSONS')
    notes.append('      LNG:name{type, context, detail}')
    notes.append('      Known lessons from previous work. Extract from NOMOS brain')
    notes.append('      or leave empty if none exist yet.')
    notes.append('')
    notes.append('    $8:  ACTIVE_CONTEXT')
    notes.append('      WRK:current{phase, current, blocked, survive}')
    notes.append('      Current execution phase and state.')
    notes.append('')
    notes.append('    $9:  RISKS')
    notes.append('      RSK:risk{risk, impact, mitigation, status}')
    notes.append('      Known risks from NOMOS brain or discovered during study.')
    notes.append('      Extract at least: description, impact (high/medium/low),')
    notes.append('      mitigation strategy. Empty entries ("-") are NOT acceptable.')
    notes.append('')
    notes.append('    $10: KNOWLEDGE')
    notes.append('      KNW:stack{tech, framework, runtime}')
    notes.append('      KNW:architecture{layers, patterns}')
    notes.append('      KNW:dependencies{external, internal}')
    notes.append('      CRITICAL: this section replaces the project manifest.')
    notes.append('      Populate with:')
    notes.append('        - Technology stack (languages, frameworks, databases, runtimes)')
    notes.append('        - Architecture patterns (layers, modules, communication)')
    notes.append('        - External and internal dependencies')
    notes.append('        - Conventions, coding standards, and project-specific guidelines')
    notes.append('')
    notes.append("    $11: CONCURRENCY")
    notes.append('      ERR:concurrency{version, last_writer, updated}')
    notes.append("      Start at version 1.",)
    notes.append('')
    notes.append('    $12: PACKAGES')
    notes.append('      DOM:package_name{path, purpose}')
    notes.append('      DOM:inventory{path:".arqux/packages/inventory.cortex", purpose:"..."}')
    notes.append('      Reference to supplemental .cortex packages stored in')
    notes.append('      .arqux/packages/. Each entry points to a package file')
    notes.append('      that can be loaded on-demand for additional context.')
    notes.append('')
    notes.append('  step:"3 - CALL project.init with the built content",')
    notes.append('  action:"project.init(name=..., path=..., seed=<built_content>)",')
    notes.append('  warning:"Do NOT use cortex.write for governance files. Use project.init.',)
    notes.append('            The seed content is written directly to brain.cortex",')
    notes.append('  warning:"Do NOT skip sections. Empty sections should have # (empty) placeholder",')
    notes.append('  warning:"Do NOT edit .cortex/ NOMOS brain — leave it intact",')
    notes.append('')
    notes.append('  !canonical_rule{')
    notes.append('    "Every governed project MUST have its own .arqux/ directory."')
    notes.append('    "project.init creates it automatically."')
    notes.append('    "A project without .arqux/ is NOT under Arqux governance."')
    notes.append('  }')
    notes.append('  !identities_scope{')
    notes.append('    "Agent identities live ONLY at workspace level."')
    notes.append('    "Path: <workspace>/.arqux/identities/<agent>.cortex"')
    notes.append('    "Projects do NOT have their own identities/ directory."')
    notes.append('    "If you see identities inside a project .arqux/, they are ERRONEOUS."')
    notes.append('  }')
    notes.append("}")
    notes.append("")
    notes.append("# -- END BRAIN SEEDING INSTRUCTIONS --")

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

    sync_brain(root, "project.bind", detail=f"agent {agent_id} bound as {role}")

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


def _update_meta_brain(ws_root: Path, name: str, path_str: str, seed: str) -> None:
    """Update meta-brain with cross-project knowledge from a new project."""
    from ..constants import META_BRAIN_CORTEX

    meta_path = ws_root / META_BRAIN_CORTEX
    if not meta_path.exists():
        return

    domain = ""
    stack = ""
    for line in seed.splitlines():
        if "DOM:area" in line or "DOM:scope" in line:
            m = __import__("re").search(r'purpose:"([^"]+)"', line)
            if m:
                domain = m.group(1)[:80]
        if "KNW:stack" in line:
            m = __import__("re").search(r'tech:"([^"]+)"', line)
            if m:
                stack = m.group(1)[:80]

    key = name.replace("-", "_").replace(" ", "_")
    entry = f"DOM:{key}{{name:\"{name}\", path:\"{path_str}\", domain:\"{domain}\", stack:\"{stack}\"}}"
    with meta_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{entry}\n")


def _now_iso() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


handler_schemas = [
    {"name": "project.init", "fn": init_project, "description": "Initialize .arqux/ in a project directory and register it in the\nworkspace.", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Project name"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}, "seed": {"type": "string", "description": "Optional pre-prepared brain.cortex CORTEX content.\nWhen provided, writes it directly as brain.cortex in one step.\nUse when the agent has already studied the project context\nand can provide FCS, OBJ, RSK, KNW, etc. directly."}, "cycle": {"type": "string", "description": "Optional cycle name to auto-create after project init (P1-D)."}}, "required": ["name"]}},
    {"name": "project.bind", "fn": bind, "description": "Bind an agent identity to the current project with a role.", "input_schema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "role": {"type": "string", "enum": ["governor", "executor", "auditor"]}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["agent_id", "role"]}},
    {"name": "project.unbind", "fn": unbind, "description": "Release an agent binding from the current project.", "input_schema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}, "required": ["agent_id"]}},
    {"name": "project.status", "fn": status, "description": "Active project status (cycles, tasks, agents).", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
    {"name": "project.lessons", "fn": lessons, "description": "List lessons local to the current project.", "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "Path to project root. Defaults to cwd."}}}},
]
