"""Tests for auditor read-only enforcement (P0-B + T-020).

Validates that AUDITOR role cannot call mutating handlers, and that
param-conditional mutators (T-020 CONDITIONAL_MUTATING) are denied only
when the invocation actually mutates.
"""

from __future__ import annotations

import os

import pytest

from arqux.constants import ROLE_AUDITOR, ROLE_EXECUTOR, ROLE_GOVERNOR
from arqux.permissions import (
    CONDITIONAL_MUTATING,
    MUTATING_HANDLERS,
    PermissionContext,
    PermissionDenied,
)


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
            "blueprint.complete",
            "task.fail", "task.create", "task.update", "task.complete",
            "cortex.entry.delete", "cortex.entry.update", "cortex.write",
            "cortex.entry.add", "cortex.entry.move",
            # T-019: destructive cortex maintenance handler (WRK write —
            # gc/patch/migrate moved to CONDITIONAL_MUTATING in T-020)
            "cortex.checkpoint",
            "protocol.adopt", "protocol.release",
            "evidence.record",
            "session.context.set", "session.close",
            "project.bind", "project.unbind",
            "identity.record",
            "cycle.create", "cycle.close",
            # T-020: residual auditor-callable mutators reconciled
            "session.bootstrap", "session.handoff", "session.pulse.compact",
            "blueprint.execute", "blueprint.synthesize", "cycle.synthesize",
            "task.run", "protocol.onboard", "skill.install",
            "sync.run", "sync.reconcile", "setup.plantuml",
        }
        missing = expected - MUTATING_HANDLERS
        assert not missing, f"Missing mutating handlers: {missing}"

    def test_conditional_handlers_not_unconditional(self) -> None:
        """T-020: conditional mutators must NOT be in MUTATING_HANDLERS —
        their non-mutating invocations stay auditor-allowed."""
        leaked = set(CONDITIONAL_MUTATING) & MUTATING_HANDLERS
        assert not leaked, f"conditional mutators leaked into MUTATING_HANDLERS: {leaked}"

    def test_conditional_mutating_covers_gated_handlers(self) -> None:
        """Every handler with a real dry-run/apply/read gate is conditional."""
        expected = {
            "cortex.learn.elevate",
            "cortex.file.validate",
            "cortex.gc",
            "cortex.patch",
            "cortex.migrate",
            "skill.evolve",
            "skill.edit",
        }
        missing = expected - set(CONDITIONAL_MUTATING)
        assert not missing, f"Missing conditional mutators: {missing}"

    def test_session_resume_not_mutating(self) -> None:
        """T-020 audit C-1: session.resume is a pure read (brain PULSE +
        SES parse, zero writes) — it must stay out of MUTATING_HANDLERS
        and out of CONDITIONAL_MUTATING (it has no mutating mode)."""
        assert "session.resume" not in MUTATING_HANDLERS
        assert "session.resume" not in CONDITIONAL_MUTATING


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


class TestCortexDestructiveHandlers:
    """T-019/T-020: destructive cortex maintenance handlers must require a
    mutator role — an auditor invoking them in a mutating mode deletes,
    renames or rewrites governance entries.

    T-020 split: ``cortex.checkpoint`` writes unconditionally →
    MUTATING_HANDLERS. ``cortex.gc``/``cortex.patch``/``cortex.migrate``
    expose real dry-run previews → CONDITIONAL_MUTATING (auditor denied
    only for the mutating invocation; see TestConditionalMutating).
    """

    UNCONDITIONAL = ["cortex.checkpoint"]
    CONDITIONAL = ["cortex.gc", "cortex.patch", "cortex.migrate"]

    @pytest.mark.parametrize("handler", UNCONDITIONAL)
    def test_auditor_denied(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="mutating handler"):
            ctx.check(handler)

    @pytest.mark.parametrize("handler", UNCONDITIONAL + CONDITIONAL)
    def test_executor_allowed(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR)
        ctx.check(handler)  # should not raise

    @pytest.mark.parametrize("handler", UNCONDITIONAL + CONDITIONAL)
    def test_governor_allowed(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="alfred", role=ROLE_GOVERNOR)
        ctx.check(handler)  # should not raise

    def test_gc_force_call_denied_via_dispatch_check(self) -> None:
        """Mirror the server dispatch path (server._wrap_handler calls
        ctx.check(name, **effective_kwargs) before invoking gc_handler)."""
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        assert ctx.can("cortex.gc", force=True, dry_run=False) is False
        with pytest.raises(PermissionDenied):
            ctx.check("cortex.gc", force=True, dry_run=False)


