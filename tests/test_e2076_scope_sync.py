"""E-2076 — session scope did not follow the active BLP.

``session.context.set`` binds a BLP once; a later ``blueprint.ready``/
``blueprint.claim`` activated another blueprint but left the pointer
behind (SES001 in CODEC-CORTEX stayed on BLP-004 while the work was
BLP-006). ready/claim now update the per-execution context pointer and
report ``stale_scope`` when the previous one diverged.
"""

from __future__ import annotations

from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint
from arqux.handlers.session import context_get, context_set


def _fill(env) -> None:
    from arqux.handlers.blueprint.lifecycle import _pending_placeholders

    bp_file = (
        env.proj_root / ".arqux" / "cycles" / env.cycle_id
        / "blueprints" / f"{env.bp_id}.md"
    )
    for marker in _pending_placeholders(bp_file, env.proj_root):
        text = bp_file.read_text(encoding="utf-8")
        bp_file.write_text(text.replace(marker, "filled"), encoding="utf-8")


def _bind(env, blp: str = "BLP-OLD") -> None:
    out = context_set(
        project="test-proj", scope=env.cycle_id, blp=blp,
        path=str(env.ws_root), ctx=env.exec_ctx,
    )
    assert out.profile == "OUT-WORK", out.to_text()


class TestScopeFollowsBlp:
    def test_ready_updates_context_blp_and_flags_stale(self, arqux_env):
        _fill(arqux_env)
        _bind(arqux_env, blp="BLP-OLD")

        out = ready_blueprint(
            arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx
        )
        assert out.profile == "OUT-WORK", out
        assert out.fields["context_blp_synced"] is True
        assert out.fields["stale_scope"] is True
        assert out.fields["previous_blp"] == "BLP-OLD"

        ctx = context_get(path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
        assert ctx.fields["blp"] == arqux_env.bp_id

    def test_claim_updates_context_blp(self, arqux_env):
        _fill(arqux_env)
        ready_blueprint(arqux_env.bp_id, path=str(arqux_env.proj_root),
                        ctx=arqux_env.gov_ctx)
        # Rebind with a stale BLP after ready — claim must realign it.
        _bind(arqux_env, blp="BLP-OTHER")

        out = claim_blueprint(
            arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx
        )
        assert out.profile == "OUT-WORK", out
        assert out.fields["context_blp_synced"] is True
        assert out.fields["previous_blp"] == "BLP-OTHER"

        ctx = context_get(path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx)
        assert ctx.fields["blp"] == arqux_env.bp_id
        assert ctx.fields["scope"] == arqux_env.cycle_id

    def test_aligned_pointer_is_not_rewritten(self, arqux_env):
        _fill(arqux_env)
        _bind(arqux_env, blp=arqux_env.bp_id)

        out = ready_blueprint(
            arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx
        )
        assert out.profile == "OUT-WORK", out
        assert out.fields["context_blp_synced"] is False
        assert out.fields["stale_scope"] is False

    def test_no_context_is_a_noop(self, arqux_env):
        _fill(arqux_env)
        out = ready_blueprint(
            arqux_env.bp_id, path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx
        )
        assert out.profile == "OUT-WORK", out
        assert out.fields["context_blp_synced"] is False
