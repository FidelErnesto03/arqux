"""E-2074 — blueprint.ac left live FAIL notes under verified ACs.

BLP-007 AC-4/5/6 in CODEC-CORTEX showed ``[x]`` + ``Verified:`` plus the
earlier ``FAIL:`` notes still standing — a record that contradicts
itself. Verification now stamps each prior FAIL note as superseded
while keeping it in history.
"""

from __future__ import annotations

from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint
from arqux.handlers.blueprint.manage import update_blueprint
from arqux.handlers.blueprint.review import ac_blueprint


def _make_in_progress(env) -> None:
    from arqux.handlers.blueprint.lifecycle import _pending_placeholders

    bp_file = _bp_file(env)
    for marker in _pending_placeholders(bp_file, env.proj_root):
        text = bp_file.read_text(encoding="utf-8")
        bp_file.write_text(text.replace(marker, "filled"), encoding="utf-8")
    ready_blueprint(env.bp_id, path=str(env.proj_root), ctx=env.gov_ctx)
    claim_blueprint(env.bp_id, path=str(env.proj_root), ctx=env.exec_ctx)


def _bp_file(env):
    return (
        env.proj_root / ".arqux" / "cycles" / env.cycle_id
        / "blueprints" / f"{env.bp_id}.md"
    )


def _body(env) -> str:
    return _bp_file(env).read_text(encoding="utf-8").split("---", 2)[2]


def _seed_ac(env) -> None:
    update_blueprint(
        env.bp_id, section="12",
        content="- [ ] **AC-01:** criterion under test",
        path=str(env.proj_root), ctx=env.gov_ctx,
    )


class TestSupersede:
    def test_verify_after_fail_supersedes_the_note(self, arqux_env):
        _seed_ac(arqux_env)
        _make_in_progress(arqux_env)

        ac_blueprint(
            arqux_env.bp_id, "AC-01", "failed", reason="first audit",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        assert "FAIL: first audit" in _body(arqux_env)

        out = ac_blueprint(
            arqux_env.bp_id, "AC-01", "verified", evidence="re-audit pass",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        assert out.profile == "OUT-WORK", out

        body = _body(arqux_env)
        assert "- [x] **AC-01:**" in body
        assert "Verified: re-audit pass" in body
        assert "FAIL: first audit (superseded — verified at" in body

    def test_verify_without_prior_fail_is_unchanged(self, arqux_env):
        _seed_ac(arqux_env)
        _make_in_progress(arqux_env)

        ac_blueprint(
            arqux_env.bp_id, "AC-01", "verified", evidence="clean pass",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        body = _body(arqux_env)
        assert "superseded" not in body
        assert "Verified: clean pass" in body

    def test_history_is_preserved(self, arqux_env):
        _seed_ac(arqux_env)
        _make_in_progress(arqux_env)
        ac_blueprint(
            arqux_env.bp_id, "AC-01", "failed", reason="audit one",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        ac_blueprint(
            arqux_env.bp_id, "AC-01", "failed", reason="audit two",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        ac_blueprint(
            arqux_env.bp_id, "AC-01", "verified", evidence="final pass",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        body = _body(arqux_env)
        assert "FAIL: audit one (superseded" in body
        assert "FAIL: audit two (superseded" in body
        assert "Verified: final pass" in body
