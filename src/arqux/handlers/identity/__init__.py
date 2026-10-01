"""identity handler package (BLP-006).

Handlers:

- ``identity.get`` — return agent identity data from .arqux/identities/
  or the packaged identities.
- ``identity.switch`` — hot identity switch in one atomic MCP call
  (BLP-011): validate, hydrate contract, register handoff + PULSE audit,
  update active context and return the ready header.
"""

from __future__ import annotations

from .get import DEFAULT_AGENT, get_handler
from .switch import switch

__all__ = [
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
]
