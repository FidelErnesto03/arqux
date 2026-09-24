"""Permissions module — role-based access control with HMAC verification.

v0.4.3 model (patched, T-020 reconciled):
    - GOVERNOR: full access to all handlers.
    - EXECUTOR: universal access except GOVERNOR_ONLY (init handlers).
    - AUDITOR: read-only — cannot mutate state. The model is a DENYLIST:
      auditor may call any handler except GOVERNOR_ONLY, MUTATING_HANDLERS,
      and CONDITIONAL_MUTATING invocations that actually mutate.
    - GOVERNOR_ONLY = {workspace.init, project.init}
    - MUTATING_HANDLERS: frozenset of handlers that mutate state/files
      unconditionally (or by default) — auditor is denied.
    - CONDITIONAL_MUTATING: dict of handler → param flag(s) gating the
      mutation. Auditor is denied only when the invocation is actually
      mutating (all listed flags truthy AND ``dry_run`` falsy); dry-run
      previews and read modes stay allowed.
    - HMAC_REQUIRED = {identity.record, evidence.record, blueprint.re_delegate}

Patches applied:
    - P0-B (0.4.3): AUDITOR can no longer call mutating handlers
      (was: fallthrough allowed all).
    - P1-S (0.4.3): docstring updated to reflect that identity.record
      requires HMAC.
    - T-019: destructive cortex maintenance handlers added to
      MUTATING_HANDLERS.
    - T-020: registry-vs-denylist reconcile — session/bootstrap/handoff/
      pulse.compact, blueprint.execute/synthesize, cycle.synthesize,
      task.run, protocol.onboard, skill.install, sync.run/reconcile and
      setup.plantuml added to MUTATING_HANDLERS; handlers with a true
      dry-run/apply/read gate moved to CONDITIONAL_MUTATING
      (cortex.learn.elevate, cortex.gc, cortex.patch, cortex.migrate,
      cortex.file.validate, skill.evolve, skill.edit); READ_ONLY_PREFIXES
      deleted (dead code — check() never consulted it; the auditor model
      is a denylist, not an allowlist).
    - T-020 audit (C-1): session.resume removed from MUTATING_HANDLERS —
      pure read of brain PULSE + SES parse, zero writes.

Environment variables:
    ARQUX_STRICT_ROLES=1     — enforce role checks (default: legacy governor-only bypass).
    ARQUX_STRICT_SECURITY=1  — enforce HMAC verification for HMAC_REQUIRED handlers.
"""

from __future__ import annotations

import enum
import logging
import os
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

from .constants import (
    ARQUX_DIR,
    PRODUCT_NAME_UPPER,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)
from .identity import IdentityManager

# --- Identity name extraction helper (BLP-008 GOV-001 P2.2) ---


def _extract_identity_name(payload: str) -> str | None:
    """Extract the IDN name from a CORTEX identity artifact payload."""
    import re
    m = re.search(r'IDN:\w+\{[^}]*?name[=:]\s*"([^"]+)"', payload)
    if m:
        return m.group(1)
    m = re.search(r'IDN:\w+\{[^}]*?name[=:]\s*([^,}\s]+)', payload)
    if m:
        return m.group(1)
    return None


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
    def from_string(cls, value: str) -> Role:
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
    def from_env(cls) -> Role:
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


# Governor-only handlers — only initialization is restricted.
GOVERNOR_ONLY: tuple[str, ...] = (
    "workspace.init",
    "project.init",
)

