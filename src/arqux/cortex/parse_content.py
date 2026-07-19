"""Shared CORTEX content-entry parser (BLP-005, BLP-009).

Provides ``parse_content_entry(content)`` — a permissive parser for
CORTEX entries of the form::

    $N:{key:val, key2:val2, ...}
    $N:{sigil:name{key:val, ...}}
    sigil:name{key:val, ...}

The parser is intentionally minimal:

- No validation. Never raises. Returns ``{}`` on bad input.
- Recognises the leading ``$N:`` section prefix and strips it.
- Recognises a ``SIGIL:name`` prefix and exposes it as ``__sigil__``
  and ``__name__``.
- Parses the inner ``{key:val, key2:val2}`` map with support for
  quoted strings (single or double) and comma separators.
- Values are returned as strings. The caller is responsible for any
  type coercion.
- Lists can be expressed as ``key:[v1,v2,v3]`` and are returned as
  Python lists of strings.

This is a "best-effort" parser intended for the canal-I content
parameter on ``cortex.entry.add``, ``task.create``, ``skill.import``,
and ``skill.edit``. It is NOT a substitute for the full CODEC-CORTEX
parser.
"""

from __future__ import annotations

import re
from typing import Any


def parse_content_entry(content: str | None) -> dict[str, Any]:
    """Parse a CORTEX content entry string into a dict.

    Returns an empty dict on bad input. Never raises.

    Examples::

        >>> parse_content_entry("$1:{priority:'high', status:'done'}")
        {'priority': 'high', 'status': 'done'}

        >>> parse_content_entry("LNG:lesson_001{kind:'process', body:'...'}")
        {'__sigil__': 'LNG', '__name__': 'lesson_001', 'kind': 'process', 'body': '...'}

        >>> parse_content_entry(None)
        {}

        >>> parse_content_entry("not a cortex entry")
        {}
    """
    if not content or not isinstance(content, str):
        return {}

    text = content.strip()
    if not text:
        return {}

    # Capture leading "$N:" or "$N.N:" section prefix as __section__ (BLP-017).
    result: dict[str, Any] = {}
    section_match = re.match(r"^\$(\d+(?:\.\d+)?):", text)
    if section_match:
        result["__section__"] = "$" + section_match.group(1)
    # Strip leading "$N:" or "$N.N:" section prefix (and any wrapping braces
    # of the form "$N:{...}") so the inner "SIGIL:name{...}" is exposed.
    text = re.sub(r"^\$\d+(?:\.\d+)?:", "", text).strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1].strip()

    # Detect "SIGIL:name{...}" or "SIGIL:name" form.
    sigil_match = re.match(r"^([A-Z][A-Z0-9_]{1,9}):([A-Za-z0-9_\-.]+)\s*(.*)$", text, re.DOTALL)
    sigil_id: str | None = None
    sigil_name: str | None = None
    if sigil_match:
        sigil_id = sigil_match.group(1)
        sigil_name = sigil_match.group(2)
        text = sigil_match.group(3).strip()

    # Now extract the inner {...} body (if any).
    inner = _extract_braces(text)
    if sigil_id:
        result["__sigil__"] = sigil_id
    if sigil_name:
        result["__name__"] = sigil_name

    if inner is None:
        # No braces — maybe the whole remaining text is just a key:val list.
        # Try to parse it as such; if it doesn't look like one, return what we have.
        parsed = _parse_kv(inner if inner is not None else text)
        if parsed:
            result.update(parsed)
        return result

    parsed = _parse_kv(inner)
    result.update(parsed)
    return result


def _extract_braces(text: str) -> str | None:
    """Return the content inside the first top-level ``{...}`` block.

    Returns ``None`` if no balanced braces are found.
    """
    if not text or "{" not in text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    # Unbalanced — return everything after the opening brace.
    return text[start + 1 :]


def _parse_kv(body: str | None) -> dict[str, Any]:
    """Parse a comma-separated list of ``key:val`` pairs.

    Values may be quoted ('...' or "...") or unquoted. Lists are
    expressed as ``[v1,v2,v3]`` and returned as a Python list.
    """
    if not body:
        return {}
    out: dict[str, Any] = {}

    # Split top-level commas (respecting nested brackets and quotes).
    parts = _split_top_level(body, ",")
    for part in parts:
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, _, val = part.partition(":")
        key = key.strip().strip('"').strip("'")
        if not key:
            continue
        val = val.strip()
        out[key] = _coerce_value(val)
    return out


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split ``text`` on ``sep`` at top level (not inside quotes/brackets)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            buf.append(c)
            if c == quote and (i == 0 or text[i - 1] != "\\"):
                quote = None
        elif c in ('"', "'"):
            quote = c
            buf.append(c)
        elif c in "[{(":
            depth += 1
            buf.append(c)
        elif c in "]})":
            depth = max(0, depth - 1)
            buf.append(c)
        elif c == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _coerce_value(raw: str) -> Any:
    """Coerce a raw value string into a Python value.

    - Strips surrounding quotes.
    - Parses ``[a,b,c]`` into a list of strings.
    - Returns a plain string otherwise.
    """
    val = raw.strip()
    if not val:
        return ""
    # List form: [v1, v2, v3]
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1]
        items = _split_top_level(inner, ",")
        return [_coerce_scalar(item.strip()) for item in items if item.strip()]
    return _coerce_scalar(val)


def _coerce_scalar(val: str) -> str:
    """Strip surrounding quotes from a scalar value."""
    if len(val) >= 2 and (
        (val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")
    ):
        return val[1:-1]
    return val
