"""context handler package (BLP-006).

Handlers:

- ``context.detect`` — scans upward for ``.arqux/`` directory
- ``context.full`` — returns full project context (cycles, agents, skills)
"""

from __future__ import annotations

from .detect import detect_handler
from .full import full_handler

__all__ = [
    "detect_handler",
    "full_handler",
    "handler_schemas",
]

handler_schemas = [
    {
        "name": "context.detect",
        "fn": detect_handler,
        "description": (
            "Scan upward from a path for a .arqux/ directory. "
            "Returns {found: bool, path: str|null, kind: 'project'|'workspace'|null}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Starting path. Defaults to cwd."},
            },
        },
    },
    {
        "name": "context.full",
        "fn": full_handler,
        "description": (
            "Return the full project context: project name, available "
            "cycles, current cycle, agents bound, skills available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Starting path. Defaults to cwd."},
            },
        },
    },
]
