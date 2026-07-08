"""Tests for the handler registry (baseline: 69 handlers)."""

from __future__ import annotations

from arqux.handlers import REGISTRY, handler_count, list_handlers


def test_handler_count_is_71() -> None:
    assert handler_count() == 71


def test_mutating_handler_count_is_51() -> None:
    session_only = {"protocol.pause", "protocol.resume"}
    utility = {
        "cortex.read", "cortex.write", "cortex.verify", "cortex.render",
        "cortex.render.diagram", "cortex.render.validate_file",
        "cortex.learn", "cortex.learn.elevate",
        "identity.record", "skill.import", "skill.convert", "skill.record",
        "skill.evolve", "skill.list", "blueprint.read", "blueprint.list",
        "setup.plantuml", "session.context.get",
    }
    excluded = session_only | utility
    mutating = [name for name in list_handlers() if name not in excluded]
    assert len(mutating) == 51


def test_handler_names_follow_module_convention() -> None:
    names = list_handlers()
    modules: set[str] = {
        "workspace", "project", "cycle", "task", "evidence", "protocol",
        "session", "cortex", "identity", "skill", "blueprint", "setup",
    }
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
    expected = {
        "blueprint": 18,
        "cortex": 14,
        "cycle": 4,
        "evidence": 3,
        "identity": 1,
        "project": 5,
        "protocol": 4,
        "session": 5,
        "setup": 1,
        "skill": 6,
        "task": 7,
        "workspace": 3,
    }
    counts: dict[str, int] = {}
    for name in list_handlers():
        module = name.split(".", 1)[0]
        counts[module] = counts.get(module, 0) + 1
    for module, count in expected.items():
        assert counts.get(module, 0) == count, (
            f"{module}: expected {count}, got {counts.get(module, 0)}"
        )
