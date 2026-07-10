"""BrainStructureValidator — Nivel 3 anatomical validator (BLP-036).

Validates that a Level-3 BRAIN artifact possesses the 13 canonical sections
($0 METADATA through $12 ISSUES) per niveles-cortex-arqux.md v3.0.

This validator is STRICTLY TOPOLOGICAL: it checks the CONTINENT (section
presence), not the CONTENT (sigil semantics). Content validation is the
job of BrainActiveStateValidator (BLP-037).

The validator operates in LENIENT mode by default (per BLP-036 §15 R-01):
missing sections emit Warnings, not Errors. This preserves backward
compatibility with workspaces that have legacy brains with fewer sections.
Errors only block WRITE operations; reads always succeed with warnings.
"""
from __future__ import annotations

import re
from typing import Any

from ..constants import (
    BRAIN_SECTION_TITLES,
    BrainSection,
    CortexLevel,
    E026_MISSING_SECTION,
    E027_MALFORMED_SECTION,
    W002_INCOMPLETE_BRAIN,
)
from ..formats import strip_metadata_block
from .base import BaseValidator, ValidationError, ValidationResult


_SECTION_HEADER_RE = re.compile(
    r"^\s*\$(?P<num>\d+)\s*:?\s*(?P<title>[A-Z_][A-Z_]*)?\s*$",
    re.MULTILINE,
)


class BrainStructureValidator(BaseValidator):
    """Validates the 13-section anatomy of a Level-3 BRAIN artifact."""

    def validate(self, artifact: Any) -> ValidationResult:
        if artifact.metadata.level is not CortexLevel.BRAIN:
            # Not a BRAIN — nothing to validate here.
            return ValidationResult(is_valid=True)

        payload = artifact.payload
        body = strip_metadata_block(payload)

        # Collect every section header present in the body.
        present: dict[int, str] = {}  # {section_num: title}
        for m in _SECTION_HEADER_RE.finditer(body):
            num = int(m.group("num"))
            title = (m.group("title") or "").strip()
            present[num] = title

        result = ValidationResult(is_valid=True)

        # Verify each of the 13 canonical sections is present.
        canonical = list(BrainSection)
        active_count = 0
        for sec in canonical:
            num = sec.number
            expected_title = BRAIN_SECTION_TITLES[sec.value]
            if num not in present:
                # Missing section — Warning (lenient mode).
                result.add_warning(
                    code=E026_MISSING_SECTION,
                    message=f"Brain missing canonical section {sec.value} ({expected_title})",
                    section=sec.value,
                )
            else:
                active_count += 1
                # Check the title matches (if present at all).
                actual_title = present[num]
                if actual_title and actual_title != expected_title:
                    result.add_warning(
                        code=E027_MALFORMED_SECTION,
                        message=(
                            f"Section ${num} title mismatch: "
                            f"expected '{expected_title}', got '{actual_title}'"
                        ),
                        section=sec.value,
                    )

        # Rule 4 (BLP-036 §7): fewer than 8 active sections → W002.
        if active_count < 8:
            result.add_warning(
                code=W002_INCOMPLETE_BRAIN,
                message=(
                    f"Brain has only {active_count}/13 active sections "
                    f"(threshold: 8)"
                ),
            )

        return result
