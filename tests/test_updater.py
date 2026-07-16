"""Tests for Universal Updater (``arqux.core.updater``)."""

from __future__ import annotations

from arqux.core.updater import Updater

SAMPLE_BODY = """\
<!-- BLP:1 -->
## §1: Planteamiento del Problema

_Describe el problema que aborda este Blueprint._

**Evidencia:**
- _Evidencia 1_
<!-- /BLP:1 -->

<!-- BLP:2 -->
## §2: Objetivo

_Concreto, verificable._
<!-- /BLP:2 -->
"""


def test_replace_basic() -> None:
    """Updater replaces content between markers."""
    updater = Updater("BLP")
    new_content = "## §1: Problema\\n\\nContenido actualizado."
    result = updater.replace(SAMPLE_BODY, "1", new_content)
    assert "Contenido actualizado." in result
    assert "<!-- BLP:1 -->" in result
    assert "<!-- /BLP:1 -->" in result


def test_replace_preserves_header() -> None:
    """When content has no ## §N:, the template header is preserved."""
    updater = Updater("BLP")
    result = updater.replace(SAMPLE_BODY, "1", "Solo texto sin header.")
    assert "## §1: Planteamiento del Problema" in result
    assert "Solo texto sin header." in result


def test_replace_replaces_header() -> None:
    """When content starts with ## §N:, the header is replaced."""
    updater = Updater("BLP")
    result = updater.replace(
        SAMPLE_BODY, "2", "## §2: Nuevo Titulo\\n\\nContenido.",
    )
    assert "## §2: Nuevo Titulo" in result
    assert "## §2: Objetivo" not in result


def test_replace_unaffected_segments() -> None:
    """Replacing one segment leaves other segments intact."""
    updater = Updater("BLP")
    result = updater.replace(SAMPLE_BODY, "1", "Nuevo §1.")
    assert "<!-- BLP:2 -->" in result
    assert "## §2: Objetivo" in result
    assert "_Concreto, verificable._" in result


def test_replace_nonexistent_segment() -> None:
    """Replacing a nonexistent segment returns the body unchanged."""
    updater = Updater("BLP")
    result = updater.replace(SAMPLE_BODY, "99", "anything")
    assert result == SAMPLE_BODY


def test_replace_with_markdown() -> None:
    """Updater handles real markdown content (bold, tables, PUML)."""
    updater = Updater("BLP")
    markdown = (
        "## §1: Real Content\\n\\n"
        "**bold text** and _italic_\\n\\n"
        "| Col1 | Col2 |\\n"
        "|------|------|\\n"
        "| A | B |\\n\\n"
        "```puml\\n"
        "@startuml\\n"
        "A --> B\\n"
        "@enduml\\n"
        "```"
    )
    result = updater.replace(SAMPLE_BODY, "1", markdown)
    assert "**bold text**" in result
    assert "| Col1 | Col2 |" in result
    assert "@startuml" in result
    assert "<!-- BLP:1 -->" in result
    assert "<!-- /BLP:1 -->" in result


def test_replace_with_cycle_type() -> None:
    """Updater works with any type prefix (e.g. CYCLE)."""
    body = """\
<!-- CYCLE:1 -->
## §1: Scope

Original.
<!-- /CYCLE:1 -->
"""
    updater = Updater("CYCLE")
    result = updater.replace(body, "1", "New scope content.")
    assert "New scope content." in result
    assert "<!-- CYCLE:1 -->" in result
