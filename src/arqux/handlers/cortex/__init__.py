"""Cortex handler package.

Split from the original monolithic ``cortex.py`` into submodules:

- ``read_write`` — read, write, verify, render handlers
- ``entries`` — entry CRUD handlers + file.validate
- ``diagram`` — diagram validation, rendering, PlantUML setup
- ``learning`` — identity.record, cortex.learn, cortex.learn.elevate

All public symbols are re-exported here for backward compatibility:
``from arqux.handlers.cortex import <name>`` still works.
"""

from __future__ import annotations

from .checkpoint import checkpoint_handler
from .diagram import (
    render_diagram_handler,
    render_validate_file_handler,
    setup_plantuml_handler,
)
from .entries import (
    entry_add_handler,
    entry_delete_handler,
    entry_get_handler,
    entry_list_handler,
    entry_move_handler,
    entry_update_handler,
    file_validate_handler,
)
from .format import format_handler
from .learning import (
    learn_elevate_handler,
    learn_scan_handler,
    record_lesson_handler,
    record_lesson_handler_legacy,
)
from .migrate import migrate_handler
from .patch import patch_handler
from .read_write import (
    _next_number,
    read_handler,
    render_handler,
    verify_handler,
    write_handler,
)
from .ref import ref_handler

__all__ = [
    "_next_number",
    "read_handler",
    "write_handler",
    "verify_handler",
    "render_handler",
    "record_lesson_handler",
    "record_lesson_handler_legacy",
    "entry_get_handler",
    "entry_add_handler",
    "entry_update_handler",
    "entry_delete_handler",
    "entry_move_handler",
    "entry_list_handler",
    "file_validate_handler",
    "render_validate_file_handler",
    "render_diagram_handler",
    "setup_plantuml_handler",
    "learn_scan_handler",
    "learn_elevate_handler",
    "ref_handler",
    "format_handler",
    "patch_handler",
    "migrate_handler",
    "handler_schemas",
]

