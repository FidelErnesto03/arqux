"""Backward-compat shim — re-exports from handlers/blueprint/ package.

P1-L PATCH (2026-07-12): This file is a 1-line stub that exists only to
preserve backward compatibility with code that imports
`from arqux.handlers.blueprint import ...` (pre-refactor style).

New code should import directly from the package submodules:
    from arqux.handlers.blueprint.manage import create, update
    from arqux.handlers.blueprint.lifecycle import ready, claim
    from arqux.handlers.blueprint.review import complete, fail, cancel, ac_blueprint
    from arqux.handlers.blueprint._read import read, list_blueprints
"""
from .blueprint import *  # noqa: F401, F403
from .blueprint import handler_schemas  # noqa: F401
