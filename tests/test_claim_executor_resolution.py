"""Regression tests for issue 2026-10-02 (blueprint.claim executor resolution).

claim used to resolve the executor from PermissionContext.from_env() — the
statically authenticated MCP server agent — ignoring the active identity set
by identity.switch / session.context.set. After a handoff Alfred→Jarvis,
blueprint.claim recorded executor=alfred (BLP-014, Conquistadores).

Executor resolution precedence:
1. ``agent_id`` param — explicit assignment, governor-only.
2. Declared executor in frontmatter + governor caller (pre-existing).
3. Active identity from workspace context.cortex (identity.switch).
4. Authenticated agent from env (fallback).
"""

from __future__ import annotations

from pathlib import Path

from arqux.constants import OUT_ERROR, PERMISSION_DENIED
from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint

from .test_blueprint_integration import _read_fm, _scrub_placeholders, _set_fm


def _write_context(ws_root: Path, agent: str) -> None:
    """Emulate identity.switch's context pointer write."""
    ctx_dir = ws_root / ".arqux"
    ctx_dir.mkdir(exist_ok=True)
    (ctx_dir / "context.cortex").write_text(
        f'$0\n\n$1: CURRENT\nCTX:{agent} project="test-proj" scope="CYCLE-TEST" '
        f'agent="{agent}" project_root="{ws_root / "test-proj"}"\n',
        encoding="utf-8",
    )


def _ready_bp(arqux_env, bp_id: str) -> None:
    _scrub_placeholders(arqux_env.proj_root, bp_id)
    ready_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)


def test_claim_uses_active_context_agent(arqux_env) -> None:
    """After identity.switch to jarvis, claim records executor=jarvis."""
    _write_context(arqux_env.ws_root, "jarvis")
    _ready_bp(arqux_env, arqux_env.bp_id)
    # Claiming as governor (the static auth) after the switch
    result = claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert "blueprint.claim ok" in result.to_text(), result.to_text()
    assert result.fields["executor"] == "jarvis"
    assert _read_fm(arqux_env.proj_root, arqux_env.bp_id)["executor"] == "jarvis"


def test_claim_explicit_agent_id_governor(arqux_env) -> None:
    """Governor may explicitly assign the executor via agent_id."""
    _ready_bp(arqux_env, arqux_env.bp_id)
    result = claim_blueprint(
        arqux_env.bp_id,
        path=str(arqux_env.proj_root),
        agent_id="jarvis",
        ctx=arqux_env.gov_ctx,
    )
    assert "blueprint.claim ok" in result.to_text(), result.to_text()
    assert result.fields["executor"] == "jarvis"


def test_claim_explicit_agent_id_requires_governor(arqux_env) -> None:
    """Executors cannot assign a different executor via agent_id."""
    _write_context(arqux_env.ws_root, "jarvis")
    _ready_bp(arqux_env, arqux_env.bp_id)
    result = claim_blueprint(
        arqux_env.bp_id,
        path=str(arqux_env.proj_root),
        agent_id="somebody",
        ctx=arqux_env.exec_ctx,
    )
    assert result.profile == OUT_ERROR
    assert PERMISSION_DENIED in result.to_text()


def test_claim_executor_env_resolution(arqux_env) -> None:
    """Executor claiming with no context pointer keeps env resolution."""
    _ready_bp(arqux_env, arqux_env.bp_id)
    result = claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
    assert result.fields["executor"] == "test-executor"


def test_claim_no_context_falls_back_to_env(arqux_env) -> None:
    """Without context.cortex, claim resolves from the caller's ctx (legacy)."""
    _ready_bp(arqux_env, arqux_env.bp_id)
    result = claim_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert result.fields["executor"] == "test-governor"


def test_claim_declared_executor_respected(arqux_env) -> None:
    """Blueprint declaring executor + governor caller → declaration wins."""
    bp_id = arqux_env.bp_id
    _set_fm(arqux_env.proj_root, bp_id, "executor", "jarvis")
    _ready_bp(arqux_env, bp_id)
    result = claim_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert "blueprint.claim ok" in result.to_text(), result.to_text()
    assert result.fields["executor"] == "jarvis"


def test_claim_declared_executor_beats_context(arqux_env) -> None:
    """Declared executor wins over a divergent context pointer."""
    bp_id = arqux_env.bp_id
    _write_context(arqux_env.ws_root, "heimdall")
    _set_fm(arqux_env.proj_root, bp_id, "executor", "jarvis")
    _ready_bp(arqux_env, bp_id)
    result = claim_blueprint(bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx)
    assert result.fields["executor"] == "jarvis"
