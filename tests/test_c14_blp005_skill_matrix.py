"""CYCLE-14 / BLP-005 — timeline instructions in the existing skill matrix.

Covers AC-01 to AC-07 (AC-08 is the independent review). These are consistency
checks over the distributed and effective copies, not new behaviour.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SRC_MATRIX = PACKAGE / "src" / "arqux" / "skills" / "protocol.skill.md"
SRC_GUIDES = PACKAGE / "src" / "arqux" / "guides.cortex"
EFFECTIVE_MATRIX = PACKAGE.parent / ".arqux" / "skills" / "protocol.skill.md"

REQUIREMENTS = ("ses_real", "ruta_acordada", "inicio_conservado", "independencia",
                "limites_naturales", "consulta_control", "conjunto_cobertura")


class TestAc01MatrixIdentity:
    def test_distributed_and_effective_carry_the_section(self):
        assert SRC_MATRIX.exists() and EFFECTIVE_MATRIX.exists()
        for path in (SRC_MATRIX, EFFECTIVE_MATRIX):
            text = path.read_text(encoding="utf-8")
            assert "timelog_native" in text, path
            assert "$8: ACTIVIDAD & TIEMPO (CYCLE-14)" in text, path

    def test_no_new_skill_or_agents_file_was_created(self):
        assert not (PACKAGE / "src" / "arqux" / "skills" / "timelog.skill.md").exists()
        # AGENTS.md and its templates are untouched: they are reference only.
        for name in ("AGENTS.md", "AGENTS.lite.md", "AGENTS.full.md"):
            assert (PACKAGE / name).exists()

    def test_matrix_did_not_gain_a_second_glossary(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert text.count("$0: PROTOCOL SKILL GLOSSARY") == 1


class TestAc02SevenRequirements:
    def test_all_seven_requirements_are_present(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        for requirement in REQUIREMENTS:
            assert requirement in text, requirement

    def test_canonical_path_and_names_are_documented(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "SESXXX_yyyymmdd_hhmiss.cortex" in text
        assert ".arqux/timelog/" in text

    def test_real_session_and_preserved_start_are_documented(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "SES real" in text
        assert "inicio UTC original" in text

    def test_coverage_and_permission_exceptions_are_documented(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "coverage=limited" in text
        assert "auditor" in text


class TestAc03IsolatedInstallation:
    def test_packaged_source_is_self_contained(self):
        # The distributed copy is what an isolated install receives; the
        # timeline section must not depend on a development path.
        text = SRC_MATRIX.read_text(encoding="utf-8")
        section = text[text.index("$8: ACTIVIDAD"):]
        assert "/home/" not in section
        assert "timelog.query" in section

    def test_effective_copy_preserved_its_customizations(self):
        # The workspace copy carries local personalizations (the usage guide and
        # the timelog-compliance gate); the update must not have dropped them.
        text = EFFECTIVE_MATRIX.read_text(encoding="utf-8")
        assert "0_usage_guide" in text
        assert "timelog_gate" in text
        assert "timelog_native" in text

    def test_guides_corpus_is_single_source(self):
        assert SRC_GUIDES.exists()
        # guides.cortex is packaged once; it is never duplicated in .arqux.
        assert not (PACKAGE.parent / ".arqux" / "guides.cortex").exists()


class TestAc04NoDedicatedCalls:
    def test_matrix_forbids_dedicated_calls_and_stopwatches(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "timelog_no_dedicated_calls" in text
        assert "NO arranca cronometros" in text

    def test_guide_measures_cost_honestly(self):
        text = SRC_GUIDES.read_text(encoding="utf-8")
        assert "sin cronometros ni llamadas dedicadas" in text


class TestAc05LanguageAndJointWork:
    def test_matrix_keeps_joint_work_and_no_blame(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "unidad funcional" in text
        assert "ranking" not in text or "sin rankings" in text

    def test_language_rule_is_stated(self):
        assert "idioma de la sesion gobierna" in SRC_MATRIX.read_text(encoding="utf-8")


class TestAc06DiscoveryHonesty:
    def test_projection_is_marked_pending(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "PENDIENTE" in text and "BLP-006" in text

    def test_how_to_returns_the_timelog_guide(self):
        from arqux.handlers import REGISTRY

        out = REGISTRY["handler.how_to"].fn(intent="registro de tiempo")
        assert out.profile == "OUT-WORK"
        assert "timelog.query" in str(out.to_text())

    def test_guide_references_only_real_handlers(self):
        from arqux.handlers import REGISTRY

        text = SRC_GUIDES.read_text(encoding="utf-8")
        for handler in ("timelog.query", "timelog.review", "timelog.purge"):
            assert handler in REGISTRY
            assert handler in text

    def test_permissions_are_documented_with_the_matrix(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "timelog_permissions" in text


class TestAc07NoExternalEffects:
    def test_matrix_states_external_is_optional_and_inactive(self):
        text = SRC_MATRIX.read_text(encoding="utf-8")
        assert "timelog_external_optional" in text
        assert "no se activa en esta fase" in text

    def test_no_timer_or_provider_is_configured(self):
        for path in (SRC_MATRIX, SRC_GUIDES):
            text = path.read_text(encoding="utf-8").lower()
            assert "api_key" not in text
            assert "token=" not in text
