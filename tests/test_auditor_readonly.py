"""Tests for auditor read-only enforcement (P0-B).

Validates that AUDITOR role cannot call mutating handlers.
"""

from __future__ import annotations

import os

import pytest

from arqux.constants import ROLE_AUDITOR, ROLE_EXECUTOR, ROLE_GOVERNOR
from arqux.permissions import MUTATING_HANDLERS, PermissionContext, PermissionDenied


@pytest.fixture(autouse=True)
def _strict_mode():
    """Enable strict role checking for all tests."""
    os.environ["ARQUX_STRICT_ROLES"] = "1"
    yield
    os.environ.pop("ARQUX_STRICT_ROLES", None)
    os.environ.pop("ARQUX_STRICT_SECURITY", None)


class TestMutatingHandlersSet:
    """P0-B: MUTATING_HANDLERS frozenset must be defined and non-empty."""

    def test_mutating_handlers_defined(self) -> None:
        assert MUTATING_HANDLERS, "MUTATING_HANDLERS is empty"
        assert isinstance(MUTATING_HANDLERS, frozenset)

    def test_mutating_handlers_includes_critical(self) -> None:
        """Critical mutating handlers must be in the set."""
        expected = {
            "blueprint.cancel", "blueprint.fail", "blueprint.update",
            "blueprint.complete", "blueprint.approve",
            "task.fail", "task.create", "task.update", "task.complete",
            "cortex.entry.delete", "cortex.entry.update", "cortex.write",
            "cortex.entry.add", "cortex.entry.move",
            "protocol.adopt", "protocol.release",
            "evidence.record",
            "session.context.set", "session.close",
            "project.bind", "project.unbind",
            "identity.record",
            "cycle.create", "cycle.close", "cycle.mature",
        }
        missing = expected - MUTATING_HANDLERS
        assert not missing, f"Missing mutating handlers: {missing}"


class TestAuditorCannotMutate:
    """P0-B: Auditor must not be able to call mutating handlers."""

    @pytest.mark.parametrize("handler", sorted(MUTATING_HANDLERS))
    def test_auditor_cannot_mutate(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR, verified=True)
        with pytest.raises(PermissionDenied, match="mutating|governor-only"):
            ctx.check(handler)

    def test_auditor_cannot_cancel_blueprint(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied):
            ctx.check("blueprint.cancel")

    def test_auditor_cannot_delete_cortex_entry(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied):
            ctx.check("cortex.entry.delete")

    def test_auditor_cannot_fail_task(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied):
            ctx.check("task.fail")

    def test_auditor_cannot_adopt_protocol(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied):
            ctx.check("protocol.adopt")


class TestAuditorCanRead:
    """Auditor must retain access to read-only handlers."""

    @pytest.mark.parametrize("handler", [
        "blueprint.read", "blueprint.list",
        "task.read", "task.list",
        "evidence.list", "evidence.read",
        "cortex.read", "cortex.verify",
        "workspace.status", "workspace.lessons",
        "project.status", "project.lessons",
        "cycle.list", "cycle.current",
        "skill.list",
    ])
    def test_auditor_can_read(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check(handler)  # should not raise


class TestExecutorAndGovernor:
    """Sanity: executor and governor can mutate (with HMAC for HMAC_REQUIRED)."""

    @pytest.mark.parametrize("handler", ["blueprint.update", "task.create", "cortex.write"])
    def test_executor_can_mutate(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR, verified=True)
        ctx.check(handler)  # should not raise

    @pytest.mark.parametrize("handler", ["blueprint.cancel", "task.fail", "cortex.entry.delete"])
    def test_governor_can_mutate(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="alfred", role=ROLE_GOVERNOR, verified=True)
        ctx.check(handler)  # should not raise

    def test_executor_still_cannot_init(self) -> None:
        ctx = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR)
        with pytest.raises(PermissionDenied, match="governor-only"):
            ctx.check("workspace.init")
