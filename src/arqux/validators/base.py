"""Base classes for the validation layer (BLP-036)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationError:
    """A single validation diagnostic (error or warning).

    Attributes:
        code: stable error code, e.g. ``"E024_LEVEL3_MISSING_FOCUS"``
        message: human-readable description
        section: section id where the error was detected (``$3``, ``$4``, ...)
        severity: ``"critical"`` | ``"high"`` | ``"medium"`` | ``"low"``
                  | ``"warning"``
    """
    code: str
    message: str
    section: str = ""
    severity: str = "warning"


@dataclass
class ValidationResult:
    """Aggregate result of running one or more validators."""
    is_valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(self, code: str, message: str, *, section: str = "",
                  severity: str = "high") -> None:
        self.errors.append(ValidationError(code=code, message=message,
                                           section=section, severity=severity))
        if severity in {"critical", "high"}:
            self.is_valid = False

    def add_warning(self, code: str, message: str, *, section: str = "") -> None:
        self.warnings.append(ValidationError(code=code, message=message,
                                             section=section,
                                             severity="warning"))

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.is_valid:
            self.is_valid = False


class InvalidValidatorError(Exception):
    """Raised when ValidatorFactory cannot resolve a validator for a level."""


class BaseValidator:
    """Abstract base for all validators (Strategy pattern).

    Subclasses MUST implement ``validate(artifact) -> ValidationResult``.
    The artifact is expected to be a ``CortexArtifact`` (BLP-035) carrying
    both ``metadata`` (ArtifactMetadata) and ``payload`` (raw text).
    """

    def validate(self, artifact: Any) -> ValidationResult:  # noqa: ANN401
        raise NotImplementedError(
            f"{type(self).__name__} must implement validate(artifact)"
        )

    # --- helpers shared by structural/semantic validators -------------------

    @staticmethod
    def _extract_section_content(payload: str, section_id: str) -> str:
        """Extract the body of a ``$N`` section from a .cortex payload.

        Returns the raw text between ``$N`` and the next ``$`` section
        marker (or end-of-file). If the section is absent, returns "".
        The §0 METADATA prelude (if present) is stripped before scanning.
        """
        import re
        from ..formats import strip_metadata_block

        body = strip_metadata_block(payload)
        # Find the section header: "$N" or "$N: TITLE" on its own line.
        # We use a tolerant regex that matches "$3", "$3:", "$3: FOCUS", etc.
        pattern = re.compile(
            r"^\s*\$" + str(section_id).lstrip("$") + r"(?:\s*:?\s*[A-Z_]*)?\s*$",
            re.MULTILINE,
        )
        match = pattern.search(body)
        if not match:
            return ""
        start = match.end()
        # Find the next $-section marker after `start`.
        next_section = re.search(r"^\s*\$\d+\s*:?\s*[A-Z_]*\s*$", body[start:],
                                 re.MULTILINE)
        if next_section:
            end = start + next_section.start()
        else:
            end = len(body)
        return body[start:end].strip()
