"""CORTEX-OUT output protocol.

Five profiles, picked by context:

    OUT-MIN     — quick acks, no detail.
    OUT-WORK    — work updates, deliverables, evidence of progress.
    OUT-AUDIT   — architecture reviews, decision logs.
    OUT-FULL    — full prose, no compression (for humans).
    OUT-ERROR   — failures, blockers, permission denials.

Format: <PROFILE> <key=value>... [message]

Examples:
    OUT-MIN ok T-001 in_progress
    OUT-WORK done T-001 evidence=E-007 coverage=87%
    OUT-AUDIT review cycle=CYCLE-01 risk=low rationale="..."
    OUT-ERROR code=PERMISSION_DENIED handler=task.create reason=executor_role
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    DEFAULT_OUT_PROFILE,
    OUT_AUDIT,
    OUT_ERROR,
    OUT_FULL,
    OUT_MIN,
    OUT_WORK,
)


@dataclass
class CortexOUT:
    """A structured CORTEX-OUT response."""

    profile: str
    fields: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    @classmethod
    def profile(cls, profile: str, message: str = "", **fields: Any) -> "CortexOUT":
        """Build a CORTEX-OUT response with the given profile."""
        return cls(profile=profile, fields=dict(fields), message=message)

    @classmethod
    def min(cls, message: str = "", **fields: Any) -> "CortexOUT":
        return cls(profile=OUT_MIN, fields=dict(fields), message=message)

    @classmethod
    def work(cls, message: str = "", **fields: Any) -> "CortexOUT":
        return cls(profile=OUT_WORK, fields=dict(fields), message=message)

    @classmethod
    def audit(cls, message: str = "", **fields: Any) -> "CortexOUT":
        return cls(profile=OUT_AUDIT, fields=dict(fields), message=message)

    @classmethod
    def full(cls, message: str = "", **fields: Any) -> "CortexOUT":
        return cls(profile=OUT_FULL, fields=dict(fields), message=message)

    @classmethod
    def error(cls, message: str = "", **fields: Any) -> "CortexOUT":
        return cls(profile=OUT_ERROR, fields=dict(fields), message=message)

    def to_text(self) -> str:
        """Render as a single text line (or multi-line for OUT-FULL)."""
        if self.profile == OUT_FULL:
            # OUT-FULL: just the message, no key=value compression.
            return self.message

        parts: list[str] = [self.profile]
        for key, value in self.fields.items():
            parts.append(f"{key}={self._format_value(value)}")
        if self.message:
            parts.append(self.message)
        return " ".join(parts)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value)
        if isinstance(value, dict):
            return ";".join(f"{k}:{v}" for k, v in value.items())
        return str(value)


def format_status(workspace_root: Any, profile: str = DEFAULT_OUT_PROFILE) -> str:
    """Format a workspace status report using the requested CORTEX-OUT profile."""
    from pathlib import Path

    root: Path = workspace_root

    if profile == OUT_MIN:
        return f"OUT-MIN workspace={root.name} projects=? cycles=? tasks=?"

    if profile == OUT_WORK:
        return (
            f"OUT-WORK workspace={root.name} "
            f"manifest={'yes' if (root / 'manifest.cortex').exists() else 'no'} "
            f"projects={'yes' if (root / 'projects.cortex').exists() else 'no'}"
        )

    if profile == OUT_AUDIT:
        lines = [f"OUT-AUDIT workspace={root.name}"]
        for child in sorted(root.iterdir()):
            if child.is_dir():
                lines.append(f"  dir={child.name}")
            elif child.is_file():
                lines.append(f"  file={child.name}")
        return "\n".join(lines)

    if profile == OUT_FULL:
        return (
            f"Workspace at {root}\n\n"
            f"This workspace is governed by the framework. The manifest "
            f"and projects index live in this directory."
        )

    return CortexOUT.error(message="unknown profile").to_text()
