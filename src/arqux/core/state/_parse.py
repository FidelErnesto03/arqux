"""Legacy CORTEX brain section parser — # SECTION format."""
from __future__ import annotations

import re

from ...constants import (
    BRAIN_SECTION_ACTIVE_CONTEXT,
    BRAIN_SECTION_CONCURRENCY,
    BRAIN_SECTION_FOCUS,
    BRAIN_SECTION_HANDOFFS,
    BRAIN_SECTION_LESSONS,
    BRAIN_SECTION_OBJECTIVES,
    BRAIN_SECTION_PULSE,
    BRAIN_SECTION_RISKS,
    BRAIN_SECTION_SESSIONS,
)

_SECTION_RE = re.compile(r"^# ([A-Z][A-Z_]+)\s*$", re.MULTILINE)


def parse_brain_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def rebuild_brain_body(sections: dict[str, str]) -> str:
    parts: list[str] = []
    for section_name in (
        BRAIN_SECTION_FOCUS,
        BRAIN_SECTION_OBJECTIVES,
        BRAIN_SECTION_SESSIONS,
        BRAIN_SECTION_HANDOFFS,
        BRAIN_SECTION_PULSE,
        BRAIN_SECTION_LESSONS,
        BRAIN_SECTION_ACTIVE_CONTEXT,
        BRAIN_SECTION_RISKS,
        BRAIN_SECTION_CONCURRENCY,
    ):
        if section_name in sections:
            parts.append(f"# {section_name}")
            parts.append("")
            parts.append(sections[section_name].strip())
            parts.append("")
    return "\n".join(parts).strip() + "\n"
