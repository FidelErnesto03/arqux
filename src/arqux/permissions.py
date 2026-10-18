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
import functools
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
    OUT_ERROR,
    PRODUCT_NAME_UPPER,
    ROLE_AUDITOR,
    ROLE_EXECUTOR,
    ROLE_GOVERNOR,
)
from .execution import authoritative_execution_key
from .identity import IdentityManager, IdentityNotFoundError

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


#: Governance role for each canonical agent identity. The *active* identity —
#: the agent named by the session context pointer — decides the effective role;
#: the transport env var is only a fallback. Without this, an identity switch
#: left the governor bit from the server env in place and a read-only auditor
#: could mutate state (F6, audit of BLP-022).
_AGENT_ROLE_BY_NAME: dict[str, str] = {
    "alfred": ROLE_GOVERNOR,
    "governor": ROLE_GOVERNOR,
    "jarvis": ROLE_EXECUTOR,
    "executor": ROLE_EXECUTOR,
    "heimdall": ROLE_AUDITOR,
    "seshat": ROLE_AUDITOR,
    "auditor": ROLE_AUDITOR,
}

#: Handlers that change WHICH identity is active. They stay callable from any
#: role; otherwise a session that switched to an auditor could never switch
#: back (F6). Elevation through this control is a separate concern.
ROLE_CONTROL_HANDLERS: frozenset[str] = frozenset({"identity.switch"})


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
    # CYCLE-14 / BLP-004: an explicit correction always writes a revision.
    "timelog.review",
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
    # issue registry mutations (T-027) — the auditor endorses via
    # audit_ref; the auditor role itself never calls these.
    "issue.create", "issue.update",
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
    # BLP-011 retrospective: identity.switch validates the target, writes
    # the handoff file + a PULSE event and updates the session context —
    # unconditional writes, so the auditor must be denied.
    "identity.switch",
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
    # preview=True (default) returns a non-mutating preview; preview=False
    # applies archive/summarize/delete.
    "timelog.purge": ("!preview",),
    # preview is read-only; prepare/send/reconcile write the batch/receipt.
    "timelog.project": ("action!=preview",),
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
    return all(_mutating_flag(call_kwargs, flag)
               for flag in CONDITIONAL_MUTATING[handler])


