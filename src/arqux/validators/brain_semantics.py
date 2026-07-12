"""BrainActiveStateValidator — Nivel 3 semantic validator (BLP-037).

Inspects the CONTENT of the FOCUS ($3) and OBJECTIVES ($4) sections to
guarantee at least one active FCS and OBJ. Emits E024_LEVEL3_MISSING_FOCUS
or E028_NO_ACTIVE_OBJECTIVES when the brain is semantically inert (a
"zombie project").

This validator depends on BLP-036's BrainStructureValidator: it only runs
if the structural validator passed (the sections must exist for content
inspection to be meaningful).

The validator is an AUDITOR (Heimdall), not an EXECUTOR (Jarvis): it
diagnoses, never auto-heals. Reviving a zombie project is the Governor's
job (start a new planning cycle).
"""
from __future__ import annotations

import re
from typing import Any

from ..constants import (
    E024_LEVEL3_MISSING_FOCUS,
    E028_NO_ACTIVE_OBJECTIVES,
    INVALID_STATUSES,
    VALID_STATUSES,
)
from .base import BaseValidator, ValidationResult

# Regex matching a sigil entry: SIGIL:name{attrs}
_SIGIL_ENTRY_RE = re.compile(
    r"(?P<sigil>[A-Z]+):(?P<name>[^\s{]+)\s*\{(?P<attrs>[^}]*)\}",
    re.DOTALL,
)


def _parse_attrs(attrs_text: str) -> dict[str, str]:
    """Parse ``key:"value", key2:'value2', key3:bar`` into a dict.

    Values may be quoted (single or double) or bare strings. Bare numeric
    values are returned as strings (callers do their own coercion).
    """
    result: dict[str, str] = {}
    for m in re.finditer(r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,}\s]+)', attrs_text):
        key = m.group(1)
        val = m.group(2)
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        result[key.lower()] = val.lower()
    return result


def _extract_sigils_from_section(payload: str, section_id: str,
                                 sigil: str) -> list[dict[str, str]]:
    """Extract all ``SIGIL:...`` entries from a ``$N`` section.

    Returns a list of dicts with keys: name, status, raw_attrs.
    """
    from .base import BaseValidator as _BV
    section_body = _BV._extract_section_content(payload, section_id)
    if not section_body:
        return []
    entries: list[dict[str, str]] = []
    for m in _SIGIL_ENTRY_RE.finditer(section_body):
        if m.group("sigil") != sigil:
            continue
        attrs = _parse_attrs(m.group("attrs"))
        attrs["name"] = m.group("name")
        entries.append(attrs)
    return entries


def _is_vigente(status: str) -> bool:
    """Return True if ``status`` is in the VALID_STATUSES whitelist.

    A blank status is treated as vigente (defensive — better to false-negative
    than to false-positive a zombie diagnosis).
    """
    if not status:
        return True
    return status in VALID_STATUSES


def _is_inerte(status: str) -> bool:
    """Return True if ``status`` is in the INVALID_STATUSES blacklist."""
    return status in INVALID_STATUSES


class BrainActiveStateValidator(BaseValidator):
    """Validates that a Level-3 BRAIN has at least one active FCS and OBJ."""

    def validate(self, artifact: Any) -> ValidationResult:
        from ..constants import CortexLevel

        if artifact.metadata.level is not CortexLevel.BRAIN:
            return ValidationResult(is_valid=True)

        result = ValidationResult(is_valid=True)
        payload = artifact.payload

        # --- FCS evaluation (FOCUS section, $3) ---
        fcs_entries = _extract_sigils_from_section(payload, "$3", "FCS")
        if not fcs_entries:
            result.add_error(
                code=E024_LEVEL3_MISSING_FOCUS,
                message="Brain $3 FOCUS has no FCS sigils — project is zombie",
                section="$3",
                severity="critical",
            )
        else:
            vigente_fcs = [e for e in fcs_entries if _is_vigente(e.get("status", ""))]
            if not vigente_fcs:
                # All FCS are inerte (done/archived/dropped/cancelled).
                result.add_error(
                    code=E024_LEVEL3_MISSING_FOCUS,
                    message=(
                        "All FCS in $3 FOCUS are inerte "
                        f"(statuses: {[e.get('status', '') for e in fcs_entries]}) "
                        "— project is zombie"
                    ),
                    section="$3",
                    severity="critical",
                )

        # --- OBJ evaluation (OBJECTIVES section, $4) ---
        obj_entries = _extract_sigils_from_section(payload, "$4", "OBJ")
        if not obj_entries:
            result.add_error(
                code=E028_NO_ACTIVE_OBJECTIVES,
                message="Brain $4 OBJECTIVES has no OBJ sigils — no active goals",
                section="$4",
                severity="high",
            )
        else:
            vigente_obj = [e for e in obj_entries if _is_vigente(e.get("status", ""))]
            if not vigente_obj:
                result.add_error(
                    code=E028_NO_ACTIVE_OBJECTIVES,
                    message=(
                        "All OBJ in $4 OBJECTIVES are inerte "
                        f"(statuses: {[e.get('status', '') for e in obj_entries]}) "
                        "— no active goals"
                    ),
                    section="$4",
                    severity="high",
                )

        return result
