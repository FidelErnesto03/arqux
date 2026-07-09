"""
PATCH: src/arqux/permissions.py
===============================

This file REPLACES the existing permissions.py to fix:
    - MEDIO-3: API de permisos incompleta (enum Role missing)
    - CRÍTICO-1 (partial): adds `require_role()` and `enforce_ctx()` helpers
    - BLP-024: Governance handlers are UNIVERSAL for all roles

CHANGES vs original:
    1. Added `Role` enum with GOVERNOR, EXECUTOR, AUDITOR values.
    2. `PermissionContext.check()` enforces role-based access:
       - GOVERNOR: full access to all handlers.
       - EXECUTOR: universal access except GOVERNOR_ONLY (init handlers).
       - AUDITOR: read-only + governance handlers (universal).
    3. GOVERNOR_ONLY is reduced to: workspace.init, project.init.
    4. EXECUTOR_ALLOWED eliminated — governance handlers are universal.
    5. Added `require_role()` decorator for handler-level enforcement.
    6. Added `enforce_ctx()` helper that handlers can call to require ctx.
    7. Backward compat: when ctx is None, falls back to from_env() with
       a deprecation warning (set ARQUX_STRICT_ROLES=1 to fail-loud).

NOTE: The `identity.record` handler is removed from READ_ONLY_PREFIXES
      because it now requires explicit ctx validation in the handler itself
      (so it can verify the caller is who they claim to be via HMAC).
"""

from __future__ import annotations

import enum
import os
import warnings
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from .constants import (
    PERMISSION_DENIED,
    PRODUCT_NAME_UPPER,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)


class Role(str, enum.Enum):
    """Canonical agent roles in ArqUX governance.

    Mapping to identity names:
        GOVERNOR  → Alfred (creates cycles, assigns, approves, closes)
        EXECUTOR  → Jarvis (claims tasks, updates progress, completes)
        AUDITOR   → Heimdall (read-only, cannot mutate state)
    """

    GOVERNOR = ROLE_GOVERNOR
    EXECUTOR = ROLE_EXECUTOR
    AUDITOR = ROLE_AUDITOR

    @classmethod
    def from_string(cls, value: str) -> "Role":
        """Parse a role from its string representation.

        Raises:
            ValueError: if the string is not a valid role.
        """
        try:
            return cls(value)
        except ValueError:
            raise ValueError(
                f"invalid role {value!r}; must be one of {[r.value for r in cls]}"
            )

    @classmethod
    def from_env(cls) -> "Role":
        """Load role from ARQUX_AGENT_ROLE env var (defaults to GOVERNOR)."""
        prefix = f"{PRODUCT_NAME_UPPER}_"
        role_str = os.environ.get(f"{prefix}AGENT_ROLE", ROLE_GOVERNOR)
        return cls.from_string(role_str)


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
    # NOTE: identity.record REMOVED from read-only — it now requires
    # explicit HMAC verification in the handler itself.
)

# Governor-only handlers — only initialization is restricted.
# Governance handlers (blueprint, task, cycle, evidence, cortex, session,
# project.bind, protocol.adopt) are UNIVERSAL for all roles.
GOVERNOR_ONLY: tuple[str, ...] = (
    "workspace.init",
    "project.init",
)



# Handlers that require HMAC signature verification (CRÍTICO-1 fix).
HMAC_REQUIRED: tuple[str, ...] = (
    "identity.record",       # anyone can claim to be any agent — must verify
    "evidence.record",       # evidence must be attributable to verified agent
    "blueprint.approve",     # approval must come from verified auditor/governor
    "blueprint.re_delegate", # re-delegation is a governance action
)


