"""Structural and semantic validators for .cortex artifacts (BLP-036/037).

The validation layer sits AFTER §0 METADATA validation (BLP-035) and BEFORE
handlers return artifacts to MCP/CLI clients. It uses the *Strategy* pattern:
``ValidatorFactory.get_validator(level)`` returns the validator appropriate
for the artifact's level.

Public API:

    ValidationResult          — dataclass (is_valid, errors, warnings)
    ValidationError           — dataclass (code, message, section, severity)
    BaseValidator             — abstract base for all validators
    BrainStructureValidator   — Nivel 3 anatomical validator (BLP-036)
    BrainActiveStateValidator — Nivel 3 semantic validator (BLP-037)
    ValidatorFactory          — registry + cascade orchestrator
"""
from __future__ import annotations

from .base import (
    BaseValidator,
    InvalidValidatorError,
    ValidationError,
    ValidationResult,
)
from .brain_semantics import BrainActiveStateValidator
from .brain_structure import BrainStructureValidator


class ValidatorFactory:
    """Registry and cascade orchestrator for level-aware validation.

    Usage::

        from arqux.formats import read_cortex_artifact
        from arqux.validators import ValidatorFactory

        artifact = read_cortex_artifact(path)
        result = ValidatorFactory.validate(artifact)
        if not result.is_valid:
            for err in result.errors:
                print(err.code, err.message)
    """

    # Lazy registry: level → list of validator instances (executed in order).
    _registry: dict[int, list[BaseValidator]] = {}

    @classmethod
    def register(cls, level: int, validator: BaseValidator) -> None:
        """Register ``validator`` for the given ``level`` (appended to chain)."""
        cls._registry.setdefault(level, []).append(validator)

    @classmethod
    def get_validators(cls, level: int) -> list[BaseValidator]:
        """Return the validator chain for ``level`` (empty list if none)."""
        return list(cls._registry.get(level, []))

    @classmethod
    def validate(cls, artifact) -> ValidationResult:
        """Run all validators registered for ``artifact.metadata.level``.

        Validators run in cascade: if a structural validator fails with
        CRITICAL errors, subsequent validators are skipped (their preconditions
        are not met).
        """
        level_int = artifact.metadata.level.value
        chain = cls.get_validators(level_int)
        if not chain:
            # No validators registered for this level — pass by default.
            return ValidationResult(is_valid=True, errors=[], warnings=[])

        combined = ValidationResult(is_valid=True, errors=[], warnings=[])
        for validator in chain:
            result = validator.validate(artifact)
            combined.errors.extend(result.errors)
            combined.warnings.extend(result.warnings)
            # Cascade: if structural validator returned CRITICAL errors,
            # stop the cascade (semantic validators depend on structure).
            if any(e.severity == "critical" for e in result.errors):
                combined.is_valid = False
                break
            if not result.is_valid:
                combined.is_valid = False

        return combined


# === Default registrations (executed at import time) =======================

from ..constants import CortexLevel as _CortexLevel  # noqa: E402

# Nivel 3 (BRAIN): structural → semantic cascade.
ValidatorFactory.register(
    _CortexLevel.BRAIN.value,
    BrainStructureValidator(),
)
ValidatorFactory.register(
    _CortexLevel.BRAIN.value,
    BrainActiveStateValidator(),
)


__all__ = [
    "BaseValidator",
    "BrainActiveStateValidator",
    "BrainStructureValidator",
    "InvalidValidatorError",
    "ValidationError",
    "ValidationResult",
    "ValidatorFactory",
]
