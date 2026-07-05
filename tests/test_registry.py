"""Tests for the handler registry."""

from __future__ import annotations

from arqux.handlers import REGISTRY, handler_count, list_handlers


def test_handler_count_is_30() -> None:
    """The full MCP surface: 26 governance handlers + 4 utility handlers
    (cortex.read, cortex.write, cortex.verify, cortex.render).

    The 26 governance includes 24 state-persisting + 2 session-only
    (protocol.pause, protocol.resume).
    """
    assert handler_count() == 30


def test_mutating_handler_count_is_24() -> None:
    """The conceptual budget: 24 handlers that mutate or read persisted state.
    Excludes session-only (pause/resume) and utility (cortex.*).
    """
    session_only = {"protocol.pause", "protocol.resume"}
    utility = {"cortex.read", "cortex.write", "cortex.verify", "cortex.render"}
    excluded = session_only | utility
    mutating = [name for name in list_handlers() if name not in excluded]
    assert len(mutating) == 24


def test_handler_names_follow_module_convention() -> None:
    names = list_handlers()
    modules = {"workspace", "project", "cycle", "task", "evidence", "protocol", "cortex"}
    for name in names:
        module = name.split(".", 1)[0]
        assert module in modules, f"unknown module for handler: {name}"


def test_each_handler_has_spec() -> None:
    for name, spec in REGISTRY.items():
        assert spec.name == name
        assert callable(spec.fn)
        assert isinstance(spec.description, str) and len(spec.description) > 0
        assert isinstance(spec.input_schema, dict)
        assert spec.input_schema.get("type") == "object"


def test_module_handler_counts() -> None:
    """Expected per-module distribution per §5.5 of the brief."""
    expected = {
        "workspace": 3,
        "project": 5,
        "cycle": 4,
        "task": 7,
        "evidence": 3,
        "protocol": 4,  # adopt + release + pause + resume
        "cortex": 4,    # read + write + verify + render
    }
    counts: dict[str, int] = {}
    for name in list_handlers():
        module = name.split(".", 1)[0]
        counts[module] = counts.get(module, 0) + 1
    for module, count in expected.items():
        assert counts.get(module, 0) == count, f"{module}: expected {count}, got {counts.get(module, 0)}"
