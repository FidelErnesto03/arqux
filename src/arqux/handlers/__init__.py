"""Handler registry.

24 handlers across 6 modules. Each handler is exposed as an MCP tool with:
    - `fn`: the callable that does the work.
    - `description`: short one-liner for tool listings.
    - `input_schema`: JSON Schema describing the handler's arguments.

The registry is the single source of truth for the handler surface.
Adding a handler requires removing one (per the fixed-budget principle).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import cycle, evidence, project, protocol, task, workspace, cortex, skill, blueprint


@dataclass(frozen=True)
class HandlerSpec:
    """Specification of a single MCP handler."""

    name: str
    fn: Callable[..., Any]
    description: str
    input_schema: dict[str, Any]


def _spec(name: str, fn: Callable[..., Any], description: str, schema: dict[str, Any]) -> HandlerSpec:
    return HandlerSpec(name=name, fn=fn, description=description, input_schema=schema)


# --- Build the registry ----------------------------------------------------

REGISTRY: dict[str, HandlerSpec] = {}


def _register(spec: HandlerSpec) -> None:
    if spec.name in REGISTRY:
        raise RuntimeError(f"duplicate handler: {spec.name}")
    REGISTRY[spec.name] = spec


# Workspace module (3 handlers)
_register(_spec(
    "workspace.init", workspace.init_workspace,
    "Initialize .arqux/ at the workspace root.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to initialize as workspace root. Defaults to cwd."},
        },
    },
))
_register(_spec(
    "workspace.status", workspace.status,
    "Workspace status (OUT-MIN by default).",
    {
        "type": "object",
        "properties": {
            "verbose": {"type": "boolean", "default": False},
            "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."},
        },
    },
))
_register(_spec(
    "workspace.lessons", workspace.lessons,
    "List lessons elevated to the meta-brain.",
    {
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "Filter lessons by source project."},
            "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."},
        },
    },
))

# Project module (5 handlers)
_register(_spec(
    "project.init", project.init_project,
    "Initialize .arqux/ in a project directory and register it in the\nworkspace.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project name"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            "seed": {"type": "string", "description": "Optional pre-prepared brain.cortex CORTEX content.\nWhen provided, writes it directly as brain.cortex in one step.\nUse when the agent has already studied the project context\nand can provide FCS, OBJ, RSK, KNW, etc. directly."},
        },
        "required": ["name"],
    },
))
_register(_spec(
    "project.bind", project.bind,
    "Bind an agent identity to the current project with a role.",
    {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "role": {"type": "string", "enum": ["governor", "executor", "auditor"]},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["agent_id", "role"],
    },
))
_register(_spec(
    "project.unbind", project.unbind,
    "Release an agent binding from the current project.",
    {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["agent_id"],
    },
))
_register(_spec(
    "project.status", project.status,
    "Active project status (cycles, tasks, agents).",
    {"type": "object", "properties": {
        "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
    }},
))
_register(_spec(
    "project.lessons", project.lessons,
    "List lessons local to the current project.",
    {"type": "object", "properties": {
        "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
    }},
))

# Cycle module (4 handlers)
_register(_spec(
    "cycle.create", cycle.create_cycle,
    "Open a new cycle in the active project.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
    },
))
_register(_spec(
    "cycle.list", cycle.list_cycles,
    "List cycles in the active project.",
    {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["open", "closed"]},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
    },
))
_register(_spec(
    "cycle.current", cycle.current_cycle,
    "Get the currently active cycle.",
    {"type": "object", "properties": {
        "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
    }},
))
_register(_spec(
    "cycle.close", cycle.close_cycle,
    "Close a cycle (no new tasks can be added).",
    {
        "type": "object",
        "properties": {
            "cycle_id": {"type": "string"},
            "summary": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["cycle_id"],
    },
))

# Task module (7 handlers)
_register(_spec(
    "task.create", task.create_task,
    "Create a governed task in the current cycle.",
    {
        "type": "object",
        "properties": {
            "obj": {"type": "string"},
            "pre": {"type": "array", "items": {"type": "string"}},
            "proc": {"type": "array", "items": {"type": "string"}},
            "ac": {"type": "array", "items": {"type": "string"}},
            "blk": {"type": "array", "items": {"type": "string"}},
            "assignee": {"type": "string"},
            "complexity": {"type": "string", "enum": ["simple", "standard", "complex"]},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["obj"],
    },
))
_register(_spec(
    "task.claim", task.claim_task,
    "An executor claims a task → status: in_progress.",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["task_id"],
    },
))
_register(_spec(
    "task.update", task.update_task,
    "Update task progress, optionally change status.",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "note": {"type": "string"},
            "status": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["task_id", "note"],
    },
))
_register(_spec(
    "task.complete", task.complete_task,
    "Mark a task done and record evidence.",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "evidence": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["task_id"],
    },
))
_register(_spec(
    "task.fail", task.fail_task,
    "Mark a task blocked and record the cause.",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "reason": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["task_id", "reason"],
    },
))
_register(_spec(
    "task.read", task.read_task,
    "Read a task (CORTEX or HCORTEX format).",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "format": {"type": "string", "enum": ["cortex", "hcortex"], "default": "cortex"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["task_id"],
    },
))
_register(_spec(
    "task.list", task.list_tasks,
    "List tasks with filters.",
    {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "assignee": {"type": "string"},
            "cycle": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
    },
))

# Evidence module (3 handlers)
_register(_spec(
    "evidence.record", evidence.record_evidence,
    "Append an evidence entry to pulse.jsonl.",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["note", "artifact", "decision", "metric", "blocker"]},
            "payload": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["task_id", "kind", "payload"],
    },
))
_register(_spec(
    "evidence.list", evidence.list_evidence,
    "Query the evidence trail.",
    {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "cycle": {"type": "string"},
            "since": {"type": "string"},
            "limit": {"type": "integer", "default": 100},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
    },
))
_register(_spec(
    "evidence.read", evidence.read_evidence,
    "Read a single evidence event by ID.",
    {
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["event_id"],
    },
))

# Protocol module (4 handlers)
_register(_spec(
    "protocol.adopt", protocol.adopt,
    "Onboard an agent with a role.",
    {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "role": {"type": "string", "enum": ["governor", "executor", "auditor"]},
            "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."},
        },
        "required": ["agent_id", "role"],
    },
))
_register(_spec(
    "protocol.release", protocol.release,
    "Fully detach an agent (clean exit, no orphans).",
    {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "path": {"type": "string", "description": "Path to workspace root. Defaults to cwd."},
        },
        "required": ["agent_id"],
    },
))
_register(_spec(
    "protocol.pause", protocol.pause,
    "Suspend governance for the current session without losing state.",
    {"type": "object", "properties": {}},
))
_register(_spec(
    "protocol.resume", protocol.resume,
    "Resume governance after a pause.",
    {"type": "object", "properties": {}},
))

# --- Utility handlers (outside governance budget) ---------------------------
#
# These handlers do NOT count toward the 24-handler governance budget.
# They expose CODEC-CORTEX operations for reading, writing, verifying,
# and rendering arbitrary .cortex files that are NOT governance state.
#
# Governance state (brain.cortex, manifest.cortex, tasks, cycles) must
# be mutated through the governance handlers only (§13).

_register(_spec(
    "cortex.read", cortex.read_handler,
    "Read and parse a .cortex file using CODEC-CORTEX.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": ["path"],
    },
))
_register(_spec(
    "cortex.write", cortex.write_handler,
    "Write (atomically) a .cortex file from CORTEX source text.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "force": {"type": "boolean", "default": False},
        },
        "required": ["path", "content"],
    },
))
_register(_spec(
    "cortex.verify", cortex.verify_handler,
    "Verify a .cortex file's structure using CODEC-CORTEX.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": ["path"],
    },
))
_register(_spec(
    "cortex.render.diagram", cortex.render_diagram_handler,
    "Render a PlantUML diagram to SVG/PNG. Requires plantuml.jar.",
    {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "PUML source text (@startuml block)"},
            "format": {"type": "string", "enum": ["svg", "png"], "default": "svg"},
            "path": {"type": "string"},
        },
        "required": ["source"],
    },
))
_register(_spec(
    "setup.plantuml", cortex.setup_plantuml_handler,
    "Download and install plantuml.jar to ~/.arqux/bin/.",
    {
        "type": "object",
        "properties": {
            "force": {"type": "boolean", "default": False},
            "path": {"type": "string"},
        },
    },
))

_register(_spec(
    "cortex.render", cortex.render_handler,
    "Render a .cortex file to HCORTEX READ markdown.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": ["path"],
    },
))

# --- identity handlers ---
_register(_spec(
    "identity.record", cortex.record_lesson_handler,
    "Record a behavioral lesson into the agent's identity file.",
    {
        "type": "object",
        "properties": {
            "lesson": {"type": "string", "description": "Lesson text"},
            "kind": {"type": "string", "description": "Lesson kind: behavioral/process/format/rule/infrastructure", "default": "behavioral"},
            "cause": {"type": "string", "description": "What caused this lesson", "default": ""},
            "agent_id": {"type": "string", "description": "Agent identifier (default: current agent)"},
            "path": {"type": "string", "description": "Path to search up from for .arqux/identities/"},
        },
        "required": ["lesson"],
    },
))

# --- learning engine handlers ---
_register(_spec(
    "cortex.learn", cortex.learn_scan_handler,
    "Scan a project brain through the CODEC-CORTEX Learning Engine.\n"
    "Returns scored entries and elevation candidates.",
    {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["project", "workspace"], "default": "project"},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
    },
))
_register(_spec(
    "cortex.learn.elevate", cortex.learn_elevate_handler,
    "Elevate a learning candidate (SES->LNG or LNG->KNW).\n"
    "Default is dry-run (shows diff without applying).\n"
    "Pass apply=true to write the elevation to brain.cortex.",
    {
        "type": "object",
        "properties": {
            "candidate_id": {"type": "string", "description": "Candidate ID from cortex.learn output"},
            "apply": {"type": "boolean", "default": False, "description": "If true, apply the elevation. Default is dry-run."},
            "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
        },
        "required": ["candidate_id"],
    },
))


# --- blueprint handlers ---
_register(_spec(
    "blueprint.create", blueprint.create_blueprint,
    "Create a new Blueprint from BLP_TEMPLATE.md in draft state.",
    {
        "type": "object",
        "properties": {
            "obj": {"type": "string", "description": "Blueprint objective"},
            "cycle": {"type": "string", "description": "Cycle ID. Uses most recent if omitted."},
            "path": {"type": "string"},
        },
        "required": ["obj"],
    },
))
_register(_spec(
    "blueprint.define", blueprint.define_blueprint,
    "Fill the Blueprint's definition sections. State → defined.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "pre": {"type": "array", "items": {"type": "string"}},
            "scope": {"type": "string"},
            "exclusions": {"type": "string"},
            "mandatory_rules": {"type": "array", "items": {"type": "string"}},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "procedure": {"type": "string"},
            "validations": {"type": "array", "items": {"type": "object"}},
            "technical_design": {"type": "string"},
            "operational_design": {"type": "string"},
            "risks": {"type": "array", "items": {"type": "string"}},
            "blocking_rule": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.mature", blueprint.mature_blueprint,
    "Enter maturation phase. Cyclic Architect interaction begins.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.ready", blueprint.ready_blueprint,
    "Architect declares Blueprint ready for execution.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.assign", blueprint.assign_blueprint,
    "Governor assigns an executor to the Blueprint.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "executor": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id", "executor"],
    },
))
_register(_spec(
    "blueprint.claim", blueprint.claim_blueprint,
    "Executor claims the Blueprint. State → in_progress.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.update", blueprint.update_blueprint,
    "Update Blueprint progress with a note.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "note": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id", "note"],
    },
))
_register(_spec(
    "blueprint.complete", blueprint.complete_blueprint,
    "Declare execution complete. State → review.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "evidence": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.cancel", blueprint.cancel_blueprint,
    "Cancel a Blueprint. Governor-only. State → cancelled.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "reason": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.fail", blueprint.fail_blueprint,
    "Blueprint hit an obstacle. State → blocked.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "reason": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id", "reason"],
    },
))
_register(_spec(
    "blueprint.approve", blueprint.approve_blueprint,
    "Auditor approves after cross-verification. State → done.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.re_delegate", blueprint.re_delegate_blueprint,
    "Re-delegate after verification fail (max 3 loops).",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.block_for_architect", blueprint.block_for_architect,
    "Block for Architect manual review after 3rd verification fail.",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.read", blueprint.read_blueprint,
    "Read a full Blueprint (HCORTEX or CORTEX format).",
    {
        "type": "object",
        "properties": {
            "bp_id": {"type": "string"},
            "format": {"type": "string", "enum": ["hcortex", "cortex"], "default": "hcortex"},
            "path": {"type": "string"},
        },
        "required": ["bp_id"],
    },
))
_register(_spec(
    "blueprint.list", blueprint.list_blueprints,
    "List Blueprints with optional filters.",
    {
        "type": "object",
        "properties": {
            "cycle": {"type": "string"},
            "status": {"type": "string"},
            "path": {"type": "string"},
        },
    },
))


# --- skill management handlers ---
_register(_spec(
    "skill.import", skill.import_skill,
    "Acquire a skill from external source, store original in originals/.",
    {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Origin (marketplace, platform, url:...)"},
            "name": {"type": "string", "description": "Skill name (e.g. oracle-apex)"},
            "content": {"type": "string", "description": "Raw skill content. Omit to get instructions first."},
            "path": {"type": "string", "description": "Path to workspace/project root"},
        },
        "required": ["source", "name"],
    },
))
_register(_spec(
    "skill.convert", skill.convert_skill,
    "Convert a skill from original format to CORTEX ultra-dense.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name"},
            "path": {"type": "string"},
        },
        "required": ["name"],
    },
))
_register(_spec(
    "skill.record", skill.record_adaptation,
    "Record a deviation (ADA) when a skill does not match the real context.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name"},
            "expected": {"type": "string", "description": "What the skill says"},
            "actual": {"type": "string", "description": "What was actually done"},
            "reason": {"type": "string", "description": "Why the deviation occurred"},
            "path": {"type": "string"},
        },
        "required": ["name", "expected", "actual", "reason"],
    },
))
_register(_spec(
    "skill.evolve", skill.evolve_skill,
    "Apply an approved adaptation to a skill. Default is dry-run.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name"},
            "adaptation_id": {"type": "string", "description": "Adaptation entry selector"},
            "apply": {"type": "boolean", "default": False, "description": "If true, apply the evolution"},
            "path": {"type": "string"},
        },
        "required": ["name", "adaptation_id"],
    },
))
_register(_spec(
    "skill.list", skill.list_skills,
    "List all available skills in .arqux/skills/.",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
    },
))


# --- Surface for tests / introspection ------------------------------------

def list_handlers() -> list[str]:
    """Return the sorted list of all handler names."""
    return sorted(REGISTRY.keys())


def handler_count() -> int:
    return len(REGISTRY)


__all__ = ["REGISTRY", "HandlerSpec", "list_handlers", "handler_count"]
