"""Identity and session lifecycle suite — finding 2.5 and lesson
`contextual_identity` (issue 2026-10-02: claim registered executor=alfred
after identity.switch to Jarvis).

Frictions covered:

- 2.5 session/identity walls: the error must present the alternatives
  (resume or close) instead of a bare failure; identity.switch must work
  from the workspace root; handoff+switch is one atomic call.
- H-3 contextual identity: the active session identity wins over the
  transport/env identity when claiming work.
"""

from __future__ import annotations

import pytest

from arqux.cortex_out import OUT_ERROR, OUT_WORK
from arqux.execution import current_execution_key
from arqux.handlers.blueprint.lifecycle import claim_blueprint
from arqux.handlers.identity.switch import switch
from arqux.session_identity import SessionOpenExists, open_session


def test_switch_works_from_workspace_root(arqux_env):
    """2.5: identity.switch used to fail when called from the ws root."""
    from arqux.handlers.session import context_set

    bound = context_set(project="test-proj", scope="", path=str(arqux_env.ws_root),
                        ctx=arqux_env.gov_ctx)
    assert bound.profile == OUT_WORK, bound.to_text()

    out = switch(agent_id="heimdall", path=str(arqux_env.ws_root),
                 ctx=arqux_env.gov_ctx)
    assert out.profile == OUT_WORK, out.to_text()
    assert out.fields.get("agent_id", "").lower() == "heimdall"


def test_unknown_identity_lists_available_contracts(arqux_env):
    out = switch(agent_id="nobody_here", path=str(arqux_env.proj_root),
                 ctx=arqux_env.gov_ctx)
    assert out.profile == OUT_ERROR, out.to_text()
    text = out.to_text().lower()
    available = out.fields.get("available_identities") or []
    assert available, out.fields
    assert "nobody_here" in text or "available" in text


def test_switch_dry_run_is_read_only(arqux_env):
    """2.5: dry_run validates the switch without handoff/context mutation."""
    context_file = arqux_env.ws_root / ".arqux" / "context.cortex"
    before = context_file.read_text(encoding="utf-8") if context_file.exists() else None

    out = switch(agent_id="heimdall", path=str(arqux_env.proj_root),
                 dry_run=True, ctx=arqux_env.gov_ctx)
    assert out.profile == OUT_WORK, out.to_text()

    after = context_file.read_text(encoding="utf-8") if context_file.exists() else None
    assert after == before


def test_second_session_error_presents_alternatives(arqux_env):
    """2.5: one open session per project; the wall explains resume-or-close."""
    open_session(
        arqux_env.proj_root,
        agent="test-governor", project="test-proj",
        execution=current_execution_key() or "exec-a",
    )
    with pytest.raises(SessionOpenExists) as excinfo:
        open_session(
            arqux_env.proj_root,
            agent="test-governor", project="test-proj",
            execution="exec-b",
        )
    assert excinfo.value.code == "SESSION_OPEN_EXISTS"
    assert excinfo.value.args, "the error must carry the alternatives"


def test_claim_without_bound_session_is_guided(arqux_env):
    """H-3/2.5: claim rejects unbound execution with a remediation string."""
    # The project has session identity, but it belongs to another execution.
    open_session(
        arqux_env.proj_root,
        agent="test-governor", project="test-proj",
        execution="exec-other",
    )
    out = claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root),
                          ctx=arqux_env.exec_ctx)
    assert out.profile == OUT_ERROR, out.to_text()
    assert out.fields.get("code") == "SESSION_UNBOUND"
    assert out.fields.get("remediation"), out.fields


def test_claim_records_active_session_identity(arqux_env):
    """H-3: after identity.switch, claim must record the ACTIVE agent."""
    from arqux.handlers.session import context_set

    bound = context_set(project="test-proj", scope="",
                        path=str(arqux_env.ws_root), ctx=arqux_env.gov_ctx)
    assert bound.profile == OUT_WORK, bound.to_text()
    bp = next(
        (arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id /
         "blueprints").glob("*.md")
    )
    # Mature the blueprint just enough to be claimable (ready → in_progress).
    text = bp.read_text(encoding="utf-8")
    text = text.replace('status: "draft"', 'status: "ready"', 1)
    bp.write_text(text, encoding="utf-8")

    switched = switch(agent_id="executor", path=str(arqux_env.proj_root),
                      ctx=arqux_env.gov_ctx)
    assert switched.profile == OUT_WORK, switched.to_text()

    out = claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root),
                          ctx=arqux_env.gov_ctx)
    assert out.profile == OUT_WORK, out.to_text()
    assert out.fields.get("executor") == "executor", out.fields
