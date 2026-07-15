"""Handler discovery — handler.list(tier).

Returns the classified list of available handlers filtered by tier.
The agent calls this to discover its capabilities dynamically,
replacing hardcoded tables in AGENTS.md.
"""

from __future__ import annotations

from typing import Any


# --- TIER MAPPING -----------------------------------------------------------
# Handlers are classified by tier.
# FULL tier = all handlers in REGISTRY (computed lazily).

NANO_HANDLERS: set[str] = {
    "workspace.status",
    "session.bootstrap",
    "project.status",
    "blueprint.read",
    "blueprint.list",
    "cycle.current",
    "cortex.read",
    "handler.list",
}

LITE_EXTRA: set[str] = {
    "blueprint.create",
    "blueprint.task",
    "blueprint.complete",
    "blueprint.ac",
    "blueprint.approve",
    "blueprint.mature",
    "blueprint.ready",
    "blueprint.assign",
    "blueprint.claim",
    "task.create",
    "task.claim",
    "task.complete",
    "cycle.list",
    "evidence.record",
    "evidence.list",
    "cortex.entry.get",
    "session.context.set",
    "session.resume",
    "session.status",
}

LITE_HANDLERS: set[str] = NANO_HANDLERS | LITE_EXTRA

# Pre-computed: which handlers go in which tier (excluding FULL = all)
_TIER_SETS: dict[str, set[str]] = {
    "NANO": NANO_HANDLERS,
    "LITE": LITE_HANDLERS,
}


def list_handlers(tier: str, ctx: Any = None) -> dict[str, Any]:
    """Return handlers classified by module, filtered by tier.

    Args:
        tier: One of NANO, LITE, FULL.
        ctx: Optional permission context injected by the MCP server. The
            discovery operation is read-only; it is accepted for adapter
            compatibility and intentionally does not change classification.

    Returns:
        Dict with _total key and module-name keys, each containing
        count and list of {name, description}.
    """
    # Lazy import to avoid circular dependency at module level
    from . import REGISTRY  # noqa: PLC0415

    tier_upper = tier.upper()
    if tier_upper == "FULL":
        allowed: set[str] = set(REGISTRY.keys())
    elif tier_upper in _TIER_SETS:
        allowed = _TIER_SETS[tier_upper]
    else:
        raise ValueError(
            f"Unknown tier: {tier!r}. Valid tiers: NANO, LITE, FULL"
        )

    by_module: dict[str, dict[str, Any]] = {}
    for name, spec in sorted(REGISTRY.items()):
        if name not in allowed:
            continue
        module = name.split(".")[0]
        if module not in by_module:
            by_module[module] = {"count": 0, "handlers": []}
        by_module[module]["handlers"].append({
            "name": name,
            "description": spec.description,
        })
        by_module[module]["count"] += 1

    total = sum(m["count"] for m in by_module.values())
    result: dict[str, Any] = {"_total": total}
    result.update(by_module)
    return result


# Handler schema for registry registration
handler_schemas: list[dict[str, Any]] = [
    {
        "name": "handler.list",
        "fn": list_handlers,
        "description": (
            "Discover available handlers classified by module, "
            "filtered by tier (NANO|LITE|FULL). "
            "Replaces hardcoded handler tables in AGENTS.md "
            "(BLP-010 meta-handler)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "enum": ["NANO", "LITE", "FULL"],
                    "description": "Tier to filter handlers by.",
                },
            },
            "required": ["tier"],
        },
    },
]
