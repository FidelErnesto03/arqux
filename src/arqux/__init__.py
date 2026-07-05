"""
Arqux — Minimum-viable governance framework for AI agent teams.

Public API surface:
    - `cli.main()` — entry point for the `arqux` console script.
    - `server.serve()` — start the MCP server.
    - `__version__` — package version string.

The framework exposes 24 MCP handlers grouped in 6 modules:
    workspace, project, cycle, task, evidence, protocol.

See `AGENTS.md` for the single-entry-point documentation.
"""

from .constants import (
    ARQUX_DIR,
    ARQUX_VERSION,
    PRODUCT_NAME,
)

__version__ = ARQUX_VERSION

__all__ = [
    "PRODUCT_NAME",
    "ARQUX_DIR",
    "ARQUX_VERSION",
    "__version__",
]
