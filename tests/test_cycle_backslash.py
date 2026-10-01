"""Regression: cycle section replacement must not interpret backslashes.

NUEVO-M1 (BLP-003 round-5 audit, pre-existing): ``cycle.synthesize`` passed
runtime text as the ``repl`` argument of ``re.sub``/``Pattern.sub``, so a
backslash in section content either raised ``re.error`` (``\\y``, ``\\1``) or
silently expanded backreferences (corrupting ``MANIFEST.md``).
"""

from __future__ import annotations

from arqux.handlers.cycle import _replace_manifest_section


def test_replace_manifest_section_backslash_literal() -> None:
    text = "## §4:\n\nold\n\n## §5:\n\nx\n"
    out = _replace_manifest_section(text, 4, "C:\\Users\\nueva")
    assert "C:\\Users\\nueva" in out


def test_replace_manifest_section_backref_literal() -> None:
    text = "<!-- CYCLE:4 -->\nold\n<!-- /CYCLE:4 -->\n"
    out = _replace_manifest_section(text, 4, "a\\1b")
    assert "a\\1b" in out
    assert out.count("<!-- CYCLE:4 -->") == 1
