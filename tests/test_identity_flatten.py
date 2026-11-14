"""T-1.20 (BLP-001 ampliacion A) — flattening preserves identity content.

Migrating an identity flattens literal newlines inside quoted values and
collapses multi-line entries into one physical line (CORTEX 1.0: one line per
idea, I004). Both are textual operations over governance contracts — an axiom or
a lesson — so the content must survive verbatim apart from the whitespace that
the join itself introduces.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/vatrox/workspace/ARQUX/scripts")


IDENTITIES = Path("/home/vatrox/workspace/ARQUX/src/arqux/identities")

MULTILINE = '''$0

# IDN | identity

$1: IDENTITY

IDN:probe{name:"Probe", purpose:"First line
                  second line
                  third line.", status:"current"}

AXM:rule{name:"rule", body:"Axiom text that fits
  on two lines.", status:"current"}
'''


def _flatten(text: str) -> str:
    """Same normalisation the prototype applies, kept local to the test."""
    out: list[str] = []
    pending: str | None = None
    for line in text.split("\n"):
        if pending is not None:
            pending += " " + line.strip()
            if pending.count('"') % 2 == 0:
                out.append(pending)
                pending = None
            continue
        if line.lstrip().startswith("#") or line.count('"') % 2 == 0:
            out.append(line)
            continue
        pending = line.rstrip()
    if pending is not None:
        out.append(pending)
    return "\n".join(out)


def _collapse(text: str) -> str:
    """Join an attrs idea that opens { and does not close } on the same line."""
    out: list[str] = []
    buffer: str | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        if buffer is not None:
            buffer += " " + stripped
            if "}" in stripped:
                out.append(buffer)
                buffer = None
            continue
        if (not stripped.startswith("#")
                and re.match(r"^[A-Z][A-Z0-9_]{1,5}:[A-Za-z0-9_.\-]+\{", stripped)
                and "}" not in stripped):
            buffer = stripped
            continue
        out.append(line)
    if buffer is not None:
        out.append(buffer)
    return "\n".join(out)


def _entries(text: str) -> dict[str, str]:
    """Map 'SIGIL:name' -> raw value text, ignoring declarations and comments."""
    found: dict[str, str] = {}
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r"^([A-Z][A-Z0-9_]{1,5}):([A-Za-z0-9_.\-]+)\{(.*)\}\s*$", stripped)
        if m and re.search(r'"[^"]*"', m.group(3)):
            found[f"{m.group(1)}:{m.group(2)}"] = m.group(3)
    return found


def test_multiline_values_are_joined_losslessly():
    """The words survive; only the line breaks become spaces."""
    before = MULTILINE
    after = _flatten(before)

    # The words survive and are joined by single spaces; only case of the
    # continuation words is preserved from the source.
    assert 'purpose:"First line second line third line."' in after
    assert 'body:"Axiom text that fits on two lines."' in after

    # No words lost: compare the word sequence of each value.
    def words(text: str) -> list[str]:
        body = " ".join(re.findall(r'"[^"]*"', text))
        return body.split()

    assert words(before) == words(after)


def test_collapse_yields_one_line_per_idea():
    """After flatten + collapse, every entry is a single physical line."""
    after = _collapse(_flatten(MULTILINE))
    for line in after.split("\n"):
        stripped = line.strip()
        if re.match(r"^[A-Z][A-Z0-9_]{1,5}:[A-Za-z0-9_.\-]+\{", stripped):
            assert stripped.count("{") == 1
            assert "}" in stripped, f"entry not closed on its line: {stripped[:60]}"


@pytest.mark.parametrize("path", sorted(IDENTITIES.glob("*.cortex")), ids=lambda p: p.stem)
def test_identity_entries_survive_migration(path: Path):
    """A real identity keeps every entry and every word through the transform."""
    original = path.read_text(encoding="utf-8")

    # The migrated counterpart may already exist; migrating again must be stable.
    flattened = _collapse(_flatten(original))

    before = _entries(original)
    after = _entries(flattened)

    missing = set(before) - set(after)
    assert not missing, f"{path.name}: entries lost: {sorted(missing)}"

    for key, value in before.items():
        before_words = " ".join(re.findall(r'"[^"]*"', value)).split()
        after_words = " ".join(re.findall(r'"[^"]*"', after[key])).split()
        assert before_words == after_words, f"{path.name}: {key} changed content"
