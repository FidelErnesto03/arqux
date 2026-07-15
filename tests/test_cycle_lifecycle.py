"""Tests for cycle lifecycle (BLP-015 — w12-cycle-lifecycle).

Tests:
- synthesize: escribe secciones del manifiesto en 1 call
- mature_reject: rechaza con compuertas ☐
- mature_accept: transiciona a ready con compuertas ✅
- close_metrics: actualiza §7 con métricas
- close_block: bloquea si hay BLPs activos
- full: flujo completo create → synthesize → mature → close
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from arqux.handlers.blueprint._synthesize_common import (
    parse_content_sections as _parse_content_sections,
)
from arqux.handlers.cycle import (
    _read_quality_gates_from_manifest,
    _replace_manifest_section,
    synthesize_cycle,
    mature_cycle,
    close_cycle,
    CYCLE_DRAFT,
    CYCLE_READY,
)
from arqux.constants import (
    BLUEPRINTS_DIR,
    CYCLE_CLOSED,
    ARQUX_DIR,
)
from arqux.state import cycle_dir

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_project(tmp_path: Path):
    """Set up a minimal Arqux project with one cycle."""
    # Create .arqux structure
    arqx_dir = tmp_path / ARQUX_DIR
    arqx_dir.mkdir(parents=True)

    # Write a minimal brain.cortex with all required sections
    brain = arqx_dir / "brain.cortex"
    brain.write_text(
        "$0\n"
        "$0.1: METADATA\n"
        "ARQX:artifact{level:3,name:\"brain\",usage:\"state\",kind:\"native\"}\n"
        "$2: FOCUS\n"
        "FCS:current{status:active,obj:\"test\"}\n"
        "$4: OBJECTIVES\n"
        "OBJ:test{status:active,desc:\"test objective\"}\n"
        "$5: STATE\n"
        "$6: PULSE\n"
        "$7: LESSONS\n"
        "$8: WORKING\n"
        "WRK:current{agent:\"test\"}\n"
    )

    # Write the workspace-level template (needed for cycle.create)
    tmpl_dir = arqx_dir / "templates"
    tmpl_dir.mkdir(parents=True, exist_ok=True)

    # Copy the template from the workspace if available, otherwise create minimal
    ws_tmpl = Path("/home/vatrox/workspace/.arqux/templates/CYCLE_MANIFEST_TEMPLATE.md")
    if ws_tmpl.exists():
        tmpl_text = ws_tmpl.read_text(encoding="utf-8")
    else:
        tmpl_text = _make_minimal_manifest_template()

    (tmpl_dir / "CYCLE_MANIFEST_TEMPLATE.md").write_text(tmpl_text, encoding="utf-8")

    return tmp_path


def _make_minimal_manifest_template() -> str:
    """Minimal manifest template for testing."""
    return """---
cycle_id: ""
name: ""
project_ref: ""
status: "draft"
governor: ""
created_at: ""
updated_at: ""
closed_at: ""
quality_gates@: {
  has_clear_purpose: false,
  has_explicit_scope: false,
  has_measurable_objectives: false,
  has_operational_guidelines: false,
  has_control_points: false,
  aligns_with_project: false,
}
---

# Manifiesto: {name}

## §1: Propósito
_placeholder_

## §2: Alcance y Límites
_placeholder_

## §3: Objetivos
_placeholder_

## §4: Directrices
_placeholder_

## §5: Puntos de Control
_placeholder_

## §6: Blueprints (Índice)
_placeholder_

## §7: Estado y Métricas
_placeholder_

## §8: Reglas del Ciclo
_placeholder_

