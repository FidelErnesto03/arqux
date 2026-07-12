"""Handler registry.

Each handler module exposes a ``handler_schemas`` list of dicts with:
    name, fn, description, input_schema

The registry iterates all modules and registers them.
Adding a handler requires removing one (per the fixed-budget principle).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import cycle, evidence, project, protocol, session, task, workspace, cortex, skill, blueprint


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

for mod in (workspace, project, cycle, task, evidence, protocol, session, cortex, skill, blueprint):
    for info in mod.handler_schemas:
        _register(HandlerSpec(**info))


def list_handlers() -> list[str]:
    return sorted(REGISTRY.keys())


def handler_count() -> int:
    return len(REGISTRY)


__all__ = ["REGISTRY", "HandlerSpec", "list_handlers", "handler_count"]