# P0-B: Mutating handlers — auditor must NEVER call these.
# This is the canonical list of handlers that mutate state/files
# UNCONDITIONALLY or BY DEFAULT. Handlers whose mutation is gated behind
# a flag param (apply/fix/force/content or a dry_run preview) live in
# CONDITIONAL_MUTATING instead — auditors keep their preview/read modes.
#
# T-020/T-021 note: read-classified handlers emit NO pulse telemetry at
# all — T-021 removed the best-effort ``kind="handler_call"`` writes from
# context.detect, context.full, identity.get, cortex.format and the
# parse_blp_template helper (a read must produce zero file writes).
# Semantic lifecycle/session pulses (session_bootstrap, session_handoff,
# blueprint_execute, task_run, checkpoint, skill_install, cortex_gc,
# cortex_migrate, cortex_patch — mutation-scoped only) DO count as
# writes. Ephemeral artifacts written under a fresh mkdtemp
# (cortex.render.diagram, cortex.render.validate_file) are caller
# outputs, not governance state.
MUTATING_HANDLERS: frozenset[str] = frozenset({
    # blueprint mutations
    "blueprint.create",
    "blueprint.ready", "blueprint.claim",
    "blueprint.update", "blueprint.complete", "blueprint.fail",
    "blueprint.cancel", "blueprint.re_delegate",
    "blueprint.block_for_architect", "blueprint.task",
    "blueprint.ac",
    # T-020: blueprint.execute writes the BLP file (marks ACs, sets
    # status=done) + PULSE unless dry_run; blueprint.synthesize creates
    # the BLP file and persists the template body (its "does NOT write
    # files" docstring was wrong). dry_run on execute is an executor
    # simulation, not an auditor preview — unconditional deny.
    "blueprint.execute", "blueprint.synthesize",
    # task mutations
    "task.create", "task.claim", "task.update", "task.complete", "task.fail",
    # T-020: task.run records PULSE + reconciles the cycle by default.
    "task.run",
    # cycle mutations
    "cycle.create", "cycle.close",
    # T-020: cycle.synthesize rewrites MANIFEST.md sections unconditionally.
    "cycle.synthesize",
    # evidence mutations
    "evidence.record",
    # cortex mutations
    "cortex.entry.add", "cortex.entry.delete", "cortex.entry.update",
    "cortex.entry.move", "cortex.write",
    # T-019: destructive cortex maintenance handler (WRK state write —
    # unconditional; gc/patch/migrate moved to CONDITIONAL_MUTATING in
    # T-020 since they expose real dry-run previews).
    "cortex.checkpoint",
    # session mutations — auditors have no session-write role (T-020:
    # bootstrap records a session_bootstrap PULSE event; handoff writes
    # handoffs/<agent>.cortex + PULSE; pulse.compact prunes the pulse and
    # writes a consolidated LNG entry — all by default). session.resume
    # is NOT here (T-020 audit C-1): it is a pure read of brain PULSE +
    # SES parse with zero writes — the auditor needs it to restore
    # session context.
    "session.context.set", "session.close",
    "session.bootstrap", "session.handoff", "session.pulse.compact",
    # project mutations
    "project.bind", "project.unbind", "project.init",
    # protocol mutations (T-020: onboard is an alias of adopt — writes
    # agents.cortex + sets env vars)
    "protocol.adopt", "protocol.release", "protocol.pause", "protocol.resume",
    "protocol.onboard",
    # identity mutations
    "identity.record",
    # skill mutations (T-020: install writes originals/ + brain SKL entry
    # + PULSE by default; evolve/edit moved to CONDITIONAL_MUTATING for
    # their dry-run/read gates)
    "skill.record", "skill.import", "skill.convert", "skill.install",
    # sync mutations (T-020): sync.run writes meta-brain; sync.reconcile
    # rewrites MANIFEST/brain/meta-brain metrics — both unconditional.
    "sync.run", "sync.reconcile",
    # setup mutations (T-020): downloads/installs plantuml.jar to
    # ~/.arqux/bin — writes outside the workspace, unconditional.
    "setup.plantuml",
    # workspace init (also GOVERNOR_ONLY)
    "workspace.init",
})

