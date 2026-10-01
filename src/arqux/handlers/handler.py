"""Handler discovery — handler.list(tier) + handler.how_to(intent).

Returns the classified list of available handlers filtered by tier.
The agent calls this to discover its capabilities dynamically,
replacing hardcoded tables in AGENTS.md.

BLP-012 adds ``handler.how_to``: intent-based usage guides served from
the curated corpus packaged in ``arqux/guides.cortex`` (single source —
versioned with the wheel, never duplicated in the workspace).
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


# ---------------------------------------------------------------------------
# handler.how_to (BLP-012) — intent-based usage guides
# ---------------------------------------------------------------------------

_GUIDES_FILENAME = "guides.cortex"


def _load_guides() -> list[dict[str, Any]]:
    """Load the curated GDE entries from the packaged corpus (read-only)."""
    from arqux.constants import PACKAGE_ROOT

    guides_path = PACKAGE_ROOT / _GUIDES_FILENAME
    if not guides_path.is_file():
        return []

    from arqux.handlers.cortex import handler_schemas as cortex_schemas

    entry_list = next(
        h for h in cortex_schemas if h["name"] == "cortex.entry.list"
    )["fn"]
    out = entry_list(str(guides_path), section="$1")
    fields = out.fields if hasattr(out, "fields") else {}
    entries = fields.get("entries") or []
    return [
        {"topic": e["name"], **(e.get("value") or {})}
        for e in entries
        if e.get("sigil") == "GDE"
    ]


def _match_guide(guides: list[dict[str, Any]], intent: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Match intent: exact alias > longest substring. Returns (guide, candidates).

    Exact matching over ALL terms runs first per guide, so a long term
    (e.g. the topic name) never shadows an exact alias match.
    """
    needle = intent.casefold().strip()
    exact: list[dict[str, Any]] = []
    partial: list[tuple[int, dict[str, Any]]] = []
    for guide in guides:
        terms = [guide.get("name", ""), guide.get("topic", "")]
        terms += [a.strip() for a in str(guide.get("aliases", "")).split(",") if a.strip()]
        terms = [t for t in terms if t]
        if any(needle == term.casefold() for term in terms):
            exact.append(guide)
            continue
        score = max(
            [len(term) for term in terms
             if term.casefold() in needle or needle in term.casefold()],
            default=0,
        )
        if score:
            partial.append((score, guide))
    if exact:
        return exact[0], exact[1:]
    partial.sort(key=lambda t: t[0], reverse=True)
    if len(partial) == 1:
        return partial[0][1], []
    if partial and partial[0][0] > partial[1][0]:
        return partial[0][1], []
    return None, [g for _score, g in partial]


def how_to(
    intent: str | None = None,
    *,
    content: str | None = None,
    path: str | None = None,
    ctx: Any = None,
) -> Any:
    """Return the curated usage guide for an intent (BLP-012, read-only).

    Matching: exact alias first, then longest substring; ambiguity lists
    candidates (never guesses). No-match returns the available topics
    plus references to ``handler.list`` and ``skill.get``.

    ``content`` accepts a CORTEX entry string with key ``intent``
    (BLP-010 meta-handler pattern — parsed value overrides the param).
    """
    from ..cortex_out import CortexOUT

    if content:
        from ..cortex.parse_content import parse_content_entry
        parsed = parse_content_entry(content)
        if parsed:
            intent = parsed.get("intent", intent)

    if not intent:
        return CortexOUT.error("intent is required", code="INVALID_ARGS")

    guides = _load_guides()
    if not guides:
        return CortexOUT.error(
            "guides corpus not found in package (guides.cortex missing)",
            code="CORPUS_UNAVAILABLE",
            hint="Reinstall the package; guides.cortex travels with the wheel.",
        )

    guide, candidates = _match_guide(guides, intent)
    topics = [g.get("topic") for g in guides]

    if guide is None:
        return CortexOUT.error(
            f"no guide found for intent={intent!r}",
            code="GUIDE_NOT_FOUND" if not candidates else "GUIDE_AMBIGUOUS",
            available_topics=topics,
            candidates=[c.get("topic") for c in candidates] or None,
            hint="Use handler.list(tier=...) for capability discovery or "
                 "skill.get(<name>) to read a full skill.",
        )

    return CortexOUT.work(
        f"handler.how_to ok topic={guide.get('topic')}",
        topic=guide.get("topic"),
        guide=guide.get("steps", ""),
        steps=guide.get("steps", ""),
        handlers_involved=guide.get("handlers", ""),
        example=guide.get("example", ""),
        candidates=[c.get("topic") for c in candidates] or None,
    )


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
    {
        "name": "handler.how_to",
        "fn": how_to,
        "description": (
            "Usage guide by intent (BLP-012): curated how-to from the "
            "packaged guides.cortex corpus — exact handler sequence with "
            "example. No-match returns available topics + hints to "
            "handler.list / skill.get. Read-only; accepts content CORTEX "
            "with key intent (BLP-010)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "What you want to do (e.g. 'cambiar de identidad', 'crear un blueprint').",
                },
                "content": {"type": "string", "description": "CORTEX content with key intent (BLP-010)."},
                "path": {"type": "string"},
            },
            "required": ["intent"],
        },
    },
]
