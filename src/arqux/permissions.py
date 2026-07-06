"""Permission enforcement middleware.

Three roles with strict, handler-level enforcement:

    governor   — creates cycles/tasks, assigns, approves, closes.
    executor   — claims tasks, updates progress, completes, fails.
    auditor    — read-only, cannot mutate state.

Permission context is loaded from environment variables:
    ARQUX_AGENT_ID     — current agent identifier
    ARQUX_AGENT_ROLE   — current agent role (governor|executor|auditor)
    ARQUX_PROJECT      — currently bound project

If no role is set, the first agent to call `workspace.init` is implicitly
promoted to governor (one-time bootstrap, recorded in manifest).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .constants import (
    PERMISSION_DENIED,
    PRODUCT_NAME_UPPER,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)


class PermissionDenied(Exception):
    """Raised when a handler is called outside the agent's role."""

    def __init__(self, agent_id: str, role: str, handler: str, reason: str) -> None:
        super().__init__(
            f"agent={agent_id} role={role} handler={handler} reason={reason}"
        )
        self.agent_id = agent_id
        self.role = role
        self.handler = handler
        self.reason = reason


# Read-only handlers — allowed for auditor.
READ_ONLY_PREFIXES: tuple[str, ...] = (
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
    "cortex.read",
    "cortex.verify",
    "cortex.render",
    "cortex.learn",
    "cortex.learn.elevate",
    "skill.list",
    "blueprint.read",
    "blueprint.list",
    "identity.record",  # any agent can record lessons to their own identity
)

# Governor-only handlers — executor cannot call.
GOVERNOR_ONLY: tuple[str, ...] = (
    "workspace.init",
    "project.init",
    "project.bind",
    "project.unbind",
    "cycle.create",
    "cycle.close",
    "task.create",
    "protocol.adopt",
)

# Executor-allowed handlers (subset of full surface).
EXECUTOR_ALLOWED: tuple[str, ...] = (
    "task.claim",
    "task.update",
    "task.complete",
    "task.fail",
    "task.read",
    "task.list",
    "evidence.record",
    "evidence.list",
    "evidence.read",
    "protocol.release",  # self-release
    "identity.record",   # executor can record own lessons
    "blueprint.claim",
    "blueprint.update",
    "blueprint.complete",
    "blueprint.fail",
    "blueprint.read",
    "blueprint.list",
)


@dataclass
class PermissionContext:
    """The currently active agent's identity and role."""

    agent_id: str
    role: str
    project: str | None = None

    @classmethod
    def from_env(cls) -> "PermissionContext":
        prefix = f"{PRODUCT_NAME_UPPER}_"
        agent_id = os.environ.get(f"{prefix}AGENT_ID", "anonymous")
        role = os.environ.get(f"{prefix}AGENT_ROLE", ROLE_AUDITOR)
        project = os.environ.get(f"{prefix}PROJECT")
        return cls(agent_id=agent_id, role=role, project=project)

    def check(self, handler: str) -> None:
        """Raise PermissionDenied if the current role cannot call `handler`."""
        if self.role == ROLE_GOVERNOR:
            # Governor can do everything except execute tasks.
            if handler == "task.claim":
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    reason="governor_cannot_execute",
                )
            return

        if self.role == ROLE_EXECUTOR:
            if handler in EXECUTOR_ALLOWED:
                return
            raise PermissionDenied(
                self.agent_id, self.role, handler,
                reason="executor_role_not_allowed",
            )

        if self.role == ROLE_AUDITOR:
            # Auditor: only read-only handlers.
            for prefix in READ_ONLY_PREFIXES:
                if handler == prefix or handler.startswith(prefix + "."):
                    return
            raise PermissionDenied(
                self.agent_id, self.role, handler,
                reason="auditor_read_only",
            )

        # Unknown role — deny by default.
        raise PermissionDenied(
            self.agent_id, self.role, handler,
            reason="unknown_role",
        )

    def can(self, handler: str) -> bool:
        """Non-raising variant of `check`."""
        try:
            self.check(handler)
            return True
        except PermissionDenied:
            return False


def deny(role: str, handler: str, reason: str = "not_allowed") -> PermissionDenied:
    """Construct a PermissionDenied exception without raising it."""
    return PermissionDenied(
        agent_id="<unknown>", role=role, handler=handler, reason=reason,
    )


# --- Bootstrap: first agent becomes governor -------------------------------

def promote_first_governor(agent_id: str) -> PermissionContext:
    """Return a governor context for the bootstrap case.

    Called by `workspace.init` when no governor exists yet.
    """
    return PermissionContext(agent_id=agent_id, role=ROLE_GOVERNOR)
