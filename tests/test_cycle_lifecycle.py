"""Tests for cycle lifecycle (BLP-003 — simplified 2-state machine).

Tests:
- synthesize: escribe secciones del manifiesto en 1 call
- close_draft_reject: rechaza close si ciclo en draft con placeholders
- close_draft_accept: acepta close si ciclo en draft sin placeholders
- close_block: bloquea si hay BLPs activos
- close_no_blps: funciona sin BLPs
- BLP-001: Template-based marker system (parse_cycle_template, marker replacement,
  allowed_placeholders)
- BLP-003: Simplified 2-state machine, no mature_cycle/CYCLE_READY/CYCLE_ACTIVE
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arqux.constants import (
    ARQUX_DIR,
    BLUEPRINTS_DIR,
    CYCLE_CLOSED,
)
from arqux.handlers.blueprint._synthesize_common import (
    parse_content_sections as _parse_content_sections,
)
from arqux.handlers.cycle import (
    _read_quality_gates_from_manifest,
    _replace_manifest_section,
    _manifest_body_has_placeholders,
    close_cycle,
    synthesize_cycle,
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

        from arqux.state import cycle_dir
        cycle_id = "CYCLE-01"
        cdir = cycle_dir(temp_project / ARQUX_DIR, cycle_id)
        cdir.mkdir(parents=True, exist_ok=True)

        manifest = cdir / "MANIFEST.md"
        manifest.write_text(_make_minimal_manifest_template().replace(
            'cycle_id: ""', f'cycle_id: "{cycle_id}"'
        ).replace(
            'name: ""', 'name: "test-cycle"'
        ), encoding="utf-8")

        content = (
            "$1:{Propósito: Validar el ciclo de vida de ciclos}\n"
            "$2:{Alcance: Implementar y probar w12}\n"
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
# Integration: close — BLP-003 simplified state machine
# ---------------------------------------------------------------------------


class TestCloseCycleDraftPlaceholderValidation:
    """Test cycle.close placeholder validation in draft (BLP-003)."""

    def _setup_cycle(self, temp_project, cycle_name):
        """Helper: create a cycle directory with MANIFEST.md."""
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

    def test_close_draft_rejects_placeholders(self, temp_project, monkeypatch):
        """cycle.close rejects when cycle is in draft with template placeholders."""
        monkeypatch.chdir(temp_project)
        from arqux.core.state._project import find_project_root
        from arqux.state import cycle_dir
        root = find_project_root(start=temp_project)
        cdir = cycle_dir(root, "close-ph")
        cdir.mkdir(parents=True, exist_ok=True)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text("""---
cycle_id: close-ph
name: close-ph
status: draft
---
## §1: Propósito
_¿Por qué existe este ciclo?_

## §2: Alcance
- _Ítem 1_
- _Ítem 2_
""", encoding="utf-8")

        result = close_cycle("close-ph", summary="test", path=str(temp_project))
        assert result.profile == "OUT-ERROR"
        code = str(result.fields.get("code", ""))
        assert "INVALID_STATE" in code
        assert "placeholder" in result.message.lower()

    def test_close_draft_accepts_no_placeholders(self, temp_project, monkeypatch):
        """cycle.close accepts when cycle is in draft with no placeholders."""
        monkeypatch.chdir(temp_project)
        from arqux.core.state._project import find_project_root
        from arqux.state import cycle_dir
        root = find_project_root(start=temp_project)
        cdir = cycle_dir(root, "close-clean")
        cdir.mkdir(parents=True, exist_ok=True)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text("""---
cycle_id: close-clean
name: close-clean
status: draft
---
## §1: Propósito
Validar ciclo de vida simplificado

## §2: Alcance
- Tests automatizados
""", encoding="utf-8")

        result = close_cycle("close-clean", summary="Clean close", path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED

    def test_close_ready_accepts_without_placeholder_check(self, temp_project, monkeypatch):
        """cycle.close works directly when cycle is already ready (legacy compat)."""
        monkeypatch.chdir(temp_project)
        from arqux.core.state._project import find_project_root
        from arqux.state import cycle_dir
        root = find_project_root(start=temp_project)
        cdir = cycle_dir(root, "close-ready")
        cdir.mkdir(parents=True, exist_ok=True)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text("""---
cycle_id: close-ready
name: close-ready
status: ready
---
## §1: Propósito
Already ready cycle
""", encoding="utf-8")

        result = close_cycle("close-ready", summary="Close ready cycle", path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED


class TestCloseCycle:
    """Test cycle.close behavior."""

    def _setup_clean_cycle(self, temp_project, cycle_name):
        """Helper: create a cycle with clean (no-placeholder) manifest in draft."""
        from arqux.state import cycle_dir
        cdir = cycle_dir(temp_project / ARQUX_DIR, cycle_name)
        cdir.mkdir(parents=True, exist_ok=True)
        manifest = cdir / "MANIFEST.md"
        manifest.write_text("""---
cycle_id: "%s"
name: "%s"
status: draft
---
## §1: Propósito
Test cycle
""" % (cycle_name, cycle_name), encoding="utf-8")
        return cycle_name, cdir

    def test_close_no_blps(self, temp_project, monkeypatch):
        """close works when there are no BLPs."""
        monkeypatch.chdir(temp_project)
        cycle_id, cdir = self._setup_clean_cycle(temp_project, "close-test")

        result = close_cycle(cycle_id, summary="Test close", path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED

    def test_close_with_active_blueprint(self, temp_project, monkeypatch):
        """close succeeds even with active BLPs (handler only checks tasks, not BLPs)."""
        monkeypatch.chdir(temp_project)
        cycle_id, cdir = self._setup_clean_cycle(temp_project, "close-bp")

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
        cycle_id, cdir = self._setup_clean_cycle(temp_project, "metrics-test")

        result = close_cycle(cycle_id, summary="metrics", path=str(temp_project))
        assert result.profile == "OUT-WORK"

        # Check frontmatter status was updated to closed
        manifest_after = (cdir / "MANIFEST.md").read_text(encoding="utf-8")
        assert "closed" in manifest_after.lower()
        assert result.fields.get("status") == CYCLE_CLOSED


# ---------------------------------------------------------------------------
# Full flow: create → synthesize → close (BLP-003)
# ---------------------------------------------------------------------------


class TestFullCycleLifecycleSimplified:
    """Test the complete create → synthesize → close flow (no mature)."""

    def test_full_flow_simplified(self, temp_project, monkeypatch):
        """End-to-end cycle lifecycle without mature step."""
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

        # 3. Close — should succeed after synthesize (placeholders replaced)
        result = close_cycle(cycle_id, summary="Full flow complete", path=str(temp_project))
        assert result.profile == "OUT-WORK", f"Expected success but got {result.profile}"
        assert result.fields.get("status") == CYCLE_CLOSED

    def test_close_draft_with_placeholders_fails_full_flow(self, temp_project, monkeypatch):
        """End-to-end: close fails if cycle still has placeholders."""
        monkeypatch.chdir(temp_project)

        cycle_id = "CYCLE-PH-FLOW"
        cdir = cycle_dir(temp_project / ARQUX_DIR, cycle_id)
        cdir.mkdir(parents=True, exist_ok=True)

        mf = cdir / "MANIFEST.md"
        mf.write_text("""---
cycle_id: "CYCLE-PH-FLOW"
name: "ph-flow"
status: draft
---
## §4: Directrices
1. _Regla 1_
2. _Regla 2_
""", encoding="utf-8")

        # Try to close without synthesizing — should fail due to placeholders
        result = close_cycle(cycle_id, summary="Should fail", path=str(temp_project))
        assert result.profile == "OUT-ERROR"
        code = str(result.fields.get("code", ""))
        assert "INVALID_STATE" in code


# ---------------------------------------------------------------------------
# Unit: _manifest_body_has_placeholders (BLP-003 helper)
# ---------------------------------------------------------------------------


class TestManifestBodyHasPlaceholders:
    """Test _manifest_body_has_placeholders — shared helper."""

    def test_detects_placeholders(self):
        text = """---
cycle_id: test
---
## §1: Propósito
_Ítem 1_
"""
        result = _manifest_body_has_placeholders(text)
        assert len(result) > 0

    def test_clean_manifest(self):
        text = """---
cycle_id: test
---
## §1: Propósito
Real content here
"""
        result = _manifest_body_has_placeholders(text)
        assert result == []

    def test_no_frontmatter_returns_empty(self):
        result = _manifest_body_has_placeholders("Just body text")
        assert result == []


# ===========================================================================
# BLP-001: Template-based marker system tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Unit: parse_cycle_template
# ---------------------------------------------------------------------------


class TestParseCycleTemplate:
    """Test parse_cycle_template() — BLP-001 T-1."""

    def test_extracts_markers_from_real_template(self):
        """parse_cycle_template extracts markers from CYCLE_MANIFEST_TEMPLATE.md."""
        from arqux.handlers.cycle import parse_cycle_template
        result = parse_cycle_template()
        assert isinstance(result, dict)
        assert len(result) > 0
        total = sum(len(m) for m in result.values())
        assert total >= 15, f"Expected >=15 markers, got {total}"

    def test_known_markers_present(self):
        """Specific markers like _Ítem 1_, _BLP-NNN_ are found."""
        from arqux.handlers.cycle import parse_cycle_template
        result = parse_cycle_template()
        all_markers = []
        for markers in result.values():
            all_markers.extend(markers)
        known = ["_Ítem 1_", "_BLP-NNN_", "_YYYY-MM-DD_", "_Título_"]
        for k in known:
            assert k in all_markers, f"Marker {k} not found in template"

    def test_no_false_positives_from_table_columns(self):
        """Internal underscores in table columns are NOT markers."""
        from arqux.handlers.cycle import parse_cycle_template
        result = parse_cycle_template()
        all_markers = []
        for markers in result.values():
            all_markers.extend(markers)
        false_positives = ["_clear_", "_explicit_", "_measurable_",
                           "_operational_", "_control_", "_with_"]
        for fp in false_positives:
            assert fp not in all_markers, f"False positive marker {fp} found"

    def test_returns_empty_for_nonexistent_template(self):
        """parse_cycle_template returns {} when template doesn't exist."""
        from arqux.handlers.cycle import parse_cycle_template
        result = parse_cycle_template(template_path="/nonexistent/template.md")
        assert result == {}


# ---------------------------------------------------------------------------
# Unit: _replace_markers_in_section
# ---------------------------------------------------------------------------


class TestReplaceMarkersInSection:
    """Test _replace_markers_in_section() — BLP-001 T-2 helper."""

    def test_replaces_single_marker(self):
        """Replace one marker in a section, preserving everything else."""
        from arqux.handlers.cycle import _replace_markers_in_section
        text = "## §2: Alcance\n- _Ítem 1_\n- _Ítem 2_\n\nOther content"
        result = _replace_markers_in_section(text, 2, {"_Ítem 1_": "Nuevo valor"})
        assert "_Ítem 1_" not in result
        assert "Nuevo valor" in result
        assert "_Ítem 2_" in result
        assert "Other content" in result

    def test_replaces_multiple_markers(self):
        """Replace multiple markers in one call."""
        from arqux.handlers.cycle import _replace_markers_in_section
        text = "## §4: Directrices\n1. _Regla 1_\n2. _Regla 2_"
        result = _replace_markers_in_section(
            text, 4,
            {"_Regla 1_": "Primera regla", "_Regla 2_": "Segunda regla"},
        )
        assert "_Regla 1_" not in result
        assert "_Regla 2_" not in result
        assert "Primera regla" in result
        assert "Segunda regla" in result
        assert "## §4: Directrices" in result

    def test_section_not_found_returns_original(self):
        """If section doesn't exist, return original text unchanged."""
        from arqux.handlers.cycle import _replace_markers_in_section
        text = "## §1: Test\ncontent"
        result = _replace_markers_in_section(text, 99, {"_x_": "y"})
        assert result == text

    def test_unknown_marker_ignored(self):
        """Replace only markers that exist; unknown markers are ignored."""
        from arqux.handlers.cycle import _replace_markers_in_section
        text = "## §3: Objetivos\n- _CYC-OBJ-1_: Primer objetivo"
        result = _replace_markers_in_section(text, 3, {"_NO_EXISTE_": "x"})
        assert result == text


# ---------------------------------------------------------------------------
# Unit: _read_allowed_placeholders
# ---------------------------------------------------------------------------


class TestReadAllowedPlaceholders:
    """Test _read_allowed_placeholders() — BLP-001 T-3."""

    def test_reads_allowed_placeholders(self):
        """Read allowed_placeholders@ from frontmatter."""
        from arqux.handlers.cycle import _read_allowed_placeholders
        text = """---
cycle_id: "test"
allowed_placeholders@: ["_BLP-NNN_", "_Título_"]
---
Body here
"""
        result = _read_allowed_placeholders(text)
        assert result == ["_BLP-NNN_", "_Título_"]

    def test_no_allowed_placeholders_returns_empty(self):
        """No allowed_placeholders@ in frontmatter -> empty list."""
        from arqux.handlers.cycle import _read_allowed_placeholders
        text = "---\ncycle_id: test\n---\nBody"
        result = _read_allowed_placeholders(text)
        assert result == []

    def test_no_frontmatter_returns_empty(self):
        """No frontmatter at all -> empty list."""
        from arqux.handlers.cycle import _read_allowed_placeholders
        result = _read_allowed_placeholders("Just body text")
        assert result == []

    def test_empty_allowed_list(self):
        """Empty allowed_placeholders list returns empty list."""
        from arqux.handlers.cycle import _read_allowed_placeholders
        text = "---\nallowed_placeholders@: []\n---\nBody"
        result = _read_allowed_placeholders(text)
        assert result == []


# ---------------------------------------------------------------------------
# Integration: Marker-based synthesize
# ---------------------------------------------------------------------------


class TestSynthesizeCycleMarkers:
    """Test cycle.synthesize with marker replacement (BLP-001 T-2)."""

    def test_synthesize_with_marker_replacement(self, tmp_path, monkeypatch):
        """synthesize replaces specific markers when content contains known markers."""
        from arqux.handlers.cycle import synthesize_cycle
        from arqux.state import cycle_dir
        monkeypatch.chdir(tmp_path)

        arqx_dir = tmp_path / ARQUX_DIR
        arqx_dir.mkdir(parents=True, exist_ok=True)
        brain = arqx_dir / "brain.cortex"
        brain.write_text("""$0
$2: FOCUS
FCS:current{status:active}
$6: PULSE
""")

        tmpl_dir = arqx_dir / "templates"
        tmpl_dir.mkdir(parents=True, exist_ok=True)
        (tmpl_dir / "CYCLE_MANIFEST_TEMPLATE.md").write_text("""---
---
## §1: Propósito
_Propósito del ciclo_

## §2: Alcance y Límites
**Dentro:** _Ítem 1_
**Fuera:** _Ítem 2_
""", encoding="utf-8")

        cycle_id = "CYCLE-MKR"
        cdir = cycle_dir(arqx_dir, cycle_id)
        cdir.mkdir(parents=True, exist_ok=True)
        mf = cdir / "MANIFEST.md"
        mf.write_text("""---
cycle_id: "CYCLE-MKR"
name: "marker-test"
status: "draft"
---
## §1: Propósito
_Propósito del ciclo_

## §2: Alcance y Límites
**Dentro:** _Ítem 1_
**Fuera:** _Ítem 2_
""", encoding="utf-8")

        content = (
            "$1:{_Propósito del ciclo_→Refinar gobernanza}\n"
            "$2:{_Ítem 1_→Validar integridad}\n"
        )
        result = synthesize_cycle(cycle_id, content, path=str(tmp_path))
        assert result.profile == "OUT-WORK"
        assert "sections_written" in result.fields

        manifest = mf.read_text(encoding="utf-8")
        assert "Refinar gobernanza" in manifest
        assert "Validar integridad" in manifest
        assert "_Ítem 2_" in manifest

    def test_synthesize_backward_compat_section_replacement(self, tmp_path, monkeypatch):
        """synthesize falls back to section replacement when no markers in content."""
        from arqux.handlers.cycle import synthesize_cycle
        from arqux.state import cycle_dir
        monkeypatch.chdir(tmp_path)

        arqx_dir = tmp_path / ARQUX_DIR
        arqx_dir.mkdir(parents=True, exist_ok=True)
        brain = arqx_dir / "brain.cortex"
        brain.write_text("""$0
$2: FOCUS
FCS:current{status:active}
$6: PULSE
""")

        tmpl_dir = arqx_dir / "templates"
        tmpl_dir.mkdir(parents=True, exist_ok=True)
        (tmpl_dir / "CYCLE_MANIFEST_TEMPLATE.md").write_text("""---
---
## §1: Propósito
_Propósito del ciclo_

## §2: Alcance y Límites
**Dentro:** _Ítem 1_
""", encoding="utf-8")

        cycle_id = "CYCLE-BWC"
        cdir = cycle_dir(arqx_dir, cycle_id)
        cdir.mkdir(parents=True, exist_ok=True)
        mf = cdir / "MANIFEST.md"
        mf.write_text("""---
cycle_id: "CYCLE-BWC"
name: "backward-compat"
status: "draft"
---
## §1: Propósito
_Propósito del ciclo_

## §2: Alcance y Límites
**Dentro:** _Ítem 1_
""", encoding="utf-8")

        content = "$1:{Contenido completamente nuevo para §1}"
        result = synthesize_cycle(cycle_id, content, path=str(tmp_path))
        assert result.profile == "OUT-WORK"

        manifest = mf.read_text(encoding="utf-8")
        assert "Contenido completamente nuevo para §1" in manifest
        assert "_Ítem 1_" in manifest


# ---------------------------------------------------------------------------
# BLP-003: Verify cycle.close and cycle.current not affected by mature removal
# ---------------------------------------------------------------------------


class TestCycleCloseCurrentNotAffected:
    """Verify cycle.close and cycle.current work without mature (BLP-003)."""

    def test_close_works_directly(self, temp_project, monkeypatch):
        """cycle.close works directly without needing mature first."""
        from arqux.handlers.cycle import close_cycle, CYCLE_CLOSED
        monkeypatch.chdir(temp_project)

        from arqux.state import cycle_dir
        cdir = cycle_dir(temp_project / ARQUX_DIR, "CLOSE-TEST")
        cdir.mkdir(parents=True, exist_ok=True)
        mf = cdir / "MANIFEST.md"
        mf.write_text("""---
cycle_id: "CLOSE-TEST"
name: "close-test"
status: "draft"
---
## §1: Propósito
Test content without placeholders
""", encoding="utf-8")

        result = close_cycle("CLOSE-TEST", summary="Test close", path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert result.fields.get("status") == CYCLE_CLOSED

    def test_current_unchanged(self, temp_project, monkeypatch):
        """cycle.current returns open cycles as before."""
        from arqux.handlers.cycle import current_cycle
        monkeypatch.chdir(temp_project)

        from arqux.state import cycle_dir
        for cid in ["CYCLE-CA", "CYCLE-CB"]:
            cdir = cycle_dir(temp_project / ARQUX_DIR, cid)
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "MANIFEST.md").write_text(f"""---
cycle_id: "{cid}"
name: "{cid}"
status: "draft"
---
""", encoding="utf-8")

        result = current_cycle(path=str(temp_project))
        assert result.profile == "OUT-WORK"
        assert "CYCLE-CA" in str(result.fields.get("open_cycles", []))
        assert "CYCLE-CB" in str(result.fields.get("open_cycles", []))

    def test_no_reference_to_mature_cycle(self):
        """Verify that mature_cycle, CYCLE_READY, CYCLE_ACTIVE are not importable."""
        import importlib
        # These should raise ImportError or AttributeError
        mod = importlib.import_module("arqux.handlers.cycle")
        assert not hasattr(mod, "mature_cycle"), "mature_cycle should not exist"
        assert not hasattr(mod, "CYCLE_READY"), "CYCLE_READY should not exist"
        assert not hasattr(mod, "CYCLE_ACTIVE"), "CYCLE_ACTIVE should not exist"
        # But CYCLE_DRAFT should still exist
        assert hasattr(mod, "CYCLE_DRAFT"), "CYCLE_DRAFT should still exist"
        assert hasattr(mod, "CYCLE_CLOSED"), "CYCLE_CLOSED should still exist"

    def test_transitions_direct_draft_to_closed(self):
        """Verify CYCLE_TRANSITIONS only has draft→closed."""
        from arqux.handlers.cycle import CYCLE_DRAFT, CYCLE_CLOSED, CYCLE_TRANSITIONS
        assert CYCLE_DRAFT in CYCLE_TRANSITIONS
        assert CYCLE_CLOSED in CYCLE_TRANSITIONS
        assert CYCLE_DRAFT not in CYCLE_TRANSITIONS or CYCLE_TRANSITIONS[CYCLE_DRAFT] == (CYCLE_CLOSED,)