class TestT020ReconciledMutators:
    """T-020: handlers that were auditor-callable mutators — now denied."""

    NEW_MUTATORS = [
        "session.bootstrap",      # writes session_bootstrap PULSE event
        "session.handoff",        # writes handoffs/<agent>.cortex + PULSE
        "session.pulse.compact",  # prunes pulse + writes consolidated LNG
        "blueprint.execute",      # marks ACs + status=done in BLP file
        "blueprint.synthesize",   # creates + persists the BLP file
        "cycle.synthesize",       # rewrites cycle MANIFEST.md sections
        "task.run",               # records PULSE + reconciles the cycle
        "protocol.onboard",       # alias of adopt — writes agents.cortex
        "skill.install",          # writes originals/ + brain SKL + PULSE
        "sync.run",               # writes meta-brain
        "sync.reconcile",         # rewrites MANIFEST/brain/meta-brain
        "setup.plantuml",         # installs plantuml.jar to ~/.arqux/bin
    ]

    @pytest.mark.parametrize("handler", NEW_MUTATORS)
    def test_auditor_denied(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="mutating handler"):
            ctx.check(handler)

    @pytest.mark.parametrize("handler", NEW_MUTATORS)
    def test_auditor_can_mirror(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        assert ctx.can(handler) is False

    @pytest.mark.parametrize("handler", NEW_MUTATORS)
    def test_executor_allowed(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR)
        ctx.check(handler)  # should not raise


class TestConditionalMutating:
    """T-020: CONDITIONAL_MUTATING — auditor denied only when the call
    actually mutates; dry-run previews and read modes stay allowed."""

    # --- cortex.learn.elevate (flag: apply) ---

    def test_elevate_dry_run_allowed(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("cortex.learn.elevate")                       # apply defaults False
        ctx.check("cortex.learn.elevate", apply=False)          # explicit preview
        assert ctx.can("cortex.learn.elevate") is True

    def test_elevate_apply_denied(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check("cortex.learn.elevate", apply=True)
        assert ctx.can("cortex.learn.elevate", apply=True) is False

    # --- cortex.gc (flag: force + dry_run=False semantics) ---

    def test_gc_preview_allowed(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("cortex.gc")                                  # dry_run defaults True
        ctx.check("cortex.gc", dry_run=True)
        ctx.check("cortex.gc", force=True, dry_run=True)        # force + preview = preview
        assert ctx.can("cortex.gc", dry_run=True) is True

    def test_gc_force_mutation_denied(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check("cortex.gc", force=True, dry_run=False)
        assert ctx.can("cortex.gc", force=True, dry_run=False) is False

    def test_gc_no_force_no_mutation_allowed(self) -> None:
        """force=False + dry_run=False is CONFIRM_REQUIRED (no mutation) —
        the check admits it because it cannot mutate."""
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("cortex.gc", force=False, dry_run=False)      # should not raise

    def test_gc_force_without_dry_run_allowed(self) -> None:
        """check() binds signature defaults — gc(force=True) with omitted
        dry_run evaluates the EFFECTIVE call (dry_run defaults True →
        preview), consistent with the dispatch path."""
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("cortex.gc", force=True)  # should not raise
        assert ctx.can("cortex.gc", force=True) is True

    # --- cortex.patch / cortex.migrate (mutate unless dry_run) ---

    @pytest.mark.parametrize("handler", ["cortex.patch", "cortex.migrate"])
    def test_default_invocation_denied(self, handler: str) -> None:
        """Both mutate by default (dry_run=False)."""
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check(handler)
        with pytest.raises(PermissionDenied):
            ctx.check(handler, dry_run=False)
        assert ctx.can(handler) is False

    @pytest.mark.parametrize("handler", ["cortex.patch", "cortex.migrate"])
    def test_dry_run_preview_allowed(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check(handler, dry_run=True)  # should not raise
        assert ctx.can(handler, dry_run=True) is True

    # --- cortex.file.validate (flag: fix) ---

    def test_file_validate_report_allowed_fix_denied(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("cortex.file.validate")                       # fix defaults False
        ctx.check("cortex.file.validate", fix=False)
        assert ctx.can("cortex.file.validate") is True
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check("cortex.file.validate", fix=True)
        assert ctx.can("cortex.file.validate", fix=True) is False

    # --- skill.evolve (flag: apply) ---

    def test_skill_evolve_preview_allowed_apply_denied(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("skill.evolve")                               # apply defaults False
        assert ctx.can("skill.evolve") is True
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check("skill.evolve", apply=True)

    # --- skill.edit (flag: content) ---

    def test_skill_edit_read_allowed_write_denied(self) -> None:
        ctx = PermissionContext(agent_id="heimdall", role=ROLE_AUDITOR)
        ctx.check("skill.edit")                                 # no content = read
        assert ctx.can("skill.edit") is True
        with pytest.raises(PermissionDenied, match="mutating invocation"):
            ctx.check("skill.edit", content="new body")
        assert ctx.can("skill.edit", content="new body") is False

    # --- other roles unaffected ---

    @pytest.mark.parametrize("handler", sorted(CONDITIONAL_MUTATING))
    def test_executor_allowed_all_modes(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="jarvis", role=ROLE_EXECUTOR)
        ctx.check(handler)
        ctx.check(handler, apply=True, fix=True, force=True,
                  dry_run=False, content="x")  # should not raise

    @pytest.mark.parametrize("handler", sorted(CONDITIONAL_MUTATING))
    def test_governor_allowed_all_modes(self, handler: str) -> None:
        ctx = PermissionContext(agent_id="alfred", role=ROLE_GOVERNOR)
        ctx.check(handler, apply=True, fix=True, force=True,
                  dry_run=False, content="x")  # should not raise


class TestConditionalDispatchBinding:
    """T-020: end-to-end dispatch — ``server._wrap_handler`` forwards call
    kwargs to ``ctx.check``, which binds signature defaults, so an omitted
    ``dry_run`` is judged at its declared default (gc defaults preview,
    patch defaults mutating)."""

    async def test_gc_force_only_previews_at_dispatch(self) -> None:
        """gc(force=True) with omitted dry_run → effective dry_run=True →
        auditor allowed (the call previews; no mutation possible)."""
        from arqux.handlers.cortex.gc import gc_handler
        from arqux.server import _wrap_handler

        os.environ["ARQUX_AGENT_ROLE"] = "auditor"
        os.environ["ARQUX_AGENT_ID"] = "heimdall"
        try:
            wrapped = _wrap_handler("cortex.gc", gc_handler)
            out = await wrapped(path="does-not-exist.cortex", force=True)
            assert "PERMISSION_DENIED" not in out
            assert "NOT_FOUND" in out  # reached the handler — preview allowed
        finally:
            os.environ.pop("ARQUX_AGENT_ROLE", None)
            os.environ.pop("ARQUX_AGENT_ID", None)

    async def test_gc_force_mutation_denied_at_dispatch(self) -> None:
        from arqux.handlers.cortex.gc import gc_handler
        from arqux.server import _wrap_handler

        os.environ["ARQUX_AGENT_ROLE"] = "auditor"
        os.environ["ARQUX_AGENT_ID"] = "heimdall"
        try:
            wrapped = _wrap_handler("cortex.gc", gc_handler)
            out = await wrapped(
                path="does-not-exist.cortex", force=True, dry_run=False
            )
            assert "PERMISSION_DENIED" in out
        finally:
            os.environ.pop("ARQUX_AGENT_ROLE", None)
            os.environ.pop("ARQUX_AGENT_ID", None)

    async def test_patch_default_denied_dry_run_allowed_at_dispatch(self) -> None:
        from arqux.handlers.cortex.patch import patch_handler
        from arqux.server import _wrap_handler

        os.environ["ARQUX_AGENT_ROLE"] = "auditor"
        os.environ["ARQUX_AGENT_ID"] = "heimdall"
        try:
            wrapped = _wrap_handler("cortex.patch", patch_handler)
            denied = await wrapped(path="x.cortex", content="$0{a}")
            assert "PERMISSION_DENIED" in denied
            allowed = await wrapped(path="x.cortex", content="$0{a}", dry_run=True)
            assert "PERMISSION_DENIED" not in allowed
        finally:
            os.environ.pop("ARQUX_AGENT_ROLE", None)
            os.environ.pop("ARQUX_AGENT_ID", None)

    async def test_unconditional_mutator_denied_at_dispatch(self) -> None:
        """session.bootstrap is unconditional — even a 'preview-ish' call
        is denied for auditor (no dry-run gate exists on it)."""
        from arqux.handlers.session import bootstrap
        from arqux.server import _wrap_handler

        os.environ["ARQUX_AGENT_ROLE"] = "auditor"
        os.environ["ARQUX_AGENT_ID"] = "heimdall"
        try:
            wrapped = _wrap_handler("session.bootstrap", bootstrap)
            out = await wrapped(path="/nonexistent-xyz")
            assert "PERMISSION_DENIED" in out
        finally:
            os.environ.pop("ARQUX_AGENT_ROLE", None)
            os.environ.pop("ARQUX_AGENT_ID", None)


class TestCliRoleEnforcement:
    """T-020 audit C-2: ``arqux call`` must enforce roles — cli._call_handler
    runs ``ctx.check(name, **kwargs)`` before invoking the handler, mirroring
    ``server._wrap_handler`` (PermissionDenied → clean OUT-ERROR, never a
    traceback)."""

    def test_auditor_denied_mutating_handler(self, tmp_path, monkeypatch) -> None:
        """arqux call task.fail under auditor → PERMISSION_DENIED."""
        from arqux.cli import _call_handler

        monkeypatch.setenv("ARQUX_STRICT_ROLES", "1")
        monkeypatch.setenv("ARQUX_AGENT_ROLE", "auditor")
        monkeypatch.setenv("ARQUX_AGENT_ID", "heimdall")
        monkeypatch.chdir(tmp_path)

        out = _call_handler("task.fail", ["task_id=T-999", "reason=audit"])
        assert "PERMISSION_DENIED" in out
        assert "OUT-ERROR" in out
        assert "handler=task.fail" in out
        assert "Traceback" not in out

    def test_auditor_allowed_read_handler(self, tmp_path, monkeypatch) -> None:
        """arqux call session.resume under auditor reaches the handler —
        the C-1 read path works end-to-end through the CLI (a domain
        NOT_FOUND error proves the permission check passed)."""
        from arqux.cli import _call_handler

        monkeypatch.setenv("ARQUX_STRICT_ROLES", "1")
        monkeypatch.setenv("ARQUX_AGENT_ROLE", "auditor")
        monkeypatch.setenv("ARQUX_AGENT_ID", "heimdall")
        monkeypatch.chdir(tmp_path)

        out = _call_handler("session.resume", [])
        assert "PERMISSION_DENIED" not in out
        assert "OUT-ERROR" in out  # reached the handler: no project here
        assert "Traceback" not in out

    def test_auditor_allowed_conditional_preview(self, tmp_path, monkeypatch) -> None:
        """arqux call cortex.gc force=true (dry_run omitted → bound to its
        True default) is a preview — auditor allowed."""
        from arqux.cli import _call_handler

        monkeypatch.setenv("ARQUX_STRICT_ROLES", "1")
        monkeypatch.setenv("ARQUX_AGENT_ROLE", "auditor")
        monkeypatch.setenv("ARQUX_AGENT_ID", "heimdall")
        monkeypatch.chdir(tmp_path)

        out = _call_handler("cortex.gc", ["path=/nonexistent-xyz", "force=true"])
        assert "PERMISSION_DENIED" not in out
        assert "Traceback" not in out

    def test_auditor_denied_conditional_mutation(self, tmp_path, monkeypatch) -> None:
        """arqux call cortex.gc force=true dry_run=false is the mutating
        invocation — auditor denied."""
        from arqux.cli import _call_handler

        monkeypatch.setenv("ARQUX_STRICT_ROLES", "1")
        monkeypatch.setenv("ARQUX_AGENT_ROLE", "auditor")
        monkeypatch.setenv("ARQUX_AGENT_ID", "heimdall")
        monkeypatch.chdir(tmp_path)

        out = _call_handler(
            "cortex.gc", ["path=/nonexistent-xyz", "force=true", "dry_run=false"]
        )
        assert "PERMISSION_DENIED" in out
        assert "OUT-ERROR" in out
        assert "Traceback" not in out

    def test_call_command_denied_exit_code(self, tmp_path, monkeypatch) -> None:
        """End-to-end: `arqux call <mutating>` under auditor exits 1 with
        PERMISSION_DENIED in the output (P1-A/B contract preserved)."""
        from click.testing import CliRunner

        from arqux.cli import main

        monkeypatch.setenv("ARQUX_STRICT_ROLES", "1")
        monkeypatch.setenv("ARQUX_AGENT_ROLE", "auditor")
        monkeypatch.setenv("ARQUX_AGENT_ID", "heimdall")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main, ["call", "task.fail", "task_id=T-999"])
        assert result.exit_code == 1
        assert "PERMISSION_DENIED" in result.output


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
        # T-020 borderline resolved as READ — telemetry/ephemeral writes
        # only, no governance-state mutation (see MUTATING_HANDLERS note):
        "cortex.format",                # pure transform + handler_call telemetry
        "cortex.render",                # pure HCORTEX render
        "cortex.render.diagram",        # ephemeral mkdtemp artifacts only
        "cortex.render.validate_file",  # reads + ephemeral render artifacts
        "cortex.ref",                   # sigil definition lookup
        "context.detect",               # .arqux detection + telemetry
        "context.full",                 # context aggregation + telemetry
        "identity.get",                 # identity read + telemetry
        "session.status",               # SES metadata read
        "session.resume",               # pure PULSE+SES read (C-1)
        "session.context.get",          # context pointer read
        "cortex.learn",                 # learning scan
        "cortex.entry.get", "cortex.entry.list",
        "handler.list",
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