def _mutating_flag(call_kwargs: dict[str, Any], flag: str) -> bool:
    """Evaluate one conditional-mutator flag.

    A leading ``!`` inverts the test, for handlers whose mutating switch is a
    *default-safe* boolean like ``preview=True``: ``timelog.purge`` mutates when
    ``preview`` is False, not when some flag is True.

    ``name!=value`` compares instead of testing truthiness, for handlers whose
    switch is an *action word*: ``timelog.project`` mutates when
    ``action != "preview"``, which is not expressible as a boolean flag.
    """
    if "!=" in flag:
        name, _, value = flag.partition("!=")
        return str(call_kwargs.get(name)) != value
    if flag.startswith("!"):
        return not call_kwargs.get(flag[1:])
    return bool(call_kwargs.get(flag))


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
    # CYCLE-14 / BLP-001: which *execution* is acting. Independent of
    # ``agent_id``: two concurrent executions of the same agent carry the same
    # identity but must not share a session. ``None`` means no unambiguous
    # execution binding — mutating session handlers must reject rather than
    # borrow another execution's session.
    execution_key: str | None = None

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

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _canonical_agent_id(
        agent_id: str,
        project_root: str | Path | None = None,
    ) -> str | None:
        """Resolve *agent_id* to its canonical ArqUX identity name.

        Mirrors ``identity.get``'s three-tier lookup (BLP-008 GOV-001 P2.2):
        project identities, then workspace identities, then the identities
        packaged with ArqUX.

        The workspace tier is not optional here. Identities live at workspace
        level by design (AGENTS.md ``AXM:identity_loading``), so a lookup
        scoped only to the active project finds nothing for every agent whose
        identity is not duplicated inside the project. That left ``agent_id``
        silently degraded to the raw ``ARQUX_AGENT_ID`` value and logged a
        resolution warning on *every* tool call.

        Results are memoized per process: identity files are large (100–200 KB)
        and ``from_env`` runs on every tool call, so re-reading and re-parsing
        one per call is pure overhead. The cache is keyed by
        ``(agent_id, project_root)``.
        """
        from .identity import IDENTITIES_DIR
        from .state import find_project_root, find_workspace_root

        canonical = agent_id.casefold()

        candidates: list[Path] = []
        effective_root = project_root if project_root is not None else find_project_root()
        if effective_root is not None:
            candidates.append(
                PermissionContext._normalize_project_root(effective_root) / ARQUX_DIR / "identities"
            )

        workspace_arqux = find_workspace_root()
        if workspace_arqux is not None:
            candidates.append(workspace_arqux / "identities")

        candidates.append(IDENTITIES_DIR)

        for identities_dir in candidates:
            try:
                artifact = IdentityManager(identities_dir=identities_dir).resolve(canonical)
            except IdentityNotFoundError:
                continue
            except Exception as exc:  # noqa: BLE001
                # A tier that exists but cannot be read is NOT "not found".
                # Swallowing it would silently fall through to the next tier and
                # run the agent under the packaged identity instead of its own.
                logger.warning(
                    "from_env: identity tier unreadable agent_id=%s dir=%s: %s",
                    agent_id, identities_dir, exc,
                )
                continue
            name = _extract_identity_name(artifact.payload)
            if name:
                return name
        return None

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
        try:
            name = cls._canonical_agent_id(agent_id, project_root)
            if name:
                agent_id = name
            else:
                # Never fail silently: a run under the raw env value instead of
                # the canonical identity is a governance-visible degradation.
                logger.warning(
                    "from_env: identity not resolved for agent_id=%s project_root=%s; "
                    "falling back to the raw ARQUX_AGENT_ID value",
                    agent_id, project_root,
                )
        except Exception as exc:
            logger.warning(
                "from_env: identity resolve failed for agent_id=%s project_root=%s: %s",
                agent_id, project_root, exc,
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
            execution_key=authoritative_execution_key(),
        )

    def check(self, handler_name: str, **call_kwargs: Any) -> None:
        """Enforce role-based access control on the given handler call.

        v0.4.3+T-020 behavior:
            - GOVERNOR: can call any handler (full access).
            - EXECUTOR: can call any handler except GOVERNOR_ONLY (init handlers).
            - AUDITOR: can call any handler EXCEPT GOVERNOR_ONLY,
              MUTATING_HANDLERS, and CONDITIONAL_MUTATING invocations that
              actually mutate. (Previously: fallthrough allowed all
              non-GOVERNOR_ONLY handlers — that was a security bug.)

        Args:
            handler_name: Dotted handler name (e.g. ``"cortex.gc"``).
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
            if handler_name in GOVERNOR_ONLY:
                raise PermissionDenied(
                    self.agent_id, self.role, handler_name,
                    "governor-only handler; executor cannot call",
                )
            return

        # P0-B FIX: Auditor is STRICTLY read-only.
        if self.role == ROLE_AUDITOR:
            if handler_name in GOVERNOR_ONLY:
                raise PermissionDenied(
                    self.agent_id, self.role, handler_name,
                    "governor-only handler; auditor cannot call",
                )
            if handler_name in MUTATING_HANDLERS:
                raise PermissionDenied(
                    self.agent_id, self.role, handler_name,
                    "mutating handler; auditor is read-only",
                )
            # T-020: param-conditional mutators — deny only when this
            # invocation actually mutates (all gate flags truthy AND
            # dry_run falsy); previews/read modes stay allowed.
            if handler_name in CONDITIONAL_MUTATING and _is_mutating_invocation(
                handler_name, _resolve_call_kwargs(handler_name, call_kwargs)
            ):
                raise PermissionDenied(
                    self.agent_id, self.role, handler_name,
                    "mutating invocation; auditor is read-only",
                )
            # All other handlers (read + governance read-only) are allowed.
            return

        # Unknown role.
        raise PermissionDenied(
            self.agent_id, self.role, handler_name,
            f"unknown role {self.role!r}",
        )

    def can(self, handler_name: str, **call_kwargs: Any) -> bool:
        """Non-raising variant of `check`."""
        try:
            self.check(handler_name, **call_kwargs)
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


def resolve_active_role(path: str | None = None) -> str | None:
    """Governance role of the ACTIVE identity, from the session context pointer.

    F6: the transport default (``ARQUX_AGENT_ROLE``, governor) must not grant a
    read-only identity the power to mutate. Returns the role mapped from the
    agent named in the context pointer, or ``None`` when there is no pointer or
    the agent is unknown (the caller then keeps the env role).
    """
    try:
        from .handlers.session import context_get  # lazy: handlers import permissions
        out = context_get(path=path)
    except Exception:  # noqa: BLE001 — resolution is best-effort
        return None
    if getattr(out, "profile", "") == OUT_ERROR:
        return None
    fields = getattr(out, "fields", {}) or {}
    agent = str(fields.get("agent", "")).casefold()
    return _AGENT_ROLE_BY_NAME.get(agent)


def apply_active_identity_role(
    ctx: PermissionContext,
    *,
    handler: str | None = None,
    path: str | None = None,
) -> PermissionContext:
    """Override *ctx*'s role with the active identity's (F6).

    ``ROLE_CONTROL_HANDLERS`` are exempt so the active identity can always be
    changed. When the pointer is absent or the agent is unknown, the ctx keeps
    the role it already had.
    """
    if handler in ROLE_CONTROL_HANDLERS:
        return ctx
    role = resolve_active_role(path)
    if role:
        ctx.role = role
    return ctx


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
