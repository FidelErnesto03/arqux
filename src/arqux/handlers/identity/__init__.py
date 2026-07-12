"""identity handler package (BLP-006).

Handlers:

- ``identity.get`` — return agent identity data from .arqux/identities/
  or the packaged identities.
"""

from __future__ import annotations

from .get import get_handler, DEFAULT_AGENT

__all__ = [
    "get_handler",
    "DEFAULT_AGENT",
    "handler_schemas",
]

handler_schemas = [
    dict(
        name="identity.get",
        fn=get_handler,
        description=(
            "Return agent identity data from .arqux/identities/<agent>.cortex "
            "or the packaged identities. Default agent_id is 'alfred'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent identifier. Defaults to 'alfred'.",
                },
                "path": {"type": "string", "description": "Starting path for resolving the project/workspace root."},
            },
        },
    ),
]
