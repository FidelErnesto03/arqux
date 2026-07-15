"""Shared helpers for the *synthesize family.

Extracted from duplicate implementations in synthesize.py and cycle.py
to avoid code duplication (BLP-006).
"""

from __future__ import annotations

import re


def parse_content_sections(content: str) -> dict[str, str]:
    """Parse a CORTEX content payload into ``{section_id: body}``.

    Supports two forms:

    1. Per-section:  ``$1:{body}`` ``$2:{body}`` …
    2. Single-body:  ``$0:{1: "body1", 2: "body2"}``

    Args:
        content: Raw CORTEX content string.

    Returns:
        dict mapping section ID (str) to body (str).
    """
    out: dict[str, str] = {}
    text = content.strip()
    if not text:
        return out

    # 1. Per-section form: scan for $N:{...} or $N.N:{...}
    pattern = re.compile(r"\$(\d+(?:\.\d+)?):\s*\{")
    matches = list(pattern.finditer(text))
    if matches:
        for m in matches:
            sid = m.group(1)
            start = m.end() - 1  # position of the opening brace
            body = _extract_brace_body(text, start)
            if body is not None:
                out[sid] = body.strip()
        return out

    # 2. Single-body form: $0:{key:val, ...}
    brace_start = text.find("{")
    if brace_start == -1:
        return out
    inner = _extract_brace_body(text, brace_start)
    if inner is None:
        return out
    for part in _split_top_level(inner, ","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, _, v = part.partition(":")
        k = k.strip().strip('"').strip("'")
        v = v.strip()
        if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def _extract_brace_body(text: str, start: int) -> str | None:
    """Return the content inside the ``{…}`` block starting at ``start``."""
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    return None


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split *text* on *sep* but not inside ``{…}`` or ``"…"`` blocks."""
    parts: list[str] = []
    depth = 0
    in_quote = False
    current: list[str] = []
    for ch in text:
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            current.append(ch)
        elif in_quote and ch in ('"', "'"):
            in_quote = False
            current.append(ch)
        elif ch == "{" and not in_quote:
            depth += 1
            current.append(ch)
        elif ch == "}" and not in_quote:
            depth -= 1
            current.append(ch)
        elif ch == sep and depth == 0 and not in_quote:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    remaining = "".join(current).strip()
    if remaining:
        parts.append(remaining)
    return parts
