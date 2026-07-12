"""Tests for the structural validator (BLP-036)."""

from __future__ import annotations

from arqux.constants import (
    E026_MISSING_SECTION,
    E027_MALFORMED_SECTION,
    W002_INCOMPLETE_BRAIN,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactUsage,
    CortexLevel,
)
from arqux.formats import CortexArtifact
from arqux.validators import (
    BrainStructureValidator,
    ValidatorFactory,
)

# --- Fixtures ---------------------------------------------------------------

def _make_brain(payload: str, *, name: str = "brain") -> CortexArtifact:
    meta = ArtifactMetadata(
        level=CortexLevel.BRAIN,
        name=name,
        usage=ArtifactUsage.STATE,
        kind=ArtifactKind.NATIVE,
    )
    return CortexArtifact(metadata=meta, payload=payload, filename=name)


FULL_BRAIN_BODY = """$0
GSIG:IDN:identity|attrs|B|Semantic|Actor identity

$1: IDENTITY
IDN:governor{project:"test"}

$2: KNOWLEDGE
KNW:meta{content:"project knowledge"}

$3: FOCUS
FCS:current{status:"current", what:"shipping v1"}

$4: OBJECTIVES
OBJ:v1{status:"active", goal:"ship v1"}

$5: STATE
WRK:current{cycle:"CYCLE-01"}

$6: LESSONS
LNG:lesson1{detail:"refactor before adding features"}

$7: DECISIONS
DEC:d1{decision:"use codec-cortex for parsing"}

$8: AXIOMS
AXM:architect_first{status:"current"}

$9: LIMITS
LIM:no_direct_edit{status:"current"}

$10: HANDOFF
HDL:1{from:"alfred", to:"jarvis"}

$11: CONCURRENCY
ERR:concurrency{version:"1"}

$12: ISSUES
ISS:1{description:"none"}
"""

# Brain with only 4 sections — should trigger W002_INCOMPLETE_BRAIN.
SPARSE_BRAIN_BODY = """$1: IDENTITY
IDN:governor{project:"test"}

$3: FOCUS
FCS:current{status:"current"}

$4: OBJECTIVES
OBJ:v1{status:"active"}

$11: CONCURRENCY
ERR:concurrency{version:"1"}
"""

# Brain with a misnamed section title.
MALFORMED_BRAIN_BODY = """$1: IDENTITY
IDN:governor{project:"test"}

$3: WRONG_TITLE
FCS:current{status:"current"}

$11: CONCURRENCY
ERR:concurrency{version:"1"}
"""

# Empty brain — should trigger 13 E026 warnings (lenient mode).
EMPTY_BRAIN_BODY = ""


# --- Tests ------------------------------------------------------------------

class TestBrainStructureValidator:
    def test_full_brain_passes(self) -> None:
        art = _make_brain(FULL_BRAIN_BODY)
        result = BrainStructureValidator().validate(art)
        assert result.is_valid is True
        # No errors, no warnings for a full 13-section brain.
        assert result.errors == []
        assert result.warnings == []

    def test_sparse_brain_emits_incomplete_warning(self) -> None:
        art = _make_brain(SPARSE_BRAIN_BODY)
        result = BrainStructureValidator().validate(art)
        # Lenient mode: warnings for missing sections, W002 for < 8 active.
        warning_codes = [w.code for w in result.warnings]
        assert W002_INCOMPLETE_BRAIN in warning_codes
        assert E026_MISSING_SECTION in warning_codes
        # But still is_valid=True (lenient).
        assert result.is_valid is True

    def test_empty_brain_emits_13_warnings(self) -> None:
        art = _make_brain(EMPTY_BRAIN_BODY)
        result = BrainStructureValidator().validate(art)
        e026_warnings = [w for w in result.warnings if w.code == E026_MISSING_SECTION]
        assert len(e026_warnings) == 13
        # W002 also emitted because 0 < 8.
        assert any(w.code == W002_INCOMPLETE_BRAIN for w in result.warnings)

    def test_malformed_section_title_emits_e027(self) -> None:
        art = _make_brain(MALFORMED_BRAIN_BODY)
        result = BrainStructureValidator().validate(art)
        warning_codes = [w.code for w in result.warnings]
        assert E027_MALFORMED_SECTION in warning_codes

    def test_non_brain_artifact_passes_through(self) -> None:
        # A Level-1 identity should not be validated by BrainStructureValidator.
        meta = ArtifactMetadata(
            level=CortexLevel.BEHAVIORAL,
            name="jarvis",
            usage=ArtifactUsage.IDENTITY,
            kind=ArtifactKind.NATIVE,
        )
        art = CortexArtifact(metadata=meta, payload="whatever")
        result = BrainStructureValidator().validate(art)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []


class TestValidatorFactory:
    def test_factory_returns_validators_for_brain_level(self) -> None:
        from arqux.constants import CortexLevel
        chain = ValidatorFactory.get_validators(CortexLevel.BRAIN.value)
        # At least the structural validator is registered.
        assert any(isinstance(v, BrainStructureValidator) for v in chain)

    def test_factory_returns_empty_for_unregistered_level(self) -> None:
        # Level 0 (PACKAGE) has no registered validators.
        chain = ValidatorFactory.get_validators(0)
        assert chain == []

    def test_factory_validate_full_brain(self) -> None:
        art = _make_brain(FULL_BRAIN_BODY)
        result = ValidatorFactory.validate(art)
        assert result.is_valid is True

    def test_factory_validate_empty_brain(self) -> None:
        art = _make_brain(EMPTY_BRAIN_BODY)
        result = ValidatorFactory.validate(art)
        # Lenient: warnings present, is_valid stays True.
        assert len(result.warnings) > 0
        # is_valid may be False only if critical errors; structural validator
        # never emits critical errors in lenient mode.
        # (BrainActiveStateValidator may emit critical errors, but an empty
        # brain has no FCS to evaluate — see BLP-037 tests for that path.)
