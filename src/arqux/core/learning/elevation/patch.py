"""Patch model for learning elevation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Patch:
    """A planned mutation to the brain."""

    source_entries: list[str]
    target_layer: str
    target_section: str
    new_entry_sigil: str
    new_entry_name: str
    new_entry_value: dict[str, Any]
    reason: str = ""
    policy_id: str | None = None
    promotion_score: int = 0
    affected_files: list[str] = field(default_factory=list)
    mode: str = "propose"  # propose | apply | apply_confirmed | block

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_entries": list(self.source_entries),
            "target_layer": self.target_layer,
            "target_section": self.target_section,
            "new_entry": {
                "sigil": self.new_entry_sigil,
                "name": self.new_entry_name,
                "value": dict(self.new_entry_value),
            },
            "reason": self.reason,
            "policy_id": self.policy_id,
            "promotion_score": self.promotion_score,
            "affected_files": list(self.affected_files),
            "mode": self.mode,
        }


__all__ = ["Patch"]
