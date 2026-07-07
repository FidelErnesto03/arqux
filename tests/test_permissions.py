"""Tests for permission system — all roles have full access.

Arqux trusts agents to follow their identity's behavioral contract.
Roles guide WHAT an agent should do, not what it CAN do.
"""

from __future__ import annotations

from arqux.constants import (
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)
from arqux.permissions import PermissionContext


def test_all_roles_can_call_any_handler() -> None:
    """Every role can access every handler — shared mind for all."""
    handlers = [
        "workspace.init",
        "workspace.status",
        "project.init",
        "cycle.create",
        "task.create",
        "task.claim",
        "task.complete",
        "evidence.record",
        "blueprint.create",
        "blueprint.approve",
        "blueprint.task",
        "blueprint.ac",
        "cortex.write",
        "cortex.learn",
        "identity.record",
        "protocol.adopt",
    ]
    for role in [ROLE_GOVERNOR, ROLE_EXECUTOR, ROLE_AUDITOR]:
        ctx = PermissionContext(agent_id=role, role=role)
        for handler in handlers:
            ctx.check(handler)  # should never raise


def test_can_always_returns_true() -> None:
    """All handlers are allowed for all roles."""
    for role in [ROLE_GOVERNOR, ROLE_EXECUTOR, ROLE_AUDITOR]:
        ctx = PermissionContext(agent_id=role, role=role)
        assert ctx.can("task.claim") is True
        assert ctx.can("workspace.init") is True
        assert ctx.can("blueprint.approve") is True