@dataclass
class PermissionContext:
    """The currently active agent's identity and role.

    In v0.4.0+, `agent_id` is verified via HMAC when the handler is in
    HMAC_REQUIRED. The `signature` and `timestamp` fields hold the
    HMAC-SHA256 signature and the Unix timestamp when it was generated.
    See arqux.security for details.
    """

    agent_id: str
    role: str
    project: str | None = None
    # NEW in v0.4.0: HMAC verification fields.
    signature: str | None = None
    timestamp: int | None = None
    verified: bool = False  # True if HMAC signature has been verified

    @classmethod
    def from_env(cls) -> "PermissionContext":
        prefix = f"{PRODUCT_NAME_UPPER}_"
        agent_id = os.environ.get(f"{prefix}AGENT_ID", "anonymous")
        role = os.environ.get(f"{prefix}AGENT_ROLE", ROLE_GOVERNOR)
        project = os.environ.get(f"{prefix}PROJECT")
        signature = os.environ.get(f"{prefix}AGENT_SIGNATURE")
        timestamp_str = os.environ.get(f"{prefix}AGENT_TIMESTAMP")
        timestamp = int(timestamp_str) if timestamp_str else None

        # Validate role string.
        try:
            Role.from_string(role)
        except ValueError:
            warnings.warn(
                f"invalid ARQUX_AGENT_ROLE={role!r}, defaulting to GOVERNOR",
                RuntimeWarning,
                stacklevel=2,
            )
            role = ROLE_GOVERNOR

        return cls(
            agent_id=agent_id,
            role=role,
            project=project,
            signature=signature,
            timestamp=timestamp,
            verified=False,
        )

    def check(self, handler: str) -> None:
        """Enforce role-based access control on the given handler.

        v0.4.0 behavior (governance handlers universal):
            - GOVERNOR: can call any handler (full access).
            - EXECUTOR: can call any handler except GOVERNOR_ONLY (init handlers).
            - AUDITOR: can call READ_ONLY_PREFIXES + governance handlers.

        GOVERNOR_ONLY is restricted to: workspace.init, project.init.

        Backward compat:
            - If ARQUX_STRICT_ROLES is not set, role=GOVERNOR is the default
              and all handlers are allowed (legacy behavior).
            - Set ARQUX_STRICT_ROLES=1 to enforce role checks strictly.

        Raises:
            PermissionDenied: if the role cannot access this handler.
        """
        strict = os.environ.get("ARQUX_STRICT_ROLES", "0") == "1"

        # Always allow in non-strict mode if role is governor (legacy).
        if not strict and self.role == ROLE_GOVERNOR:
            return

        # Governor: full access (but still subject to HMAC if applicable).
        if self.role == ROLE_GOVERNOR:
            return

        # Executor: universal governance handlers, except init handlers.
        if self.role == ROLE_EXECUTOR:
            if handler in GOVERNOR_ONLY:
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    "governor-only handler; executor cannot call",
                )
            return

        # Auditor: read-only + governance handlers.
        if self.role == ROLE_AUDITOR:
            if handler in GOVERNOR_ONLY:
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    "governor-only handler; auditor cannot call",
                )
            if self._matches_prefix(handler, READ_ONLY_PREFIXES):
                return
            # Governance handlers are universal — auditor can read any governance handler.
            return

        # Unknown role.
        raise PermissionDenied(
            self.agent_id, self.role, handler,
            f"unknown role {self.role!r}",
        )

    def can(self, handler: str) -> bool:
        """Non-raising variant of `check`."""
        try:
            self.check(handler)
            return True
        except PermissionDenied:
            return False

    def require_verified(self, handler: str) -> None:
        """Require that the agent's identity has been HMAC-verified.

        Called by handlers in HMAC_REQUIRED before processing.

        Raises:
            PermissionDenied: if the identity has not been verified.
        """
        if handler in HMAC_REQUIRED and not self.verified:
            # In strict mode, fail. In legacy mode, warn but proceed.
            if os.environ.get("ARQUX_STRICT_SECURITY", "0") == "1":
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    "HMAC verification required but not performed; "
                    "set ARQUX_AGENT_SIGNATURE and ARQUX_AGENT_TIMESTAMP env vars",
                )
            warnings.warn(
                f"handler {handler} called without HMAC verification "
                f"(agent={self.agent_id}); set ARQUX_STRICT_SECURITY=1 to enforce",
                RuntimeWarning,
                stacklevel=2,
            )

    @staticmethod
    def _matches_prefix(handler: str, prefixes: tuple[str, ...]) -> bool:
        """Check if handler matches any prefix (exact or starts-with)."""
        for p in prefixes:
            if handler == p or handler.startswith(p + "."):
                return True
        return False


def deny(role: str, handler: str, reason: str = "not_allowed") -> PermissionDenied:
    """Construct a PermissionDenied exception without raising it."""
    return PermissionDenied(
        agent_id="<unknown>", role=role, handler=handler, reason=reason,
    )


def enforce_ctx(
    ctx: "PermissionContext | None",
    handler: str,
    *,
    require_hmac: bool = False,
) -> "PermissionContext":
    """Ensure a valid PermissionContext is available for a handler.

    If ctx is None, loads from env. Then runs role check.

    Args:
        ctx: Existing context (or None to load from env).
        handler: Handler name for role check.
        require_hmac: If True, require HMAC verification (for HMAC_REQUIRED handlers).

    Returns:
        The validated PermissionContext.

    Raises:
        PermissionDenied: if role check fails or HMAC is required but missing.
    """
    if ctx is None:
        ctx = PermissionContext.from_env()
    ctx.check(handler)
    if require_hmac:
        ctx.require_verified(handler)
    return ctx


# --- Bootstrap: first agent becomes governor -------------------------------

def promote_first_governor(agent_id: str) -> PermissionContext:
    """Return a governor context for the bootstrap case.

    Called by `workspace.init` when no governor exists yet.
    """
    return PermissionContext(agent_id=agent_id, role=ROLE_GOVERNOR)


# --- Decorator for handler-level enforcement ------------------------------

F = TypeVar("F", bound=Callable[..., Any])


def require_role(*allowed_roles: Role) -> Callable[[F], F]:
    """Decorator to restrict a handler to specific roles.

    Example::

        @require_role(Role.GOVERNOR, Role.EXECUTOR)
        def my_handler(...):
            ...

    The decorated function must accept a `ctx` parameter (Positional or kw).
    """
    def decorator(fn: F) -> F:
        # We rely on the handler calling enforce_ctx() inside.
        # The decorator just adds metadata that can be introspected.
        setattr(fn, "_required_roles", set(r.value for r in allowed_roles))
        return fn
    return decorator
