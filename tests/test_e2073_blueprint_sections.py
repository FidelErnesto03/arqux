"""E-2073 — blueprints accepted content in the wrong sections.

BLP-005/BLP-006 in CODEC-CORTEX ended with tasks in §7, risks in §9 and
ACs in §10; ``blueprint.task T-6.2`` then answered a bare NOT_FOUND.
The update path now rejects content whose shape belongs to another
section, and blueprint.task reports where a task actually lives.
"""

from __future__ import annotations

from arqux.handlers.blueprint.lifecycle import claim_blueprint, ready_blueprint
from arqux.handlers.blueprint.manage import task_blueprint, update_blueprint


def _make_in_progress(env) -> None:

    bp_file = (
        env.proj_root / ".arqux" / "cycles" / env.cycle_id
        / "blueprints" / f"{env.bp_id}.md"
    )
    from arqux.handlers.blueprint.lifecycle import _pending_placeholders

    for marker in _pending_placeholders(bp_file, env.proj_root):
        text = bp_file.read_text(encoding="utf-8")
        bp_file.write_text(text.replace(marker, "filled"), encoding="utf-8")
    ready_blueprint(env.bp_id, path=str(env.proj_root), ctx=env.gov_ctx)
    claim_blueprint(env.bp_id, path=str(env.proj_root), ctx=env.exec_ctx)


class TestSectionShapeGuard:
    def test_task_lines_outside_14_are_rejected(self, arqux_env):
        out = update_blueprint(
            arqux_env.bp_id, section="7",
            content="Reglas:\n- [ ] **T-7.1:** tarea infiltrada",
            path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
        )
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "INVALID_ARGS"
        assert "§14" in out.message

    def test_ac_rows_outside_12_are_rejected(self, arqux_env):
        out = update_blueprint(
            arqux_env.bp_id, section="10",
            content="| AC-1 | criterio | consulta | pending |",
            path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
        )
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "INVALID_ARGS"
        assert "§12" in out.message

    def test_task_lines_inside_14_are_accepted(self, arqux_env):
        out = update_blueprint(
            arqux_env.bp_id, section="14",
            content="- [ ] **T-14.1:** tarea legítima",
            path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
        )
        assert out.profile == "OUT-WORK", out

    def test_prose_sections_still_pass(self, arqux_env):
        out = update_blueprint(
            arqux_env.bp_id, section="5",
            content="Contexto narrativo sin checklists ni tablas de AC.",
            path=str(arqux_env.proj_root), ctx=arqux_env.gov_ctx,
        )
        assert out.profile == "OUT-WORK", out


class TestTaskLookupReportsOriginSection:
    def test_task_in_wrong_section_reports_where_it_lives(self, arqux_env):
        _make_in_progress(arqux_env)
        bp_file = (
            arqux_env.proj_root / ".arqux" / "cycles" / arqux_env.cycle_id
            / "blueprints" / f"{arqux_env.bp_id}.md"
        )
        body = bp_file.read_text(encoding="utf-8")
        # Simulate the legacy corruption: task id referenced inside §7.
        anchor = "<!-- BLP:7 -->"
        assert anchor in body
        body = body.replace(
            anchor, anchor + "\nRegla: completar T-6.2 antes del cierre.\n", 1
        )
        bp_file.write_text(body, encoding="utf-8")

        out = task_blueprint(
            arqux_env.bp_id, "T-6.2", "completed",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "NOT_FOUND"
        assert out.fields["found_in_section"] == "7"
        assert "§7" in out.message

    def test_unknown_task_keeps_plain_not_found(self, arqux_env):
        _make_in_progress(arqux_env)
        out = task_blueprint(
            arqux_env.bp_id, "T-9.9", "completed",
            path=str(arqux_env.proj_root), ctx=arqux_env.exec_ctx,
        )
        assert out.profile == "OUT-ERROR", out
        assert out.fields["code"] == "NOT_FOUND"
        assert "found_in_section" not in out.fields
