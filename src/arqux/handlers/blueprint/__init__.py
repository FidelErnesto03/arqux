"""Blueprint handler package.

Split from the original monolithic ``blueprint.py`` into submodules:

- ``lifecycle`` — create, define, mature, ready, assign, claim
- ``review`` — complete, approve, ac, re_delegate, block_for_architect, fail, cancel
- ``manage`` — update, gate, task
- ``_helpers`` — shared constants, private helpers, read_blueprint, list_blueprints

All public symbols are re-exported here for backward compatibility:
``from arqux.handlers.blueprint import <name>`` still works.
"""

from __future__ import annotations

from ._helpers import (
    BLUEPRINT_TEMPLATE,
    BP_BLOCKED,
    BP_CANCELLED,
    BP_DEFINED,
    BP_DONE,
    BP_DRAFT,
    BP_IN_PROGRESS,
    BP_MATURING,
    BP_READY,
    BP_REVIEW,
    LEARNING_GATE,
    MATURATION_GATES,
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
    assign_blueprint,
    claim_blueprint,
    create_blueprint,
    define_blueprint,
    mature_blueprint,
    ready_blueprint,
)
from .manage import (
    gate_blueprint,
    task_blueprint,
    update_blueprint,
)
from .review import (
    ac_blueprint,
    approve_blueprint,
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
    "BP_DEFINED",
    "BP_DONE",
    "BP_DRAFT",
    "BP_IN_PROGRESS",
    "BP_MATURING",
    "BP_READY",
    "BP_REVIEW",
    "LEARNING_GATE",
    "MAX_VERIFICATION_LOOPS",
    "MATURATION_GATES",
    "QUALITY_GATES",
    "VALID_TRANSITIONS",
    # Public helpers
    "list_blueprints",
    "next_blueprint_id_safe",
    "read_blueprint",
    "scan_markers",
    # Lifecycle
    "assign_blueprint",
    "claim_blueprint",
    "create_blueprint",
    "define_blueprint",
    "mature_blueprint",
    "ready_blueprint",
    # Synthesize (BLP-007)
    "synthesize_blueprint",
    # Execute (BLP-010)
    "execute_blueprint",
    # Manage
    "gate_blueprint",
    "task_blueprint",
    "update_blueprint",
    # Review
    "ac_blueprint",
    "approve_blueprint",
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
    {"name": "blueprint.define", "fn": define_blueprint, "description": "Fill the Blueprint's definition sections. State → defined. Accepts a 'sections' dict (BLP-012) mapping section IDs ('BLP:N') to content — section IDs are validated dynamically against BLP_TEMPLATE.md via parse_blp_template().", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "pre": {"type": "array", "items": {"type": "string"}}, "scope": {"type": "string"}, "exclusions": {"type": "string"}, "mandatory_rules": {"type": "array", "items": {"type": "string"}}, "acceptance_criteria": {"type": "array", "items": {"type": "string"}}, "procedure": {"type": "string"}, "validations": {"type": "array", "items": {"type": "object"}}, "technical_design": {"type": "string"}, "operational_design": {"type": "string"}, "risks": {"type": "array", "items": {"type": "string"}}, "blocking_rule": {"type": "string"}, "sections": {"type": "object", "description": "Dynamic dict of section_id (e.g. 'BLP:3') -> content string. Section IDs validated against BLP_TEMPLATE.md (BLP-012)."}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.mature", "fn": mature_blueprint, "description": "Enter maturation phase. Mode 'live' for synchronous co-design, 'async' (default) for cyclic iteration.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "mode": {"type": "string", "enum": ["live", "async"], "default": "async", "description": "Maturation mode: 'live' for synchronous co-design, 'async' for cyclic iteration."}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.gate", "fn": gate_blueprint, "description": "Approve one or all Blueprint quality gates after Architect maturation.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "gate": {"type": "string", "description": "Quality gate name, or 'all' for maturation gates."}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.ready", "fn": ready_blueprint, "description": "Architect declares Blueprint ready for execution.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.assign", "fn": assign_blueprint, "description": "Governor assigns an executor to the Blueprint.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "executor": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id", "executor"]}},
    {"name": "blueprint.claim", "fn": claim_blueprint, "description": "Executor claims the Blueprint. State → in_progress.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.task", "fn": task_blueprint, "description": "Update one task's checkbox in §14. Status: in_progress/completed.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "task_id": {"type": "string", "description": "Task ID like T-1.1"}, "status": {"type": "string", "enum": ["in_progress", "completed"]}, "evidence": {"type": "string", "description": "Optional evidence note"}, "path": {"type": "string"}}, "required": ["bp_id", "task_id", "status"]}},
    {"name": "blueprint.ac", "fn": ac_blueprint, "description": "Verify one AC in §12. Fail triggers auto re-delegate (max 3).", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "ac_id": {"type": "string", "description": "AC ID like AC-01"}, "status": {"type": "string", "enum": ["verified", "failed"]}, "evidence": {"type": "string", "description": "Evidence if verified"}, "reason": {"type": "string", "description": "Reason if failed"}, "path": {"type": "string"}}, "required": ["bp_id", "ac_id", "status"]}},
    {"name": "blueprint.update", "fn": update_blueprint, "description": "Update Blueprint progress with a note or refine a single section.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "note": {"type": "string", "description": "Progress note to append"}, "section": {"type": "string", "description": "Section number like '§3' or '3'"}, "content": {"type": "string", "description": "Section content (text or markdown)"}, "puml": {"type": "string", "description": "PlantUML source for diagram sections"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.complete", "fn": complete_blueprint, "description": "Declare execution complete. State → review.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "evidence": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.cancel", "fn": cancel_blueprint, "description": "Cancel a Blueprint. Governor-only. State → cancelled.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "reason": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.fail", "fn": fail_blueprint, "description": "Blueprint hit an obstacle. State → blocked.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "reason": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id", "reason"]}},
    {"name": "blueprint.approve", "fn": approve_blueprint, "description": "Auditor approves after cross-verification. State → done.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.re_delegate", "fn": re_delegate_blueprint, "description": "Re-delegate after verification fail (max 3 loops).", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.block_for_architect", "fn": block_for_architect, "description": "Block for Architect manual review after 3rd verification fail.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.read", "fn": read_blueprint, "description": "Read a full Blueprint (HCORTEX or CORTEX format).", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string"}, "format": {"type": "string", "enum": ["hcortex", "cortex"], "default": "hcortex"}, "path": {"type": "string"}}, "required": ["bp_id"]}},
    {"name": "blueprint.list", "fn": list_blueprints, "description": "List Blueprints with optional filters.", "input_schema": {"type": "object", "properties": {"cycle": {"type": "string"}, "status": {"type": "string"}, "path": {"type": "string"}}}},
    {"name": "blueprint.synthesize", "fn": synthesize_blueprint, "description": "Write a Blueprint's content sections in one call from a CORTEX content payload (BLP-007). Validates section IDs against BLP_TEMPLATE.md via parse_blp_template(). Creates the BLP file if it doesn't exist (status=draft). Does NOT change BLP status — only writes content. Writes atomically.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string", "description": "Blueprint ID e.g. 'BLP-007'. Created with status=draft if not exists."}, "content": {"type": "string", "description": "CORTEX content payload. Per-section form: '$N:{body}'. Single-body form: '$0:{1: \"body1\", 2: \"body2\"}'."}, "path": {"type": "string"}}, "required": ["bp_id", "content"]}},
    {"name": "blueprint.execute", "fn": execute_blueprint, "description": "Execute a Blueprint: verify §3 preconditions, run §14 tasks sequentially, verify §12 ACs, mark complete (BLP-010 meta-handler). Supports dry_run mode.", "input_schema": {"type": "object", "properties": {"bp_id": {"type": "string", "description": "Blueprint ID."}, "content": {"type": "string", "description": "CORTEX content with keys bp_id, evidence, fail_reason."}, "dry_run": {"type": "boolean", "default": False, "description": "If true, report what would happen without modifying state."}, "path": {"type": "string"}}, "required": ["bp_id"]}},
]