# T-020: Param-conditional mutators — handler → tuple of param names that
# must ALL be truthy for the invocation to mutate. Independently of the
# tuple, a truthy ``dry_run`` kwarg always marks the call non-mutating.
# The auditor is denied ONLY for the mutating invocation — dry-run
# previews and read modes remain allowed. This is a denylist refinement,
# not a policy engine.
#
# Policy (conditional vs unconditional): CONDITIONAL_MUTATING is reserved
# for auditor-meaningful previews (gc dedupe-preview, learn.elevate diff,
# file.validate report). Handlers whose dry_run merely simulates an
# EXECUTOR-domain action stay unconditional mutators — blueprint.execute,
# task.run, skill.install, session.handoff, session.pulse.compact — an
# auditor has no legitimate use for a simulated execution.
#
# An empty tuple means the handler mutates unless ``dry_run`` is truthy
# (no other flag gates it).
CONDITIONAL_MUTATING: dict[str, tuple[str, ...]] = {
    # apply=False (default) returns a dry-run elevation diff; apply=True
    # writes the elevation into brain.cortex.
    "cortex.learn.elevate": ("apply",),
    # fix=False (default) only reports duplicates; fix=True renames them
    # via atomic rewrite.
    "cortex.file.validate": ("fix",),
    # dry_run defaults True (pure preview); mutates iff force=True AND
    # dry_run=False.
    "cortex.gc": ("force",),
    # dry_run defaults False — writes entry bodies by default;
    # dry_run=True is a preview.
    "cortex.patch": (),
    # dry_run defaults False — writes the target file by default;
    # dry_run=True is a preview.
    "cortex.migrate": (),
    # apply=False (default) shows the proposed ADA change; apply=True
    # marks it applied in the skill file.
    "skill.evolve": ("apply",),
    # Without content, reads the skill file (auditor-legit); a truthy
    # content param writes the file/section.
    "skill.edit": ("content",),
}

