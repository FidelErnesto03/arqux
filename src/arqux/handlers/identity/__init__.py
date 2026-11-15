"""identity handler package (BLP-006).

Handlers:

- ``identity.get`` — return agent identity data from .arqux/identities/
  or the packaged identities.
- ``identity.switch`` — hot identity switch in one atomic MCP call
  (BLP-011): validate, hydrate contract, register handoff + PULSE audit,
  update active context and return the ready header.
"""

from __future__ import annotations

from .elevate import elevate
from .get import DEFAULT_AGENT, get_handler
from .switch import switch

__all__ = [
    "elevate",
    "get_handler",
    "DEFAULT_AGENT",
    "switch",
    "handler_schemas",
]

handler_schemas = [
    {
        "name": "identity.get",
        "fn": get_handler,
        "description": (
            "Return agent identity data from .arqux/identities/<agent>.cortex "
            "or the packaged identities. Default agent_id is 'alfred'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent identifier. Defaults to 'alfred'.",
                },
                "path": {"type": "string", "description": "Starting path for resolving the project/workspace root."},
            },
        },
    },
    {
        "name": "identity.switch",
        "fn": switch,
        "description": (
            "Hot identity switch in one atomic call (BLP-011): validate the "
            "identity exists, hydrate the full contract, register handoff + "
            "PULSE audit, update the active context and return the header. "
            "Accepts content CORTEX and dry_run (meta-handler BLP-010)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Target identity (case-insensitive).",
                },
                "content": {
                    "type": "string",
                    "description": "CORTEX content with keys agent_id, summary, blps, tasks.",
                },
                "dry_run": {"type": "boolean", "default": False},
                "path": {"type": "string"},
            },
        },
    },
    {
        "name": "identity.elevate",
        "fn": elevate,
        "description": (
            "Elevate a brain.cortex $8 LNG lesson into an agent identity "
            "contract (AXM or LIM) — the behavioral learning line. "
            "Default is dry-run returning the proposal + preview_hash; "
            "apply=true requires confirm_hash matching the reviewed proposal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "string",
                    "description": "LNG entry name in brain $8 (e.g. verify_post_write_state).",
                },
                "agent": {
                    "type": "string",
                    "description": "Target identity (e.g. alfred, jarvis).",
                },
                "contract_type": {
                    "type": "string",
                    "enum": ["AXIOM", "LIMIT"],
                    "description": "AXIOM → AXM sigil | LIMIT → LIM sigil.",
                },
                "apply": {
                    "type": "boolean",
                    "default": False,
                    "description": "Apply the elevation (requires confirm_hash).",
                },
                "confirm_hash": {
                    "type": "string",
                    "description": "preview_hash from the dry-run proposal.",
                },
                "path": {"type": "string", "description": "Path to project root."},
            },
            "required": ["lesson_id", "agent", "contract_type"],
        },
    },
]
