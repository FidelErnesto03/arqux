"""Backward-compat shim — re-exports from handlers/cortex/ package.

P1-L PATCH (2026-07-12): This file is a 1-line stub that exists only to
preserve backward compatibility with code that imports
`from arqux.handlers.cortex import ...` (pre-refactor style).

New code should import directly from the package submodules:
    from arqux.handlers.cortex.entries import add_entry, delete_entry
    from arqux.handlers.cortex.read_write import cortex_read, cortex_write
    from arqux.handlers.cortex.learning import learn, elevate
    from arqux.handlers.cortex.diagram import render_diagram
"""
from .cortex import *  # noqa: F401, F403
from .cortex import handler_schemas  # noqa: F401
