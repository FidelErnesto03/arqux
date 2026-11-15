"""Error taxonomy for the native ArqUX learning engine (BLP-002).

Replaces the codec re-export of ``LearningError`` so that the learning engine
is self-contained. Every error carries a
typed code (``LE001``..``LE017``) and a human-readable cause, because a silent
``[]`` is the exact bug this module exists to close.
"""
# ruff: noqa: N801 — LE###_Name is the intentional error-code taxonomy.
from __future__ import annotations


class LearningEngineError(Exception):
    """Base error for the learning engine."""

    code: str = "LE000"

    def __init__(self, message: str, *, cause: str | None = None) -> None:
        self.cause = cause
        super().__init__(f"[{self.code}] {message}" if cause is None else f"[{self.code}] {message} — {cause}")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return super().__str__()


class LE001_DocumentMissing(LearningEngineError):
    code = "LE001"


class LE002_SectionNotFound(LearningEngineError):
    code = "LE002"


class LE003_EntrySigilUnknown(LearningEngineError):
    code = "LE003"


class LE004_PolicyInvalid(LearningEngineError):
    code = "LE004"


class LE005_CandidateNotFound(LearningEngineError):
    code = "LE005"


class LE006_ElevationRejected(LearningEngineError):
    code = "LE006"


class LE007_FingerprintMismatch(LearningEngineError):
    code = "LE007"


class LE008_ElevationBlocked(LearningEngineError):
    """Proposed elevation is blocked by policy or protected sigil."""

    code = "LE008"


class LE009_GateViolation(LearningEngineError):
    """A required quality gate is not satisfied."""

    code = "LE009"


class LE010_PolicyNotFound(LearningEngineError):
    """A named policy does not exist in the policy set."""

    code = "LE010"


class LE011_PolicyParseError(LearningEngineError):
    """Policy document is structurally invalid."""

    code = "LE011"


class LE012_ScoreOutOfRange(LearningEngineError):
    """Computed score is outside the accepted range."""

    code = "LE012"


class LE013_DryRunRequired(LearningEngineError):
    """apply mode requested without explicit confirmation."""

    code = "LE013"


class LE014_CandidateNotActionable(LearningEngineError):
    """A candidate was produced but its own evidence is below threshold."""

    code = "LE014"


class LE015_BrainUnreadable(LearningEngineError):
    """The brain cannot be parsed (IO, invalid CORTEX)."""

    code = "LE015"


class LE016_IndexEmpty(LearningEngineError):
    """The index built successfully but contains no entries."""

    code = "LE016"


class LearningEngineUnavailable(LearningEngineError):
    """Raised when the learning engine cannot operate.

    Carries the underlying cause (missing brain, locked file, etc.) so the
    caller can report it instead of swallowing it into an empty list.
    """

    code = "LE017"


__all__ = [
    "LE001_DocumentMissing",
    "LE002_SectionNotFound",
    "LE003_EntrySigilUnknown",
    "LE004_PolicyInvalid",
    "LE005_CandidateNotFound",
    "LE006_ElevationRejected",
    "LE007_FingerprintMismatch",
    "LE008_ElevationBlocked",
    "LE009_GateViolation",
    "LE010_PolicyNotFound",
    "LE011_PolicyParseError",
    "LE012_ScoreOutOfRange",
    "LE013_DryRunRequired",
    "LE014_CandidateNotActionable",
    "LE015_BrainUnreadable",
    "LE016_IndexEmpty",
    "LearningEngineError",
    "LearningEngineUnavailable",
]
