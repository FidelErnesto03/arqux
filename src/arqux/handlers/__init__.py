"""Handler registry.

Each handler module exposes a ``handler_schemas`` list of dicts with:
    name, fn, description, input_schema

The registry iterates all modules and registers them.

Adding a handler requires removing one (per the fixed-budget principle).

P1-L PATCH (2026-07-12): Documented the stub shims (handlers/blueprint.py
and handlers/cortex.py) as backward-compat re-exports of the package
modules (handlers/blueprint/ and handlers/cortex/).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Note: handlers/blueprint.py and handlers/cortex.py are 1-line stub shims
# that re-export from handlers/blueprint/ and handlers/cortex/ packages.
# They exist for backward compatibility with code that imports
# `from arqux.handlers.blueprint import ...` (pre-refactor style).
# New code should import directly from the package:
#   from arqux.handlers.blueprint.manage import create
#   from arqux.handlers.cortex.entries import add_entry
from . import (
    blueprint,
    cortex,
    cycle,
    evidence,
    handler,
    project,
    protocol,
    session,
    skill,
    sync,
    task,
    workspace,
)
from . import context as context_pkg
from . import identity as identity_pkg


@dataclass(frozen=True)
class HandlerSpec:
    name: str
    fn: Callable[..., Any]
    description: str
    input_schema: dict[str, Any]


REGISTRY: dict[str, HandlerSpec] = {}


def _register(spec: HandlerSpec) -> None:
    if spec.name in REGISTRY:
        raise RuntimeError(f"duplicate handler: {spec.name}")
    REGISTRY[spec.name] = spec


# --- Register all handlers from each module ---------------------------------

for mod in (workspace, project, cycle, task, evidence, protocol, session, cortex, skill, blueprint, sync, context_pkg, identity_pkg, handler):
    for info in mod.handler_schemas:
        _register(HandlerSpec(**info))


def list_handlers() -> list[str]:
    return sorted(REGISTRY.keys())


def handler_count() -> int:
    return len(REGISTRY)


__all__ = ["REGISTRY", "HandlerSpec", "list_handlers", "handler_count"]
