"""Blueprint handler package.

Split from the original monolithic ``blueprint.py`` into submodules:

- ``lifecycle`` — create, ready, claim
- ``review`` — complete, ac, re_delegate, block_for_architect, fail, cancel
- ``manage`` — update, task
- ``_helpers`` — shared constants, private helpers, read_blueprint, list_blueprints

All public symbols are re-exported here for backward compatibility:
``from arqux.handlers.blueprint import <name>`` still works.

Simplified lifecycle: draft → ready → in_progress → done + cancelled/blocked (BLP-004)
"""

from __future__ import annotations

from ._helpers import (
    BLUEPRINT_TEMPLATE,
    BP_BLOCKED,
    BP_CANCELLED,
    BP_DONE,
    BP_DRAFT,
    BP_IN_PROGRESS,
    BP_READY,
    MAX_VERIFICATION_LOOPS,
    QUALITY_GATES,
    VALID_TRANSITIONS,
    next_blueprint_id_safe,
    scan_markers,
)
from ._read import (
    list_blueprints,
    read_blueprint,
)
from .execute import execute_blueprint
from .lifecycle import (
    claim_blueprint,
    create_blueprint,
    ready_blueprint,
)
from .manage import (
    task_blueprint,
    update_blueprint,
)
from .review import (
    ac_blueprint,
    block_for_architect,
    cancel_blueprint,
    complete_blueprint,
    fail_blueprint,
    re_delegate_blueprint,
)
from .synthesize import synthesize_blueprint

__all__ = [
    # Constants
    "BLUEPRINT_TEMPLATE",
    "BP_BLOCKED",
    "BP_CANCELLED",
    "BP_DONE",
    "BP_DRAFT",
    "BP_IN_PROGRESS",
    "BP_READY",
    "MAX_VERIFICATION_LOOPS",
    "QUALITY_GATES",
    "VALID_TRANSITIONS",
    # Public helpers
    "list_blueprints",
    "next_blueprint_id_safe",
    "read_blueprint",
    "scan_markers",
    # Lifecycle
    "claim_blueprint",
    "create_blueprint",
    "ready_blueprint",
    # Synthesize (BLP-007)
    "synthesize_blueprint",
    # Execute (BLP-010)
    "execute_blueprint",
    # Manage
    "task_blueprint",
    "update_blueprint",
    # Review
    "ac_blueprint",
    "block_for_architect",
    "cancel_blueprint",
    "complete_blueprint",
    "fail_blueprint",
    "re_delegate_blueprint",
    # Schema
    "handler_schemas",
]

handler_schemas = [
    {"name": "blueprint.create", "fn": create_blueprint, "description": "Create a new Blueprint from BLP_TEMPLATE.md in draft state.", "input_schema": {"type": "object", "properties": {"obj": {"type": "string", "description": "Blueprint objective"}, "cycle": {"type": "string", "description": "Cycle ID. Uses most recent if omitted."}, "path": {"type": "string"}}, "required": ["obj"]}},
    {"name": "blueprint.ready", "fn": ready_blueprint, "description": "Architect declares Blueprint ready for execution. draft → ready.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.claim", "fn": claim_blueprint, "description": "Executor claims the Blueprint. ready → in_progress + implicit executor assignment.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.task", "fn": task_blueprint, "description": "Update one task's checkbox in §14. Status: in_progress/completed.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "task_id": {"type": "string", "description": "Task ID like T-1.1"}, "status": {"type": "string", "enum": ["in_progress", "completed"]}, "evidence": {"type": "string", "description": "Optional evidence note"}, "path": {"type": "string"}}, "required": ["bp_id", "task_id", "status"]}},
    {"name": "blueprint.ac", "fn": ac_blueprint, "description": "Verify one AC in §12.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "ac_id": {"type": "string", "description": "AC ID like AC-01"}, "status": {"type": "string", "enum": ["verified", "failed"]}, "evidence": {"type": "string", "description": "Evidence if verified"}, "reason": {"type": "string", "description": "Reason if failed"}, "path": {"type": "string"}}, "required": ["bp_id", "ac_id", "status"]}},
    {"name": "blueprint.update", "fn": update_blueprint, "description": "Update Blueprint progress with a note or refine a single section.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "note": {"type": "string", "description": "Progress note to append"}, "section": {"type": "string", "description": "Section number like '§3' or '3'"}, "content": {"type": "string", "description": "Section content (text or markdown)"}, "puml": {"type": "string", "description": "PlantUML source for diagram sections"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.complete", "fn": complete_blueprint, "description": "Declare execution complete. in_progress → done (completado + aprobado en 1 paso).", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "evidence": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.cancel", "fn": cancel_blueprint, "description": "Cancel a Blueprint. Governor-only. State → cancelled.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "reason": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.fail", "fn": fail_blueprint, "description": "Blueprint hit an obstacle. State → blocked.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "reason": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id", "reason"]}},
    {"name": "blueprint.re_delegate", "fn": re_delegate_blueprint, "description": "Re-delegate after verification failure. Re-opens a done/blocked blueprint.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.block_for_architect", "fn": block_for_architect, "description": "Block for Architect manual review.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.read", "fn": read_blueprint, "description": "Read a full Blueprint (HCORTEX or CORTEX format).", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "format": {"type": "string", "enum": ["hcortex", "cortex"], "default": "hcortex"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.list", "fn": list_blueprints, "description": "List Blueprints with optional filters.", "input_schema": {"type": "object", "properties": {"cycle": {"type": "string"}, "status": {"type": "string"}, "path": {"type": "string"}}}},
    {"name": "blueprint.synthesize", "fn": synthesize_blueprint, "description": "GUIDE MODE: creates or finds the BLP and returns the next pending section. Agent writes directly via blueprint.update(). synthesize does NOT write files.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string", "description": "Blueprint ID e.g. 'BLP-007'. Created with status=draft if not exists."}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.execute", "fn": execute_blueprint, "description": "Execute a Blueprint: verify §3 preconditions, run §14 tasks sequentially, verify §12 ACs, mark complete (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string", "description": "Blueprint ID."}, "content": {"type": "string", "description": "CORTEX content with keys bp_id, evidence, fail_reason."}, "dry_run": {"type": "boolean", "default": False, "description": "If true, report what would happen without modifying state."}, "path": {"type": "string"}}, "required": ["bp_id"]}},
]
