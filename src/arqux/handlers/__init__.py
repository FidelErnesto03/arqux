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

from . import cycle, evidence, project, protocol, task, workspace


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
        },
    },
))

# Project module (5 handlers)
_register(_spec(
    "project.init", project.init_project,
    "Initialize .arqux/ in a project directory and register it in the workspace.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "path": {"type": "string"},
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
        },
        "required": ["agent_id"],
    },
))
_register(_spec(
    "project.status", project.status,
    "Active project status (cycles, tasks, agents).",
    {"type": "object", "properties": {}},
))
_register(_spec(
    "project.lessons", project.lessons,
    "List lessons local to the current project.",
    {"type": "object", "properties": {}},
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
        },
    },
))
_register(_spec(
    "cycle.current", cycle.current_cycle,
    "Get the currently active cycle.",
    {"type": "object", "properties": {}},
))
_register(_spec(
    "cycle.close", cycle.close_cycle,
    "Close a cycle (no new tasks can be added).",
    {
        "type": "object",
        "properties": {
            "cycle_id": {"type": "string"},
            "summary": {"type": "string"},
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
        },
        "required": ["obj"],
    },
))
_register(_spec(
    "task.claim", task.claim_task,
    "An executor claims a task → status: in_progress.",
    {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
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
        },
    },
))
_register(_spec(
    "evidence.read", evidence.read_evidence,
    "Read a single evidence event by ID.",
    {
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
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
        },
        "required": ["agent_id", "role"],
    },
))
_register(_spec(
    "protocol.release", protocol.release,
    "Fully detach an agent (clean exit, no orphans).",
    {
        "type": "object",
        "properties": {"agent_id": {"type": "string"}},
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


# --- Surface for tests / introspection ------------------------------------

def list_handlers() -> list[str]:
    """Return the sorted list of all handler names."""
    return sorted(REGISTRY.keys())


def handler_count() -> int:
    return len(REGISTRY)


__all__ = ["REGISTRY", "HandlerSpec", "list_handlers", "handler_count"]