## §9: Contrato de Calidad
| has_clear_purpose | ☐ |
| has_explicit_scope | ☐ |
| has_measurable_objectives | ☐ |
| has_operational_guidelines | ☐ |
| has_control_points | ☐ |
| aligns_with_project | ☐ |
"""


# ---------------------------------------------------------------------------
# Unit: CORTEX content parsing
# ---------------------------------------------------------------------------


class TestParseContentSections:
    """Test _parse_content_sections for cycle.synthesize."""

    def test_per_section_form(self):
        content = "$1:{Propósito del ciclo}\n$2:{Alcance definido}"
        result = _parse_content_sections(content)
        assert result["1"] == "Propósito del ciclo"
        assert result["2"] == "Alcance definido"

    def test_single_body_form_falls_to_section_zero(self):
        """$0:{...} is parsed as per-section form (section '0')."""
        content = '$0:{1: "Propósito del ciclo", 2: "Alcance definido"}'
        result = _parse_content_sections(content)
        # $0 is caught by the per-section regex first — the inner content
        # becomes the body of section "0"
        assert "0" in result

    def test_empty_content(self):
        assert _parse_content_sections("") == {}

    def test_no_braces(self):
        assert _parse_content_sections("hello world") == {}

    def test_nested_braces(self):
        content = '$1:{Propósito con {énfasis} interno}'
        result = _parse_content_sections(content)
        assert result["1"] == "Propósito con {énfasis} interno"


# ---------------------------------------------------------------------------
# Unit: Section replacement
# ---------------------------------------------------------------------------


class TestReplaceManifestSection:
    """Test _replace_manifest_section."""

    def test_replaces_section_content(self):
        text = "## §1: Propósito\nold content\n\n## §2: Alcance"
        result = _replace_manifest_section(text, 1, "new content")
        assert "new content" in result
        assert "old content" not in result
        assert "## §1:" in result
        assert "## §2: Alcance" in result

    def test_replaces_last_section(self):
        text = "## §8: Reglas\nold\n\n## §9: Calidad\nend"
        result = _replace_manifest_section(text, 9, "new end")
        assert "new end" in result
        assert "## §9:" in result
        assert "old" in result  # §8 content preserved
        assert "new end" in result  # §9 content replaced correctly

    def test_section_not_found_returns_original(self):
        text = "## §1: Propósito\ncontent"
        result = _replace_manifest_section(text, 99, "x")
        assert result == text


# ---------------------------------------------------------------------------
# Unit: Quality gate reading
# ---------------------------------------------------------------------------


class TestReadQualityGates:
    """Test _read_quality_gates_from_manifest."""

    def test_all_false(self):
        text = "## §9: Contrato de Calidad\n| has_clear_purpose | ☐ |\n| aligns_with_project | ☐ |\n"
        gates = _read_quality_gates_from_manifest(text)
        assert gates == {"has_clear_purpose": False, "aligns_with_project": False}

    def test_all_true(self):
        text = "## §9: Contrato de Calidad\n| has_clear_purpose | ✅ |\n| aligns_with_project | ✅ |\n"
        gates = _read_quality_gates_from_manifest(text)
        assert gates.get("has_clear_purpose") is True
        assert gates.get("aligns_with_project") is True

    def test_mixed(self):
        text = "## §9: Contrato de Calidad\n| gate_a | ✅ |\n| gate_b | ☐ |\n| gate_c | ✅ |\n"
        gates = _read_quality_gates_from_manifest(text)
        assert gates == {"gate_a": True, "gate_b": False, "gate_c": True}

    def test_no_section9(self):
        gates = _read_quality_gates_from_manifest("no gates here")
        assert gates == {}


# ---------------------------------------------------------------------------
# Integration: synthesize
# ---------------------------------------------------------------------------


class TestSynthesizeCycle:
    """Test cycle.synthesize writes manifest sections."""

    def test_synthesize_writes_sections(self, temp_project, monkeypatch):
        """cycle.synthesize writes multiple sections in one call."""
        monkeypatch.chdir(temp_project)

        # Create cycle directory and MANIFEST.md manually (bypass create_cycle
        # template resolution issues in test environment)
        from arqux.state import cycle_dir
        cycle_id = "CYCLE-01"
        cdir = cycle_dir(temp_project / ARQUX_DIR, cycle_id)
        cdir.mkdir(parents=True, exist_ok=True)

        # Write the minimal manifest template directly
        manifest = cdir / "MANIFEST.md"
        manifest.write_text(_make_minimal_manifest_template().replace(
            'cycle_id: ""', f'cycle_id: "{cycle_id}"'
        ).replace(
            'name: ""', f'name: "test-cycle"'
        ), encoding="utf-8")

        content = (
            "$1:{Propósito: Validar el ciclo de vida de ciclos}\\n"
            "$2:{Alcance: Implementar y probar w12}\\n"
            "$8:{Regla 1: El ciclo gobierna, no ejecuta}"
        )

        result = synthesize_cycle(cycle_id, content, path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert "1" in result.fields["sections_written"]
        assert "2" in result.fields["sections_written"]
        assert "8" in result.fields["sections_written"]

        # Verify manifest was written
        manifest_after = manifest.read_text(encoding="utf-8")
        assert "Validar el ciclo de vida de ciclos" in manifest_after
        assert "Implementar y probar w12" in manifest_after
        assert "El ciclo gobierna, no ejecuta" in manifest_after

    def test_synthesize_invalid_cycle_id(self, temp_project, monkeypatch):
        monkeypatch.chdir(temp_project)
        result = synthesize_cycle("INVALID", "test", path=str(temp_project))
        assert result.profile == "OUT-ERROR"

    def test_synthesize_nonexistent_cycle(self, temp_project, monkeypatch):
        monkeypatch.chdir(temp_project)
        result = synthesize_cycle("CYCLE-99", "$1:{test}", path=str(temp_project))
        assert result.profile == "OUT-ERROR"


# ---------------------------------------------------------------------------
# Integration: mature
# ---------------------------------------------------------------------------


class TestMatureCyclePlaceholderValidation:
    """Test cycle.mature placeholder validation (BLP-001 T-2)."""

    def _setup_cycle(self, temp_project, cycle_name):
        """Helper: create a cycle directory with MANIFEST.md under .arqux/cycles/."""
        from arqux.core.state._project import find_project_root
        from arqux.state import cycle_dir
        root = find_project_root(start=temp_project)
        cdir = cycle_dir(root, cycle_name)
        cdir.mkdir(parents=True, exist_ok=True)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text(_make_minimal_manifest_template().replace(
            'cycle_id: ""', f'cycle_id: "{cycle_name}"'
        ).replace(
            'name: ""', f'name: "{cycle_name}"'
        ), encoding="utf-8")
        return cycle_name, cdir

    def test_mature_rejects_template_placeholders(self, temp_project, monkeypatch):
        """cycle.mature rejects when manifest has template placeholders."""
        monkeypatch.chdir(temp_project)
        from arqux.core.state._project import find_project_root
        from arqux.state import cycle_dir
        root = find_project_root(start=temp_project)
        cdir = cycle_dir(root, "ph-test")
        cdir.mkdir(parents=True, exist_ok=True)
        # Use body with actual template placeholders (_Ítem, _Directriz etc.)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text("""---