def _resolve_call_kwargs(handler: str, call_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Bind *call_kwargs* against the registered handler's signature.

    Conditional-mutator flags must be judged at their EFFECTIVE values:
    ``cortex.gc`` declares ``dry_run=True`` (default preview) while
    ``cortex.patch`` declares ``dry_run=False`` (default mutation), so an
    omitted ``dry_run`` means different things per handler. Lazy-imports
    REGISTRY to avoid the module-level cycle (handlers → permissions).

    Falls back to the raw kwargs when the handler is unregistered or its
    signature rejects the args (params then count as falsy).
    """
    try:
        import inspect

        from .handlers import REGISTRY  # noqa: PLC0415 — lazy, circular

        spec = REGISTRY.get(handler)
        if spec is None:
            return call_kwargs
        bound = inspect.signature(spec.fn).bind_partial(**call_kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except Exception:  # noqa: BLE001 — resolution is best-effort
        return call_kwargs


def _is_mutating_invocation(handler: str, call_kwargs: dict[str, Any]) -> bool:
    """True when a CONDITIONAL_MUTATING call actually mutates state.

    Mutating iff every flag in the handler's tuple is truthy AND the
    effective ``dry_run`` is falsy. An empty tuple reduces to
    ``not dry_run`` (the handler mutates unless asked to preview).

    Args:
        handler: Dotted handler name present in CONDITIONAL_MUTATING.
        call_kwargs: Effective call arguments — defaults already bound via
            ``_resolve_call_kwargs``.
    """
    if call_kwargs.get("dry_run"):
        return False
    return all(call_kwargs.get(flag) for flag in CONDITIONAL_MUTATING[handler])


# Handlers that require HMAC signature verification (CRÍTICO-1 fix).
HMAC_REQUIRED: tuple[str, ...] = (
    "identity.record",       # anyone can claim to be any agent — must verify
    "evidence.record",       # evidence must be attributable to verified agent
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
    # HMAC verification fields.
    signature: str | None = None
    timestamp: int | None = None
    verified: bool = False  # True if HMAC signature has been verified

    @staticmethod
    def _normalize_project_root(root: str | Path) -> Path:
        """If *root* points to the .arqux/ directory, return its parent instead.

        ``find_project_root()`` returns the ``.arqux/`` directory, but
        ``IdentityManager(project_root=...)`` appends ``.arqux/`` internally
        (``<project_root>/.arqux/identities/``). Without normalization, passing
        ``.arqux/`` as project_root creates a double-nesting bug:
        ``.arqux/.arqux/identities/`` (GOV-001 P2).
        """
        p = Path(root)
        if p.name == ARQUX_DIR:
            return p.parent
        return p

    @classmethod
    def from_env(cls, project_root: str | Path | None = None) -> PermissionContext:
        prefix = f"{PRODUCT_NAME_UPPER}_"
        agent_id = os.environ.get(f"{prefix}AGENT_ID", "anonymous")
        role = os.environ.get(f"{prefix}AGENT_ROLE", ROLE_GOVERNOR)
        project = os.environ.get(f"{prefix}PROJECT")
        signature = os.environ.get(f"{prefix}AGENT_SIGNATURE")
        timestamp_str = os.environ.get(f"{prefix}AGENT_TIMESTAMP")
        timestamp = int(timestamp_str) if timestamp_str else None

        # Resolve runtime agent_id to canonical ArqUX identity (BLP-008 GOV-001 P2.2)
        if project_root is not None:
            proj_path = cls._normalize_project_root(project_root)
            try:
                im = IdentityManager(project_root=proj_path)
                artifact = im.resolve(agent_id)
                # Extract name from IDN entry if available
                name = _extract_identity_name(artifact.payload)
                if name:
                    agent_id = name
            except Exception as exc:
                logger.warning(
                    "from_env: identity resolve failed for agent_id=%s project_root=%s: %s",
                    agent_id, project_root, exc,
                )
        else:
            # P2 fallback: try to auto-detect project root from CWD
            try:
                from .state import find_project_root
                auto_root = find_project_root()
                if auto_root is not None:
                    normalized = cls._normalize_project_root(auto_root)
                    im = IdentityManager(project_root=normalized)
                    artifact = im.resolve(agent_id)
                    name = _extract_identity_name(artifact.payload)
                    if name:
                        agent_id = name
            except Exception as exc:
                logger.warning(
                    "from_env: P2 fallback identity resolve failed for agent_id=%s: %s",
                    agent_id, exc,
                )

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

    def check(self, handler: str, **call_kwargs: Any) -> None:
        """Enforce role-based access control on the given handler call.

        v0.4.3+T-020 behavior:
            - GOVERNOR: can call any handler (full access).
            - EXECUTOR: can call any handler except GOVERNOR_ONLY (init handlers).
            - AUDITOR: can call any handler EXCEPT GOVERNOR_ONLY,
              MUTATING_HANDLERS, and CONDITIONAL_MUTATING invocations that
              actually mutate. (Previously: fallthrough allowed all
              non-GOVERNOR_ONLY handlers — that was a security bug.)

        Args:
            handler: Dotted handler name (e.g. ``"cortex.gc"``).
            call_kwargs: Call arguments for conditional-mutator evaluation
                (T-020). For handlers in CONDITIONAL_MUTATING the args are
                bound against the registered signature first, so omitted
                params are judged at their declared defaults (e.g.
                ``cortex.gc`` dry_run defaults True = preview;
                ``cortex.patch`` dry_run defaults False = mutating).

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

        # P0-B FIX: Auditor is STRICTLY read-only.
        if self.role == ROLE_AUDITOR:
            if handler in GOVERNOR_ONLY:
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    "governor-only handler; auditor cannot call",
                )
            if handler in MUTATING_HANDLERS:
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    "mutating handler; auditor is read-only",
                )
            # T-020: param-conditional mutators — deny only when this
            # invocation actually mutates (all gate flags truthy AND
            # dry_run falsy); previews/read modes stay allowed.
            if handler in CONDITIONAL_MUTATING and _is_mutating_invocation(
                handler, _resolve_call_kwargs(handler, call_kwargs)
            ):
                raise PermissionDenied(
                    self.agent_id, self.role, handler,
                    "mutating invocation; auditor is read-only",
                )
            # All other handlers (read + governance read-only) are allowed.
            return

        # Unknown role.
        raise PermissionDenied(
            self.agent_id, self.role, handler,
            f"unknown role {self.role!r}",
        )

    def can(self, handler: str, **call_kwargs: Any) -> bool:
        """Non-raising variant of `check`."""
        try:
            self.check(handler, **call_kwargs)
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


def deny(role: str, handler: str, reason: str = "not_allowed") -> PermissionDenied:
    """Construct a PermissionDenied exception without raising it."""
    return PermissionDenied(
        agent_id="<unknown>", role=role, handler=handler, reason=reason,
    )


def enforce_ctx(
    ctx: PermissionContext | None,
    handler: str,
    *,
    require_hmac: bool = False,
) -> PermissionContext:
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
        fn._required_roles = {r.value for r in allowed_roles}
        return fn
    return decorator
