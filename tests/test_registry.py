"""Tests for the handler registry.

CYCLE-03 BLPs added:
- BLP-003: cortex.ref, cortex.format (+2)
- BLP-006: context.detect, context.full, identity.get (+3, new 'context' module)
- BLP-007: blueprint.synthesize (+1)
- BLP-008: session.bootstrap (+1)
- BLP-010: cortex.patch, cortex.migrate, task.run, skill.install, session.handoff, blueprint.execute (+6)
Total: 86 (was 73).
"""

from __future__ import annotations

from arqux.handlers import REGISTRY, handler_count, list_handlers


def test_handler_count_is_96() -> None:
    """Total handler count is 96 (BLP-003 added blueprint.frontmatter.update)."""
    assert handler_count() == 96


def test_handler_list_accepts_mcp_context() -> None:
    """The MCP wrapper injects ctx into every registered handler."""
    result = REGISTRY["handler.list"].fn("NANO", ctx=object())

    assert result["_total"] == 8
    assert "handler" in result
    assert any(item["name"] == "handler.list" for item in result["handler"]["handlers"])


def test_mutating_handler_count() -> None:
    session_only = {"protocol.pause", "protocol.resume"}
    utility = {
        "cortex.read", "cortex.write", "cortex.verify", "cortex.render",
        "cortex.render.diagram", "cortex.render.validate_file",
        "cortex.file.validate",
        "cortex.learn", "cortex.learn.elevate",
        "cortex.ref", "cortex.format",
        "cortex.migrate",  # transform handler (utility)
        "identity.record", "identity.get",
        "skill.import", "skill.convert", "skill.record",
        "skill.evolve", "skill.list", "blueprint.read", "blueprint.list",
        "setup.plantuml", "session.context.get",
        "context.detect", "context.full",
        "session.bootstrap", "session.status", "session.resume",
    }
    excluded = session_only | utility
    mutating = [name for name in list_handlers() if name not in excluded]
    assert len(mutating) > 50


def test_handler_names_follow_module_convention() -> None:
    names = list_handlers()
    modules: set[str] = {
        "workspace", "project", "cycle", "task", "evidence", "issue", "protocol",
        "session", "cortex", "identity", "skill", "blueprint", "setup",
        "context", "handler", "sync",
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
        "blueprint": 16,  # +1: blueprint.frontmatter.update (BLP-003)
        "context": 2,
        "cortex": 21,  # +1: cortex.gc (BLP-002)
        "cycle": 5,  # simplified lifecycle (BLP-003)
        "evidence": 3,
        "identity": 3,  # +2: identity.get, identity.switch (BLP-011)
        "handler": 2,  # +1: handler.how_to (BLP-012)
        "issue": 4,  # T-027: issue.create/update/list/read
        "project": 5,
        "protocol": 5,
        "session": 8,  # +3: bootstrap, handoff, pulse.compact
        "setup": 1,
        "skill": 8,  # +2: skill.install, skill.get (BLP-012)
        "task": 8,  # +1: task.run
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
