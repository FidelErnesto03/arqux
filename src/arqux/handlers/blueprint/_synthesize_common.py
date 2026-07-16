"""Shared helpers for the *synthesize family.

Extracted from duplicate implementations in synthesize.py and cycle.py
to avoid code duplication (BLP-006).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)
from pathlib import Path


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
        # Warn if some $N: patterns were found without braces (missing {})
        bare_refs = re.findall(r"\$(\d+):\s*(?!\{)", text)
        if bare_refs and not out:
            logger.warning(
                "P1.2a: found $N: patterns without braces: %s. "
                "Per-section format requires $N:{body}. Did you forget { and }?",
                bare_refs,
            )
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


# ---------------------------------------------------------------------------
# P1.3: Per-section report (BLP-008 GOV-001)
# ---------------------------------------------------------------------------


def _check_marker_missing(body: str, section_id: str) -> bool:
    """Check if a section still has template placeholder markers."""
    markers = [
        "_Describe the problem",
        "_Concrete, verifiable",
        "_Precondition",
        "_The rule that governs",
        "_Description_",
        "_Impact_",
        "_Mitigation_",
        "_placeholder_",
    ]
    return any(marker.lower() in body.lower() for marker in markers)


def generate_section_report(
    body: str,
    sections_written: list[str],
    sections_skipped: list[str],
    sections_errors: list[dict],
) -> dict[str, dict[str, object]]:
    """Generate a per-section report with section_id, body, marker_status.

    Returns a dict mapping section_id -> {section_id, body_preview, marker_status,
    written, skipped, error}.
    """
    report: dict[str, dict[str, object]] = {}
    all_ids = set(sections_written) | set(sections_skipped)

    for sid in all_ids:
        open_tag = f"<!-- BLP:{sid} -->"
        close_tag = f"<!-- /BLP:{sid} -->"
        marker_pattern = rf"{re.escape(open_tag)}.*?{re.escape(close_tag)}"
        match = re.search(marker_pattern, body, re.DOTALL)
        section_text = match.group(0) if match else ""

        preview = section_text[:120].strip() if section_text else ""
        has_placeholder = _check_marker_missing(section_text, sid) if section_text else True

        entry: dict[str, object] = {
            "section_id": sid,
            "body_preview": preview,
            "marker_status": "missing" if has_placeholder else "ok",
            "written": sid in set(sections_written),
            "skipped": sid in set(sections_skipped),
            "error": False,
        }
        report[sid] = entry

    for err in sections_errors:
        sid = err.get("id", "")
        if sid in report:
            report[sid]["error"] = True
            report[sid]["error_msg"] = err.get("error", "")

    return report


# ---------------------------------------------------------------------------
# P1.4: Post-write placeholder verification (BLP-008 GOV-001)
# ---------------------------------------------------------------------------


def verify_no_placeholders(bp_path: str | Path) -> dict[str, object]:
    """Re-read a BLP.md and verify no template placeholders remain.

    Returns a dict with:
        path (str): the verified file path
        leftover_placeholders (list[str]): any placeholder markers found
        verified (bool): True if no placeholders remain
    """
    import re as _re

    fpath = Path(bp_path)
    if not fpath.exists():
        return {"path": str(bp_path), "error": "file not found", "verified": False}

    text = fpath.read_text(encoding="utf-8")

    placeholder_patterns = [
        (r"_Describe the problem[^_]*_", "§1 problem statement"),
        (r"_Concrete, verifiable[^_]*_", "§2 objective"),
        (r"_Precondition \d[^_]*_", "§3 precondition"),
        (r"_The rule that governs[^_]*_", "§4 guiding principle"),
        (r"_Context[^_]*_", "§5 context"),
        (r"_Include[^_]*_", "§6 scope"),
        (r"_Rule \d[^_]*_", "§7 mandatory rules"),
        (r"_Technical design[^_]*_", "§8 technical design"),
        (r"_Operational design[^_]*_", "§9 operational design"),
        (r"_Inputs[^_]*_", "§10 contracts"),
        (r"_Work procedure[^_]*_", "§11 work procedure"),
        (r"_AC-\d+[^_]*_", "§12 acceptance criteria"),
        (r"_Validation[^_]*_", "§13 validations"),
        (r"_Task[^_]*_", "§14 tasks"),
        (r"_Risk[^_]*_", "§15 risks"),
        (r"_Blocking rule[^_]*_", "§16 blocking rule"),
        (r"_Modified files[^_]*_", "§17 expected output"),
        (r"_Quality gate[^_]*_", "§18 quality contract"),
        (_re.escape("_placeholder_"), "generic"),
    ]

    found: list[str] = []
    for pattern, desc in placeholder_patterns:
        matches = _re.findall(pattern, text, _re.IGNORECASE | _re.DOTALL)
        for m in matches:
            found.append(f"{desc}: {m.strip()[:80]}")

    return {
        "path": str(bp_path),
        "leftover_placeholders": found,
        "verified": len(found) == 0,
    }
