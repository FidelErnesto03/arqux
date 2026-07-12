"""cortex.format handler (BLP-003).

Transforms content between CORTEX (machine, canal I) and HCORTEX
(human-readable, canal E).

Two directions are supported:

- ``format="hcortex"`` (default): CORTEX → HCORTEX. Renders each
  ``$N`` section as a markdown header (``## §N: TITLE``) and each
  sigil entry as a labelled bullet or sub-section.
- ``format="cortex"``: HCORTEX → CORTEX. Parses a markdown document
  with ``## §N: ...`` headers back into raw CORTEX entries.

The handler accepts either inline ``content`` text or a ``path`` to a
``.cortex`` / ``.hcortex.md`` file. When both are given, ``content``
wins.

This handler is permissive — it is NOT a full CODEC-CORTEX parser.
For round-trip fidelity use ``cortex.read`` + ``cortex.write``.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...cortex.sigils import get_sigil
from ...cortex_out import CortexOUT
from ...permissions import PermissionContext
from ...pulse import append_pulse_to_brain, next_pulse_event_id
from ...state import find_project_root

# ---------------------------------------------------------------------------
# CORTEX → HCORTEX
# ---------------------------------------------------------------------------


def _cortex_to_hcortex(text: str) -> str:
    """Render a CORTEX document as HCORTEX markdown.

    - ``$0`` and ``$0.1`` (glossary / metadata) are skipped from the
      readable output (they are noise for humans).
    - ``$N: TITLE`` becomes ``## §N: TITLE``.
    - ``SIGIL:name{...}`` becomes ``### SIGIL:name`` followed by a
      definition list of the entry's attrs.
    - Lines starting with ``#`` (comments) inside a section are skipped.
    """
    if not text:
        return ""

    out_lines: list[str] = []
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # Section header: "$N: TITLE" or "$N.N: TITLE"
        sec_match = re.match(r"^\$(\d+(?:\.\d+)?):\s*(.*)$", line)
        if sec_match:
            sec_id = sec_match.group(1)
            title = sec_match.group(2).strip()
            # Skip $0 / $0.1 — glossary/metadata, not for humans.
            if sec_id.startswith("0"):
                current_section = None
                continue
            current_section = sec_id
            out_lines.append("")
            out_lines.append(f"## §{sec_id}: {title}")
            out_lines.append("")
            continue

        # Skip everything while inside $0 (glossary).
        if current_section is None and line.startswith("$"):
            # Some files put $0 alone on a line, then comments.
            continue

        # Comment lines (start with #) — skip in HCORTEX output.
        if line.lstrip().startswith("#"):
            continue

        # Blank line — preserve.
        if not line.strip():
            out_lines.append("")
            continue

        # Entry: SIGIL:name{...}  or  SIGIL:name  (no attrs)
        entry_match = re.match(
            r"^([A-Z][A-Z0-9_]{1,9}):([A-Za-z0-9_\-.]+)\s*(\{.*\})?\s*$",
            line,
        )
        if entry_match and current_section is not None:
            sigil_id = entry_match.group(1)
            entry_name = entry_match.group(2)
            attrs_raw = entry_match.group(3) or ""
            out_lines.append(f"### {sigil_id}:{entry_name}")
            if attrs_raw:
                attrs = _parse_attrs(attrs_raw)
                if attrs:
                    out_lines.append("")
                    for k, v in attrs.items():
                        out_lines.append(f"- **{k}**: {v}")
            out_lines.append("")
            # Also emit the sigil description as a hint, when known.
            sigil_def = get_sigil(sigil_id)
            if sigil_def:
                out_lines.append(f"> _{sigil_def.get('description', '')}_")
                out_lines.append("")
            continue

        # GSIG declarations are skipped from the readable view.
        if line.startswith("GSIG:"):
            continue

        # Default: copy the line verbatim if we are inside a section.
        if current_section is not None:
            out_lines.append(line)

    # Collapse runs of more than two blank lines.
    cleaned: list[str] = []
    blank_run = 0
    for line in out_lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 2:
                cleaned.append(line)
        else:
            blank_run = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n"


def _parse_attrs(body: str) -> dict[str, str]:
    """Parse a ``{key:val, key2:val2}`` body into a dict (permissive)."""
    if not body:
        return {}
    body = body.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    out: dict[str, str] = {}
    for part in _split_top_level(body, ","):
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


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split ``text`` on ``sep`` at top level (not inside quotes/brackets)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for c in text:
        if quote:
            buf.append(c)
            if c == quote:
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
    if buf:
        parts.append("".join(buf))
    return parts


# ---------------------------------------------------------------------------
# HCORTEX → CORTEX
# ---------------------------------------------------------------------------


def _hcortex_to_cortex(md: str) -> str:
    """Parse an HCORTEX markdown document back into CORTEX.

    Recognises:

    - ``## §N: TITLE``  →  ``$N: TITLE``
    - ``### SIGIL:name`` followed by a ``- **key**: value`` list
      →  ``SIGIL:name{key:value, key2:value2}``
    - Bare ``SIGIL:name{...}`` lines are preserved as-is.

    Lines that don't match either form are dropped.
    """
    if not md:
        return ""

    out_lines: list[str] = []
    # Always start with a $0 glossary placeholder so the file is parseable.
    out_lines.append("$0")
    out_lines.append("")

    pending_entry: tuple[str, str] | None = None  # (sigil, name)
    pending_attrs: dict[str, str] = {}

    def _flush_entry() -> None:
        nonlocal pending_entry, pending_attrs
        if pending_entry is None:
            return
        sigil, name = pending_entry
        if pending_attrs:
            attrs_str = ", ".join(f'{k}:{_quote(v)}' for k, v in pending_attrs.items())
            out_lines.append(f"{sigil}:{name}{{{attrs_str}}}")
        else:
            out_lines.append(f"{sigil}:{name}")
        pending_entry = None
        pending_attrs = {}

    lines = md.splitlines()
    for raw_line in lines:
        line = raw_line.rstrip()

        # Section header: "## §N: TITLE" or "## §N.N: TITLE"
        sec_match = re.match(r"^##\s*§(\d+(?:\.\d+)?):\s*(.*)$", line)
        if sec_match:
            _flush_entry()
            sec_id = sec_match.group(1)
            title = sec_match.group(2).strip()
            out_lines.append("")
            out_lines.append(f"${sec_id}: {title}")
            out_lines.append("")
            continue

        # Entry header: "### SIGIL:name"
        entry_match = re.match(r"^###\s+([A-Z][A-Z0-9_]{1,9}):([A-Za-z0-9_\-.]+)\s*$", line)
        if entry_match:
            _flush_entry()
            pending_entry = (entry_match.group(1), entry_match.group(2))
            continue

        # Attrs list: "- **key**: value"
        attr_match = re.match(r"^-\s+\*\*([^*]+)\*\*\s*:\s*(.*)$", line)
        if attr_match and pending_entry is not None:
            k = attr_match.group(1).strip()
            v = attr_match.group(2).strip()
            pending_attrs[k] = v
            continue

        # Bare CORTEX entry line — preserve verbatim.
        bare_match = re.match(
            r"^([A-Z][A-Z0-9_]{1,9}):([A-Za-z0-9_\-.]+)\s*(\{.*\})?\s*$",
            line,
        )
        if bare_match:
            _flush_entry()
            out_lines.append(line)
            continue

        # Everything else (blockquotes, paragraphs, blank lines) is dropped
        # from the CORTEX output, but blank lines inside a section are kept
        # for readability.
        if not line.strip() and out_lines and out_lines[-1] != "":
            out_lines.append("")

    _flush_entry()
    return "\n".join(out_lines).strip() + "\n"


def _quote(val: str) -> str:
    """Quote a value for CORTEX attrs output."""
    if val == "":
        return '""'
    # If it contains spaces, commas, or quotes — wrap in double quotes.
    if any(c in val for c in (" ", ",", '"', "'", "{", "}")):
        escaped = val.replace('"', '\\"')
        return f'"{escaped}"'
    return val


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def format_handler(
    content: str | None = None,
    *,
    target: str = "hcortex",
    path: str | None = None,
    ctx: PermissionContext | None = None,
) -> CortexOUT:
    """Transform content between CORTEX and HCORTEX.

    Args:
        content: Source text to transform. If omitted, reads from ``path``.
        target: Target format — ``"hcortex"`` (CORTEX→HCORTEX, default) or
            ``"cortex"`` (HCORTEX→CORTEX).
        path: Optional path to a file. Used as the source when ``content``
            is not given, and to record PULSE.
        ctx: Permission context.

    The source format is inferred from ``target`` (the handler always
    transforms FROM the other format TO ``target``).
    """
    if target not in ("hcortex", "cortex"):
        return CortexOUT.error(
            f"invalid target={target!r} (must be 'hcortex' or 'cortex')",
            code="INVALID_ARGS",
        )

    # Resolve source text.
    if content is None:
        if not path:
            return CortexOUT.error(
                "either content or path is required",
                code="INVALID_ARGS",
            )
        src_path = Path(path)
        if not src_path.exists():
            return CortexOUT.error(f"file not found: {path}", code="NOT_FOUND")
        try:
            content = src_path.read_text(encoding="utf-8")
        except OSError as exc:
            return CortexOUT.error(str(exc), code="READ_ERROR")

    if not content or not content.strip():
        return CortexOUT.error("content is empty", code="INVALID_ARGS")

    try:
        if target == "hcortex":
            rendered = _cortex_to_hcortex(content)
            source_format = "cortex"
        else:
            rendered = _hcortex_to_cortex(content)
            source_format = "hcortex"
    except Exception as exc:  # noqa: BLE001 — permissive parser, but guard anyway
        return CortexOUT.error(str(exc), code="TRANSFORM_ERROR")

    _record_pulse(path, ctx, action="cortex.format", target=target, source=source_format)

    return CortexOUT.work(
        f"cortex.format ok {source_format}->{target} bytes={len(rendered)}",
        target=target,
        source_format=source_format,
        bytes_out=len(rendered),
        content=rendered,
    )


def _record_pulse(
    path: str | None,
    ctx: PermissionContext | None,
    *,
    action: str,
    target: str,
    source: str,
) -> None:
    """Append a PULSE event for a cortex.format call (best-effort)."""
    try:
        root = find_project_root(start=path)
        if root is None:
            return
        agent = (ctx or PermissionContext.from_env()).agent_id
        event_id = next_pulse_event_id(root)
        append_pulse_to_brain(
            root,
            event_id=event_id,
            task_id="-",
            kind="handler_call",
            agent=agent,
            payload=f"[{action}] {source}->{target}",
        )
    except Exception:  # noqa: BLE001
        pass