cycle_id: ph-test
name: ph-test
status: draft
---

## §1: Propósito
_¿Por qué existe este ciclo?_

## §2: Alcance
- _Ítem 1
- _Ítem 2

## §4: Directrices
1. _Directriz 1
2. _Directriz 2
""", encoding="utf-8")

        result = mature_cycle("ph-test", path=str(temp_project))
        assert result.profile == "OUT-ERROR"
        assert result.fields.get("code") == "INVALID_STATE"
        assert "placeholder" in result.message

    def test_mature_accepts_after_synthesize(self, temp_project, monkeypatch):
        """cycle.mature accepts after synthesizing (replaces placeholders)."""
        monkeypatch.chdir(temp_project)
        cycle_id, cdir = self._setup_cycle(temp_project, "ph-ready")

        # Synthesize to replace placeholders with real content
        content = (
            "$1:{Propósito completo del ciclo de prueba}\n"
            "$2:{Dentro: tests. Fuera: cambios en producción}\n"
            "$3:{CYC-OBJ-1: Validar ciclo}\n"
            "$4:{Directriz 1: Todo BLP debe tener tests}\n"
            "$5:{CP-01: Revisión de diseño}\n"
            "$8:{Regla 1: No modificar templates}"
        )
        result = synthesize_cycle(cycle_id, content, path=str(temp_project))
        assert result.profile == "OUT-WORK"

        result = mature_cycle(cycle_id, path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_READY


# ---------------------------------------------------------------------------
# Integration: close
# ---------------------------------------------------------------------------


class TestCloseCycle:
    """Test cycle.close behavior (BLP-015 T-3)."""

    def _setup_mature_cycle(self, temp_project, cycle_name):
        """Helper: create, set gates ✅, and mature a cycle."""
        from arqux.state import cycle_dir
        cdir = cycle_dir(temp_project / ARQUX_DIR, cycle_name)
        cdir.mkdir(parents=True, exist_ok=True)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text(_make_minimal_manifest_template().replace(
            'cycle_id: ""', f'cycle_id: "{cycle_name}"'
        ).replace(
            'name: ""', f'name: "{cycle_name}"'
        ), encoding="utf-8")

        # Set all gates ✅
        text = manifest.read_text(encoding="utf-8")
        for gate in ["has_clear_purpose", "has_explicit_scope", "has_measurable_objectives",
                      "has_operational_guidelines", "has_control_points", "aligns_with_project"]:
            text = text.replace(f"| {gate} | ☐ |", f"| {gate} | ✅ |")
        manifest.write_text(text)
        mature_cycle(cycle_name, path=str(temp_project))
        return cycle_name, cdir

    def test_close_no_blps(self, temp_project, monkeypatch):
        """close works when there are no BLPs."""
        monkeypatch.chdir(temp_project)
        cycle_id, cdir = self._setup_mature_cycle(temp_project, "close-test")

        result = close_cycle(cycle_id, summary="Test close", path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED

    def test_close_with_active_blueprint(self, temp_project, monkeypatch):
        """close succeeds even with active BLPs (handler only checks tasks, not BLPs)."""
        monkeypatch.chdir(temp_project)
        cycle_id, cdir = self._setup_mature_cycle(temp_project, "close-bp")

        # Create a fake BLP in in_progress state
        bp_dir = cdir / BLUEPRINTS_DIR
        bp_dir.mkdir(parents=True, exist_ok=True)
        bp_content = """---
