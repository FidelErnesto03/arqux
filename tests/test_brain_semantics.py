"""Tests for BrainActiveStateValidator — semantic validation (BLP-037)."""

from __future__ import annotations

from arqux.constants import (
    E024_LEVEL3_MISSING_FOCUS,
    E028_NO_ACTIVE_OBJECTIVES,
    ArtifactKind,
    ArtifactMetadata,
    ArtifactUsage,
    CortexLevel,
)
from arqux.formats import CortexArtifact
from arqux.validators import BrainActiveStateValidator, ValidatorFactory
from arqux.validators.brain_semantics import (
    _extract_sigils_from_section,
    _is_inerte,
    _is_vigente,
)

# --- Fixtures ---------------------------------------------------------------

def _make_brain(payload: str) -> CortexArtifact:
    meta = ArtifactMetadata(
        level=CortexLevel.BRAIN,
        name="brain",
        usage=ArtifactUsage.STATE,
        kind=ArtifactKind.NATIVE,
    )
    return CortexArtifact(metadata=meta, payload=payload, filename="brain")


def _brain_with(focus_entries: str = "", obj_entries: str = "") -> str:
    """Build a brain body with the given FCS/OBJ entries."""
    parts = ["$3: FOCUS"]
    if focus_entries:
        parts.append(focus_entries)
    parts.append("$4: OBJECTIVES")
    if obj_entries:
        parts.append(obj_entries)
    parts.append("$11: CONCURRENCY")
    parts.append('ERR:concurrency{version:"1"}')
    return "\n".join(parts)


# --- Helper function tests --------------------------------------------------

class TestHelpers:
    def test_is_vigente_current(self) -> None:
        assert _is_vigente("current") is True

    def test_is_vigente_blocked(self) -> None:
        assert _is_vigente("blocked") is True

    def test_is_vigente_done(self) -> None:
        assert _is_vigente("done") is False

    def test_is_vigente_archived(self) -> None:
        assert _is_vigente("archived") is False

    def test_is_vigente_blank_is_vigente(self) -> None:
        # Blank status is treated as vigente (defensive).
        assert _is_vigente("") is True

    def test_is_inerte_done(self) -> None:
        assert _is_inerte("done") is True

    def test_is_inerte_current(self) -> None:
        assert _is_inerte("current") is False

    def test_extract_sigils_finds_fcs(self) -> None:
        payload = _brain_with(
            focus_entries='FCS:current{status:"current", what:"ship v1"}',
            obj_entries='OBJ:v1{status:"active", goal:"ship"}',
        )
        fcs = _extract_sigils_from_section(payload, "$3", "FCS")
        assert len(fcs) == 1
        assert fcs[0]["name"] == "current"
        assert fcs[0]["status"] == "current"

    def test_extract_sigils_returns_empty_when_section_absent(self) -> None:
        payload = "$11: CONCURRENCY\nERR:concurrency{version:'1'}\n"
        assert _extract_sigils_from_section(payload, "$3", "FCS") == []


# --- Validator tests --------------------------------------------------------

class TestBrainActiveStateValidator:
    def test_healthy_brain_passes(self) -> None:
        payload = _brain_with(
            focus_entries='FCS:current{status:"current", what:"ship v1"}',
            obj_entries='OBJ:v1{status:"active", goal:"ship"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        assert result.is_valid is True
        assert result.errors == []

    def test_blocked_fcs_is_vigente(self) -> None:
        # AC-03: FCS with status="blocked" is considered valid.
        payload = _brain_with(
            focus_entries='FCS:current{status:"blocked", what:"waiting on deps"}',
            obj_entries='OBJ:v1{status:"active"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        assert result.is_valid is True

    def test_no_fcs_emits_e024(self) -> None:
        # AC-01: $3 with no FCS sigils → E024.
        payload = _brain_with(
            focus_entries="(free text without sigils)",
            obj_entries='OBJ:v1{status:"active"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        codes = [e.code for e in result.errors]
        assert E024_LEVEL3_MISSING_FOCUS in codes
        assert not result.is_valid

    def test_all_fcs_done_emits_e024(self) -> None:
        # AC-02: all FCS with status="done" → E024.
        payload = _brain_with(
            focus_entries='FCS:v0{status:"done"}\nFCS:v1{status:"done"}',
            obj_entries='OBJ:v1{status:"active"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        codes = [e.code for e in result.errors]
        assert E024_LEVEL3_MISSING_FOCUS in codes

    def test_mixed_fcs_one_current_passes(self) -> None:
        # AC: multiple FCS, one done, one current → valid.
        payload = _brain_with(
            focus_entries='FCS:v0{status:"done"}\nFCS:v1{status:"current"}',
            obj_entries='OBJ:v1{status:"active"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        assert result.is_valid is True

    def test_no_obj_emits_e028(self) -> None:
        # AC-04: $4 with no OBJ → E028.
        payload = _brain_with(
            focus_entries='FCS:current{status:"current"}',
            obj_entries="(no objectives yet)",
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        codes = [e.code for e in result.errors]
        assert E028_NO_ACTIVE_OBJECTIVES in codes

    def test_all_obj_done_emits_e028(self) -> None:
        payload = _brain_with(
            focus_entries='FCS:current{status:"current"}',
            obj_entries='OBJ:v0{status:"done"}\nOBJ:v1{status:"archived"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        codes = [e.code for e in result.errors]
        assert E028_NO_ACTIVE_OBJECTIVES in codes

    def test_zombie_brain_emits_both_e024_and_e028(self) -> None:
        payload = _brain_with(
            focus_entries='FCS:v0{status:"done"}',
            obj_entries='OBJ:v0{status:"done"}',
        )
        art = _make_brain(payload)
        result = BrainActiveStateValidator().validate(art)
        codes = [e.code for e in result.errors]
        assert E024_LEVEL3_MISSING_FOCUS in codes
        assert E028_NO_ACTIVE_OBJECTIVES in codes

    def test_non_brain_artifact_passes_through(self) -> None:
        meta = ArtifactMetadata(
            level=CortexLevel.BEHAVIORAL,
            name="jarvis",
            usage=ArtifactUsage.IDENTITY,
            kind=ArtifactKind.NATIVE,
        )
        art = CortexArtifact(metadata=meta, payload="...")
        result = BrainActiveStateValidator().validate(art)
        assert result.is_valid is True


class TestValidatorFactoryCascade:
    def test_factory_emits_e024_for_zombie_brain(self) -> None:
        payload = _brain_with(
            focus_entries='FCS:v0{status:"done"}',
            obj_entries='OBJ:v0{status:"done"}',
        )
        art = _make_brain(payload)
        result = ValidatorFactory.validate(art)
        codes = [e.code for e in result.errors]
        assert E024_LEVEL3_MISSING_FOCUS in codes
        assert E028_NO_ACTIVE_OBJECTIVES in codes
        assert not result.is_valid

    def test_factory_passes_for_healthy_brain(self) -> None:
        payload = _brain_with(
            focus_entries='FCS:current{status:"current"}',
            obj_entries='OBJ:v1{status:"active"}',
        )
        art = _make_brain(payload)
        result = ValidatorFactory.validate(art)
        assert result.is_valid is True
