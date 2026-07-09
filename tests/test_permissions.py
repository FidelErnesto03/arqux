"""Tests for the permission system — governance handlers are universal.

v0.4.0 model:
    - GOVERNOR: full access to all handlers.
    - EXECUTOR: universal access except GOVERNOR_ONLY (init handlers).
    - AUDITOR: read-only + governance handlers (universal).
    - GOVERNOR_ONLY = {workspace.init, project.init}
    - HMAC_REQUIRED enforced for identity.record, evidence.record,
      blueprint.approve, blueprint.re_delegate.
"""

from __future__ import annotations

import os

import pytest

from arqux.constants import (
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)
from arqux.permissions import (
    GOVERNOR_ONLY,
    HMAC_REQUIRED,
    PermissionContext,
    PermissionDenied,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(role: str, agent_id: str = "test-agent") -> PermissionContext:
    """Create a PermissionContext with strict mode enabled."""
    os.environ["ARQUX_STRICT_ROLES"] = "1"
    return PermissionContext(agent_id=agent_id, role=role)


@pytest.fixture(autouse=True)
def _strict_mode():
    """Enable strict role checking for all tests."""
    os.environ["ARQUX_STRICT_ROLES"] = "1"
    yield
    os.environ.pop("ARQUX_STRICT_ROLES", None)
    os.environ.pop("ARQUX_STRICT_SECURITY", None)


# ---------------------------------------------------------------------------
# T-2.6: All roles can invoke governance handlers
# ---------------------------------------------------------------------------

class TestGovernanceHandlersUniversal:
    """Governance handlers are accessible by all roles."""

    GOVERNANCE_HANDLERS = [
        "cycle.create",
        "cycle.mature",
        "cycle.close",
        "task.create",
        "task.claim",
        "task.update",
        "task.complete",
        "task.fail",
        "task.read",
        "task.list",
        "blueprint.create",
        "blueprint.read",
        "blueprint.list",
        "blueprint.claim",
        "blueprint.update",
        "blueprint.complete",
        "blueprint.fail",
        "evidence.record",
        "evidence.list",
        "evidence.read",
        "cortex.read",
        "cortex.write",
        "cortex.verify",
        "cortex.learn",
        "session.context.set",
        "session.resume",
        "project.bind",
        "project.unbind",
        "protocol.adopt",
        "protocol.release",
        "identity.record",
        "skill.list",
        "workspace.status",
        "workspace.lessons",
        "project.status",
        "project.lessons",
    ]

    @pytest.mark.parametrize("handler", GOVERNANCE_HANDLERS)
    def test_governor_can_invoke(self, handler: str) -> None:
        ctx = _ctx(ROLE_GOVERNOR)
        ctx.check(handler)  # should not raise

    @pytest.mark.parametrize("handler", GOVERNANCE_HANDLERS)
    def test_executor_can_invoke(self, handler: str) -> None:
        ctx = _ctx(ROLE_EXECUTOR)
        ctx.check(handler)  # should not raise

    @pytest.mark.parametrize("handler", GOVERNANCE_HANDLERS)
    def test_auditor_can_invoke(self, handler: str) -> None:
        ctx = _ctx(ROLE_AUDITOR)
        ctx.check(handler)  # should not raise


# ---------------------------------------------------------------------------
# T-2.7: Init handlers are governor-only
# ---------------------------------------------------------------------------

class TestInitHandlersGovernorOnly:
    """workspace.init and project.init are restricted to governor."""

    @pytest.mark.parametrize("handler", ["workspace.init", "project.init"])
    def test_governor_can_init(self, handler: str) -> None:
        ctx = _ctx(ROLE_GOVERNOR)
        ctx.check(handler)  # should not raise

    @pytest.mark.parametrize("handler", ["workspace.init", "project.init"])
    def test_executor_cannot_init(self, handler: str) -> None:
        ctx = _ctx(ROLE_EXECUTOR)
        with pytest.raises(PermissionDenied, match="governor-only"):
            ctx.check(handler)

    @pytest.mark.parametrize("handler", ["workspace.init", "project.init"])
    def test_auditor_cannot_init(self, handler: str) -> None:
        ctx = _ctx(ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="governor-only"):
            ctx.check(handler)


# ---------------------------------------------------------------------------
# T-2.8: HMAC_REQUIRED enforced
# ---------------------------------------------------------------------------

class TestHmacRequired:
    """Handlers in HMAC_REQUIRED must have verified HMAC in strict security."""

    @pytest.mark.parametrize("handler", list(HMAC_REQUIRED))
    def test_unverified_raises_in_strict(self, handler: str) -> None:
        os.environ["ARQUX_STRICT_SECURITY"] = "1"
        ctx = _ctx(ROLE_GOVERNOR)
        ctx.verified = False
        with pytest.raises(PermissionDenied, match="HMAC verification required"):
            ctx.require_verified(handler)

    @pytest.mark.parametrize("handler", list(HMAC_REQUIRED))
    def test_verified_passes(self, handler: str) -> None:
        os.environ["ARQUX_STRICT_SECURITY"] = "1"
        ctx = _ctx(ROLE_GOVERNOR)
        ctx.verified = True
        ctx.require_verified(handler)  # should not raise


# ---------------------------------------------------------------------------
# T-2.9: Legacy mode backward compatibility
# ---------------------------------------------------------------------------

class TestLegacyMode:
    """Non-strict mode (default) allows governor full access without role check."""

    def test_governor_full_access_without_strict(self) -> None:
        os.environ.pop("ARQUX_STRICT_ROLES", None)
        ctx = PermissionContext(agent_id="legacy-agent", role=ROLE_GOVERNOR)
        # Should not raise even for GOVERNOR_ONLY handlers
        ctx.check("workspace.init")
        ctx.check("project.init")
        ctx.check("task.create")

    def test_strict_mode_enforces(self) -> None:
        os.environ["ARQUX_STRICT_ROLES"] = "1"
        ctx = PermissionContext(agent_id="strict-agent", role=ROLE_EXECUTOR)
        with pytest.raises(PermissionDenied):
            ctx.check("workspace.init")


# ---------------------------------------------------------------------------
# Additional: can() and deny() helpers
# ---------------------------------------------------------------------------

class TestCanHelper:
    """Test the non-raising can() variant."""

    def test_can_returns_true_for_allowed(self) -> None:
        ctx = _ctx(ROLE_EXECUTOR)
        assert ctx.can("task.create") is True

    def test_can_returns_false_for_denied(self) -> None:
        ctx = _ctx(ROLE_EXECUTOR)
        assert ctx.can("workspace.init") is False

    def test_can_returns_true_for_governor_init(self) -> None:
        ctx = _ctx(ROLE_GOVERNOR)
        assert ctx.can("workspace.init") is True


class TestDenyHelper:
    """Test the deny() helper constructs PermissionDenied."""

    def test_deny_constructs_exception(self) -> None:
        from arqux.permissions import deny
        exc = deny(ROLE_EXECUTOR, "workspace.init", "test reason")
        assert isinstance(exc, PermissionDenied)
        assert exc.role == ROLE_EXECUTOR
        assert exc.handler == "workspace.init"


# ---------------------------------------------------------------------------
# Additional: enforce_ctx()
# ---------------------------------------------------------------------------

class TestEnforceCtx:
    """Test enforce_ctx() helper."""

    def test_enforce_ctx_with_none_loads_from_env(self) -> None:
        from arqux.permissions import enforce_ctx
        os.environ["ARQUX_AGENT_ROLE"] = ROLE_GOVERNOR
        ctx = enforce_ctx(None, "task.create")
        assert ctx.role == ROLE_GOVERNOR

    def test_enforce_ctx_raises_on_bad_role(self) -> None:
        from arqux.permissions import enforce_ctx
        os.environ["ARQUX_STRICT_ROLES"] = "1"
        os.environ["ARQUX_AGENT_ROLE"] = ROLE_AUDITOR
        with pytest.raises(PermissionDenied):
            enforce_ctx(None, "workspace.init")
