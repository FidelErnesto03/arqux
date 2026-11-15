from __future__ import annotations

from pathlib import Path

from arqux.constants import BrainSection
from arqux.core.learning.document import load_brain_document
from arqux.core.learning.sections import section_for_sigil


def test_section_for_sigil_vigente_real_brain():
    # Vigente: real project brain resolves by existing section titles.
    doc = load_brain_document(Path("/home/vatrox/workspace/ARQUX"))
    assert doc is not None
    assert section_for_sigil("LNG", doc) == "$8"  # $8: LESSONS in canon brain
    assert section_for_sigil("KNW", doc) == "$11"  # $11: KNOWLEDGE in canon brain
    assert section_for_sigil("SES", doc) == "$5"  # $5: SESSIONS
    assert section_for_sigil("CNST", doc) == "$10"  # $10: RISKS in canon brain


def test_section_for_sigil_fallback_without_document():
    assert section_for_sigil("LNG", None) == BrainSection.LESSONS.value
    assert section_for_sigil("KNW", None) == BrainSection.KNOWLEDGE.value
    assert section_for_sigil("RSK", None) == BrainSection.RISKS.value
    assert section_for_sigil("NXT", None) == BrainSection.ACTIVE_CONTEXT.value
