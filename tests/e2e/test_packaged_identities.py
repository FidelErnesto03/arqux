"""Published agent identities must be BASIC contracts.

The workspace copies accumulate behavioral lessons from real incidents
(`LNG:` entries with project names, dates and sessions). Those are local
knowledge and must never ship: the published package carries the role
contract only — identity, axioms, limits and description.

Verified against the 0.9.0 release (2026-11-14): packaged identities had 0
episodic entries while the deployed workspace copies carried 10 (alfred),
18 (jarvis), 1 (governor) and 1 (heimdall).
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IDENTITIES = sorted((ROOT / "src" / "arqux" / "identities").glob("*.cortex"))

EPISODIC = ("LNG:", "SES:", "WRK:", "AUD:", "FCS:", "OBJ:", "HDL:")


@pytest.mark.parametrize("path", IDENTITIES, ids=lambda p: p.stem)
def test_published_identity_is_a_basic_contract(path: Path):
    text = path.read_text(encoding="utf-8")

    episodic = [sigil for sigil in EPISODIC if f"\n{sigil}" in text or text.startswith(sigil)]
    assert not episodic, f"{path.name} ships episodic/local learning: {episodic}"

    assert "IDN:" in text, f"{path.name} has no identity entry"
    assert "AXM:" in text, f"{path.name} has no axioms"
    assert "LIM:" in text, f"{path.name} has no limits"
    assert "DESC:" in text, f"{path.name} has no description"

    for local in ("/home/", "/Users/", "C:\\\\"):
        assert local not in text, f"{path.name} leaks a local path: {local}"
