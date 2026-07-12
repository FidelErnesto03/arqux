"""Lesson data models, exceptions, and parser utilities."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

# --- Exceptions (BLP-038 §10) ------------------------------------------------

class LessonNotFoundError(Exception):
    """Raised when a lesson_id cannot be found in the LessonStore."""

class InsufficientConfidenceError(Exception):
    """Raised when a lesson's confidence/occurrences are below thresholds.

    Per BLP-038 §11: elevation requires ``occurrences >= 2`` AND
    ``confidence >= 0.7``.
    """

class InvalidLessonStatusError(Exception):
    """Raised when a lesson is already ``elevated`` or ``expired``."""

class ContainerIdentityError(Exception):
    """Raised when the source/target container cannot be resolved."""

class AgentIdentityError(Exception):
    """Raised when an unknown agent name is provided."""


# --- Lesson sigil parser ----------------------------------------------------

_LNG_RE = re.compile(
    r"LNG:(?P<name>[^\s{]+)\s*\{(?P<attrs>[^}]*)\}",
    re.DOTALL,
)


def _parse_lng_attrs(attrs_text: str) -> dict[str, str]:
    """Parse a sigil attrs body into a dict (key → original-case value)."""
    result: dict[str, str] = {}
    for m in re.finditer(
        r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,}\s]+)',
        attrs_text,
    ):
        key = m.group(1)
        val = m.group(2)
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        result[key] = val
    return result


def _now_epoch() -> int:
    return int(time.time())


# --- Lesson data ------------------------------------------------------------

@dataclass
class Lesson:
    """A single behavioral lesson entry (sigilo LNG)."""
    lesson_id: str
    agent: str
    context: str
    pattern: str
    evidence_ref: str = ""
    confidence: float = 0.0
    occurrences: int = 1
    ttl: int = 30          # cycles
    status: str = "raw"    # raw | elevated | discarded | expired
    captured_at: int = 0
    line: str = "behavioral"  # which line this lesson belongs to

    def to_sigil(self) -> str:
        """Render this lesson as an ``LNG:<id>{...}`` line."""
        return (
            f"LNG:{self.lesson_id}{{"
            f'type:"{self.line}", '
            f"confidence:{self.confidence}, "
            f"occurrences:{self.occurrences}, "
            f"ttl:{self.ttl}, "
            f'status:"{self.status}"'
            "}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_id": self.lesson_id,
            "agent": self.agent,
            "context": self.context,
            "pattern": self.pattern,
            "evidence_ref": self.evidence_ref,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "ttl": self.ttl,
            "status": self.status,
            "captured_at": self.captured_at,
            "line": self.line,
        }
