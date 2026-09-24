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
    "blueprint.ready",
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

DEFAULT_HANDLER_LIMIT = 50


def list_handlers(
    tier: str,
    ctx: Any = None,
    limit: int | None = None,
    offset: int = 0,
    compact: bool = False,
) -> dict[str, Any]:
    """Return handlers classified by module, filtered by tier.

    Args:
        tier: One of NANO, LITE, FULL.
        ctx: Optional permission context injected by the MCP server. The
            discovery operation is read-only; it is accepted for adapter
            compatibility and intentionally does not change classification.
        limit: Max handlers per page (default 50). ``_next_offset`` pages
            through the full listing.
        offset: Handlers to skip before the page.
        compact: When True, return only handler names (no descriptions).

    Returns:
        Dict with _total, _returned, _offset, _next_offset keys and
        module-name keys, each containing count and list of
        {name, description} (or names only when compact=True).
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

    try:
        limit_i = DEFAULT_HANDLER_LIMIT if limit is None else int(limit)
        offset_i = int(offset)
    except (TypeError, ValueError):
        raise ValueError("limit and offset must be integers") from None
    if limit_i < 1 or offset_i < 0:
        raise ValueError("limit must be >= 1 and offset must be >= 0")

    names = sorted(name for name in REGISTRY if name in allowed)
    total = len(names)
    page = names[offset_i : offset_i + limit_i]
    next_offset = offset_i + limit_i if offset_i + limit_i < total else None

    by_module: dict[str, dict[str, Any]] = {}
    for name in page:
        module = name.split(".")[0]
        if module not in by_module:
            by_module[module] = {"count": 0, "handlers": []}
        if compact:
            by_module[module]["handlers"].append(name)
        else:
            by_module[module]["handlers"].append({
                "name": name,
                "description": REGISTRY[name].description,
            })
        by_module[module]["count"] += 1

    result: dict[str, Any] = {
        "_total": total,
        "_returned": len(page),
        "_offset": offset_i,
        "_next_offset": next_offset,
    }
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
            "Paginated: limit (default 50) + offset; fields _total, "
            "_returned, _offset, _next_offset report the pagination "
            "state. compact=true returns names only. "
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
                "limit": {"type": "integer", "default": 50, "description": "Max handlers per page."},
                "offset": {"type": "integer", "default": 0, "description": "Handlers to skip before the page."},
                "compact": {"type": "boolean", "default": False, "description": "Return handler names only (no descriptions)."},
            },
            "required": ["tier"],
        },
    },
]
