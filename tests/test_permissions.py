"""Tests for permission enforcement."""

from __future__ import annotations

import pytest

from arqux.constants import (
    PERMISSION_DENIED,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)
from arqux.permissions import PermissionContext, PermissionDenied


def test_governor_can_call_workspace_init() -> None:
    ctx = PermissionContext(agent_id="g", role=ROLE_GOVERNOR)
    ctx.check("workspace.init")  # should not raise


def test_governor_cannot_call_task_claim() -> None:
    ctx = PermissionContext(agent_id="g", role=ROLE_GOVERNOR)
    with pytest.raises(PermissionDenied) as exc_info:
        ctx.check("task.claim")
    assert exc_info.value.reason == "governor_cannot_execute"


def test_executor_can_call_task_claim() -> None:
    ctx = PermissionContext(agent_id="e", role=ROLE_EXECUTOR)
    ctx.check("task.claim")  # should not raise


def test_executor_cannot_call_task_create() -> None:
    ctx = PermissionContext(agent_id="e", role=ROLE_EXECUTOR)
    with pytest.raises(PermissionDenied) as exc_info:
        ctx.check("task.create")
    assert exc_info.value.reason == "executor_role_not_allowed"


def test_executor_cannot_call_cycle_create() -> None:
    ctx = PermissionContext(agent_id="e", role=ROLE_EXECUTOR)
    with pytest.raises(PermissionDenied) as exc_info:
        ctx.check("cycle.create")
    assert exc_info.value.reason == "executor_role_not_allowed"


def test_auditor_can_call_read_only_handlers() -> None:
    ctx = PermissionContext(agent_id="a", role=ROLE_AUDITOR)
    for handler in [
        "workspace.status",
        "workspace.lessons",
        "project.status",
        "project.lessons",
        "cycle.list",
        "cycle.current",
        "task.read",
        "task.list",
        "evidence.list",
        "evidence.read",
    ]:
        ctx.check(handler)  # should not raise


def test_auditor_cannot_call_mutating_handlers() -> None:
    ctx = PermissionContext(agent_id="a", role=ROLE_AUDITOR)
    for handler in [
        "workspace.init",
        "project.init",
        "cycle.create",
        "task.create",
        "task.claim",
        "task.update",
        "task.complete",
        "task.fail",
        "evidence.record",
        "protocol.adopt",
    ]:
        with pytest.raises(PermissionDenied) as exc_info:
            ctx.check(handler)
        assert exc_info.value.reason == "auditor_read_only"


def test_unknown_role_is_denied() -> None:
    ctx = PermissionContext(agent_id="x", role="superuser")
    with pytest.raises(PermissionDenied) as exc_info:
        ctx.check("workspace.init")
    assert exc_info.value.reason == "unknown_role"


def test_can_returns_bool() -> None:
    gov = PermissionContext(agent_id="g", role=ROLE_GOVERNOR)
    assert gov.can("workspace.init") is True
    assert gov.can("task.claim") is False