handler_schemas = [
    {
        "name": "cortex.read",
        "fn": read_handler,
        "description": (
            "Read and parse a .cortex file. mode='cortex' (default) returns "
            "raw CORTEX entries as dict (canal I); mode='hcortex' renders "
            "human-readable markdown (canal E)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["cortex", "hcortex"],
                    "default": "cortex",
                    "description": "Output format: cortex (raw dict, canal I) or hcortex (markdown, canal E).",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "cortex.ref",
        "fn": ref_handler,
        "description": (
            "Return the definition of a CORTEX sigil (name, type, risk, "
            "layer, description). Reads from local sigil cache."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sigil": {
                    "type": "string",
                    "description": "Sigil identifier (case-insensitive), e.g. 'WRK', 'lng'.",
                },
                "path": {"type": "string"},
            },
            "required": ["sigil"],
        },
    },
    {
        "name": "cortex.format",
        "fn": format_handler,
        "description": (
            "Transform content between CORTEX (machine) and HCORTEX "
            "(human-readable). target='hcortex' (default) renders sigils "
            "as readable headers; target='cortex' parses headers back."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Source text to transform. If omitted, reads from path."},
                "target": {
                    "type": "string",
                    "enum": ["hcortex", "cortex"],
                    "default": "hcortex",
                },
                "path": {"type": "string"},
            },
        },
    },
    {
        "name": "cortex.write",
        "fn": write_handler,
        "description": "Write (atomically) a .cortex file from CORTEX source text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "cortex.verify",
        "fn": verify_handler,
        "description": "Verify a .cortex file's structure using CODEC-CORTEX.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "cortex.render",
        "fn": render_handler,
        "description": "Render a .cortex file to HCORTEX READ markdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "cortex.render.validate_file",
        "fn": render_validate_file_handler,
        "description": "Validate all PUML blocks in a file. Returns D1-D5 checklist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "cortex.render.diagram",
        "fn": render_diagram_handler,
        "description": "Render a PlantUML diagram to SVG/PNG. Requires plantuml.jar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "PUML source text (@startuml block)"},
                "format": {"type": "string", "enum": ["svg", "png"], "default": "svg"},
                "path": {"type": "string"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "cortex.file.validate",
        "fn": file_validate_handler,
        "description": "Scan a .cortex file for duplicate entry names and optionally fix them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file or directory containing .cortex files"},
                "fix": {"type": "boolean", "default": False, "description": "If true, rename duplicates with _XXXX suffix"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "setup.plantuml",
        "fn": setup_plantuml_handler,
        "description": "Download and install plantuml.jar to ~/.arqux/bin/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "force": {"type": "boolean", "default": False},
                "path": {"type": "string"},
            },
        },
    },
    {
        "name": "identity.record",
        "fn": record_lesson_handler,
        "description": "Record a behavioral lesson into the agent's identity file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson": {"type": "string", "description": "Lesson text"},
                "kind": {"type": "string", "description": "Lesson kind: behavioral/process/format/rule/infrastructure", "default": "behavioral"},
                "cause": {"type": "string", "description": "What caused this lesson", "default": ""},
                "prevention": {"type": "string", "description": "How to prevent this lesson from recurring. Required for LNG entries."},
                "agent_id": {"type": "string", "description": "Agent identifier (default: current agent)"},
                "path": {"type": "string", "description": "Path to search up from for .arqux/identities/"},
            },
            "required": ["lesson"],
        },
    },
    {
        "name": "cortex.learn",
        "fn": learn_scan_handler,
        "description": "Scan a project brain through the CODEC-CORTEX Learning Engine.\n"
        "Returns scored entries and elevation candidates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["project", "workspace"], "default": "project"},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
        },
    },
    {
        "name": "cortex.learn.elevate",
        "fn": learn_elevate_handler,
        "description": "Elevate a learning candidate (SES->LNG or LNG->KNW).\n"
        "Default is dry-run (shows diff without applying).\n"
        "Pass apply=true with confirm_hash from a reviewed dry-run to write the elevation to brain.cortex.",
        "input_schema": {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string", "description": "Candidate ID from cortex.learn output"},
                "apply": {"type": "boolean", "default": False, "description": "If true, apply the elevation. Default is dry-run."},
                "confirm_hash": {"type": "string", "description": "Preview hash from a reviewed dry-run. Required when apply=true."},
                "path": {"type": "string", "description": "Path to project root. Defaults to cwd."},
            },
            "required": ["candidate_id"],
        },
    },
    {
        "name": "cortex.entry.get",
        "fn": entry_get_handler,
        "description": (
            "Read entries matching a CORTEX selector from a .cortex file. "
            "format='cortex' returns raw CORTEX entries (canal I); "
            "format='hcortex' (default) returns parsed dicts (canal E)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file"},
                "selector": {"type": "string", "description": "CORTEX selector e.g. $2/FCS:current or LNG:*"},
                "format": {
                    "type": "string",
                    "enum": ["cortex", "hcortex"],
                    "default": "hcortex",
                    "description": "Output format: cortex (raw entry strings, canal I) or hcortex (parsed dicts, canal E).",
                },
            },
            "required": ["path", "selector"],
        },
    },
    {
        "name": "cortex.entry.add",
        "fn": entry_add_handler,
        "description": (
            "Add a new entry to a .cortex file. Accepts a 'content' CORTEX "
            "entry string (BLP-005, canal I) — when provided, fields "
            "extracted from content override individual params."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file"},
                "section": {"type": "string", "description": "Section ID e.g. $5"},
                "sigil": {"type": "string", "description": "Sigil e.g. LNG"},
                "name": {"type": "string", "description": "Entry name"},
                "value": {"type": "string", "description": "Entry value (attrs body or plain text)"},
                "content": {"type": "string", "description": "CORTEX entry string 'sigil:name{key:val,...}' — overrides sigil/name/value when present (canal I)."},
                "create_section": {"type": "boolean", "default": False},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["path", "section", "sigil", "name", "value"],
        },
    },
    {
        "name": "cortex.entry.update",
        "fn": entry_update_handler,
        "description": "Update an entry selected by a CORTEX selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file"},
                "selector": {"type": "string", "description": "CORTEX selector e.g. $5/LNG:lesson"},
                "set_": {"type": "string", "description": "Key:value pairs to merge (attrs entries). Not JSON — raw 'key:val,key2:val2'"},
                "replace_body": {"type": "string", "description": "New body text (cuerpo/bloque entries)"},
                "append": {"type": "boolean", "default": False, "description": "Append to existing body"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["path", "selector"],
        },
    },
    {
        "name": "cortex.entry.delete",
        "fn": entry_delete_handler,
        "description": "Delete an entry matching a CORTEX selector from a .cortex file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file"},
                "selector": {"type": "string", "description": "CORTEX selector"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["path", "selector"],
        },
    },
    {
        "name": "cortex.entry.move",
        "fn": entry_move_handler,
        "description": "Move an entry between sections in a .cortex file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file"},
                "selector": {"type": "string", "description": "CORTEX selector"},
                "to_section": {"type": "string", "description": "Target section ID e.g. $7"},
            },
            "required": ["path", "selector", "to_section"],
        },
    },
    {
        "name": "cortex.entry.list",
        "fn": entry_list_handler,
        "description": (
            "List entries in a .cortex file, optionally filtered. "
            "format='cortex' returns raw CORTEX entries (canal I); "
            "format='hcortex' (default) returns parsed dicts (canal E)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file"},
                "section": {"type": "string", "description": "Filter by section ID"},
                "sigil": {"type": "string", "description": "Filter by sigil"},
                "format": {
                    "type": "string",
                    "enum": ["cortex", "hcortex"],
                    "default": "hcortex",
                    "description": "Output format: cortex (raw entry strings, canal I) or hcortex (parsed dicts, canal E).",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "cortex.patch",
        "fn": patch_handler,
        "description": (
            "Patch multiple entries in a .cortex file from a CORTEX content "
            "payload (BLP-010 meta-handler). Accepts content as "
            "'$SELECTOR:{new_body}'. Supports dry_run mode."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .cortex file."},
                "content": {"type": "string", "description": "CORTEX content with selectors and new bodies."},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "cortex.migrate",
        "fn": migrate_handler,
        "description": (
            "Migrate a .cortex file by applying a named transform "
            "(reseccionar|resigilar). Writes atomically (BLP-010 meta-handler). "
            "Supports dry_run mode."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string"},
                "target_path": {"type": "string"},
                "transform": {"type": "string", "enum": ["reseccionar", "resigilar"]},
                "content": {"type": "string", "description": "CORTEX content with keys source_path, target_path, transform."},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["source_path", "target_path", "transform"],
        },
    },
    {
        "name": "cortex.checkpoint",
        "fn": checkpoint_handler,
        "description": (
            "Persist the agent's working state (WRK:current) as a single "
            "CORTEX line in brain.cortex §8. Accepts content as key:value "
            "pairs (fcs:,obj:,tasks:,state:)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "CORTEX content: fcs:...,obj:...,tasks:...,state:...",
                },
                "path": {"type": "string", "description": "Path to project root."},
            },
            "required": ["content"],
        },
    },
]
