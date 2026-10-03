"""Regression test for issue 2026-10-02 (schema mismatch verifier<->format).

codec-cortex (published <=0.6.2) requires a `name` ATTRIBUTE on every entry,
but in CODEC-CORTEX the entry name lives in the KEY (SIGIL:name). This made
cortex.verify emit one W001_MISSING_FIELDS per entry on every healthy brain
(576/584 entries in ARQUX brain.cortex), so `valid=false` became systemic and
buried real E-code diagnostics.

Decision (Arquitecto): codec-cortex is NOT to be changed/released — the fix
travels with arqux as a load-time shim that empties
SchemaResolver.ALWAYS_REQUIRED (issue-fix lives in local-only maintenance of
the codec source for future releases, out of scope here).

Verified: the ARQUX brain's real defects (6 incomplete LNG + invalid RSK
status/severity) were sanitized the same day via MCP handlers.
"""

from __future__ import annotations

import pytest


def test_resolver_shim_empties_always_required() -> None:
    """Importing arqux.core.state must neutralize ALWAYS_REQUIRED."""
    pytest.importorskip("cortex")

    from arqux.core.state import _HAS_CODEC_CORTEX

    assert _HAS_CODEC_CORTEX, "codec-cortex is required for this test"

    from cortex.core.schema import SchemaResolver

    assert frozenset() == SchemaResolver.ALWAYS_REQUIRED


def test_verify_healthy_brain_without_name_attrs(tmp_path) -> None:
    """A well-formed brain without `name` attrs must verify clean (no W001)."""
    from arqux.core.state import cortex_verify

    brain = tmp_path / "brain.cortex"
    brain.write_text(
        "$0\n\n# FCS   | focus | attrs | H | Working | Focus\n"
        '# LNG   | lesson | attrs | M | Episodic | Lessons\n'
        '# OBJ   | objective | attrs | H | Working | Active goal\n'
        "\n"
        "$1: FOCUS\n"
        'FCS:current{what:"x", priority:"medium", status:"current", survive:"work"}\n'
        "\n"
        "$2: OBJECTIVES\n"
        'OBJ:goal{goal:"g", status:"current", success:"s", survive:"work"}\n'
        "\n"
        "$3: LESSONS\n"
        'LNG:demo{type:"contextual", cause:"c", lesson:"l", prevention:"p"}\n',
        encoding="utf-8",
    )
    result = cortex_verify(brain)
    assert result["valid"] is True, result["diagnostics"]
    assert not any("W001_MISSING_FIELDS" in d for d in result["diagnostics"])
