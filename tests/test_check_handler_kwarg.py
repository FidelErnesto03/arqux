"""Regression: ctx.check/can must accept a call kwarg named 'handler'.

Issue 2026-10-01: ``ctx.check(name, **kwargs)`` collided when a handler has a
parameter literally named ``handler`` (e.g. ``issue.create``), because
``check``'s first parameter was also named ``handler`` — Python raised
``TypeError: got multiple values for argument 'handler'``.
"""

from __future__ import annotations

from arqux.constants import ROLE_AUDITOR, ROLE_EXECUTOR, ROLE_GOVERNOR
from arqux.permissions import PermissionContext


def test_check_accepts_handler_kwarg() -> None:
    ctx = PermissionContext(agent_id="g", role=ROLE_GOVERNOR)
    # Must not raise TypeError for the 'handler' call kwarg.
    ctx.check("issue.create", severity="low", desc="x", handler="alfred")


def test_can_accepts_handler_kwarg() -> None:
    ctx = PermissionContext(agent_id="g", role=ROLE_GOVERNOR)
    assert ctx.can("issue.create", severity="low", desc="x", handler="alfred") is True


def test_check_role_logic_intact() -> None:
    # Signature rename must not break role enforcement.
    PermissionContext(agent_id="e", role=ROLE_EXECUTOR).check(
        "issue.create", severity="low", desc="x", handler="alfred"
    )
    # Auditor is read-only: a mutating handler still denies.
    from arqux.permissions import PermissionDenied

    auditor = PermissionContext(agent_id="a", role=ROLE_AUDITOR)
    try:
        auditor.check("issue.create", severity="low", desc="x")
    except PermissionDenied:
        pass
    else:  # pragma: no cover
        raise AssertionError("auditor must be denied a mutating handler")