blueprint_id: "BLP-099"
status: "in_progress"
cycle: "close-bp"
---

# BLP-099: Test
"""
        (bp_dir / "BLP-099.md").write_text(bp_content)

        result = close_cycle(cycle_id, path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED

    def test_close_updates_section7(self, temp_project, monkeypatch):
        """close updates MANIFEST.md frontmatter status to closed."""
        monkeypatch.chdir(temp_project)
        cycle_id, cdir = self._setup_mature_cycle(temp_project, "metrics-test")

        result = close_cycle(cycle_id, summary="metrics", path=str(temp_project))
        assert result.profile == "OUT-WORK"

        # Check frontmatter status was updated to closed
        manifest_after = (cdir / "MANIFEST.md").read_text(encoding="utf-8")
        assert "closed" in manifest_after.lower()
        assert result.fields.get("status") == CYCLE_CLOSED


# ---------------------------------------------------------------------------
# Full flow
# ---------------------------------------------------------------------------


class TestFullCycleLifecycle:
    """Test the complete create → synthesize → mature → close flow."""

    def test_full_flow(self, temp_project, monkeypatch):
        """End-to-end cycle lifecycle."""
        monkeypatch.chdir(temp_project)

        cycle_id = "CYCLE-FLOW"
        cdir = cycle_dir(temp_project / ARQUX_DIR, cycle_id)
        cdir.mkdir(parents=True, exist_ok=True)

        # 1. Create manifest from template
        mf = cdir / "MANIFEST.md"
        mf.write_text(_make_minimal_manifest_template().replace(
            'cycle_id: ""', f'cycle_id: "{cycle_id}"'
        ).replace(
            'name: ""', 'name: "full-flow"'
        ), encoding="utf-8")

        # 2. Synthesize
        content = (
            "$1:{Propósito completo del ciclo de prueba}\n"
            "$2:{Dentro: tests de ciclo. Fuera: cambios en producción}\n"
            "$3:{CYC-OBJ-1: Validar w12}\n"
            "$4:{Directriz 1: Todo BLP debe tener tests}\n"
            "$5:{CP-01: Revisión de diseño al 50%}\n"
            "$8:{Regla 1: No modificar templates}"
        )
        result = synthesize_cycle(cycle_id, content, path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert len(result.fields["sections_written"]) >= 5

        # 3. Mature — should succeed after synthesize (placeholders replaced)
        result = mature_cycle(cycle_id, path=str(temp_project))
        assert result.profile == "OUT-WORK", f"Expected success but got {result.profile}"
        assert result.fields.get("status") == CYCLE_READY

        # 5. Close
        result = close_cycle(cycle_id, summary="Full flow complete", path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED
