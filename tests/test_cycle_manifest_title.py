"""Regression: cycle.synthesize must preserve the manifest section header title.

`_replace_manifest_section` used to hardcode ``## §N:`` when writing a section
that has no ``<!-- CYCLE:N -->`` marker, stripping titles such as
``## §6: Blueprints (Índice)``. It now preserves the existing header line.
"""

from __future__ import annotations

from arqux.handlers.cycle import _replace_manifest_section

MANIFEST = (
    "## §6: Blueprints (Índice)\n"
    "\n"
    "| BLP ID | Título |\n"
    "|---|---|\n"
    "| BLP-001 | old |\n"
    "\n"
    "## §7: Estado y Métricas\n"
    "\n"
    "**Done:** 1\n"
)


def test_replace_manifest_section_preserves_header_title() -> None:
    out = _replace_manifest_section(MANIFEST, 6, "| BLP ID | Objetivo |\n|---|---|\n| BLP-001 | CYC-OBJ-1 |")
    assert "## §6: Blueprints (Índice)" in out, "header title was stripped"
    assert "| CYC-OBJ-1 |" in out, "new content was not written"
    assert "| BLP-001 | old |" not in out, "old content was not replaced"
    # The next section is untouched.
    assert "## §7: Estado y Métricas" in out


def test_replace_manifest_section_marker_path_preserves_header() -> None:
    marked = "## §6: Blueprints (Índice)\n<!-- CYCLE:6 -->\nold\n<!-- /CYCLE:6 -->\n"
    out = _replace_manifest_section(marked, 6, "new body")
    assert "## §6: Blueprints (Índice)" in out
    assert "<!-- CYCLE:6 -->" in out and "<!-- /CYCLE:6 -->" in out
    assert "new body" in out
